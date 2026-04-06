"""ErrorImpactScore model — pre-computed impact scores for audit errors.

Impact score = severity_weight x monthly_traffic from Metrika.
Pre-computed by Celery task after each audit run to keep dashboard fast.
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


class ErrorImpactScore(Base):
    """Pre-computed impact score per (site, page_url, check_code).

    impact_score = severity_weight * monthly_traffic
    where severity_weight comes from SEVERITY_WEIGHTS in impact_score_service.

    Updated via INSERT ... ON CONFLICT DO UPDATE after each audit run.
    """

    __tablename__ = "error_impact_scores"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "page_url", "check_code", name="uq_eis_site_page_check"
        ),
        Index("ix_eis_site_impact", "site_id", "impact_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    check_code: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    severity_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_traffic: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impact_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
