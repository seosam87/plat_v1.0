"""Yandex Metrika API client and DB helper functions.

Fetches organic traffic data (daily aggregate and per-page) from the
Yandex Metrika Statistics API v1. All API calls use OAuth token auth.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrika import MetrikaTrafficDaily, MetrikaTrafficPage, MetrikaEvent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "https://api-metrika.yandex.net/stat/v1"
TIMEOUT = 30.0
ORGANIC_FILTER = "ym:s:trafficSource=='organic' AND ym:s:isRobot=='No'"
METRICS = "ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds"
METRIC_KEYS = ["visits", "users", "bounce_rate", "page_depth", "avg_duration_seconds"]


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict:
    return {"Authorization": f"OAuth {token}"}


# ---------------------------------------------------------------------------
# API client functions
# ---------------------------------------------------------------------------


async def fetch_daily_traffic(
    counter_id: str, token: str, date1: str, date2: str
) -> list[dict]:
    """Fetch daily organic traffic for a counter over a date range.

    Returns list of dicts with keys:
    date, visits, users, bounce_rate, page_depth, avg_duration_seconds
    """
    params = {
        "id": counter_id,
        "date1": date1,
        "date2": date2,
        "metrics": METRICS,
        "filters": ORGANIC_FILTER,
        "group": "day",
        "limit": 1000,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{API_BASE}/data/bytime",
            params=params,
            headers=_headers(token),
        )
        resp.raise_for_status()
        data = resp.json()

    time_intervals = data.get("time_intervals", [])
    metric_data = data.get("data", [])

    rows: list[dict] = []
    if not metric_data:
        return rows

    # data[0].metrics is a list of per-day metric arrays
    day_metrics = metric_data[0].get("metrics", [])

    for i, interval in enumerate(time_intervals):
        # interval is [start, end], date is the start date
        day_date = interval[0] if isinstance(interval, list) else interval
        # Normalize to YYYY-MM-DD if needed
        if len(day_date) > 10:
            day_date = day_date[:10]

        values = day_metrics[i] if i < len(day_metrics) else []
        # Metrics order: visits, users, bounceRate, pageDepth, avgVisitDurationSeconds
        rows.append({
            "date": day_date,
            "visits": int(values[0]) if len(values) > 0 else 0,
            "users": int(values[1]) if len(values) > 1 else 0,
            "bounce_rate": round(float(values[2]), 2) if len(values) > 2 else None,
            "page_depth": round(float(values[3]), 2) if len(values) > 3 else None,
            "avg_duration_seconds": int(values[4]) if len(values) > 4 else None,
        })

    logger.info(
        "Metrika daily traffic fetched",
        counter_id=counter_id,
        date1=date1,
        date2=date2,
        rows=len(rows),
    )
    return rows


async def fetch_page_traffic(
    counter_id: str,
    token: str,
    date1: str,
    date2: str,
    limit: int = 500,
) -> list[dict]:
    """Fetch per-page organic traffic for a counter over a date range.

    Paginates until all rows are retrieved. Strips query parameters from URLs.

    Returns list of dicts with keys:
    page_url, visits, bounce_rate, page_depth, avg_duration_seconds
    """
    page_metrics = "ym:s:visits,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds"
    params = {
        "id": counter_id,
        "date1": date1,
        "date2": date2,
        "dimensions": "ym:s:startURL",
        "metrics": page_metrics,
        "filters": ORGANIC_FILTER,
        "sort": "-ym:s:visits",
        "limit": limit,
        "offset": 0,
    }

    all_rows: list[dict] = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        while True:
            resp = await client.get(
                f"{API_BASE}/data",
                params=params,
                headers=_headers(token),
            )
            resp.raise_for_status()
            data = resp.json()

            total_rows = data.get("total_rows", 0)
            records = data.get("data", [])

            for record in records:
                dims = record.get("dimensions", [])
                metrics = record.get("metrics", [])

                raw_url = dims[0].get("name", "") if dims else ""
                # Strip query parameters for URL normalization
                normalized_url = urlsplit(raw_url)._replace(query="", fragment="").geturl()

                all_rows.append({
                    "page_url": normalized_url,
                    "visits": int(metrics[0]) if len(metrics) > 0 else 0,
                    "bounce_rate": round(float(metrics[1]), 2) if len(metrics) > 1 else None,
                    "page_depth": round(float(metrics[2]), 2) if len(metrics) > 2 else None,
                    "avg_duration_seconds": int(metrics[3]) if len(metrics) > 3 else None,
                })

            if len(all_rows) >= total_rows or len(records) < limit:
                break

            params["offset"] = params["offset"] + limit  # type: ignore[assignment]

    logger.info(
        "Metrika page traffic fetched",
        counter_id=counter_id,
        date1=date1,
        date2=date2,
        rows=len(all_rows),
    )
    return all_rows


# ---------------------------------------------------------------------------
# DB functions
# ---------------------------------------------------------------------------


async def save_daily_snapshots(
    db: AsyncSession, site_id: uuid.UUID, rows: list[dict]
) -> int:
    """Upsert daily traffic rows into metrika_traffic_daily.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE for idempotency.
    Returns count of rows processed.
    """
    if not rows:
        return 0

    values = [
        {
            "id": uuid.uuid4(),
            "site_id": site_id,
            "traffic_date": date.fromisoformat(row["date"]),
            "visits": row.get("visits", 0),
            "users": row.get("users", 0),
            "bounce_rate": row.get("bounce_rate"),
            "page_depth": row.get("page_depth"),
            "avg_duration_seconds": row.get("avg_duration_seconds"),
        }
        for row in rows
    ]

    stmt = pg_insert(MetrikaTrafficDaily).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_metrika_daily_site_date",
        set_={
            "visits": stmt.excluded.visits,
            "users": stmt.excluded.users,
            "bounce_rate": stmt.excluded.bounce_rate,
            "page_depth": stmt.excluded.page_depth,
            "avg_duration_seconds": stmt.excluded.avg_duration_seconds,
        },
    )
    await db.execute(stmt)
    return len(values)


async def save_page_snapshots(
    db: AsyncSession,
    site_id: uuid.UUID,
    period_start: date,
    period_end: date,
    rows: list[dict],
) -> int:
    """Upsert per-page traffic rows into metrika_traffic_pages.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE for idempotency.
    Returns count of rows processed.
    """
    if not rows:
        return 0

    values = [
        {
            "id": uuid.uuid4(),
            "site_id": site_id,
            "period_start": period_start,
            "period_end": period_end,
            "page_url": row["page_url"],
            "visits": row.get("visits", 0),
            "bounce_rate": row.get("bounce_rate"),
            "page_depth": row.get("page_depth"),
            "avg_duration_seconds": row.get("avg_duration_seconds"),
        }
        for row in rows
    ]

    stmt = pg_insert(MetrikaTrafficPage).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_metrika_pages_site_period_url",
        set_={
            "visits": stmt.excluded.visits,
            "bounce_rate": stmt.excluded.bounce_rate,
            "page_depth": stmt.excluded.page_depth,
            "avg_duration_seconds": stmt.excluded.avg_duration_seconds,
        },
    )
    await db.execute(stmt)
    return len(values)


async def get_daily_traffic(
    db: AsyncSession,
    site_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Retrieve daily traffic rows for a site within a date range.

    Defaults to last 90 days if date_from/date_to are not specified.
    Returns list of dicts ordered by traffic_date ASC.
    """
    if date_from is None:
        date_from = date.today() - timedelta(days=90)
    if date_to is None:
        date_to = date.today()

    result = await db.execute(
        select(MetrikaTrafficDaily)
        .where(
            MetrikaTrafficDaily.site_id == site_id,
            MetrikaTrafficDaily.traffic_date >= date_from,
            MetrikaTrafficDaily.traffic_date <= date_to,
        )
        .order_by(MetrikaTrafficDaily.traffic_date.asc())
    )
    rows = result.scalars().all()

    return [
        {
            "date": str(row.traffic_date),
            "visits": row.visits,
            "users": row.users,
            "bounce_rate": float(row.bounce_rate) if row.bounce_rate is not None else None,
            "page_depth": float(row.page_depth) if row.page_depth is not None else None,
            "avg_duration_seconds": row.avg_duration_seconds,
        }
        for row in rows
    ]


