"""Add suggest_jobs table for keyword suggest expansion requests.

Revision ID: 0040
Revises: 0039
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suggest_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("seed", sa.String(200), nullable=False),
        sa.Column("include_google", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("expected_count", sa.Integer, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("cache_hit", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("cache_key", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sj_user_created",
        "suggest_jobs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sj_user_created", table_name="suggest_jobs")
    op.drop_table("suggest_jobs")
