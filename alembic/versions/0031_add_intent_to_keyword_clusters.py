"""add intent column to keyword_clusters

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE clusterintent AS ENUM ('unknown', 'commercial', 'informational', 'navigational'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    intent_enum = postgresql.ENUM(
        "unknown", "commercial", "informational", "navigational",
        name="clusterintent", create_type=False,
    )
    op.add_column("keyword_clusters", sa.Column("intent", intent_enum, nullable=False, server_default="unknown"))


def downgrade() -> None:
    op.drop_column("keyword_clusters", "intent")
    sa.Enum(name="clusterintent").drop(op.get_bind(), checkfirst=True)
