"""add site_groups, user_site_groups M2M, site_group_id FK on sites

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "user_site_groups",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("site_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("site_groups.id", ondelete="CASCADE"), primary_key=True),
    )

    op.add_column(
        "sites",
        sa.Column("site_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("site_groups.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_sites_site_group_id", "sites", ["site_group_id"])


def downgrade() -> None:
    op.drop_index("ix_sites_site_group_id")
    op.drop_column("sites", "site_group_id")
    op.drop_table("user_site_groups")
    op.drop_table("site_groups")
