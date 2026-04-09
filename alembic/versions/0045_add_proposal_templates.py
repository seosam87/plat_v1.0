"""Phase 22: add proposal_templates table for proposal templates feature.

Revision ID: 0045
Revises: 0044
Create Date: 2026-04-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGENUM, UUID

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

# Pre-existing enum — create_type=False so PGENUM doesn't try to CREATE TYPE again
templatetype_enum = PGENUM(
    "proposal", "audit_report", "brief", name="templatetype", create_type=False
)


def upgrade() -> None:
    # Create TemplateType enum type safely
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE templatetype AS ENUM ('proposal', 'audit_report', 'brief');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
        """
    )

    op.create_table(
        "proposal_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "template_type",
            templatetype_enum,
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "body",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_proposal_templates_type",
        "proposal_templates",
        ["template_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_proposal_templates_type", table_name="proposal_templates")
    op.drop_table("proposal_templates")

    op.execute("DROP TYPE IF EXISTS templatetype")
