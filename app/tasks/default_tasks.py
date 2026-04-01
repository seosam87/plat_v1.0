from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.default_tasks.send_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_notification(self, message: str, channel: str = "telegram") -> dict:
    """Send notification via configured channel (currently Telegram)."""
    from app.services.telegram_service import is_configured, send_message_sync

    if channel == "telegram":
        if not is_configured():
            logger.info("Telegram not configured, notification skipped")
            return {"status": "skipped", "reason": "telegram not configured"}

        success = send_message_sync(message)
        if success:
            logger.info("Notification sent via Telegram")
            return {"status": "sent", "channel": "telegram"}
        else:
            logger.warning("Telegram send failed, retrying")
            raise self.retry(exc=RuntimeError("Telegram send failed"))
    else:
        logger.warning("Unknown notification channel", channel=channel)
        return {"status": "skipped", "reason": f"unknown channel: {channel}"}
