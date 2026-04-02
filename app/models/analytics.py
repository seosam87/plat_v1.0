import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SessionStatus(str, PyEnum):
    draft = "draft"
    positions_checked = "positions_checked"
    serp_parsed = "serp_parsed"
    competitor_found = "competitor_found"
    compared = "compared"
    brief_created = "brief_created"
    completed = "completed"


class AnalysisSession(Base):
    """Analytical workflow session — stores keyword selection and workflow state."""

    __tablename__ = "analysis_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus), nullable=False, default=SessionStatus.draft
    )
    keyword_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    filters_applied: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    keyword_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    competitor_domain: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class SessionSerpResult(Base):
    """SERP TOP-10 results per keyword per session."""

    __tablename__ = "session_serp_results"

    __table_args__ = (
        UniqueConstraint("session_id", "keyword_id", name="uq_serp_result_session_keyword"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    keyword_phrase: Mapped[str] = mapped_column(String(1000), nullable=False)
    results_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    features: Mapped[list | None] = mapped_column(JSON, nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class CompetitorPageData(Base):
    """One-time crawl of a competitor page for comparison."""

    __tablename__ = "competitor_page_data"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    domain: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_schema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_toc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    internal_link_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headings_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    crawl_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="light")
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class ContentBrief(Base):
    """Generated content brief (ТЗ) from analysis session."""

    __tablename__ = "content_briefs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    recommended_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    headings_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    structure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
