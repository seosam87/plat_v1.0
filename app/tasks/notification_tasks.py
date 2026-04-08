"""Celery task for nightly notification cleanup.

Deletes notifications older than 30 days to enforce retention policy.
Scheduled via Celery Beat at 03:00 Europe/Moscow.
"""
from __future__ import annotations

import asyncio

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.notification_tasks.cleanup_old_notifications",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def cleanup_old_notifications(self) -> dict:
    """Delete notification rows older than 30 days.

    Returns:
        Dict with status and deleted_count.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_cleanup())
    except Exception as exc:
        logger.error("Notification cleanup task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


async def _cleanup() -> dict:
    """Async implementation: delete rows where created_at < now() - 30 days."""
    from sqlalchemy import text

    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "DELETE FROM notifications"
                " WHERE created_at < NOW() - INTERVAL '30 days'"
            )
        )
        deleted = result.rowcount
        await db.commit()

    logger.info("Notification cleanup complete", deleted_count=deleted)
    return {"status": "ok", "deleted_count": deleted}
