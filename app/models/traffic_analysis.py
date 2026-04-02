import uuid
from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VisitSource(str, PyEnum):
    organic = "organic"
    direct = "direct"
    referral = "referral"
    bot_suspected = "bot_suspected"
    injection_suspected = "injection_suspected"


class TrafficAnalysisSession(Base):
    __tablename__ = "traffic_analysis_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="metrika")
    total_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bot_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    organic_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anomaly_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class TrafficVisit(Base):
    __tablename__ = "traffic_visits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("traffic_analysis_sessions.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    page_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source: Mapped[VisitSource] = mapped_column(SAEnum(VisitSource), nullable=False, default=VisitSource.organic)
    referer: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    geo_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bot_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class BotPattern(Base):
    __tablename__ = "bot_patterns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pattern_value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
