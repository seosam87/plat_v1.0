"""add ad_traffic table

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_traffic",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("traffic_date", sa.Date, nullable=False),
        sa.Column("sessions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("conversions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ad_traffic_site_date", "ad_traffic", ["site_id", "traffic_date"])


def downgrade() -> None:
    op.drop_table("ad_traffic")
