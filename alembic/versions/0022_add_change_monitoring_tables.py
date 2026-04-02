"""add change monitoring tables

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-02
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums via raw SQL to avoid SQLAlchemy auto-create conflicts
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE changetype AS ENUM ('page_404', 'noindex_added', 'schema_removed', "
        "'title_changed', 'h1_changed', 'canonical_changed', "
        "'meta_description_changed', 'content_changed', 'new_page'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    changetype_enum = postgresql.ENUM(
        "page_404", "noindex_added", "schema_removed",
        "title_changed", "h1_changed", "canonical_changed",
        "meta_description_changed", "content_changed", "new_page",
        name="changetype", create_type=False,
    )

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE alertseverity AS ENUM ('error', 'warning', 'info'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    alertseverity_enum = postgresql.ENUM("error", "warning", "info", name="alertseverity", create_type=False)

    # change_alert_rules
    op.create_table(
        "change_alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("change_type", changetype_enum, unique=True, nullable=False),
        sa.Column("severity", alertseverity_enum, nullable=False, server_default="warning"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # change_alerts
    op.create_table(
        "change_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crawl_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_type", changetype_enum, nullable=False),
        sa.Column("severity", alertseverity_enum, nullable=False),
        sa.Column("page_url", sa.String(2000), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_change_alerts_site_crawl", "change_alerts", ["site_id", "crawl_job_id"])
    op.create_index("ix_change_alerts_site_created", "change_alerts", ["site_id", "created_at"])

    # digest_schedules
    op.create_table(
        "digest_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("day_of_week", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("hour", sa.Integer(), nullable=False, server_default=sa.text("9")),
        sa.Column("minute", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cron_expression", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Seed default alert rules
    rules_table = sa.table(
        "change_alert_rules",
        sa.column("id", postgresql.UUID),
        sa.column("change_type", sa.String),
        sa.column("severity", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("description", sa.String),
    )
    op.bulk_insert(rules_table, [
        {"id": str(uuid.uuid4()), "change_type": "page_404", "severity": "error", "is_active": True, "description": "Страница вернула 404"},
        {"id": str(uuid.uuid4()), "change_type": "noindex_added", "severity": "error", "is_active": True, "description": "Появился noindex на странице"},
        {"id": str(uuid.uuid4()), "change_type": "schema_removed", "severity": "error", "is_active": True, "description": "Удалена schema.org разметка"},
        {"id": str(uuid.uuid4()), "change_type": "title_changed", "severity": "warning", "is_active": True, "description": "Изменился title страницы"},
        {"id": str(uuid.uuid4()), "change_type": "h1_changed", "severity": "warning", "is_active": True, "description": "Изменился H1 страницы"},
        {"id": str(uuid.uuid4()), "change_type": "canonical_changed", "severity": "warning", "is_active": True, "description": "Изменился canonical URL"},
        {"id": str(uuid.uuid4()), "change_type": "meta_description_changed", "severity": "warning", "is_active": True, "description": "Изменилось meta description"},
        {"id": str(uuid.uuid4()), "change_type": "content_changed", "severity": "info", "is_active": True, "description": "Изменился контент страницы"},
        {"id": str(uuid.uuid4()), "change_type": "new_page", "severity": "info", "is_active": True, "description": "Обнаружена новая страница"},
    ])


def downgrade() -> None:
    op.drop_table("digest_schedules")
    op.drop_table("change_alerts")
    op.drop_table("change_alert_rules")
    sa.Enum(name="alertseverity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="changetype").drop(op.get_bind(), checkfirst=True)
