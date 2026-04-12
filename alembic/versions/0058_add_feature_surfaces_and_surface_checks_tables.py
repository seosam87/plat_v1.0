"""add feature_surfaces and surface_checks tables

Revision ID: 0058
Revises: 0057
Create Date: 2026-04-12

Creates 2 tables for Phase 999.10 QA Surface Tracker:
feature_surfaces (parent, one per user flow) and
surface_checks (child, one per surface: desktop, mobile, telegram).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw DDL for enum creation — avoids SQLAlchemy double-create problem
    op.execute(
        "CREATE TYPE surface AS ENUM ('desktop', 'mobile', 'telegram')"
    )
    op.execute(
        "CREATE TYPE checkstatus AS ENUM ('not_tested', 'passed', 'failed', 'needs_retest')"
    )

    # Create feature_surfaces table (no enums here)
    op.create_table(
        "feature_surfaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("retest_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.UniqueConstraint("slug", name="uq_feature_surfaces_slug"),
    )

    # Create surface_checks using postgresql.ENUM(create_type=False)
    # to reference already-created enum types
    op.create_table(
        "surface_checks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_surfaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "surface",
            postgresql.ENUM(
                "desktop", "mobile", "telegram",
                name="surface",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "not_tested", "passed", "failed", "needs_retest",
                name="checkstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="not_tested",
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("tested_by", sa.String(100), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("feature_id", "surface", name="uq_feature_surface"),
    )

    # Create indexes
    op.create_index(
        "ix_surface_checks_feature_id", "surface_checks", ["feature_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_surface_checks_feature_id", table_name="surface_checks")
    op.drop_table("surface_checks")
    op.drop_table("feature_surfaces")
    op.execute("DROP TYPE IF EXISTS checkstatus")
    op.execute("DROP TYPE IF EXISTS surface")
