"""Add competitors table.

Revision ID: 0034
Revises: 0033
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competitors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(500), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_competitors_site_id", "competitors", ["site_id"])


def downgrade() -> None:
    op.drop_index("ix_competitors_site_id")
    op.drop_table("competitors")
