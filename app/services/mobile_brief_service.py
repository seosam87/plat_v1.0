"""Mobile brief service: render copywriter brief template, send via Telegram/email."""
from __future__ import annotations

from jinja2 import Environment, FileSystemLoader
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.client import Client

_env = Environment(loader=FileSystemLoader("app/templates"))


def render_brief(
    project_name: str,
    site_url: str,
    length: str,
    tone: str,
    keywords: list[str],
) -> str:
    """Render copywriter brief to plain text string."""
    tmpl = _env.get_template("briefs/copywriter_brief.txt.j2")
    return tmpl.render(
        project_name=project_name,
        site_url=site_url,
        length=length,
        tone=tone,
        keywords=keywords,
    )


async def list_clients_for_brief(db: AsyncSession) -> list[dict]:
    """List clients with email for recipient select (per D-11).
    Uses Client.email IS NOT NULL only (Client has no telegram_username)."""
    stmt = (
        select(Client)
        .where(Client.email.isnot(None))
        .where(Client.is_deleted == False)  # noqa: E712
        .order_by(Client.company_name)
    )
    result = await db.execute(stmt)
    clients = result.scalars().all()
    return [{"id": str(c.id), "name": c.company_name, "email": c.email} for c in clients]


async def send_brief_telegram(text: str, client_email: str) -> bool:
    """Send brief text via Telegram. For Phase 30 MVP, text briefs <4000 chars
    are sent as inline messages. Longer briefs sent as .txt attachment.
    Uses existing notification service pattern."""
    logger.info(f"Brief Telegram send requested for {client_email}, text length={len(text)}")
    try:
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot not configured, skipping brief send")
            return False
        # Import here to avoid circular dependency
        from app.services.telegram_service import send_message_sync

        if len(text) <= 4000:
            msg = text
        else:
            # For long texts, truncate with link note
            msg = text[:3900] + "\n\n[Полный текст ТЗ доступен в платформе]"
        ok = send_message_sync(msg)
        return bool(ok)
    except Exception as e:
        logger.error(f"Telegram brief send failed: {e}")
        return False


async def send_brief_email(text: str, client_email: str, project_name: str) -> bool:
    """Send brief text via email. Plain text body, no attachment for <4000 chars."""
    logger.info(f"Brief email send requested for {client_email}, text length={len(text)}")
    try:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = f"ТЗ копирайтеру: {project_name}"
        msg["From"] = settings.SMTP_FROM or "noreply@seo-platform.local"
        msg["To"] = client_email
        if len(text) <= 4000:
            msg.set_content(text)
        else:
            msg.set_content("ТЗ копирайтеру прикреплено к письму.")
            msg.add_attachment(
                text.encode("utf-8"),
                maintype="text",
                subtype="plain",
                filename="brief.txt",
            )
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST or "localhost",
            port=int(settings.SMTP_PORT or 587),
        )
        return True
    except Exception as e:
        logger.error(f"Email brief send failed: {e}")
        return False
