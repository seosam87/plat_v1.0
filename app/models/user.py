import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SAEnum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, PyEnum):
    admin = "admin"
    manager = "manager"
    client = "client"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), nullable=False, default=UserRole.client
    )
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
    # Per-user Anthropic API key stored Fernet-encrypted (migration 0041, D-02)
    anthropic_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    # Telegram user ID — 64-bit integer, set when user links Telegram account (migration 0051)
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True, default=None
    )

    @property
    def has_anthropic_key(self) -> bool:
        """Returns True if the user has a configured Anthropic API key."""
        return bool(self.anthropic_api_key_encrypted)
