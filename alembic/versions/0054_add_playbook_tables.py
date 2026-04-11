"""add playbook tables

Revision ID: 0054
Revises: 0053
Create Date: 2026-04-11

Creates 8 tables for Phase 999.8 Playbook Builder:
expert_sources, block_categories, playbook_blocks, block_media,
playbooks, playbook_steps, project_playbooks, project_playbook_steps.
Seeds 8 BlockCategory rows inline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. expert_sources
    # -----------------------------------------------------------------
    op.create_table(
        "expert_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("bio_md", sa.Text(), nullable=True),
        sa.Column("external_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("slug", name="uq_expert_sources_slug"),
    )
    op.create_index("ix_expert_sources_slug", "expert_sources", ["slug"])

    # -----------------------------------------------------------------
    # 2. block_categories
    # -----------------------------------------------------------------
    op.create_table(
        "block_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(100), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("slug", name="uq_block_categories_slug"),
    )
    op.create_index("ix_block_categories_slug", "block_categories", ["slug"])

    # -----------------------------------------------------------------
    # 3. playbook_blocks
    # -----------------------------------------------------------------
    op.create_table(
        "playbook_blocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), nullable=False),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("block_categories.id"),
            nullable=False,
        ),
        sa.Column(
            "expert_source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("expert_sources.id"),
            nullable=True,
        ),
        sa.Column("summary_md", sa.Text(), nullable=False),
        sa.Column("checklist_md", sa.Text(), nullable=True),
        sa.Column(
            "action_kind",
            sa.Enum(
                "run_crawl",
                "open_keywords",
                "open_competitors",
                "open_content_plan",
                "open_commercial_check",
                "open_brief",
                "manual_note",
                name="actionkind",
            ),
            nullable=False,
        ),
        sa.Column(
            "prerequisites",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("estimated_days", sa.Integer(), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("slug", name="uq_playbook_blocks_slug"),
    )
    op.create_index("ix_playbook_blocks_slug", "playbook_blocks", ["slug"])
    op.create_index(
        "ix_playbook_blocks_category_id", "playbook_blocks", ["category_id"]
    )

    # -----------------------------------------------------------------
    # 4. block_media
    # -----------------------------------------------------------------
    op.create_table(
        "block_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "block_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbook_blocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum("video", "article", name="blockmediakind"),
            nullable=False,
        ),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_block_media_block_id", "block_media", ["block_id"])

    # -----------------------------------------------------------------
    # 5. playbooks
    # -----------------------------------------------------------------
    op.create_table(
        "playbooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(300), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "commerce",
                "content",
                "technical",
                "mixed",
                name="playbookcategory",
            ),
            nullable=True,
        ),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("slug", name="uq_playbooks_slug"),
    )
    op.create_index("ix_playbooks_slug", "playbooks", ["slug"])

    # -----------------------------------------------------------------
    # 6. playbook_steps
    # -----------------------------------------------------------------
    op.create_table(
        "playbook_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "playbook_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "block_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbook_blocks.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("note_md", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "playbook_id", "position", name="uq_playbook_step_position"
        ),
    )
    op.create_index(
        "ix_playbook_steps_playbook_id", "playbook_steps", ["playbook_id"]
    )

    # -----------------------------------------------------------------
    # 7. project_playbooks
    # -----------------------------------------------------------------
    op.create_table(
        "project_playbooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # D-12: nullable + no cascade — template deletion must not kill copies.
        sa.Column(
            "playbook_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbooks.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "paused",
                "done",
                "archived",
                name="projectplaybookstatus",
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "applied_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_project_playbooks_project_id", "project_playbooks", ["project_id"]
    )

    # -----------------------------------------------------------------
    # 8. project_playbook_steps
    # -----------------------------------------------------------------
    op.create_table(
        "project_playbook_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_playbook_id",
            UUID(as_uuid=True),
            sa.ForeignKey("project_playbooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "block_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbook_blocks.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "in_progress",
                "done",
                name="projectplaybookstepstatus",
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "prerequisites",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "assignee_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("note_md", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_project_playbook_steps_project_playbook_id",
        "project_playbook_steps",
        ["project_playbook_id"],
    )

    # -----------------------------------------------------------------
    # Seed BlockCategory (8 rows, Russian) — CD-05 inline bulk_insert
    # -----------------------------------------------------------------
    now = datetime(2026, 4, 11, tzinfo=timezone.utc)
    categories_table = sa.table(
        "block_categories",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("icon", sa.String),
        sa.column("display_order", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        categories_table,
        [
            {
                "id": uuid.uuid4(),
                "name": "Анализ конкурентов",
                "slug": "competitors",
                "icon": "magnifying-glass",
                "display_order": 10,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Сбор ключей",
                "slug": "keywords",
                "icon": "key",
                "display_order": 20,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Анализ структуры сайта",
                "slug": "site-structure",
                "icon": "squares-2x2",
                "display_order": 30,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Коммерческие страницы",
                "slug": "commerce",
                "icon": "shopping-cart",
                "display_order": 40,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Контент",
                "slug": "content",
                "icon": "document-text",
                "display_order": 50,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Техничка",
                "slug": "technical",
                "icon": "wrench",
                "display_order": 60,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Ссылочная стратегия",
                "slug": "backlinks",
                "icon": "link",
                "display_order": 70,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "Регулярные работы",
                "slug": "regular",
                "icon": "arrow-path",
                "display_order": 80,
                "created_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("project_playbook_steps")
    op.drop_table("project_playbooks")
    op.drop_table("playbook_steps")
    op.drop_table("playbooks")
    op.drop_table("block_media")
    op.drop_table("playbook_blocks")
    op.drop_table("block_categories")
    op.drop_table("expert_sources")
    sa.Enum(name="projectplaybookstepstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="projectplaybookstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="playbookcategory").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="blockmediakind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="actionkind").drop(op.get_bind(), checkfirst=True)
