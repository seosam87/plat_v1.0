"""add page snapshots table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "crawl_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_data",
            postgresql.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("diff_data", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_page_snapshots_page_id", "page_snapshots", ["page_id"])
    op.create_index("ix_page_snapshots_crawl_job_id", "page_snapshots", ["crawl_job_id"])


def downgrade() -> None:
    op.drop_index("ix_page_snapshots_crawl_job_id", table_name="page_snapshots")
    op.drop_index("ix_page_snapshots_page_id", table_name="page_snapshots")
    op.drop_table("page_snapshots")
