"""add wp_content_jobs table and seo_plugin field on sites

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wp_content_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("wp_post_id", sa.Integer, nullable=True),
        sa.Column("page_url", sa.String(2000), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "awaiting_approval", "approved",
                "pushed", "rolled_back", "failed",
                name="jobstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("original_content", sa.Text, nullable=True),
        sa.Column("processed_content", sa.Text, nullable=True),
        sa.Column("diff_json", postgresql.JSON, nullable=True),
        sa.Column("rollback_payload", postgresql.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_wp_content_jobs_site_id", "wp_content_jobs", ["site_id"])
    op.create_index("ix_wp_content_jobs_status", "wp_content_jobs", ["status"])

    # Add seo_plugin field to sites (yoast / rankmath / unknown)
    op.add_column(
        "sites",
        sa.Column("seo_plugin", sa.String(50), nullable=True, server_default="unknown"),
    )


def downgrade() -> None:
    op.drop_column("sites", "seo_plugin")
    op.drop_table("wp_content_jobs")
    op.execute("DROP TYPE IF EXISTS jobstatus")
