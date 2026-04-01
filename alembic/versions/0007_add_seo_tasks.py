"""add seo_tasks table for auto-generated crawl issues

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seo_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "crawl_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "task_type",
            sa.Enum("page_404", "lost_indexation", name="tasktype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "resolved", name="taskstatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_seo_tasks_site_id", "seo_tasks", ["site_id"])
    op.create_index("ix_seo_tasks_status", "seo_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_seo_tasks_status")
    op.drop_index("ix_seo_tasks_site_id")
    op.drop_table("seo_tasks")
    op.execute("DROP TYPE IF EXISTS tasktype")
    op.execute("DROP TYPE IF EXISTS taskstatus")
