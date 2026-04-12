"""Celery tasks for notification management.

- cleanup_old_notifications: nightly cleanup (30-day retention)
- dispatch_tg_error_notification: push error alerts to Telegram for opted-in users (D-12, D-13)
"""
from __future__ import annotations

import asyncio

import httpx
from loguru import logger
from sqlalchemy import select

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


@celery_app.task(
    name="app.tasks.notification_tasks.dispatch_tg_error_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue="default",
)
def dispatch_tg_error_notification(self, user_id: str, title: str, body: str) -> dict:
    """Send an error notification to Telegram for a user who has opted in.

    Per D-12 / D-13: only sent when user.telegram_id is set AND
    user.tg_notifications_enabled is True.

    Args:
        user_id: User UUID string.
        title:   Notification title (shown in bold).
        body:    Notification body text.

    Returns:
        Dict with ``sent`` (bool) and optional ``reason`` or ``task_id``.
    """
    from app.config import settings
    from app.database import get_sync_db
    from app.models.user import User

    with get_sync_db() as db:
        user = db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

        if not user:
            return {"sent": False, "reason": "user not found"}
        if not user.telegram_id:
            return {"sent": False, "reason": "no telegram_id"}
        if not user.tg_notifications_enabled:
            return {"sent": False, "reason": "tg_notifications_enabled=False"}

        telegram_id = user.telegram_id

    text = f"&#128308; <b>{title}</b>\n{body}"
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        resp = httpx.post(
            url,
            json={
                "chat_id": telegram_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(
            "TG error notification sent to user {} (tg_id={})", user_id, telegram_id
        )
        return {"sent": True}
    except Exception as exc:
        logger.warning(
            "TG notification failed for user {}: {}", user_id, exc
        )
        raise self.retry(exc=exc)


def register_notifications_cleanup_schedule() -> None:
    """Register nightly cleanup schedule in RedBeat (idempotent).

    RedBeat scheduler ignores static ``celery_app.conf.beat_schedule`` — entries
    must be persisted as ``RedBeatSchedulerEntry`` in Redis. Called from the
    ``beat_init`` hook in ``app.celery_app`` alongside other restore_* functions.
    """
    from celery.schedules import crontab
    from redbeat import RedBeatSchedulerEntry

    key = "notifications-cleanup-nightly"
    try:
        existing = RedBeatSchedulerEntry.from_key(f"redbeat:{key}", app=celery_app)
        existing.delete()
    except KeyError:
        pass

    entry = RedBeatSchedulerEntry(
        name=key,
        task="app.tasks.notification_tasks.cleanup_old_notifications",
        schedule=crontab(hour=3, minute=0),
        app=celery_app,
    )
    entry.save()
    logger.info("Registered notifications-cleanup-nightly in RedBeat (03:00 daily)")
