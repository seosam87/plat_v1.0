"""Add canonical_url column to pages table.

Revision ID: 0035
Revises: 0034
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("canonical_url", sa.String(2000), nullable=True))


def downgrade() -> None:
    op.drop_column("pages", "canonical_url")
