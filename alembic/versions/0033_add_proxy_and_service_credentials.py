"""add proxies, service_credentials tables and sites.yandex_region

Revision ID: 0033
Revises: 0032
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_credentials",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_name", sa.String(100), nullable=False, unique=True),
        sa.Column("credential_data", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "proxies",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.String(500), nullable=False, unique=True),
        sa.Column(
            "proxy_type",
            sa.String(20),
            nullable=False,
            server_default="http",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="unchecked",
        ),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "sites",
        sa.Column(
            "yandex_region",
            sa.Integer(),
            nullable=True,
            server_default="213",
        ),
    )


def downgrade() -> None:
    op.drop_column("sites", "yandex_region")
    op.drop_table("proxies")
    op.drop_table("service_credentials")
