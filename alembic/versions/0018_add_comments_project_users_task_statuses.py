"""add project_comments, project_users M2M, extend task statuses

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Project comments
    op.create_table(
        "project_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_project_comments_project_id", "project_comments", ["project_id"])

    # Project users M2M (access control)
    op.create_table(
        "project_users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    )

    # Extend task status enum with 'assigned' and 'review'
    # PostgreSQL ALTER TYPE ... ADD VALUE
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'assigned' AFTER 'open'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'review' AFTER 'in_progress'")

    # Extend task type enum with new types
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'missing_page'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'cannibalization'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'manual'")


def downgrade() -> None:
    op.drop_table("project_users")
    op.drop_table("project_comments")
    # Note: PostgreSQL does not support removing enum values; they remain but are unused
