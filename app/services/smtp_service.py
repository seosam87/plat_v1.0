"""SMTP email wrapper for scheduled report delivery."""
from __future__ import annotations

import asyncio
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from app.config import settings


async def _send_email_async(to: str, subject: str, body_html: str) -> bool:
    """Send HTML email via aiosmtplib (async implementation)."""
    import aiosmtplib

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=True,
        timeout=30,
    )
    return True


def send_email_sync(to: str, subject: str, body_html: str) -> bool:
    """Send HTML email synchronously (for use in Celery tasks).

    Silently skips if SMTP_HOST is not configured (matching Telegram pattern).

    Returns:
        True on success, False on skip or error.
    """
    if not settings.SMTP_HOST:
        logger.debug("SMTP not configured, skipping email delivery")
        return False

    try:
        asyncio.run(_send_email_async(to, subject, body_html))
        logger.info("Email sent via SMTP", to=to, subject=subject)
        return True
    except Exception as exc:
        logger.warning("SMTP delivery failed", to=to, subject=subject, error=str(exc))
        return False


async def _send_email_with_attachment_async(
    to: str,
    subject: str,
    body_html: str,
    attachment_bytes: bytes,
    attachment_filename: str,
) -> bool:
    """Send HTML email with PDF attachment via aiosmtplib (async implementation)."""
    import aiosmtplib

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    part = MIMEApplication(attachment_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
    msg.attach(part)

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=True,
        timeout=30,
    )
    return True


def send_email_with_attachment_sync(
    to: str,
    subject: str,
    body_html: str,
    attachment_bytes: bytes,
    attachment_filename: str,
) -> bool:
    """Send email with PDF attachment. Used by document send Celery task.

    Silently skips if SMTP_HOST is not configured (matching Telegram pattern).

    Returns:
        True on success, False on skip or error.
    """
    if not settings.SMTP_HOST:
        logger.debug("SMTP not configured, skipping email with attachment")
        return False
    try:
        asyncio.run(
            _send_email_with_attachment_async(
                to, subject, body_html, attachment_bytes, attachment_filename
            )
        )
        logger.info("Email with attachment sent", to=to, filename=attachment_filename)
        return True
    except Exception as exc:
        logger.warning(
            "SMTP attachment delivery failed", to=to, error=str(exc)
        )
        return False
