"""Add error_impact_scores table for pre-computed audit error impact scores.

Revision ID: 0038
Revises: 0037
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "error_impact_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_url", sa.String(2000), nullable=False),
        sa.Column("check_code", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("severity_weight", sa.Integer, nullable=False),
        sa.Column("monthly_traffic", sa.Integer, nullable=False, server_default="0"),
        sa.Column("impact_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "site_id", "page_url", "check_code", name="uq_eis_site_page_check"
        ),
    )
    op.create_index(
        "ix_eis_site_impact",
        "error_impact_scores",
        ["site_id", "impact_score"],
    )


def downgrade() -> None:
    op.drop_index("ix_eis_site_impact", table_name="error_impact_scores")
    op.drop_table("error_impact_scores")