async def get_page_traffic(
    db: AsyncSession,
    site_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> list[dict]:
    """Retrieve per-page traffic rows for a site and period.

    Returns list of dicts ordered by visits DESC.
    """
    result = await db.execute(
        select(MetrikaTrafficPage)
        .where(
            MetrikaTrafficPage.site_id == site_id,
            MetrikaTrafficPage.period_start == period_start,
            MetrikaTrafficPage.period_end == period_end,
        )
        .order_by(MetrikaTrafficPage.visits.desc())
    )
    rows = result.scalars().all()

    return [
        {
            "page_url": row.page_url,
            "visits": row.visits,
            "bounce_rate": float(row.bounce_rate) if row.bounce_rate is not None else None,
            "page_depth": float(row.page_depth) if row.page_depth is not None else None,
            "avg_duration_seconds": row.avg_duration_seconds,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Pure computation functions
# ---------------------------------------------------------------------------


def compute_period_delta(rows_a: list[dict], rows_b: list[dict]) -> list[dict]:
    """Compare two traffic periods, computing deltas and identifying new/lost pages.

    Joins on page_url. Returns union of all URLs found in either period,
    sorted by visits_b descending (current period).

    Args:
        rows_a: Traffic rows for the comparison (older) period.
        rows_b: Traffic rows for the current (newer) period.

    Returns:
        List of dicts with visits_a, visits_b, visits_delta, bounce_rate_a/b,
        page_depth_a/b, avg_duration_a/b, is_new, is_lost for each URL.
    """
    # Build lookup maps
    map_a: dict[str, dict] = {r["page_url"]: r for r in rows_a}
    map_b: dict[str, dict] = {r["page_url"]: r for r in rows_b}

    all_urls = set(map_a.keys()) | set(map_b.keys())

    result: list[dict] = []
    empty = {"visits": 0, "bounce_rate": None, "page_depth": None, "avg_duration_seconds": None}

    for url in all_urls:
        a = map_a.get(url, empty)
        b = map_b.get(url, empty)

        visits_a = a.get("visits", 0) or 0
        visits_b = b.get("visits", 0) or 0

        result.append({
            "page_url": url,
            "visits_a": visits_a,
            "visits_b": visits_b,
            "visits_delta": visits_b - visits_a,
            "bounce_rate_a": a.get("bounce_rate"),
            "bounce_rate_b": b.get("bounce_rate"),
            "page_depth_a": a.get("page_depth"),
            "page_depth_b": b.get("page_depth"),
            "avg_duration_a": a.get("avg_duration_seconds"),
            "avg_duration_b": b.get("avg_duration_seconds"),
            "is_new": visits_a == 0 and visits_b > 0,
            "is_lost": visits_a > 0 and visits_b == 0,
        })

    # Sort by current period visits descending
    result.sort(key=lambda r: r["visits_b"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------


async def get_events(db: AsyncSession, site_id: uuid.UUID) -> list[MetrikaEvent]:
    """Return all events for a site ordered by event_date ASC."""
    result = await db.execute(
        select(MetrikaEvent)
        .where(MetrikaEvent.site_id == site_id)
        .order_by(MetrikaEvent.event_date.asc())
    )
    return list(result.scalars().all())


async def create_event(
    db: AsyncSession,
    site_id: uuid.UUID,
    event_date: date,
    label: str,
    color: str = "#6b7280",
) -> MetrikaEvent:
    """Create and persist a new MetrikaEvent."""
    event = MetrikaEvent(
        site_id=site_id,
        event_date=event_date,
        label=label,
        color=color,
    )
    db.add(event)
    await db.flush()
    return event


async def delete_event(db: AsyncSession, event_id: uuid.UUID) -> bool:
    """Delete an event by ID. Returns True if a row was deleted."""
    result = await db.execute(
        delete(MetrikaEvent).where(MetrikaEvent.id == event_id)
    )
    return result.rowcount > 0
