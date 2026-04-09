"""SiteIntake model for site audit intake feature."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IntakeStatus(str, PyEnum):
    draft = "draft"
    complete = "complete"


class SiteIntake(Base):
    __tablename__ = "site_intakes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[IntakeStatus] = mapped_column(
        SAEnum(IntakeStatus), nullable=False, default=IntakeStatus.draft
    )

    # Section data (JSON fields)
    goals_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Expected: {"main_goal": str, "target_regions": str, "competitors": [str], "notes": str}
    technical_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Expected: {"robots_notes": str}

    # Section completion flags
    section_access: Mapped[bool] = mapped_column(Boolean, default=False)
    section_goals: Mapped[bool] = mapped_column(Boolean, default=False)
    section_analytics: Mapped[bool] = mapped_column(Boolean, default=False)
    section_technical: Mapped[bool] = mapped_column(Boolean, default=False)
    section_checklist: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
