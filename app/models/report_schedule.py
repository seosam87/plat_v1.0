"""ReportSchedule: singleton model for global report delivery configuration."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportSchedule(Base):
    """Singleton row (id=1) controlling morning digest and weekly report delivery."""

    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Morning digest (Telegram text message)
    morning_digest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    morning_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    morning_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Weekly summary report (PDF via SMTP)
    weekly_report_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    weekly_day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weekly_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    weekly_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Email recipient for weekly report
    smtp_to: Mapped[str | None] = mapped_column(String(320), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )
