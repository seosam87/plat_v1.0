import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChangeType(str, PyEnum):
    page_404 = "page_404"
    noindex_added = "noindex_added"
    schema_removed = "schema_removed"
    title_changed = "title_changed"
    h1_changed = "h1_changed"
    canonical_changed = "canonical_changed"
    meta_description_changed = "meta_description_changed"
    content_changed = "content_changed"
    new_page = "new_page"


class AlertSeverity(str, PyEnum):
    error = "error"
    warning = "warning"
    info = "info"


class ChangeAlertRule(Base):
    """Global rule mapping change type to severity."""

    __tablename__ = "change_alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    change_type: Mapped[ChangeType] = mapped_column(
        SAEnum(ChangeType), unique=True, nullable=False
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity), nullable=False, default=AlertSeverity.warning
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class ChangeAlert(Base):
    """History of detected changes and sent alerts."""

    __tablename__ = "change_alerts"

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
    change_type: Mapped[ChangeType] = mapped_column(
        SAEnum(ChangeType), nullable=False
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity), nullable=False
    )
    page_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class DigestSchedule(Base):
    """Per-site weekly digest schedule."""

    __tablename__ = "digest_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cron_expression: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
