import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProposalStatus(str, PyEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class GapGroup(Base):
    """Manual grouping of gap keywords."""

    __tablename__ = "gap_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class GapKeyword(Base):
    """Competitor keyword not in our set — a content gap."""

    __tablename__ = "gap_keywords"

    __table_args__ = (
        UniqueConstraint(
            "site_id", "competitor_domain", "phrase",
            name="uq_gap_keyword_site_comp_phrase",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    competitor_domain: Mapped[str] = mapped_column(String(500), nullable=False)
    phrase: Mapped[str] = mapped_column(String(1000), nullable=False)
    frequency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competitor_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    our_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    potential_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gap_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="serp")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class GapProposal(Base):
    """Content plan proposal from gap analysis — pending user approval."""

    __tablename__ = "gap_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    gap_keyword_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gap_keywords.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    target_phrase: Mapped[str] = mapped_column(String(1000), nullable=False)
    frequency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    potential_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus), nullable=False, default=ProposalStatus.pending
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_plan_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_plan_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
