"""Dashboard overview aggregation: cross-site positions and today's tasks."""
from __future__ import annotations

import json
from datetime import date

import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy import select, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.task import SeoTask, TaskStatus

CACHE_KEY_POSITIONS = "dashboard:agg_positions"
CACHE_TTL = 300  # 5 minutes


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def aggregated_positions(db: AsyncSession) -> dict:
    """Cross-site aggregate: TOP-3/10/100 counts + weekly trend."""
    r = await _get_redis()
    try:
        cached = await r.get(CACHE_KEY_POSITIONS)
        if cached:
            logger.debug("dashboard:agg_positions cache hit")
            return json.loads(cached)

        result = await db.execute(text("""
            WITH latest AS (
                SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                    kp.position, kp.delta, kp.checked_at
                FROM keyword_positions kp
                ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
            ),
            trend AS (
                SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                    kp.delta
                FROM keyword_positions kp
                WHERE kp.checked_at >= NOW() - INTERVAL '7 days'
                  AND kp.delta IS NOT NULL
                ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
            )
            SELECT
                COUNT(*) FILTER (WHERE l.position IS NOT NULL AND l.position <= 3)   AS top3,
                COUNT(*) FILTER (WHERE l.position IS NOT NULL AND l.position <= 10)  AS top10,
                COUNT(*) FILTER (WHERE l.position IS NOT NULL AND l.position <= 100) AS top100,
                (SELECT COUNT(*) FROM trend WHERE delta > 0) AS trend_up,
                (SELECT COUNT(*) FROM trend WHERE delta < 0) AS trend_down
            FROM latest l
        """))
        row = result.mappings().one_or_none()
        data = {
            "top3":       int(row["top3"])       if row and row["top3"]       else 0,
            "top10":      int(row["top10"])      if row and row["top10"]      else 0,
            "top100":     int(row["top100"])     if row and row["top100"]     else 0,
            "trend_up":   int(row["trend_up"])   if row and row["trend_up"]   else 0,
            "trend_down": int(row["trend_down"]) if row and row["trend_down"] else 0,
        }
        await r.set(CACHE_KEY_POSITIONS, json.dumps(data), ex=CACHE_TTL)
        logger.debug("dashboard:agg_positions cache miss — stored")
        return data
    finally:
        await r.aclose()


async def todays_tasks(db: AsyncSession) -> list[dict]:
    """Tasks due today or overdue, plus all in-progress tasks. Max 20."""
    today = date.today()
    active_statuses = [
        TaskStatus.open,
        TaskStatus.assigned,
        TaskStatus.in_progress,
        TaskStatus.review,
    ]
    stmt = (
        select(SeoTask)
        .where(
            SeoTask.status.in_(active_statuses),
            or_(
                SeoTask.status == TaskStatus.in_progress,
                and_(SeoTask.due_date.isnot(None), SeoTask.due_date <= today),
            ),
        )
        .order_by(SeoTask.due_date.asc().nullslast(), SeoTask.priority.asc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "url": t.url,
            "priority": t.priority.value,
            "status": t.status.value,
            "site_id": str(t.site_id),
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "is_overdue": (t.due_date is not None and t.due_date < today),
        }
        for t in rows
    ]
