"""GeneratedDocument model for PDF document generation (Phase 23)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.proposal_template import TemplateType


class GeneratedDocument(Base):
    """Stores a generated PDF document linked to a client and template.

    Status lifecycle: pending -> processing -> ready | failed

    pdf_data is nullable until generation completes.
    Version cap: max 3 documents per client+template pair (enforced by service).
    """

    __tablename__ = "generated_documents"
    __table_args__ = (
        Index("ix_gd_client_created", "client_id", "created_at"),
        Index("ix_gd_template_id", "template_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proposal_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_type: Mapped[TemplateType] = mapped_column(
        SAEnum(TemplateType, name="templatetype", create_type=False),
        nullable=False,
    )
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="document.pdf"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
