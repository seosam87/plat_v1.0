"""add tg_notifications_enabled to users

Revision ID: 0056
Revises: 0055
Create Date: 2026-04-12

Adds tg_notifications_enabled boolean column to users table.
Controlled by D-14: single toggle for Telegram notification preference.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "tg_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "tg_notifications_enabled")
