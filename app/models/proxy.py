import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProxyType(str, PyEnum):
    http = "http"
    socks5 = "socks5"


class ProxyStatus(str, PyEnum):
    active = "active"
    dead = "dead"
    unchecked = "unchecked"


class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    proxy_type: Mapped[ProxyType] = mapped_column(
        SAEnum(ProxyType, native_enum=False, create_constraint=False),
        nullable=False,
        default=ProxyType.http,
    )
    status: Mapped[ProxyStatus] = mapped_column(
        SAEnum(ProxyStatus, native_enum=False, create_constraint=False),
        nullable=False,
        default=ProxyStatus.unchecked,
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
