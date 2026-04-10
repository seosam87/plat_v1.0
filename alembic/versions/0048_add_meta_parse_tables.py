"""Phase 24-03: add meta_parse_jobs and meta_parse_results tables.

Revision ID: 0048
Revises: 0047
Create Date: 2026-04-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_parse_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_urls", JSONB, nullable=False),
        sa.Column("url_count", sa.Integer(), nullable=False),
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
    op.create_index("ix_mpj_user_created", "meta_parse_jobs", ["user_id", "created_at"])

    op.create_table(
        "meta_parse_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id", UUID(as_uuid=True),
            sa.ForeignKey("meta_parse_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_url", sa.String(2000), nullable=False),
        sa.Column("final_url", sa.String(2000), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("h1", sa.String(500), nullable=True),
        sa.Column("h2_list", JSONB, nullable=True),
        sa.Column("meta_description", sa.String(1000), nullable=True),
        sa.Column("canonical", sa.String(2000), nullable=True),
        sa.Column("robots", sa.String(200), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
    )
    op.create_index("ix_mpr_job_id", "meta_parse_results", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_mpr_job_id", table_name="meta_parse_results")
    op.drop_table("meta_parse_results")
    op.drop_index("ix_mpj_user_created", table_name="meta_parse_jobs")
    op.drop_table("meta_parse_jobs")
