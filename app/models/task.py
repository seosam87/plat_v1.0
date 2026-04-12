import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskType(str, PyEnum):
    page_404 = "page_404"
    lost_indexation = "lost_indexation"
    missing_page = "missing_page"
    cannibalization = "cannibalization"
    manual = "manual"
    yandex_indexing = "yandex_indexing"
    yandex_crawl = "yandex_crawl"
    yandex_sanction = "yandex_sanction"


class TaskPriority(str, PyEnum):
    p1 = "p1"  # Critical
    p2 = "p2"  # High
    p3 = "p3"  # Medium
    p4 = "p4"  # Low


class TaskStatus(str, PyEnum):
    open = "open"
    assigned = "assigned"
    in_progress = "in_progress"
    review = "review"
    resolved = "resolved"


class SeoTask(Base):
    """Auto-generated SEO task from crawl results (404, noindex flip, etc.)."""

    __tablename__ = "seo_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    crawl_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_type: Mapped[TaskType] = mapped_column(
        SAEnum(TaskType), nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), nullable=False, default=TaskStatus.open
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(TaskPriority), nullable=False, default=TaskPriority.p3
    )
    source_error_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("yandex_errors.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
