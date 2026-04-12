"""QA Surface Tracker models — FeatureSurface + SurfaceCheck.

Per D-01: a 'feature' is a user flow/scenario, not an individual route.
Per D-02: parent-child — one FeatureSurface + child SurfaceCheck per surface.
"""
from __future__ import annotations
import uuid
import enum
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Surface(str, enum.Enum):
    desktop  = "desktop"
    mobile   = "mobile"
    telegram = "telegram"


class CheckStatus(str, enum.Enum):
    not_tested   = "not_tested"
    passed       = "passed"
    failed       = "failed"
    needs_retest = "needs_retest"


class FeatureSurface(Base):
    __tablename__ = "feature_surfaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    retest_days: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        server_default=sa.func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    checks: Mapped[list["SurfaceCheck"]] = relationship(
        "SurfaceCheck", back_populates="feature", cascade="all, delete-orphan"
    )


class SurfaceCheck(Base):
    __tablename__ = "surface_checks"
    __table_args__ = (
        sa.UniqueConstraint("feature_id", "surface", name="uq_feature_surface"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("feature_surfaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    surface: Mapped[Surface] = mapped_column(sa.Enum(Surface), nullable=False)
    status: Mapped[CheckStatus] = mapped_column(
        sa.Enum(CheckStatus), nullable=False, default=CheckStatus.not_tested
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    tested_by: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        server_default=sa.func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    feature: Mapped[FeatureSurface] = relationship(
        "FeatureSurface", back_populates="checks"
    )
