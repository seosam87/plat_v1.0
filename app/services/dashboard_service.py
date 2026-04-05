"""Dashboard service: per-project aggregation with Redis cache."""
from __future__ import annotations

import json

import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

CACHE_KEY = "dashboard:projects_table"
CACHE_TTL = 300  # 5 minutes


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def projects_table(db: AsyncSession) -> list[dict]:
    """Return per-project aggregated metrics, cached in Redis for 300s.

    Single SQL query replaces the previous O(N) site_overview loop.
    Returns a list of dicts with keys:
        id, name, status, site_name, site_id, open_tasks, in_progress_tasks,
        top3, top10, top30, total_positions
    """
    r = await _get_redis()
    try:
        cached = await r.get(CACHE_KEY)
        if cached:
            logger.debug("dashboard:projects_table cache hit")
            return json.loads(cached)

        result = await db.execute(text("""
            WITH latest_positions AS (
                SELECT DISTINCT ON (kp.keyword_id, kp.engine, kp.site_id)
                    kp.site_id, kp.position
                FROM keyword_positions kp
                ORDER BY kp.keyword_id, kp.engine, kp.site_id, kp.checked_at DESC
            ),
            site_pos AS (
                SELECT site_id,
                    COUNT(*) FILTER (WHERE position <= 3) AS top3,
                    COUNT(*) FILTER (WHERE position <= 10) AS top10,
                    COUNT(*) FILTER (WHERE position <= 30) AS top30,
                    COUNT(*) AS total
                FROM latest_positions
                GROUP BY site_id
            )
            SELECT
                p.id::text, p.name, p.status, s.name AS site_name, p.site_id::text,
                COUNT(t.id) FILTER (WHERE t.status IN ('open', 'assigned')) AS open_tasks,
                COUNT(t.id) FILTER (WHERE t.status = 'in_progress') AS in_progress_tasks,
                COALESCE(sp.top3, 0) AS top3,
                COALESCE(sp.top10, 0) AS top10,
                COALESCE(sp.top30, 0) AS top30,
                COALESCE(sp.total, 0) AS total_positions,
                p.created_at
            FROM projects p
            JOIN sites s ON s.id = p.site_id
            LEFT JOIN seo_tasks t ON t.project_id = p.id
            LEFT JOIN site_pos sp ON sp.site_id = p.site_id
            WHERE p.status != 'archived'
            GROUP BY p.id, s.name, p.site_id, sp.top3, sp.top10, sp.top30, sp.total
            ORDER BY p.created_at DESC
        """))

        rows = result.mappings().all()
        data = [
            {
                "id": row["id"],
                "name": row["name"],
                "status": row["status"],
                "site_name": row["site_name"],
                "site_id": row["site_id"],
                "open_tasks": int(row["open_tasks"] or 0),
                "in_progress_tasks": int(row["in_progress_tasks"] or 0),
                "top3": int(row["top3"] or 0),
                "top10": int(row["top10"] or 0),
                "top30": int(row["top30"] or 0),
                "total_positions": int(row["total_positions"] or 0),
            }
            for row in rows
        ]

        await r.set(CACHE_KEY, json.dumps(data), ex=CACHE_TTL)
        logger.debug("dashboard:projects_table cache miss — stored %d rows", len(data))
        return data
    finally:
        await r.aclose()
