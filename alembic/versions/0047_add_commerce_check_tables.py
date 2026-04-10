"""Phase 24: add commerce_check_jobs and commerce_check_results tables.

Revision ID: 0047
Revises: 0046
Create Date: 2026-04-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commerce_check_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_phrases", JSONB, nullable=False),
        sa.Column("phrase_count", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_ccj_user_created", "commerce_check_jobs", ["user_id", "created_at"])

    op.create_table(
        "commerce_check_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id", UUID(as_uuid=True),
            sa.ForeignKey("commerce_check_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("commercialization", sa.Integer(), nullable=True),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("geo_dependent", sa.Boolean(), nullable=True),
        sa.Column("localized", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_ccr_job_id", "commerce_check_results", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_ccr_job_id", table_name="commerce_check_results")
    op.drop_table("commerce_check_results")
    op.drop_index("ix_ccj_user_created", table_name="commerce_check_jobs")
    op.drop_table("commerce_check_jobs")
