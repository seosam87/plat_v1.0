"""add analytics workspace tables

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-02
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE sessionstatus AS ENUM ('draft', 'positions_checked', 'serp_parsed', "
        "'competitor_found', 'compared', 'brief_created', 'completed'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    session_status_enum = postgresql.ENUM(
        "draft", "positions_checked", "serp_parsed", "competitor_found",
        "compared", "brief_created", "completed",
        name="sessionstatus", create_type=False,
    )

    # analysis_sessions
    op.create_table(
        "analysis_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", session_status_enum, nullable=False, server_default="draft"),
        sa.Column("keyword_ids", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("filters_applied", postgresql.JSON(), nullable=True),
        sa.Column("keyword_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("competitor_domain", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_analysis_sessions_site", "analysis_sessions", ["site_id"])

    # session_serp_results
    op.create_table(
        "session_serp_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keyword_phrase", sa.String(1000), nullable=False),
        sa.Column("results_json", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("features", postgresql.JSON(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "keyword_id", name="uq_serp_result_session_keyword"),
    )

    # competitor_page_data
    op.create_table(
        "competitor_page_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("domain", sa.String(500), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("h1", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("has_schema", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_toc", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("internal_link_count", sa.Integer(), nullable=True),
        sa.Column("headings_json", postgresql.JSON(), nullable=True),
        sa.Column("crawl_mode", sa.String(20), nullable=False, server_default="light"),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_competitor_page_data_session", "competitor_page_data", ["session_id"])

    # content_briefs
    op.create_table(
        "content_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("target_url", sa.String(2000), nullable=True),
        sa.Column("recommended_title", sa.Text(), nullable=True),
        sa.Column("recommended_h1", sa.Text(), nullable=True),
        sa.Column("recommended_meta", sa.Text(), nullable=True),
        sa.Column("keywords_json", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("headings_json", postgresql.JSON(), nullable=True),
        sa.Column("structure_notes", sa.Text(), nullable=True),
        sa.Column("competitor_data_json", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_content_briefs_site", "content_briefs", ["site_id"])


def downgrade() -> None:
    op.drop_table("content_briefs")
    op.drop_table("competitor_page_data")
    op.drop_table("session_serp_results")
    op.drop_table("analysis_sessions")
    sa.Enum(name="sessionstatus").drop(op.get_bind(), checkfirst=True)
