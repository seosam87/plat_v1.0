"""add report_schedules table

Revision ID: 9c65e7d94183
Revises: 0035
Create Date: 2026-04-05 18:16:13.638286

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9c65e7d94183'
down_revision: Union[str, None] = '0035'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'report_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('morning_digest_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('morning_hour', sa.Integer(), nullable=False, server_default='9'),
        sa.Column('morning_minute', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('weekly_report_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('weekly_day_of_week', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('weekly_hour', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('weekly_minute', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('smtp_to', sa.String(length=320), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('report_schedules')
