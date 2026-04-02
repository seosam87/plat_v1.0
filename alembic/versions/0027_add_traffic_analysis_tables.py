"""add traffic analysis tables

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-02
"""
import uuid
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE visitsource AS ENUM ('organic', 'direct', 'referral', 'bot_suspected', 'injection_suspected'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    visit_source = postgresql.ENUM("organic", "direct", "referral", "bot_suspected", "injection_suspected", name="visitsource", create_type=False)

    op.create_table(
        "traffic_analysis_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="metrika"),
        sa.Column("total_visits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("bot_visits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("organic_visits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("anomaly_detected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "traffic_visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("traffic_analysis_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_url", sa.String(2000), nullable=False),
        sa.Column("source", visit_source, nullable=False, server_default="organic"),
        sa.Column("referer", sa.String(2000), nullable=True),
        sa.Column("user_agent", sa.String(1000), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("geo_country", sa.String(100), nullable=True),
        sa.Column("geo_city", sa.String(100), nullable=True),
        sa.Column("device_type", sa.String(20), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("bot_reason", sa.String(255), nullable=True),
    )
    op.create_index("ix_traffic_visits_session", "traffic_visits", ["session_id"])

    op.create_table(
        "bot_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("pattern_type", sa.String(20), nullable=False),
        sa.Column("pattern_value", sa.String(500), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # Seed common bot patterns
    patterns_table = sa.table("bot_patterns",
        sa.column("id", postgresql.UUID), sa.column("pattern_type", sa.String),
        sa.column("pattern_value", sa.String), sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean))
    op.bulk_insert(patterns_table, [
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "Googlebot", "description": "Google crawler", "is_active": True},
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "YandexBot", "description": "Yandex crawler", "is_active": True},
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "bingbot", "description": "Bing crawler", "is_active": True},
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "AhrefsBot", "description": "Ahrefs crawler", "is_active": True},
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "SemrushBot", "description": "Semrush crawler", "is_active": True},
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "MJ12bot", "description": "Majestic crawler", "is_active": True},
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "DotBot", "description": "DotBot crawler", "is_active": True},
        {"id": str(uuid.uuid4()), "pattern_type": "ua", "pattern_value": "PetalBot", "description": "Huawei crawler", "is_active": True},
    ])


def downgrade() -> None:
    op.drop_table("bot_patterns")
    op.drop_table("traffic_visits")
    op.drop_table("traffic_analysis_sessions")
    sa.Enum(name="visitsource").drop(op.get_bind(), checkfirst=True)
