"""add metrika tables and site metrika fields

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Metrika fields to sites table
    op.add_column("sites", sa.Column("metrika_counter_id", sa.String(50), nullable=True))
    op.add_column("sites", sa.Column("metrika_token", sa.Text(), nullable=True))

    # Create metrika_traffic_daily table
    op.create_table(
        "metrika_traffic_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("traffic_date", sa.Date, nullable=False),
        sa.Column("visits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("users", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bounce_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("page_depth", sa.Numeric(5, 2), nullable=True),
        sa.Column("avg_duration_seconds", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "traffic_date", name="uq_metrika_daily_site_date"),
    )
    op.create_index(
        "ix_metrika_traffic_daily_site_date",
        "metrika_traffic_daily",
        ["site_id", "traffic_date"],
    )

    # Create metrika_traffic_pages table
    op.create_table(
        "metrika_traffic_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("page_url", sa.Text, nullable=False),
        sa.Column("visits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bounce_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("page_depth", sa.Numeric(5, 2), nullable=True),
        sa.Column("avg_duration_seconds", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "site_id", "period_start", "period_end", "page_url",
            name="uq_metrika_pages_site_period_url",
        ),
    )
    op.create_index(
        "ix_metrika_traffic_pages_site_period",
        "metrika_traffic_pages",
        ["site_id", "period_start", "period_end"],
    )

    # Create metrika_events table
    op.create_table(
        "metrika_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("color", sa.String(20), nullable=False, server_default="#6b7280"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_metrika_events_site_date",
        "metrika_events",
        ["site_id", "event_date"],
    )


def downgrade() -> None:
    op.drop_table("metrika_events")
    op.drop_table("metrika_traffic_pages")
    op.drop_table("metrika_traffic_daily")
    op.drop_column("sites", "metrika_token")
    op.drop_column("sites", "metrika_counter_id")
