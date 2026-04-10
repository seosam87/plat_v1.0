"""BriefJob + BriefResult — Copywriting Brief SERP aggregation tool."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BriefJob(Base):
    """Stores a copywriting brief job.

    Status lifecycle: pending -> running -> complete | failed

    A BriefJob runs a 4-step Celery chain:
    1. SERP fetch (XMLProxy) — collect TOP-10 URLs per phrase
    2. Crawl TOP-10 pages (Playwright) — extract H2s and visible text
    3. Aggregate — compute word frequencies, H2 cloud, volume stats
    4. Finalize — mark complete, clear intermediate data
    """

    __tablename__ = "brief_jobs"
    __table_args__ = (Index("ix_bj_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_phrases: Mapped[list] = mapped_column(JSONB, nullable=False)
    phrase_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_region: Mapped[int] = mapped_column(Integer, nullable=False, default=213)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intermediate_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class BriefResult(Base):
    """Stores aggregated result from a BriefJob (one row per job)."""

    __tablename__ = "brief_results"
    __table_args__ = (Index("ix_br_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brief_jobs.id", ondelete="CASCADE"), nullable=False
    )
    title_suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    h2_cloud: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    highlights: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    thematic_words: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    avg_text_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_h2_count: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    commercialization_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_crawled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_attempted: Mapped[int | None] = mapped_column(Integer, nullable=True)
