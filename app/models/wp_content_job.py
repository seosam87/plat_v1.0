import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(str, PyEnum):
    pending = "pending"
    processing = "processing"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    pushed = "pushed"
    rolled_back = "rolled_back"
    failed = "failed"


class WpContentJob(Base):
    """Tracks a content enrichment pipeline run for a single WP page."""

    __tablename__ = "wp_content_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    wp_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    post_type: Mapped[str | None] = mapped_column(String(100), nullable=True, default="posts")
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), nullable=False, default=JobStatus.pending
    )
    heading_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    has_toc: Mapped[bool | None] = mapped_column(nullable=True, default=False)
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rollback_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pushed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
