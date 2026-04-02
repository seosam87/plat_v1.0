"""add platform_issues table

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE issuestatus AS ENUM ('open', 'in_progress', 'resolved'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    issue_status = postgresql.ENUM("open", "in_progress", "resolved", name="issuestatus", create_type=False)

    op.create_table(
        "platform_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", issue_status, nullable=False, server_default="open"),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("platform_issues")
    sa.Enum(name="issuestatus").drop(op.get_bind(), checkfirst=True)
