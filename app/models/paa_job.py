"""PAAJob + PAAResult — People Also Ask SERP aggregation tool."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PAAJob(Base):
    """Stores a PAA (People Also Ask) extraction job.

    Status lifecycle: pending -> running -> complete | failed
    """

    __tablename__ = "paa_jobs"
    __table_args__ = (Index("ix_pj_user_created", "user_id", "created_at"),)

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


class PAAResult(Base):
    """Stores a single PAA question result from a PAAJob.

    Per D-09: flat table (no JSON tree). One row per question per phrase.
    source_block: "частые вопросы" or "похожие запросы"
    """

    __tablename__ = "paa_results"
    __table_args__ = (Index("ix_pr_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("paa_jobs.id", ondelete="CASCADE"), nullable=False
    )
    phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_block: Mapped[str] = mapped_column(String(50), nullable=False)
