"""add cannibalization resolver

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-02
"""
import uuid
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    res_type = sa.Enum("merge_content", "set_canonical", "redirect_301", "split_keywords", name="resolutiontype")
    res_type.create(op.get_bind(), checkfirst=True)
    res_status = sa.Enum("proposed", "in_progress", "resolved", "rejected", name="resolutionstatus")
    res_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "cannibalization_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword_phrase", sa.String(1000), nullable=False),
        sa.Column("competing_urls", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("resolution_type", res_type, nullable=False),
        sa.Column("primary_url", sa.String(2000), nullable=True),
        sa.Column("action_plan", sa.Text(), nullable=False),
        sa.Column("status", res_status, nullable=False, server_default="proposed"),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seo_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cannibal_res_site", "cannibalization_resolutions", ["site_id"])


def downgrade() -> None:
    op.drop_table("cannibalization_resolutions")
    sa.Enum(name="resolutionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="resolutiontype").drop(op.get_bind(), checkfirst=True)
