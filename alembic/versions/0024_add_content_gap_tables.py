"""add content gap tables

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-02
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE proposalstatus AS ENUM ('pending', 'approved', 'rejected'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    proposal_status_enum = postgresql.ENUM("pending", "approved", "rejected", name="proposalstatus", create_type=False)

    op.create_table(
        "gap_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "gap_keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("competitor_domain", sa.String(500), nullable=False),
        sa.Column("phrase", sa.String(1000), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("competitor_position", sa.Integer(), nullable=True),
        sa.Column("our_position", sa.Integer(), nullable=True),
        sa.Column("potential_score", sa.Float(), nullable=True),
        sa.Column("gap_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gap_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="serp"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("site_id", "competitor_domain", "phrase", name="uq_gap_keyword_site_comp_phrase"),
    )
    op.create_index("ix_gap_keywords_site", "gap_keywords", ["site_id"])

    op.create_table(
        "gap_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gap_keyword_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gap_keywords.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("target_phrase", sa.String(1000), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("potential_score", sa.Float(), nullable=True),
        sa.Column("status", proposal_status_enum, nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("content_plan_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_plan_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_gap_proposals_site", "gap_proposals", ["site_id"])


def downgrade() -> None:
    op.drop_table("gap_proposals")
    op.drop_table("gap_keywords")
    op.drop_table("gap_groups")
    sa.Enum(name="proposalstatus").drop(op.get_bind(), checkfirst=True)
