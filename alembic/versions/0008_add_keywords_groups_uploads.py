"""add keyword_groups, keywords, file_uploads tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # keyword_groups (must be created before keywords due to FK)
    op.create_table(
        "keyword_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("keyword_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_keyword_groups_site_id", "keyword_groups", ["site_id"])

    # keywords
    op.create_table(
        "keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("keyword_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phrase", sa.String(1000), nullable=False),
        sa.Column("frequency", sa.Integer, nullable=True),
        sa.Column("region", sa.String(255), nullable=True),
        sa.Column(
            "engine",
            sa.Enum("yandex", "google", name="searchengine"),
            nullable=True,
        ),
        sa.Column("target_url", sa.String(2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_keywords_site_id", "keywords", ["site_id"])
    op.create_index("ix_keywords_group_id", "keywords", ["group_id"])
    op.create_index("ix_keywords_phrase", "keywords", ["phrase"])

    # file_uploads
    op.create_table(
        "file_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_type",
            sa.Enum(
                "topvisor", "key_collector", "screaming_frog", "yandex_metrika",
                name="filetype",
            ),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("stored_path", sa.String(1000), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "done", "failed", name="uploadstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("row_count", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_file_uploads_site_id", "file_uploads", ["site_id"])


def downgrade() -> None:
    op.drop_table("file_uploads")
    op.drop_table("keywords")
    op.drop_table("keyword_groups")
    op.execute("DROP TYPE IF EXISTS filetype")
    op.execute("DROP TYPE IF EXISTS uploadstatus")
    op.execute("DROP TYPE IF EXISTS searchengine")
