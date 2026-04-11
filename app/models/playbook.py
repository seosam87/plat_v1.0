"""Phase 999.8 Playbook Builder models.

8 SQLAlchemy models for the reusable promotion-plan system:

Library:
- ExpertSource       — optional author/expert attached to a block
- BlockCategory      — block taxonomy (8 seeded categories in Russian)
- PlaybookBlock      — a reusable methodology block
- BlockMedia         — videos/articles attached to a block

Templates:
- Playbook           — reusable template assembled from blocks
- PlaybookStep       — ordered block inside a template

Applied copies (per project):
- ProjectPlaybook    — a playbook applied to a project (copy-on-apply)
- ProjectPlaybookStep — per-project, per-step status

All FK ondelete rules follow D-12 (copy-on-apply). ProjectPlaybook.playbook_id
is NULLABLE so deleting a template never cascades into applied copies.

Enums use explicit `name=...` so Alembic migrations produce stable type names.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ActionKind(str, PyEnum):
    """What the block's primary CTA does in the UI."""

    run_crawl = "run_crawl"
    open_keywords = "open_keywords"
    open_competitors = "open_competitors"
    open_content_plan = "open_content_plan"
    open_commercial_check = "open_commercial_check"
    open_brief = "open_brief"
    manual_note = "manual_note"


class BlockMediaKind(str, PyEnum):
    video = "video"
    article = "article"


class ProjectPlaybookStatus(str, PyEnum):
    active = "active"
    paused = "paused"
    done = "done"
    archived = "archived"


class ProjectPlaybookStepStatus(str, PyEnum):
    open = "open"
    in_progress = "in_progress"
    done = "done"


class PlaybookCategory(str, PyEnum):
    """Template-level category filter (D-09)."""

    commerce = "commerce"
    content = "content"
    technical = "technical"
    mixed = "mixed"


# ---------------------------------------------------------------------------
# 1. ExpertSource
# ---------------------------------------------------------------------------


class ExpertSource(Base):
    __tablename__ = "expert_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    bio_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# 2. BlockCategory
# ---------------------------------------------------------------------------


class BlockCategory(Base):
    __tablename__ = "block_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# 3. PlaybookBlock
# ---------------------------------------------------------------------------


class PlaybookBlock(Base):
    __tablename__ = "playbook_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("block_categories.id"),
        nullable=False,
        index=True,
    )
    expert_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expert_sources.id"),
        nullable=True,
    )
    summary_md: Mapped[str] = mapped_column(Text, nullable=False)
    checklist_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_kind: Mapped[ActionKind] = mapped_column(
        SAEnum(ActionKind, name="actionkind"), nullable=False
    )
    prerequisites: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    estimated_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    category = relationship("BlockCategory")
    expert_source = relationship("ExpertSource")
    media = relationship(
        "BlockMedia",
        back_populates="block",
        cascade="all, delete-orphan",
        order_by="BlockMedia.display_order",
    )


# ---------------------------------------------------------------------------
# 4. BlockMedia
# ---------------------------------------------------------------------------


class BlockMedia(Base):
    __tablename__ = "block_media"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playbook_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[BlockMediaKind] = mapped_column(
        SAEnum(BlockMediaKind, name="blockmediakind"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    block = relationship("PlaybookBlock", back_populates="media")


# ---------------------------------------------------------------------------
# 5. Playbook
# ---------------------------------------------------------------------------


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(300), nullable=False, unique=True, index=True
    )
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[PlaybookCategory | None] = mapped_column(
        SAEnum(PlaybookCategory, name="playbookcategory"), nullable=True
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    steps = relationship(
        "PlaybookStep",
        back_populates="playbook",
        cascade="all, delete-orphan",
        order_by="PlaybookStep.position",
    )


# ---------------------------------------------------------------------------
# 6. PlaybookStep
# ---------------------------------------------------------------------------


class PlaybookStep(Base):
    __tablename__ = "playbook_steps"
    __table_args__ = (
        UniqueConstraint("playbook_id", "position", name="uq_playbook_step_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("playbook_blocks.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    note_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    playbook = relationship("Playbook", back_populates="steps")
    block = relationship("PlaybookBlock")


# ---------------------------------------------------------------------------
# 7. ProjectPlaybook
# ---------------------------------------------------------------------------


class ProjectPlaybook(Base):
    __tablename__ = "project_playbooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # D-12: nullable + no cascade so template deletion never kills applied copies.
    playbook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("playbooks.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[ProjectPlaybookStatus] = mapped_column(
        SAEnum(ProjectPlaybookStatus, name="projectplaybookstatus"),
        nullable=False,
        default=ProjectPlaybookStatus.active,
        server_default="active",
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    steps = relationship(
        "ProjectPlaybookStep",
        back_populates="project_playbook",
        cascade="all, delete-orphan",
        order_by="ProjectPlaybookStep.position",
    )


# ---------------------------------------------------------------------------
# 8. ProjectPlaybookStep
# ---------------------------------------------------------------------------


class ProjectPlaybookStep(Base):
    __tablename__ = "project_playbook_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_playbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_playbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("playbook_blocks.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ProjectPlaybookStepStatus] = mapped_column(
        SAEnum(ProjectPlaybookStepStatus, name="projectplaybookstepstatus"),
        nullable=False,
        default=ProjectPlaybookStepStatus.open,
        server_default="open",
    )
    prerequisites: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    note_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    project_playbook = relationship("ProjectPlaybook", back_populates="steps")
    block = relationship("PlaybookBlock")


__all__ = [
    "ActionKind",
    "BlockMediaKind",
    "ProjectPlaybookStatus",
    "ProjectPlaybookStepStatus",
    "PlaybookCategory",
    "ExpertSource",
    "BlockCategory",
    "PlaybookBlock",
    "BlockMedia",
    "Playbook",
    "PlaybookStep",
    "ProjectPlaybook",
    "ProjectPlaybookStep",
]
