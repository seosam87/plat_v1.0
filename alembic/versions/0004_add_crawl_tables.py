"""add crawl tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawl_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "done", "failed", name="crawljobstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pages_crawled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_table(
        "pages",
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
            sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("h1", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("internal_link_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "page_type",
            sa.Enum(
                "category", "article", "landing", "product", "unknown",
                name="pagetype",
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("has_toc", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_schema", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_noindex", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "crawled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("crawl_job_id", "url", name="uq_pages_crawl_job_url"),
    )


def downgrade() -> None:
    op.drop_table("pages")
    op.execute("DROP TYPE IF EXISTS pagetype")
    op.drop_table("crawl_jobs")
    op.execute("DROP TYPE IF EXISTS crawljobstatus")
