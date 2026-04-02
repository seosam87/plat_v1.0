"""add content audit tables and fields

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-02
"""
import json
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create contenttype enum
    content_type_enum = sa.Enum(
        "informational", "commercial", "unknown", name="contenttype"
    )
    content_type_enum.create(op.get_bind(), checkfirst=True)

    # Add content_type to pages
    op.add_column(
        "pages",
        sa.Column(
            "content_type", content_type_enum, nullable=False, server_default="unknown"
        ),
    )

    # Add cta_template_html to sites
    op.add_column(
        "sites", sa.Column("cta_template_html", sa.Text(), nullable=True)
    )

    # Create audit_check_definitions table
    op.create_table(
        "audit_check_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        ),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "applies_to", content_type_enum, nullable=False, server_default="unknown"
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "severity", sa.String(20), nullable=False, server_default="warning"
        ),
        sa.Column(
            "auto_fixable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("fix_action", sa.String(50), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create audit_results table
    op.create_table(
        "audit_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        ),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_url", sa.String(2000), nullable=False),
        sa.Column("check_code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "wp_content_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wp_content_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "site_id", "page_url", "check_code", name="uq_audit_result_site_page_check"
        ),
    )
    op.create_index(
        "ix_audit_results_site_url", "audit_results", ["site_id", "page_url"]
    )

    # Create schema_templates table
    op.create_table(
        "schema_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        ),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("schema_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("template_json", sa.Text(), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "site_id", "schema_type", name="uq_schema_template_site_type"
        ),
    )

    # Seed default check definitions
    checks_table = sa.table(
        "audit_check_definitions",
        sa.column("id", postgresql.UUID),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("applies_to", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("severity", sa.String),
        sa.column("auto_fixable", sa.Boolean),
        sa.column("fix_action", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        checks_table,
        [
            {
                "id": str(uuid.uuid4()),
                "code": "toc_present",
                "name": "Наличие TOC",
                "description": "Проверка наличия оглавления (Table of Contents)",
                "applies_to": "informational",
                "is_active": True,
                "severity": "warning",
                "auto_fixable": True,
                "fix_action": "inject_toc",
                "sort_order": 10,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "schema_present",
                "name": "Schema.org разметка",
                "description": "Проверка наличия JSON-LD schema.org",
                "applies_to": "unknown",
                "is_active": True,
                "severity": "warning",
                "auto_fixable": True,
                "fix_action": "inject_schema",
                "sort_order": 20,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "author_block",
                "name": "Блок автора",
                "description": "Проверка наличия блока автора на странице",
                "applies_to": "informational",
                "is_active": True,
                "severity": "warning",
                "auto_fixable": False,
                "fix_action": None,
                "sort_order": 30,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "related_posts",
                "name": "Похожие статьи",
                "description": "Проверка наличия блока рекомендованных/похожих статей",
                "applies_to": "informational",
                "is_active": True,
                "severity": "warning",
                "auto_fixable": False,
                "fix_action": None,
                "sort_order": 40,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "cta_present",
                "name": "CTA-блок",
                "description": "Проверка наличия призыва к действию (Call to Action)",
                "applies_to": "commercial",
                "is_active": True,
                "severity": "error",
                "auto_fixable": True,
                "fix_action": "inject_cta",
                "sort_order": 50,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "internal_links",
                "name": "Внутренние ссылки",
                "description": "Проверка наличия внутренних ссылок (минимум 1)",
                "applies_to": "unknown",
                "is_active": True,
                "severity": "warning",
                "auto_fixable": True,
                "fix_action": "inject_links",
                "sort_order": 60,
            },
            {
                "id": str(uuid.uuid4()),
                "code": "noindex_check",
                "name": "Отсутствие noindex",
                "description": "Страница не должна иметь noindex (если не намеренно)",
                "applies_to": "unknown",
                "is_active": True,
                "severity": "error",
                "auto_fixable": False,
                "fix_action": None,
                "sort_order": 70,
            },
        ],
    )

    # Seed default schema templates
    templates_table = sa.table(
        "schema_templates",
        sa.column("id", postgresql.UUID),
        sa.column("site_id", postgresql.UUID),
        sa.column("schema_type", sa.String),
        sa.column("name", sa.String),
        sa.column("template_json", sa.Text),
        sa.column("is_default", sa.Boolean),
    )
    op.bulk_insert(
        templates_table,
        [
            {
                "id": str(uuid.uuid4()),
                "site_id": None,
                "schema_type": "Article",
                "name": "Article (по умолчанию)",
                "template_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@type": "Article",
                        "headline": "{{title}}",
                        "url": "{{url}}",
                        "author": {"@type": "Person", "name": "{{author}}"},
                        "datePublished": "{{date_published}}",
                    },
                    ensure_ascii=False,
                ),
                "is_default": True,
            },
            {
                "id": str(uuid.uuid4()),
                "site_id": None,
                "schema_type": "Service",
                "name": "Service (по умолчанию)",
                "template_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@type": "Service",
                        "name": "{{title}}",
                        "url": "{{url}}",
                        "description": "{{description}}",
                        "provider": {
                            "@type": "Organization",
                            "name": "{{site_name}}",
                        },
                    },
                    ensure_ascii=False,
                ),
                "is_default": True,
            },
            {
                "id": str(uuid.uuid4()),
                "site_id": None,
                "schema_type": "Product",
                "name": "Product (по умолчанию)",
                "template_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "name": "{{title}}",
                        "url": "{{url}}",
                        "description": "{{description}}",
                    },
                    ensure_ascii=False,
                ),
                "is_default": True,
            },
            {
                "id": str(uuid.uuid4()),
                "site_id": None,
                "schema_type": "LocalBusiness",
                "name": "LocalBusiness (по умолчанию)",
                "template_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@type": "LocalBusiness",
                        "name": "{{site_name}}",
                        "url": "{{url}}",
                        "description": "{{description}}",
                    },
                    ensure_ascii=False,
                ),
                "is_default": True,
            },
            {
                "id": str(uuid.uuid4()),
                "site_id": None,
                "schema_type": "FAQ",
                "name": "FAQ (по умолчанию)",
                "template_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@type": "FAQPage",
                        "mainEntity": [
                            {
                                "@type": "Question",
                                "name": "{{question_1}}",
                                "acceptedAnswer": {
                                    "@type": "Answer",
                                    "text": "{{answer_1}}",
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                "is_default": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("schema_templates")
    op.drop_table("audit_results")
    op.drop_table("audit_check_definitions")
    op.drop_column("sites", "cta_template_html")
    op.drop_column("pages", "content_type")
    content_type_enum = sa.Enum(
        "informational", "commercial", "unknown", name="contenttype"
    )
    content_type_enum.drop(op.get_bind(), checkfirst=True)
