"""MetaParseJob + MetaParseResult — meta tag parsing tool."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetaParseJob(Base):
    """Stores a meta tag parsing job.

    Status lifecycle: pending -> running -> complete | failed
    """

    __tablename__ = "meta_parse_jobs"
    __table_args__ = (Index("ix_mpj_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_urls: Mapped[list] = mapped_column(JSONB, nullable=False)  # list of URL strings
    url_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class MetaParseResult(Base):
    """Stores a single URL result from a MetaParseJob."""

    __tablename__ = "meta_parse_results"
    __table_args__ = (Index("ix_mpr_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_parse_jobs.id", ondelete="CASCADE"), nullable=False
    )
    # input_url: submitted URL; final_url: URL after redirects
    input_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    h1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    h2_list: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list of up to 10 H2 strings
    meta_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    canonical: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    robots: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. "index, follow"
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
