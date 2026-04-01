"""add sites table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False, unique=True),
        sa.Column("wp_username", sa.String(255), nullable=False),
        sa.Column("encrypted_app_password", sa.Text(), nullable=False),
        sa.Column(
            "connection_status",
            sa.Enum("unknown", "connected", "failed", name="connectionstatus"),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sites_url", "sites", ["url"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_sites_url", table_name="sites")
    op.drop_table("sites")
    op.execute("DROP TYPE IF EXISTS connectionstatus")
