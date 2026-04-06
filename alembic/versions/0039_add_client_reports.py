"""Add client_reports table for storing PDF instruction reports per site.

Revision ID: 0039
Revises: 0038
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("blocks_config", sa.JSON, nullable=False),
        sa.Column("pdf_data", sa.LargeBinary, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_cr_site_created",
        "client_reports",
        ["site_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cr_site_created", table_name="client_reports")
    op.drop_table("client_reports")
