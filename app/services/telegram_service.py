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


CHANGE_TYPE_LABELS = {
    "page_404": "Страница вернула 404",
    "noindex_added": "Добавлен noindex",
    "schema_removed": "Удалена schema.org",
    "title_changed": "Изменён title",
    "h1_changed": "Изменён H1",
    "canonical_changed": "Изменён canonical",
    "meta_description_changed": "Изменено meta description",
    "content_changed": "Изменён контент",
    "new_page": "Новая страница",
}


def format_change_alert(
    site_name: str,
    change_type: str,
    page_url: str,
    details: str = "",
) -> str:
    """Format a change monitoring alert message."""
    label = CHANGE_TYPE_LABELS.get(change_type, change_type)
    msg = (
        f"\U0001f534 <b>SEO Alert</b>\n"
        f"Site: {site_name}\n"
        f"Change: {label}\n"
        f"URL: {page_url}\n"
    )
    if details:
        msg += f"Details: {details}\n"
    return msg


def format_weekly_digest(
    site_name: str,
    changes: list[dict],
    period: str,
) -> str:
    """Format a weekly digest message.

    changes: list of {change_type, severity, page_url, details}
    """
    if not changes:
        return (
            f"\U0001f4ca <b>Еженедельный дайджест: {site_name}</b>\n"
            f"Период: {period}\n\n"
            f"Нет изменений за этот период."
        )

    errors = [c for c in changes if c.get("severity") == "error"]
    warnings = [c for c in changes if c.get("severity") == "warning"]
    infos = [c for c in changes if c.get("severity") == "info"]

    lines = [
        f"\U0001f4ca <b>Еженедельный дайджест: {site_name}</b>",
        f"Период: {period}",
        "",
    ]

    if errors:
        lines.append(f"\U0001f534 Критичные ({len(errors)}):")
        for c in errors[:10]:
            label = CHANGE_TYPE_LABELS.get(c["change_type"], c["change_type"])
            lines.append(f"  • {label}: {c['page_url']}")
        lines.append("")

    if warnings:
        lines.append(f"\u26a0\ufe0f Предупреждения ({len(warnings)}):")
        for c in warnings[:15]:
            label = CHANGE_TYPE_LABELS.get(c["change_type"], c["change_type"])
            lines.append(f"  • {label}: {c['page_url']}")
        lines.append("")

    if infos:
        lines.append(f"\u2139\ufe0f Информация ({len(infos)}):")
        if len(infos) <= 5:
            for c in infos:
                label = CHANGE_TYPE_LABELS.get(c["change_type"], c["change_type"])
                lines.append(f"  • {label}: {c['page_url']}")
        else:
            lines.append(f"  {len(infos)} изменений")
        lines.append("")

    lines.append(f"Всего изменений: {len(changes)}")

    msg = "\n".join(lines)
    # Telegram limit ~4096 chars
    if len(msg) > 4000:
        msg = msg[:3990] + "\n..."
    return msg


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
