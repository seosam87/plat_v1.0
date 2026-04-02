"""add architecture tables and page fields

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-02
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    arch_role_enum = sa.Enum(
        "pillar", "service", "subservice", "article", "trigger",
        "authority", "link_accelerator", "unknown",
        name="architecturerole",
    )
    arch_role_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("pages", sa.Column("source", sa.String(20), nullable=False, server_default="crawl"))
    op.add_column("pages", sa.Column("architecture_role", arch_role_enum, nullable=False, server_default="unknown"))

    op.create_table(
        "sitemap_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("in_sitemap", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("in_crawl", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("site_id", "url", name="uq_sitemap_entry_site_url"),
    )

    op.create_table(
        "page_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crawl_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("target_url", sa.String(2000), nullable=False),
        sa.Column("anchor_text", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_page_links_site_crawl_source", "page_links", ["site_id", "crawl_job_id", "source_url"])


def downgrade() -> None:
    op.drop_table("page_links")
    op.drop_table("sitemap_entries")
    op.drop_column("pages", "architecture_role")
    op.drop_column("pages", "source")
    sa.Enum(name="architecturerole").drop(op.get_bind(), checkfirst=True)
