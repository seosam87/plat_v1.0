"""add agent tables

Revision ID: 0057
Revises: 0056
Create Date: 2026-04-12

Creates 4 tables for Phase 999.9 AI Agent / Prompt Library:
agent_categories, ai_agents, agent_favourites, agent_jobs.
Seeds 5 AgentCategory rows inline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. agent_categories
    # -----------------------------------------------------------------
    op.create_table(
        "agent_categories",
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
        sa.UniqueConstraint("slug", name="uq_agent_categories_slug"),
    )
    op.create_index("ix_agent_categories_slug", "agent_categories", ["slug"])

    # -----------------------------------------------------------------
    # 2. ai_agents
    # -----------------------------------------------------------------
    op.create_table(
        "ai_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(200), nullable=True),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_categories.id"),
            nullable=False,
        ),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        # LLM settings
        sa.Column(
            "model",
            sa.String(100),
            nullable=False,
            server_default="claude-haiku-4-5-20251001",
        ),
        sa.Column(
            "temperature",
            sa.Numeric(3, 2),
            nullable=False,
            server_default="0.70",
        ),
        sa.Column(
            "max_tokens", sa.Integer(), nullable=False, server_default="800"
        ),
        sa.Column(
            "output_format",
            sa.String(20),
            nullable=False,
            server_default="text",
        ),
        # Meta
        sa.Column(
            "tags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "usage_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "fork_of_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ai_agents.id", ondelete="SET NULL"),
            nullable=True,
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
    )
    op.create_index("ix_ai_agents_category_id", "ai_agents", ["category_id"])

    # -----------------------------------------------------------------
    # 3. agent_favourites
    # -----------------------------------------------------------------
    op.create_table(
        "agent_favourites",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ai_agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # -----------------------------------------------------------------
    # 4. agent_jobs
    # -----------------------------------------------------------------
    op.create_table(
        "agent_jobs",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ai_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_name", sa.String(300), nullable=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("inputs_json", JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "input_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "output_tokens", sa.Integer(), nullable=False, server_default="0"
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
    )

    # -----------------------------------------------------------------
    # Seed AgentCategory (5 rows, Russian) — inline bulk_insert
    # -----------------------------------------------------------------
    now = datetime(2026, 4, 12, tzinfo=timezone.utc)
    categories_table = sa.table(
        "agent_categories",
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
                "id": uuid.UUID("fa732773-af95-4ca5-a02e-810baac9c055"),
                "name": "Контент",
                "slug": "content",
                "icon": "document-text",
                "display_order": 0,
                "created_at": now,
            },
            {
                "id": uuid.UUID("7b10c3e0-77d8-4ccc-b362-1b1b98213c26"),
                "name": "Аудит",
                "slug": "audit",
                "icon": "magnifying-glass",
                "display_order": 1,
                "created_at": now,
            },
            {
                "id": uuid.UUID("fe9a4969-1949-4017-b920-255bc5c2fffa"),
                "name": "Аналитика",
                "slug": "analytics",
                "icon": "chart-bar",
                "display_order": 2,
                "created_at": now,
            },
            {
                "id": uuid.UUID("4ee586aa-8c28-4a2a-a30a-5d758147569a"),
                "name": "Техническое SEO",
                "slug": "technical-seo",
                "icon": "cog-6-tooth",
                "display_order": 3,
                "created_at": now,
            },
            {
                "id": uuid.UUID("48fba592-a002-450f-b706-82fbf414b34d"),
                "name": "Разное",
                "slug": "misc",
                "icon": "squares-2x2",
                "display_order": 4,
                "created_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("agent_jobs")
    op.drop_table("agent_favourites")
    op.drop_index("ix_ai_agents_category_id", table_name="ai_agents")
    op.drop_table("ai_agents")
    op.drop_index("ix_agent_categories_slug", table_name="agent_categories")
    op.drop_table("agent_categories")
