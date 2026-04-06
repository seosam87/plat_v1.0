"""KeywordLatestPosition model — flat table for fast analytical queries.

Replaces expensive DISTINCT ON partition scans in dashboard, Quick Wins,
and Dead Content queries. Maintained by refresh_latest_positions() in
position_service.py, called after every write_positions_batch().

One row per (keyword_id, engine). Updated via INSERT ... ON CONFLICT DO UPDATE.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KeywordLatestPosition(Base):
    """Flat cache of the most recent position per (keyword_id, engine).

    Updated by refresh_latest_positions() after each position batch write.
    Indexed on (site_id, position) for Quick Wins range queries.
    """

    __tablename__ = "keyword_latest_positions"
    __table_args__ = (
        UniqueConstraint("keyword_id", "engine", name="uq_klp_keyword_engine"),
        Index("ix_klp_site_position", "site_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
