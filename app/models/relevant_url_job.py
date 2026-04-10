"""RelevantUrlJob + RelevantUrlResult — relevant URL finder tool."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RelevantUrlJob(Base):
    """Stores a relevant URL finder job.

    Status lifecycle: pending -> running -> complete | partial | failed

    partial: XMLProxy balance exhausted mid-run, partial results saved.
    target_domain: the domain to search for in Yandex TOP-10.
    """

    __tablename__ = "relevant_url_jobs"
    __table_args__ = (Index("ix_ruj_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_phrases: Mapped[list] = mapped_column(JSONB, nullable=False)
    target_domain: Mapped[str] = mapped_column(String(500), nullable=False)
    phrase_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RelevantUrlResult(Base):
    """One result row per phrase in a RelevantUrlJob.

    url and position are None when the target domain is not found in TOP-10.
    top_competitors contains up to 3 competing domain strings.
    """

    __tablename__ = "relevant_url_results"
    __table_args__ = (Index("ix_rur_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relevant_url_jobs.id", ondelete="CASCADE"), nullable=False
    )
    phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_competitors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
