"""Phase 23: add generated_documents table for document generation feature.

Revision ID: 0046
Revises: 0045
Create Date: 2026-04-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None

# Reuse existing templatetype enum from migration 0045 — create_type=False
# prevents "type templatetype already exists" error.
templatetype_enum = sa.Enum(
    "proposal", "audit_report", "brief",
    name="templatetype", create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "generated_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id", UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_id", UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "template_id", UUID(as_uuid=True),
            sa.ForeignKey("proposal_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_type", templatetype_enum, nullable=False),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False, server_default="document.pdf"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_gd_client_created", "generated_documents", ["client_id", "created_at"])
    op.create_index("ix_gd_template_id", "generated_documents", ["template_id"])


def downgrade() -> None:
    op.drop_index("ix_gd_template_id", table_name="generated_documents")
    op.drop_index("ix_gd_client_created", table_name="generated_documents")
    op.drop_table("generated_documents")
    # Do NOT drop templatetype enum — it belongs to migration 0045
