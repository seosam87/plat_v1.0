"""SuggestJob model — stores keyword suggest job requests with lifecycle status.

Each record tracks a single alphabetic expansion request for a seed keyword,
including Yandex/Google source selection, cache hit tracking, and result counts.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SuggestJob(Base):
    """Stores a keyword suggest expansion job.

    Status lifecycle: pending -> running -> complete | partial | failed

    partial: proxies exhausted mid-expansion, partial results returned.
    cache_hit: True if results were served from Redis without external API calls.
    """

    __tablename__ = "suggest_jobs"
    __table_args__ = (
        Index("ix_sj_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    seed: Mapped[str] = mapped_column(String(200), nullable=False)
    include_google: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cache_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
