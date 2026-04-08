"""Notification model — stores in-app notifications per user.

Each row represents one notification event emitted by a Celery task or service.
Notifications are user-scoped (user_id = the user who triggered the task).
Retention: 30 days max via nightly cleanup task.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    """In-app notification for a user.

    Severity levels: 'info' (green), 'warning' (yellow), 'error' (red).
    kind uses dotted namespace: 'crawl.completed', 'pdf.ready', etc.
    is_read flips to True when the user opens the bell dropdown.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    link_url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default=sa.text("'info'")
    )
    is_read: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    def __init__(self, **kwargs):
        # Set Python-side defaults so attributes are available before flush
        kwargs.setdefault("severity", "info")
        kwargs.setdefault("is_read", False)
        super().__init__(**kwargs)
