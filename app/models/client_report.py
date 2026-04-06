"""ClientReport model — stores generated client instruction PDF reports per site.

Each record holds the blocks config used to generate the report, the PDF bytes
after rendering, and a status field tracking the async generation lifecycle.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClientReport(Base):
    """Stores a client instruction PDF report linked to a site.

    Status lifecycle: pending -> generating -> ready | failed

    pdf_data is nullable until generation completes.
    blocks_config records which data blocks were requested, e.g.:
        {"quick_wins": true, "audit_errors": true, "dead_content": true, "positions": true}
    """

    __tablename__ = "client_reports"
    __table_args__ = (
        Index("ix_cr_site_created", "site_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    blocks_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
