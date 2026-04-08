"""Phase 17: add notifications table with indexes.

Revision ID: 0042
Revises: 0041
Create Date: 2026-04-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link_url", sa.String(500), nullable=False),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Index 1: lookup unread for a user (primary query pattern for bell count)
    op.create_index(
        "ix_notifications_user_id_is_read",
        "notifications",
        ["user_id", "is_read"],
    )

    # Index 2: lookup recent notifications for a user (feed query)
    op.create_index(
        "ix_notifications_user_id_created_at",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
    )

    # Index 3: lookup by site (for site-scoped views)
    op.create_index(
        "ix_notifications_site_id",
        "notifications",
        ["site_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_site_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id_is_read", table_name="notifications")
    op.drop_table("notifications")
