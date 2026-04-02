import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SitemapEntry(Base):
    """Sitemap.xml comparison result per URL."""

    __tablename__ = "sitemap_entries"

    __table_args__ = (
        UniqueConstraint("site_id", "url", name="uq_sitemap_entry_site_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    in_sitemap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    in_crawl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class PageLink(Base):
    """Internal link graph: source → target with anchor text."""

    __tablename__ = "page_links"

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
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    anchor_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
