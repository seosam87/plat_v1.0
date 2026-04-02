import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConnectionStatus(str, PyEnum):
    unknown = "unknown"
    connected = "connected"
    failed = "failed"


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    wp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stores Fernet-encrypted WP Application Password as base64 text
    encrypted_app_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        SAEnum(ConnectionStatus), nullable=False, default=ConnectionStatus.unknown
    )
    site_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("site_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    seo_plugin: Mapped[str | None] = mapped_column(String(50), nullable=True, default="unknown")
    metrika_counter_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metrika_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_template_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    yandex_region: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
