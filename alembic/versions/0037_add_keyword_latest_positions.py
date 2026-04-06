"""Add keyword_latest_positions flat table for fast analytical queries.

Revision ID: 0037
Revises: 0036
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "keyword_latest_positions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "keyword_id",
            UUID(as_uuid=True),
            sa.ForeignKey("keywords.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine", sa.String(20), nullable=False),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("position", sa.Integer, nullable=True),
        sa.Column("previous_position", sa.Integer, nullable=True),
        sa.Column("delta", sa.Integer, nullable=True),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("keyword_id", "engine", name="uq_klp_keyword_engine"),
    )
    op.create_index(
        "ix_klp_site_position",
        "keyword_latest_positions",
        ["site_id", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_klp_site_position", table_name="keyword_latest_positions")
    op.drop_table("keyword_latest_positions")
