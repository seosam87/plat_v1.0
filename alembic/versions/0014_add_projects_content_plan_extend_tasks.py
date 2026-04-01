"""add projects, content_plan_items; extend seo_tasks with project_id/assignee/due_date

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("active", "paused", "completed", "archived", name="projectstatus"), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_site_id", "projects", ["site_id"])

    # Content plan items
    op.create_table(
        "content_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("keywords.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proposed_title", sa.String(500), nullable=False),
        sa.Column("status", sa.Enum("idea", "planned", "writing", "review", "published", name="contentstatus"), nullable=False, server_default="idea"),
        sa.Column("planned_date", sa.Date, nullable=True),
        sa.Column("wp_post_id", sa.Integer, nullable=True),
        sa.Column("wp_post_url", sa.String(2000), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_content_plan_items_project_id", "content_plan_items", ["project_id"])

    # Extend seo_tasks
    op.add_column("seo_tasks", sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True))
    op.add_column("seo_tasks", sa.Column("assignee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("seo_tasks", sa.Column("due_date", sa.Date, nullable=True))
    op.create_index("ix_seo_tasks_project_id", "seo_tasks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_seo_tasks_project_id")
    op.drop_column("seo_tasks", "due_date")
    op.drop_column("seo_tasks", "assignee_id")
    op.drop_column("seo_tasks", "project_id")
    op.drop_table("content_plan_items")
    op.drop_table("projects")
    op.execute("DROP TYPE IF EXISTS projectstatus")
    op.execute("DROP TYPE IF EXISTS contentstatus")
