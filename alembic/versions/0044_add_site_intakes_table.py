"""Phase 21: add site_intakes table for site audit intake feature.

Revision ID: 0044
Revises: 0043
Create Date: 2026-04-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGENUM, JSON, UUID

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

# Pre-existing enum — created with checkfirst, so safe to run multiple times
intakestatus_enum = PGENUM("draft", "complete", name="intakestatus", create_type=False)


def upgrade() -> None:
    # Create IntakeStatus enum type safely
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE intakestatus AS ENUM ('draft', 'complete');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
        """
    )

    op.create_table(
        "site_intakes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "status",
            intakestatus_enum,
            nullable=False,
            server_default="draft",
        ),
        # JSON section data
        sa.Column("goals_data", JSON, nullable=True),
        sa.Column("technical_data", JSON, nullable=True),
        # Section completion flags
        sa.Column(
            "section_access",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "section_goals",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "section_analytics",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "section_technical",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "section_checklist",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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

    op.create_index("ix_site_intakes_site_id", "site_intakes", ["site_id"])


def downgrade() -> None:
    op.drop_index("ix_site_intakes_site_id", table_name="site_intakes")
    op.drop_table("site_intakes")

    op.execute("DROP TYPE IF EXISTS intakestatus")
