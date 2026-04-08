"""Notification helper — emit in-app notifications for users.

Usage in Celery tasks and services:
    from app.services.notifications import notify

    n = await notify(
        db=db,
        user_id=user_id,
        kind="crawl.completed",
        title="Краулинг завершён",
        body=f"Сайт {site.url} успешно просканирован: {page_count} страниц.",
        link_url=f"/sites/{site_id}/crawl",
        site_id=site_id,
        severity="info",
    )
    await db.commit()

Guard pattern (per D-02 — skip if no user scope):
    if user_id is None:
        logger.debug("no user scope; skipping in-app notification", task=...)
        return
    await notify(db=db, user_id=user_id, ...)
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def notify(
    db: AsyncSession,
    user_id: UUID,
    kind: str,
    title: str,
    body: str,
    link_url: str,
    site_id: UUID | None = None,
    severity: Literal["info", "warning", "error"] = "info",
) -> Notification:
    """Insert a Notification row and flush (does NOT commit — caller commits).

    Args:
        db: Async SQLAlchemy session. Caller owns the transaction.
        user_id: UUID of the user who triggered the task.
        kind: Machine-readable event type, e.g. 'crawl.completed'.
        title: Short human-readable heading (max 200 chars).
        body: Full notification text.
        link_url: URL the user is taken to when they click the notification.
        site_id: Optional FK to sites.id; pass None for system/global events.
        severity: One of 'info', 'warning', 'error'. Controls badge colour.

    Returns:
        The newly-created Notification instance (id populated after flush).
    """
    n = Notification(
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        link_url=link_url,
        site_id=site_id,
        severity=severity,
    )
    db.add(n)
    await db.flush()
    return n
