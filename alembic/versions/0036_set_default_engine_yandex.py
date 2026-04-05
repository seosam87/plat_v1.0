"""Set default engine to yandex for all keywords missing engine value.

Revision ID: 0036
Revises: 0035
"""
from alembic import op

revision = "0036"
down_revision = "9c65e7d94183"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE keywords SET engine = 'yandex' WHERE engine IS NULL")


def downgrade() -> None:
    pass  # Cannot reliably revert — we don't know which were originally NULL
