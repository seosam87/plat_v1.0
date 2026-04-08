import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CrawlJobStatus(str, PyEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class PageType(str, PyEnum):
    category = "category"
    article = "article"
    landing = "landing"
    product = "product"
    unknown = "unknown"


class ContentType(str, PyEnum):
    informational = "informational"
    commercial = "commercial"
    unknown = "unknown"


class ArchitectureRole(str, PyEnum):
    pillar = "pillar"
    service = "service"
    subservice = "subservice"
    article = "article"
    trigger = "trigger"
    authority = "authority"
    link_accelerator = "link_accelerator"
    unknown = "unknown"


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[CrawlJobStatus] = mapped_column(
        SAEnum(CrawlJobStatus), nullable=False, default=CrawlJobStatus.pending
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Page(Base):
    __tablename__ = "pages"

    __table_args__ = (UniqueConstraint("crawl_job_id", "url"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    crawl_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    internal_link_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_type: Mapped[PageType] = mapped_column(
        SAEnum(PageType), nullable=False, default=PageType.unknown
    )
    content_type: Mapped[ContentType] = mapped_column(
        SAEnum(ContentType), nullable=False, default=ContentType.unknown
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="crawl")
    architecture_role: Mapped[ArchitectureRole] = mapped_column(
        SAEnum(ArchitectureRole), nullable=False, default=ArchitectureRole.unknown
    )
    has_toc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_schema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_noindex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canonical_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inlinks_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geo_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


class PageSnapshot(Base):
    __tablename__ = "page_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    crawl_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Stores: title, h1, meta_description, http_status, content_preview
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Stores {field: {"old": ..., "new": ...}} for changed fields; null if no diff
    diff_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
