"""Celery tasks for Telegram channel post management."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.channel_tasks.publish_scheduled_posts",
    bind=True,
    max_retries=2,
    queue="default",
    soft_time_limit=120,
    time_limit=180,
)
def publish_scheduled_posts(self) -> dict:
    """Publish all posts whose scheduled_at <= now().

    Runs every 60 seconds via Celery Beat.
    One post failure does not stop others from being processed.
    """
    from app.database import get_sync_db
    from app.models.channel_post import PostStatus, TelegramChannelPost
    from app.config import settings
    from sqlalchemy import select

    published = 0
    failed = 0

    with get_sync_db() as db:
        now = datetime.now(timezone.utc)
        rows = db.execute(
            select(TelegramChannelPost).where(
                TelegramChannelPost.status == PostStatus.scheduled,
                TelegramChannelPost.scheduled_at <= now,
            )
        ).scalars().all()

        for post in rows:
            try:
                if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHANNEL_ID:
                    logger.warning("Telegram not configured, skipping scheduled publish", post_id=post.id)
                    failed += 1
                    continue

                token = settings.TELEGRAM_BOT_TOKEN
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                resp = httpx.post(url, json={
                    "chat_id": settings.TELEGRAM_CHANNEL_ID,
                    "text": post.content,
                    "parse_mode": "HTML",
                }, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("ok"):
                    raise ValueError(f"Telegram API error: {data.get('description')}")

                message_id = data.get("result", {}).get("message_id")
                post.telegram_message_id = message_id
                post.status = PostStatus.published
                post.published_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(post)
                published += 1
                logger.info("Scheduled post published", post_id=post.id, message_id=message_id)

            except Exception as exc:
                logger.error("Failed to publish scheduled post", post_id=post.id, error=str(exc))
                failed += 1
                # Continue processing other posts — do not re-raise

    logger.info("publish_scheduled_posts complete", published=published, failed=failed)
    return {"published": published, "failed": failed}


# Register in Celery Beat schedule: publish every 60 seconds
celery_app.conf.beat_schedule["publish-scheduled-channel-posts"] = {
    "task": "app.tasks.channel_tasks.publish_scheduled_posts",
    "schedule": 60.0,
}
