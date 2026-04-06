"""Position writer service.

Stores position data from any source (GSC, DataForSEO, Yandex, file import)
into the partitioned keyword_positions table. Computes delta vs previous check.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.keyword_latest_position import KeywordLatestPosition  # noqa: F401
from app.models.position import KeywordPosition


async def write_position(
    db: AsyncSession,
    keyword_id: uuid.UUID,
    site_id: uuid.UUID,
    engine: str,
    position: int | None,
    checked_at: datetime | None = None,
    region: str | None = None,
    url: str | None = None,
    clicks: int | None = None,
    impressions: int | None = None,
    ctr: float | None = None,
) -> KeywordPosition:
    """Write a single position record with delta computation."""
    if checked_at is None:
        checked_at = datetime.now(timezone.utc)

    # Ensure partition exists for this month
    await db.execute(text("SELECT create_kp_partition(:d)"), {"d": checked_at.date()})

    # Find previous position for delta
    prev = await _get_previous_position(db, keyword_id, engine)
    previous_position = prev.position if prev else None
    delta = None
    if previous_position is not None and position is not None:
        delta = previous_position - position  # positive = improved

    record = KeywordPosition(
        keyword_id=keyword_id,
        site_id=site_id,
        engine=engine,
        region=region,
        position=position,
        previous_position=previous_position,
        delta=delta,
        url=url,
        clicks=clicks,
        impressions=impressions,
        ctr=ctr,
        checked_at=checked_at,
    )
    db.add(record)
    await db.flush()
    return record


async def write_positions_batch(
    db: AsyncSession,
    site_id: uuid.UUID,
    rows: list[dict],
    batch_size: int = 500,
) -> int:
    """Write multiple position records. Each row dict:
    {keyword_id, engine, position, region?, url?, clicks?, impressions?, ctr?, checked_at?}
    """
    count = 0
    # Ensure partition for current month
    now = datetime.now(timezone.utc)
    await db.execute(text("SELECT create_kp_partition(:d)"), {"d": now.date()})

    for row in rows:
        keyword_id = row["keyword_id"]
        engine = row.get("engine", "google")
        position = row.get("position")
        checked_at = row.get("checked_at", now)

        if isinstance(checked_at, str):
            checked_at = datetime.fromisoformat(checked_at)
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)

        # Delta: find previous
        prev = await _get_previous_position(db, keyword_id, engine)
        previous_position = prev.position if prev else None
        delta = None
        if previous_position is not None and position is not None:
            delta = previous_position - position

        record = KeywordPosition(
            keyword_id=keyword_id,
            site_id=site_id,
            engine=engine,
            region=row.get("region"),
            position=position,
            previous_position=previous_position,
            delta=delta,
            url=row.get("url"),
            clicks=row.get("clicks"),
            impressions=row.get("impressions"),
            ctr=row.get("ctr"),
            checked_at=checked_at,
        )
        db.add(record)
        count += 1
        if count % batch_size == 0:
            await db.flush()

    if count % batch_size != 0:
        await db.flush()

    logger.info("Positions written", site_id=str(site_id), count=count)
    await refresh_latest_positions(db, site_id)
    return count


async def get_latest_positions(
    db: AsyncSession,
    site_id: uuid.UUID,
    engine: str | None = None,
    top_n: int | None = None,
    region: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[KeywordPosition]:
    """Get latest position per keyword for a site.

    Uses DISTINCT ON (keyword_id, engine) with ORDER BY checked_at DESC.
    """
    # Raw SQL for DISTINCT ON (not natively supported by SQLAlchemy ORM)
    filters = ["kp.site_id = :site_id"]
    params: dict = {"site_id": site_id, "limit": limit, "offset": offset}

    if engine:
        filters.append("kp.engine = :engine")
        params["engine"] = engine
    if region:
        filters.append("kp.region = :region")
        params["region"] = region

    top_filter = ""
    if top_n:
        top_filter = f"WHERE position <= {int(top_n)}"

    where_clause = " AND ".join(filters)

    query = text(f"""
        SELECT * FROM (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.*
            FROM keyword_positions kp
            WHERE {where_clause}
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        ) latest
        {top_filter}
        ORDER BY latest.position ASC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(query, params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def get_position_history(
    db: AsyncSession,
    keyword_id: uuid.UUID,
    engine: str = "google",
    days: int = 90,
) -> list[dict]:
    """Get position history for a keyword over the last N days (for chart)."""
    query = text("""
        SELECT position, checked_at, url, clicks, impressions, delta
        FROM keyword_positions
        WHERE keyword_id = :keyword_id
          AND engine = :engine
          AND checked_at >= NOW() - INTERVAL ':days days'
        ORDER BY checked_at ASC
    """.replace(":days", str(int(days))))

    result = await db.execute(query, {"keyword_id": keyword_id, "engine": engine})
    return [
        {
            "position": r.position,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None,
            "url": r.url,
            "clicks": r.clicks,
            "impressions": r.impressions,
            "delta": r.delta,
        }
        for r in result
    ]


async def refresh_latest_positions(db: AsyncSession, site_id: uuid.UUID) -> int:
    """Refresh keyword_latest_positions for a site using INSERT ... ON CONFLICT DO UPDATE.

    Selects the most recent position per (keyword_id, engine) for the given site
    using DISTINCT ON, then upserts into keyword_latest_positions.

    Returns the number of rows inserted or updated.
    """
    query = text("""
        INSERT INTO keyword_latest_positions
            (id, keyword_id, site_id, engine, region, position, previous_position,
             delta, url, checked_at, updated_at)
        SELECT
            gen_random_uuid(),
            kp.keyword_id,
            kp.site_id,
            kp.engine,
            kp.region,
            kp.position,
            kp.previous_position,
            kp.delta,
            kp.url,
            kp.checked_at,
            NOW()
        FROM (
            SELECT DISTINCT ON (kp2.keyword_id, kp2.engine)
                kp2.*
            FROM keyword_positions kp2
            WHERE kp2.site_id = :site_id
            ORDER BY kp2.keyword_id, kp2.engine, kp2.checked_at DESC
        ) kp
        ON CONFLICT (keyword_id, engine) DO UPDATE SET
            position         = EXCLUDED.position,
            previous_position = EXCLUDED.previous_position,
            delta            = EXCLUDED.delta,
            url              = EXCLUDED.url,
            region           = EXCLUDED.region,
            checked_at       = EXCLUDED.checked_at,
            updated_at       = NOW()
    """)
    result = await db.execute(query, {"site_id": site_id})
    row_count = result.rowcount
    logger.debug(
        "Refreshed keyword_latest_positions",
        site_id=str(site_id),
        rows=row_count,
    )
    return row_count


async def _get_previous_position(
    db: AsyncSession,
    keyword_id: uuid.UUID,
    engine: str,
) -> KeywordPosition | None:
    """Get the most recent position record for a keyword+engine."""
    result = await db.execute(
        select(KeywordPosition)
        .where(
            KeywordPosition.keyword_id == keyword_id,
            KeywordPosition.engine == engine,
        )
        .order_by(KeywordPosition.checked_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_position_distribution(
    db: AsyncSession,
    site_id: uuid.UUID,
    engine: str | None = None,
) -> dict:
    """Count keywords in TOP-3, TOP-10, TOP-30, TOP-100, and not ranked.

    Uses the latest position per keyword (DISTINCT ON).
    Returns dict: {top3, top10, top30, top100, not_ranked, total}.
    """
    engine_filter = "AND kp.engine = :engine" if engine else ""
    params: dict = {"site_id": site_id}
    if engine:
        params["engine"] = engine

    query = text(f"""
        WITH latest AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.position
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id {engine_filter}
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        )
        SELECT
            COUNT(*) FILTER (WHERE position IS NOT NULL AND position <= 3) AS top3,
            COUNT(*) FILTER (WHERE position IS NOT NULL AND position <= 10) AS top10,
            COUNT(*) FILTER (WHERE position IS NOT NULL AND position <= 30) AS top30,
            COUNT(*) FILTER (WHERE position IS NOT NULL AND position <= 100) AS top100,
            COUNT(*) FILTER (WHERE position IS NULL) AS not_ranked,
            COUNT(*) AS total
        FROM latest
    """)
    result = await db.execute(query, params)
    row = result.mappings().one()
    return dict(row)


async def get_lost_gained_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    days: int = 7,
    engine: str | None = None,
    threshold: int = 10,
) -> dict:
    """Find keywords that entered or left the TOP-N over the last N days.

    'gained': was not in top-threshold (or no data), now in top-threshold.
    'lost': was in top-threshold, now out (or no recent data).
    Returns dict with 'gained' and 'lost' lists of dicts.
    """
    engine_filter = "AND kp.engine = :engine" if engine else ""
    params: dict = {"site_id": site_id, "days": days, "threshold": threshold}
    if engine:
        params["engine"] = engine

    query = text(f"""
        WITH recent AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.keyword_id, kp.engine, kp.position, kp.checked_at
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id
              AND kp.checked_at >= NOW() - MAKE_INTERVAL(days => :days)
              {engine_filter}
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        ),
        previous AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.keyword_id, kp.engine, kp.position
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id
              AND kp.checked_at < NOW() - MAKE_INTERVAL(days => :days)
              {engine_filter}
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        )
        SELECT
            r.keyword_id, r.engine,
            p.position AS old_position,
            r.position AS new_position
        FROM recent r
        LEFT JOIN previous p ON r.keyword_id = p.keyword_id AND r.engine = p.engine
        WHERE
            (p.position IS NULL OR p.position > :threshold) AND r.position IS NOT NULL AND r.position <= :threshold
            OR
            (p.position IS NOT NULL AND p.position <= :threshold) AND (r.position IS NULL OR r.position > :threshold)
    """)
    result = await db.execute(query, params)
    rows = result.mappings().all()

    gained = []
    lost = []
    for r in rows:
        item = {
            "keyword_id": r["keyword_id"],
            "engine": r["engine"],
            "old_position": r["old_position"],
            "new_position": r["new_position"],
        }
        new_pos = r["new_position"]
        if new_pos is not None and new_pos <= threshold:
            gained.append(item)
        else:
            lost.append(item)

    return {"gained": gained, "lost": lost}


async def compare_positions_by_date(
    db: AsyncSession,
    site_id: uuid.UUID,
    date_a: str,
    date_b: str,
    engine: str | None = None,
) -> list[dict]:
    """Compare positions between two dates (YYYY-MM-DD).

    Returns list of dicts: keyword_id, engine, position_a, position_b, delta.
    """
    engine_filter = "AND kp.engine = :engine" if engine else ""
    params: dict = {"site_id": site_id, "date_a": date_a, "date_b": date_b}
    if engine:
        params["engine"] = engine

    query = text(f"""
        WITH pos_a AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.keyword_id, kp.engine, kp.position, kp.url
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id
              AND kp.checked_at::date = :date_a::date
              {engine_filter}
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        ),
        pos_b AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.keyword_id, kp.engine, kp.position, kp.url
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id
              AND kp.checked_at::date = :date_b::date
              {engine_filter}
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        )
        SELECT
            COALESCE(a.keyword_id, b.keyword_id) AS keyword_id,
            COALESCE(a.engine, b.engine) AS engine,
            a.position AS position_a,
            b.position AS position_b,
            CASE
                WHEN a.position IS NOT NULL AND b.position IS NOT NULL
                    THEN a.position - b.position
                ELSE NULL
            END AS delta,
            a.url AS url_a,
            b.url AS url_b
        FROM pos_a a
        FULL OUTER JOIN pos_b b ON a.keyword_id = b.keyword_id AND a.engine = b.engine
        ORDER BY COALESCE(b.position, 999) ASC
    """)
    result = await db.execute(query, params)
    return [dict(r) for r in result.mappings().all()]


async def get_positions_by_url(
    db: AsyncSession,
    site_id: uuid.UUID,
    url_filter: str,
    engine: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Get latest positions filtered by ranking URL (substring match).

    Returns list of position dicts for keywords ranking on the given URL.
    """
    engine_filter = "AND kp.engine = :engine" if engine else ""
    params: dict = {"site_id": site_id, "url_filter": f"%{url_filter}%", "limit": limit}
    if engine:
        params["engine"] = engine

    query = text(f"""
        SELECT * FROM (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.*
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id {engine_filter}
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        ) latest
        WHERE latest.url ILIKE :url_filter
        ORDER BY latest.position ASC NULLS LAST
        LIMIT :limit
    """)
    result = await db.execute(query, params)
    return [dict(r) for r in result.mappings().all()]


# ---- Sync version for Celery tasks ----

def write_position_sync(
    db: Session,
    keyword_id: uuid.UUID,
    site_id: uuid.UUID,
    engine: str,
    position: int | None,
    checked_at: datetime | None = None,
    **kwargs,
) -> None:
    """Sync version for use in Celery tasks."""
    if checked_at is None:
        checked_at = datetime.now(timezone.utc)

    db.execute(text("SELECT create_kp_partition(:d)"), {"d": checked_at.date()})

    # Previous position
    prev = db.execute(
        select(KeywordPosition)
        .where(
            KeywordPosition.keyword_id == keyword_id,
            KeywordPosition.engine == engine,
        )
        .order_by(KeywordPosition.checked_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    previous_position = prev.position if prev else None
    delta = None
    if previous_position is not None and position is not None:
        delta = previous_position - position

    record = KeywordPosition(
        keyword_id=keyword_id,
        site_id=site_id,
        engine=engine,
        position=position,
        previous_position=previous_position,
        delta=delta,
        checked_at=checked_at,
        **kwargs,
    )
    db.add(record)
