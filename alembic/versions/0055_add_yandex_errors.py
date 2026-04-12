"""add yandex errors table and task type extensions

Revision ID: 0055
Revises: 0054
Create Date: 2026-04-12

Creates yandex_errors table, yandex_error_type and yandex_error_status enums,
extends tasktype enum with 3 new values (yandex_indexing, yandex_crawl,
yandex_sanction), and adds source_error_id FK to seo_tasks.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create new enum types
    op.execute(
        "DO $$ BEGIN CREATE TYPE yandex_error_type AS ENUM ('indexing', 'crawl', 'sanction'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE yandex_error_status AS ENUM ('open', 'ignored', 'resolved'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # 2. Create yandex_errors table
    # Use create_type=False — enum types were created above via op.execute
    error_type_col = postgresql.ENUM(
        "indexing", "crawl", "sanction", name="yandex_error_type", create_type=False
    )
    error_status_col = postgresql.ENUM(
        "open", "ignored", "resolved", name="yandex_error_status", create_type=False
    )
    op.create_table(
        "yandex_errors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("error_type", error_type_col, nullable=False),
        sa.Column("subtype", sa.String(100), nullable=False, server_default=""),
        sa.Column("url", sa.String(2000), nullable=False, server_default=""),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", error_status_col, nullable=False, server_default="open"),
    )
    op.create_index("ix_yandex_errors_site_id_type", "yandex_errors", ["site_id", "error_type"])
    op.create_index("ix_yandex_errors_site_id_status", "yandex_errors", ["site_id", "status"])
    op.create_unique_constraint(
        "uq_yandex_errors_identity", "yandex_errors", ["site_id", "error_type", "subtype", "url"]
    )

    # 3. Extend tasktype enum (NOT in transaction — Pitfall 1: ALTER TYPE cannot run inside a transaction)
    op.execute("COMMIT")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_indexing'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_crawl'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_sanction'")
    op.execute("BEGIN")

    # 4. Add source_error_id FK to seo_tasks
    op.add_column(
        "seo_tasks",
        sa.Column("source_error_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_seo_tasks_source_error_id",
        "seo_tasks",
        "yandex_errors",
        ["source_error_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_seo_tasks_source_error_id", "seo_tasks", type_="foreignkey")
    op.drop_column("seo_tasks", "source_error_id")
    op.drop_table("yandex_errors")
    op.execute("DROP TYPE IF EXISTS yandex_error_type")
    op.execute("DROP TYPE IF EXISTS yandex_error_status")
    # Note: Cannot remove enum values from tasktype — Postgres limitation.
    # Downgrade leaves yandex_indexing, yandex_crawl, yandex_sanction values in tasktype.
