"""TelegramChannelPost model — stores posts for publishing to a Telegram channel.

Each row represents a draft, scheduled, or published post.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class PostStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    published = "published"


class TelegramChannelPost(Base):
    """Post for a managed Telegram channel.

    title:              Internal reference title (not sent to Telegram)
    content:            Markdown/HTML text sent to Telegram
    status:             draft | scheduled | published
    telegram_message_id: Message ID returned by Bot API after sendMessage
    scheduled_at:       When to auto-publish (Beat task checks every 60s)
    published_at:       Actual publish timestamp
    pinned:             Whether the message is currently pinned in the channel
    created_by_id:      FK to users table
    """

    __tablename__ = "telegram_channel_posts"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        sa.Enum(PostStatus, name="post_status", create_type=True),
        nullable=False,
        default=PostStatus.draft,
        server_default="draft",
    )
    telegram_message_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    pinned: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        sa.Index("ix_channel_posts_status", "status"),
        sa.Index("ix_channel_posts_scheduled_at", "scheduled_at"),
    )
