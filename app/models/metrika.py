import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetrikaTrafficDaily(Base):
    """Daily site-level traffic aggregate from Yandex Metrika (for charts and widgets)."""

    __tablename__ = "metrika_traffic_daily"
    __table_args__ = (
        UniqueConstraint("site_id", "traffic_date", name="uq_metrika_daily_site_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    traffic_date: Mapped[date] = mapped_column(Date, nullable=False)
    visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounce_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    page_depth: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    avg_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class MetrikaTrafficPage(Base):
    """Per-page traffic aggregate from Yandex Metrika over a date range."""

    __tablename__ = "metrika_traffic_pages"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "period_start", "period_end", "page_url",
            name="uq_metrika_pages_site_period_url",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounce_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    page_depth: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    avg_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class MetrikaEvent(Base):
    """Manual event markers for chart overlay (e.g. schema.org added, site redesign)."""

    __tablename__ = "metrika_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6b7280")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
