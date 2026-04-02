import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ResolutionType(str, PyEnum):
    merge_content = "merge_content"
    set_canonical = "set_canonical"
    redirect_301 = "redirect_301"
    split_keywords = "split_keywords"


class ResolutionStatus(str, PyEnum):
    proposed = "proposed"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


class CannibalizationResolution(Base):
    __tablename__ = "cannibalization_resolutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    keyword_phrase: Mapped[str] = mapped_column(String(1000), nullable=False)
    competing_urls: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    resolution_type: Mapped[ResolutionType] = mapped_column(SAEnum(ResolutionType), nullable=False)
    primary_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    action_plan: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ResolutionStatus] = mapped_column(SAEnum(ResolutionStatus), nullable=False, default=ResolutionStatus.proposed)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("seo_tasks.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
