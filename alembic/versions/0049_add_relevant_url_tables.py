"""Phase 24-04: add relevant_url_jobs and relevant_url_results tables.

Revision ID: 0049
Revises: 0046
Create Date: 2026-04-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0049"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relevant_url_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_phrases", JSONB, nullable=False),
        sa.Column("target_domain", sa.String(500), nullable=False),
        sa.Column("phrase_count", sa.Integer, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_ruj_user_created", "relevant_url_jobs", ["user_id", "created_at"])

    op.create_table(
        "relevant_url_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("relevant_url_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("position", sa.Integer, nullable=True),
        sa.Column("top_competitors", JSONB, nullable=True),
    )
    op.create_index("ix_rur_job_id", "relevant_url_results", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_rur_job_id", table_name="relevant_url_results")
    op.drop_table("relevant_url_results")
    op.drop_index("ix_ruj_user_created", table_name="relevant_url_jobs")
    op.drop_table("relevant_url_jobs")
