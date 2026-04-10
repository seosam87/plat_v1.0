"""Phase 25-01: add brief_jobs, brief_results, paa_jobs, paa_results, wordstat_batch_jobs,
wordstat_batch_results, wordstat_monthly_data tables.

Revision ID: 0050
Revises: 0049
Create Date: 2026-04-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- brief_jobs ---
    op.create_table(
        "brief_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_phrases", JSONB, nullable=False),
        sa.Column("phrase_count", sa.Integer, nullable=False),
        sa.Column("input_region", sa.Integer, nullable=False, server_default="213"),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("progress_pct", sa.Integer, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("intermediate_data", JSONB, nullable=True),
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
    op.create_index("ix_bj_user_created", "brief_jobs", ["user_id", "created_at"])

    # --- brief_results ---
    op.create_table(
        "brief_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("brief_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title_suggestions", JSONB, nullable=True),
        sa.Column("h2_cloud", JSONB, nullable=True),
        sa.Column("highlights", JSONB, nullable=True),
        sa.Column("thematic_words", JSONB, nullable=True),
        sa.Column("avg_text_length", sa.Integer, nullable=True),
        sa.Column("avg_h2_count", sa.Numeric(5, 1), nullable=True),
        sa.Column("commercialization_pct", sa.Integer, nullable=True),
        sa.Column("pages_crawled", sa.Integer, nullable=True),
        sa.Column("pages_attempted", sa.Integer, nullable=True),
    )
    op.create_index("ix_br_job_id", "brief_results", ["job_id"])

    # --- paa_jobs ---
    op.create_table(
        "paa_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_phrases", JSONB, nullable=False),
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
    op.create_index("ix_pj_user_created", "paa_jobs", ["user_id", "created_at"])

    # --- paa_results ---
    op.create_table(
        "paa_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("paa_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("source_block", sa.String(50), nullable=False),
    )
    op.create_index("ix_pr_job_id", "paa_results", ["job_id"])

    # --- wordstat_batch_jobs ---
    op.create_table(
        "wordstat_batch_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_phrases", JSONB, nullable=False),
        sa.Column("phrase_count", sa.Integer, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("progress_pct", sa.Integer, nullable=True),
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
    op.create_index("ix_wbj_user_created", "wordstat_batch_jobs", ["user_id", "created_at"])

    # --- wordstat_batch_results ---
    op.create_table(
        "wordstat_batch_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("wordstat_batch_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("freq_exact", sa.Integer, nullable=True),
        sa.Column("freq_broad", sa.Integer, nullable=True),
    )
    op.create_index("ix_wbr_job_id", "wordstat_batch_results", ["job_id"])

    # --- wordstat_monthly_data ---
    op.create_table(
        "wordstat_monthly_data",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "result_id",
            sa.Integer,
            sa.ForeignKey("wordstat_batch_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("frequency", sa.Integer, nullable=False),
    )
    op.create_index("ix_wmd_result_id", "wordstat_monthly_data", ["result_id"])


def downgrade() -> None:
    op.drop_index("ix_wmd_result_id", table_name="wordstat_monthly_data")
    op.drop_table("wordstat_monthly_data")
    op.drop_index("ix_wbr_job_id", table_name="wordstat_batch_results")
    op.drop_table("wordstat_batch_results")
    op.drop_index("ix_wbj_user_created", table_name="wordstat_batch_jobs")
    op.drop_table("wordstat_batch_jobs")
    op.drop_index("ix_pr_job_id", table_name="paa_results")
    op.drop_table("paa_results")
    op.drop_index("ix_pj_user_created", table_name="paa_jobs")
    op.drop_table("paa_jobs")
    op.drop_index("ix_br_job_id", table_name="brief_results")
    op.drop_table("brief_results")
    op.drop_index("ix_bj_user_created", table_name="brief_jobs")
    op.drop_table("brief_jobs")
