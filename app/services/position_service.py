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
