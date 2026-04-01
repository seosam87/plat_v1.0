"""Telegram alert service for position drops."""
from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def is_configured() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


async def send_message(text: str) -> bool:
    """Send a message to the configured Telegram chat."""
    if not is_configured():
        logger.debug("Telegram not configured, skipping alert")
        return False

    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            })
            resp.raise_for_status()
            logger.info("Telegram alert sent")
            return True
    except Exception as exc:
        logger.warning("Telegram alert failed", error=str(exc))
        return False


def send_message_sync(text: str) -> bool:
    """Sync version for Celery tasks."""
    if not is_configured():
        return False

    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        resp = httpx.post(url, json={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Telegram alert failed (sync)", error=str(exc))
        return False


def format_position_drop_alert(
    site_name: str,
    keyword: str,
    old_pos: int,
    new_pos: int,
    url: str | None = None,
) -> str:
    """Format a position drop alert message."""
    delta = new_pos - old_pos
    emoji = "\U0001f534"  # red circle
    msg = (
        f"{emoji} <b>Position Drop</b>\n"
        f"Site: {site_name}\n"
        f"Keyword: <b>{keyword}</b>\n"
        f"Position: {old_pos} → {new_pos} ({delta:+d})\n"
    )
    if url:
        msg += f"URL: {url}\n"
    return msg
