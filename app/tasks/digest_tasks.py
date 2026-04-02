"""Celery task for weekly digest."""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.digest_tasks.send_weekly_digest",
    bind=True,
    max_retries=2,
    queue="default",
    soft_time_limit=60,
    time_limit=90,
)
def send_weekly_digest(self, site_id: str) -> dict:
    """Send weekly digest for a site via Telegram."""
    import uuid
    from app.database import get_sync_db
    from app.services.digest_service import send_digest

    try:
        with get_sync_db() as db:
            result = send_digest(db, uuid.UUID(site_id))
            logger.info("Weekly digest sent", site_id=site_id, result=result)
            return result
    except Exception as exc:
        logger.error("Digest task failed", site_id=site_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
