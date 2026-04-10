"""Add telegram_channel_posts table.

Revision ID: 0052
Revises: 0051
Create Date: 2026-04-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type via raw SQL (IF NOT EXISTS to be idempotent)
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'post_status') THEN CREATE TYPE post_status AS ENUM ('draft', 'scheduled', 'published'); END IF; END $$")

    # Create the table using raw SQL to avoid SQLAlchemy re-creating the enum
    op.execute("""
        CREATE TABLE telegram_channel_posts (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            status post_status NOT NULL DEFAULT 'draft',
            telegram_message_id BIGINT,
            scheduled_at TIMESTAMPTZ,
            published_at TIMESTAMPTZ,
            pinned BOOLEAN NOT NULL DEFAULT false,
            created_by_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.create_index(
        "ix_channel_posts_status",
        "telegram_channel_posts",
        ["status"],
    )
    op.create_index(
        "ix_channel_posts_scheduled_at",
        "telegram_channel_posts",
        ["scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_channel_posts_scheduled_at", table_name="telegram_channel_posts")
    op.drop_index("ix_channel_posts_status", table_name="telegram_channel_posts")
    op.drop_table("telegram_channel_posts")
    op.execute("DROP TYPE IF EXISTS post_status")
