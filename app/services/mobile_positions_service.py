"""Mobile positions service: async queries for /m/positions page.

Standalone async service — queries keyword_latest_positions with Keyword JOIN
for fast per-site position display on the mobile interface.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword_latest_position import KeywordLatestPosition
from app.models.keyword import Keyword


async def get_mobile_positions(
    db: AsyncSession,
    site_id: uuid.UUID,
    period_days: int | None = None,
    dropped_only: bool = False,
    limit: int = 100,
) -> list[dict]:
    """Query keyword_latest_positions for a site with optional filters.

    Args:
        db: Async database session.
        site_id: Site UUID to filter by.
        period_days: If set, filter to positions checked within the last N days.
        dropped_only: If True, return only keywords with negative delta (position drops).
        limit: Maximum number of results to return.

    Returns:
        List of dicts with keys: id, phrase, position, previous_position,
        delta, engine, checked_at.
    """
    logger.debug(
        "get_mobile_positions: site_id={}, period_days={}, dropped_only={}, limit={}",
        site_id, period_days, dropped_only, limit,
    )

    stmt = (
        select(
            KeywordLatestPosition.id,
            KeywordLatestPosition.position,
            KeywordLatestPosition.previous_position,
            KeywordLatestPosition.delta,
            KeywordLatestPosition.engine,
            KeywordLatestPosition.checked_at,
            Keyword.phrase,
        )
        .join(Keyword, KeywordLatestPosition.keyword_id == Keyword.id)
        .where(KeywordLatestPosition.site_id == site_id)
    )

    if dropped_only:
        stmt = stmt.where(KeywordLatestPosition.delta < 0)

    if period_days is not None:
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        stmt = stmt.where(KeywordLatestPosition.checked_at >= cutoff)

    stmt = stmt.order_by(
        func.abs(KeywordLatestPosition.delta).desc().nullslast()
    ).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()
    logger.debug("get_mobile_positions: found {} rows", len(rows))

    return [
        {
            "id": str(row.id),
            "phrase": row.phrase,
            "position": row.position,
            "previous_position": row.previous_position,
            "delta": row.delta,
            "engine": row.engine,
            "checked_at": row.checked_at,
        }
        for row in rows
    ]
