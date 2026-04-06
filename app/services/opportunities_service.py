"""Growth Opportunities service: gap keywords, lost positions, cannibalization, visibility trend.

Provides four data functions for the Growth Opportunities dashboard:
- get_gap_summary: gap keywords from GapKeyword table
- get_lost_positions: keywords with delta <= -5 from keyword_latest_positions
- get_cannibalization: keywords with 2+ pages in top-50 from keyword_latest_positions
- get_visibility_trend: Metrika traffic week/month comparison (no charts, numbers only)

Design decisions:
- Uses keyword_latest_positions (flat table) — NOT the partitioned keyword_positions
- Lost positions threshold: delta <= -5 (significant rank drop)
- Cannibalization threshold: position <= 50 (top-50 reduces noise)
- Visibility trend: pure function compute_visibility_trend() + DB wrapper
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gap import GapKeyword
from app.models.metrika import MetrikaTrafficDaily


async def get_gap_summary(
    db: AsyncSession,
    site_id: uuid.UUID,
    limit: int = 100,
) -> dict:
    """Return gap keywords summary for the site.

    Args:
        db: Async database session.
        site_id: Site to query.
        limit: Maximum number of items to return.

    Returns:
        dict with:
            count: total gap keyword count for site
            total_potential_traffic: SUM of frequency for rows where frequency is not null
            frequency_available: False if >50% of rows have null frequency
            items: list of dicts with id, phrase, competitor_domain, competitor_position,
                   our_position, potential_score
    """
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(GapKeyword).where(GapKeyword.site_id == site_id)
    )
    total_count = count_result.scalar() or 0

    # Get items ordered by potential_score DESC NULLS LAST
    items_result = await db.execute(
        select(GapKeyword)
        .where(GapKeyword.site_id == site_id)
        .order_by(GapKeyword.potential_score.desc().nullslast())
        .limit(limit)
    )
    items = items_result.scalars().all()

    # Compute total_potential_traffic (sum of frequency where not null)
    total_potential_traffic = sum(item.frequency for item in items if item.frequency is not None)

    # Check if frequency is available for >50% of rows
    null_count = sum(1 for item in items if item.frequency is None)
    frequency_available = True
    if items and null_count > len(items) * 0.5:
        frequency_available = False

    return {
        "count": total_count,
        "total_potential_traffic": total_potential_traffic,
        "frequency_available": frequency_available,
        "items": [
            {
                "id": str(item.id),
                "phrase": item.phrase,
                "competitor_domain": item.competitor_domain,
                "competitor_position": item.competitor_position,
                "our_position": item.our_position,
                "potential_score": item.potential_score,
            }
            for item in items
        ],
    }


async def get_lost_positions(
    db: AsyncSession,
    site_id: uuid.UUID,
    limit: int = 200,
) -> dict:
    """Return keywords with significant position drops (delta <= -5).

    Uses keyword_latest_positions (flat table, NOT partitioned keyword_positions).
    Excludes rows where position IS NULL.

    Args:
        db: Async database session.
        site_id: Site to query.
        limit: Maximum number of items to return.

    Returns:
        dict with:
            count: number of items returned
            items: list of dicts with keyword_id, phrase, url, position, previous_position, delta
    """
    result = await db.execute(
        text(
            """
            SELECT klp.keyword_id, k.phrase, klp.url, klp.position, klp.previous_position, klp.delta
            FROM keyword_latest_positions klp
            JOIN keywords k ON k.id = klp.keyword_id
            WHERE klp.site_id = :site_id AND klp.delta <= -5 AND klp.position IS NOT NULL
            ORDER BY klp.delta ASC LIMIT :limit
            """
        ),
        {"site_id": site_id, "limit": limit},
    )
    rows = result.fetchall()

    items = [
        {
            "keyword_id": str(row[0]),
            "phrase": row[1],
            "url": row[2],
            "position": row[3],
            "previous_position": row[4],
            "delta": row[5],
        }
        for row in rows
    ]

    return {"count": len(items), "items": items}


async def get_cannibalization(
    db: AsyncSession,
    site_id: uuid.UUID,
) -> dict:
    """Return keywords where 2+ distinct pages appear in top-50 positions.

    Uses keyword_latest_positions (flat table) with position <= 50 threshold.
    Results are grouped in Python by keyword_id, sorted by page_count DESC.

    Args:
        db: Async database session.
        site_id: Site to query.

    Returns:
        dict with:
            count: number of keyword groups with cannibalization
            items: list of dicts with keyword_id, phrase, pages (list of url/position), page_count
    """
    result = await db.execute(
        text(
            """
            WITH multi_page AS (
                SELECT keyword_id, COUNT(DISTINCT url) AS page_count
                FROM keyword_latest_positions
                WHERE site_id = :site_id AND position IS NOT NULL AND position <= 50 AND url IS NOT NULL
                GROUP BY keyword_id HAVING COUNT(DISTINCT url) >= 2
            )
            SELECT klp.keyword_id, k.phrase, klp.url, klp.position
            FROM keyword_latest_positions klp
            JOIN keywords k ON k.id = klp.keyword_id
            JOIN multi_page mp ON mp.keyword_id = klp.keyword_id
            WHERE klp.site_id = :site_id AND klp.position <= 50
            ORDER BY klp.keyword_id, klp.position
            """
        ),
        {"site_id": site_id},
    )
    rows = result.fetchall()

    # Group by keyword_id in Python
    groups: dict[str, dict] = {}
    for row in rows:
        kw_id = str(row[0])
        if kw_id not in groups:
            groups[kw_id] = {
                "keyword_id": kw_id,
                "phrase": row[1],
                "pages": [],
                "page_count": 0,
            }
        # Add page if url not already in list (avoid duplicates from multiple engines)
        existing_urls = {p["url"] for p in groups[kw_id]["pages"]}
        if row[2] not in existing_urls:
            groups[kw_id]["pages"].append({"url": row[2], "position": row[3]})

    # Compute page_count per group and sort
    for group in groups.values():
        group["page_count"] = len(group["pages"])

    # Sort by page_count DESC
    items = sorted(groups.values(), key=lambda g: g["page_count"], reverse=True)

    return {"count": len(items), "items": items}


def compute_visibility_trend(daily_rows: list[dict]) -> dict:
    """Compute visibility trend from daily traffic rows (pure function, no DB).

    Args:
        daily_rows: List of dicts with keys:
            traffic_date: date object
            visits: int

    Returns:
        dict with:
            current_week_visits: SUM(visits) for last 7 days
            prev_week_visits: SUM(visits) for 8-14 days ago
            week_change_pct: % change (0.0 if prev is 0)
            current_month_visits: SUM(visits) for last 30 days
            prev_month_visits: SUM(visits) for 31-60 days ago
            month_change_pct: % change (0.0 if prev is 0)
    """
    today = date.today()

    # Week boundaries
    current_week_start = today - timedelta(days=7)
    prev_week_start = today - timedelta(days=14)

    # Month boundaries
    current_month_start = today - timedelta(days=30)
    prev_month_start = today - timedelta(days=60)

    current_week_visits = 0
    prev_week_visits = 0
    current_month_visits = 0
    prev_month_visits = 0

    for row in daily_rows:
        traffic_date = row["traffic_date"]
        visits = row["visits"]

        # Current week: last 7 days (days 1-7 ago, inclusive)
        if current_week_start <= traffic_date < today:
            current_week_visits += visits

        # Previous week: 8-14 days ago (inclusive)
        if prev_week_start <= traffic_date < current_week_start:
            prev_week_visits += visits

        # Current month: last 30 days (days 1-30 ago, inclusive)
        if current_month_start <= traffic_date < today:
            current_month_visits += visits

        # Previous month: 31-60 days ago (inclusive)
        if prev_month_start <= traffic_date < current_month_start:
            prev_month_visits += visits

    # Compute change percentages
    if prev_week_visits > 0:
        week_change_pct = round((current_week_visits - prev_week_visits) / prev_week_visits * 100, 1)
    else:
        week_change_pct = 0.0

    if prev_month_visits > 0:
        month_change_pct = round(
            (current_month_visits - prev_month_visits) / prev_month_visits * 100, 1
        )
    else:
        month_change_pct = 0.0

    return {
        "current_week_visits": current_week_visits,
        "prev_week_visits": prev_week_visits,
        "week_change_pct": week_change_pct,
        "current_month_visits": current_month_visits,
        "prev_month_visits": prev_month_visits,
        "month_change_pct": month_change_pct,
    }


async def get_visibility_trend(
    db: AsyncSession,
    site_id: uuid.UUID,
) -> dict:
    """Query MetrikaTrafficDaily for last 60 days and compute visibility trend.

    Args:
        db: Async database session.
        site_id: Site to query.

    Returns:
        dict from compute_visibility_trend() with week/month visit totals and % changes.
    """
    cutoff = date.today() - timedelta(days=60)
    result = await db.execute(
        select(MetrikaTrafficDaily)
        .where(
            MetrikaTrafficDaily.site_id == site_id,
            MetrikaTrafficDaily.traffic_date >= cutoff,
        )
        .order_by(MetrikaTrafficDaily.traffic_date)
    )
    rows = result.scalars().all()

    daily_rows = [
        {"traffic_date": row.traffic_date, "visits": row.visits}
        for row in rows
    ]

    return compute_visibility_trend(daily_rows)
