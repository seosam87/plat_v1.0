"""Celery task for batch intent detection."""
from __future__ import annotations

import asyncio
import uuid

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.intent_tasks.batch_detect_intents",
    bind=True,
    max_retries=1,
    queue="default",
    soft_time_limit=600,
    time_limit=660,
)
def batch_detect_intents(
    self, site_id: str, keyword_ids: list[str] | None = None
) -> dict:
    """Detect intents for keywords via SERP analysis."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_batch_detect(site_id, keyword_ids))
    except Exception as exc:
        logger.error("Batch intent detection failed", site_id=site_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()


async def _batch_detect(site_id: str, keyword_ids: list[str] | None) -> dict:
    from app.database import async_session_factory
    from app.services.intent_service import batch_detect_intent, get_unclustered_keywords

    async with async_session_factory() as db:
        if keyword_ids:
            kw_uuids = [uuid.UUID(kid) for kid in keyword_ids]
        else:
            unclustered = await get_unclustered_keywords(db, uuid.UUID(site_id))
            kw_uuids = [uuid.UUID(k["id"]) for k in unclustered]

        if not kw_uuids:
            return {"processed": 0, "commercial": 0, "informational": 0, "mixed": 0}

        proposals = await batch_detect_intent(db, uuid.UUID(site_id), kw_uuids)

        counts = {"commercial": 0, "informational": 0, "mixed": 0, "unknown": 0}
        for p in proposals:
            intent = p.get("proposed_intent", "unknown")
            counts[intent] = counts.get(intent, 0) + 1

        return {"processed": len(proposals), **counts}
