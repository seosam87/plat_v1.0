"""make wp credentials optional on sites

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-02
"""
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("sites", "wp_username", nullable=True)
    op.alter_column("sites", "encrypted_app_password", nullable=True)


def downgrade() -> None:
    op.alter_column("sites", "wp_username", nullable=False)
    op.alter_column("sites", "encrypted_app_password", nullable=False)
