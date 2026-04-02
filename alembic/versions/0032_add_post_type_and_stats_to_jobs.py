"""add post_type, heading_count, has_toc to wp_content_jobs

Revision ID: 0032
Revises: 0031
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wp_content_jobs", sa.Column("post_type", sa.String(100), nullable=True, server_default="posts"))
    op.add_column("wp_content_jobs", sa.Column("heading_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("wp_content_jobs", sa.Column("has_toc", sa.Boolean(), nullable=True, server_default="false"))


def downgrade() -> None:
    op.drop_column("wp_content_jobs", "has_toc")
    op.drop_column("wp_content_jobs", "heading_count")
    op.drop_column("wp_content_jobs", "post_type")
