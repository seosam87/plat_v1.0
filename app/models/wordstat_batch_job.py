"""WordstatBatchJob + WordstatBatchResult + WordstatMonthlyData — Wordstat batch tool."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WordstatBatchJob(Base):
    """Stores a Wordstat batch frequency check job.

    Status lifecycle: pending -> running -> complete | failed
    """

    __tablename__ = "wordstat_batch_jobs"
    __table_args__ = (Index("ix_wbj_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_phrases: Mapped[list] = mapped_column(JSONB, nullable=False)
    phrase_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class WordstatBatchResult(Base):
    """Stores per-phrase frequency result from a WordstatBatchJob."""

    __tablename__ = "wordstat_batch_results"
    __table_args__ = (Index("ix_wbr_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wordstat_batch_jobs.id", ondelete="CASCADE"), nullable=False
    )
    phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    freq_exact: Mapped[int | None] = mapped_column(Integer, nullable=True)
    freq_broad: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WordstatMonthlyData(Base):
    """Stores monthly frequency data per WordstatBatchResult.

    Per D-13: separate normalized table (not embedded JSON) for flexible queries.
    year_month format: "2026-03"
    """

    __tablename__ = "wordstat_monthly_data"
    __table_args__ = (Index("ix_wmd_result_id", "result_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wordstat_batch_results.id", ondelete="CASCADE"), nullable=False
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False)
