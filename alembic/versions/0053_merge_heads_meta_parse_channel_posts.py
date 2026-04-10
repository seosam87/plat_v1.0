"""merge heads: meta_parse + channel_posts

Revision ID: 0053
Revises: 0048, 0052
Create Date: 2026-04-10 23:03:37.851525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0053'
down_revision: Union[str, None] = ('0048', '0052')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
