"""CommerceCheckJob + CommerceCheckResult — commercialization analysis tool."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CommerceCheckJob(Base):
    """Stores a commercialization check job.

    Status lifecycle: pending -> running -> complete | partial | failed

    partial: XMLProxy balance exhausted mid-run, partial results saved.
    """

    __tablename__ = "commerce_check_jobs"
    __table_args__ = (Index("ix_ccj_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_phrases: Mapped[list] = mapped_column(JSONB, nullable=False)
    phrase_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CommerceCheckResult(Base):
    """Stores a single phrase result from a CommerceCheckJob."""

    __tablename__ = "commerce_check_results"
    __table_args__ = (Index("ix_ccr_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commerce_check_jobs.id", ondelete="CASCADE"), nullable=False
    )
    phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    commercialization: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geo_dependent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    localized: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
