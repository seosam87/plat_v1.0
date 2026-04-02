"""add priority column to seo_tasks

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE taskpriority AS ENUM ('p1', 'p2', 'p3', 'p4'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    priority_enum = postgresql.ENUM("p1", "p2", "p3", "p4", name="taskpriority", create_type=False)
    op.add_column("seo_tasks", sa.Column("priority", priority_enum, nullable=False, server_default="p3"))


def downgrade() -> None:
    op.drop_column("seo_tasks", "priority")
    sa.Enum(name="taskpriority").drop(op.get_bind(), checkfirst=True)
