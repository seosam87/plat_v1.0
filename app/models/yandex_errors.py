import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class YandexErrorType(str, PyEnum):
    indexing = "indexing"
    crawl = "crawl"
    sanction = "sanction"


class YandexErrorStatus(str, PyEnum):
    open = "open"
    ignored = "ignored"
    resolved = "resolved"


class YandexError(Base):
    __tablename__ = "yandex_errors"
    __table_args__ = (
        Index("ix_yandex_errors_site_id_type", "site_id", "error_type"),
        Index("ix_yandex_errors_site_id_status", "site_id", "status"),
        UniqueConstraint("site_id", "error_type", "subtype", "url", name="uq_yandex_errors_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    error_type: Mapped[YandexErrorType] = mapped_column(
        SAEnum(YandexErrorType, name="yandex_error_type", create_constraint=False, native_enum=True),
        nullable=False,
    )
    subtype: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[YandexErrorStatus] = mapped_column(
        SAEnum(YandexErrorStatus, name="yandex_error_status", create_constraint=False, native_enum=True),
        nullable=False,
        default=YandexErrorStatus.open,
    )
