"""Phase 16: add geo_score column, llm tables, and geo check definitions.

Revision ID: 0041
Revises: 0040
Create Date: 2026-04-08
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add geo_score to pages
    op.add_column("pages", sa.Column("geo_score", sa.Integer(), nullable=True))

    # 2. Add anthropic_api_key_encrypted to users (per D-02)
    op.add_column(
        "users",
        sa.Column("anthropic_api_key_encrypted", sa.Text(), nullable=True),
    )

    # 3. Add weight column to audit_check_definitions (needed for geo_* rows)
    op.add_column(
        "audit_check_definitions",
        sa.Column("weight", sa.Integer(), nullable=True),
    )

    # 4. Create llm_brief_jobs table (per D-04)
    op.create_table(
        "llm_brief_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "brief_id",
            UUID(as_uuid=True),
            sa.ForeignKey("content_briefs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("output_json", JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # 5. Create llm_usage table (per D-06)
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "brief_id",
            UUID(as_uuid=True),
            sa.ForeignKey("content_briefs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            sa.BigInteger(),
            sa.ForeignKey("llm_brief_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column(
            "input_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "output_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # 6. Index on llm_usage(user_id, created_at DESC) for usage queries
    op.create_index(
        "ix_llm_usage_user_created",
        "llm_usage",
        ["user_id", sa.text("created_at DESC")],
    )

    # 7. Seed 9 geo_* rows into audit_check_definitions
    # Uses op.execute with raw SQL to avoid ORM dependency on content enums
    geo_checks = [
        (
            "geo_faq_schema",
            "FAQPage schema",
            "На странице присутствует JSON-LD разметка FAQPage для ответов на частые вопросы.",
            15,
        ),
        (
            "geo_article_author",
            "Article + Author schema",
            "На странице присутствует схема Article с указанием автора (Person/Author) для атрибуции контента.",
            15,
        ),
        (
            "geo_breadcrumbs",
            "BreadcrumbList schema",
            "На странице присутствует JSON-LD разметка BreadcrumbList для навигационных хлебных крошек.",
            10,
        ),
        (
            "geo_answer_first",
            "Прямой ответ в первом абзаце",
            "Первый абзац после H1 содержит не более 60 слов и включает глагол — прямой ответ на запрос.",
            15,
        ),
        (
            "geo_update_date",
            "Дата обновления",
            "На странице присутствует тег time[datetime] или поле dateModified в JSON-LD с датой обновления контента.",
            10,
        ),
        (
            "geo_h2_questions",
            "H2 как вопросы",
            "Не менее 30% заголовков H2 сформулированы как вопросы (Who/What/How/Why/Что/Как/Почему и др.).",
            10,
        ),
        (
            "geo_external_citations",
            "Внешние ссылки на авторитетные источники",
            "Страница содержит не менее 2 внешних ссылок на авторитетные домены (gov, edu, wikipedia.org и др.).",
            10,
        ),
        (
            "geo_ai_robots",
            "AI-боты не заблокированы",
            "Файл robots.txt не запрещает обход страницы AI-ботами: GPTBot, ClaudeBot, PerplexityBot и другими.",
            10,
        ),
        (
            "geo_summary_block",
            "TL;DR / Summary блок",
            "До первого H2 присутствует явный блок с классом/id summary, tldr или key-takeaways.",
            5,
        ),
    ]

    conn = op.get_bind()
    for i, (code, name, description, weight) in enumerate(geo_checks):
        conn.execute(
            sa.text(
                """
                INSERT INTO audit_check_definitions
                    (id, code, name, description, applies_to, is_active,
                     severity, auto_fixable, fix_action, sort_order, weight, created_at)
                VALUES
                    (:id, :code, :name, :description, 'unknown', true,
                     'info', false, null, :sort_order, :weight, NOW())
                ON CONFLICT (code) DO UPDATE
                SET weight = EXCLUDED.weight,
                    description = EXCLUDED.description
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "code": code,
                "name": name,
                "description": description,
                "sort_order": 100 + i,
                "weight": weight,
            },
        )


def downgrade() -> None:
    # Remove geo_* check definitions
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM audit_check_definitions WHERE code LIKE 'geo_%'"
        )
    )

    # Drop index and tables in dependency order
    op.drop_index("ix_llm_usage_user_created", table_name="llm_usage")
    op.drop_table("llm_usage")
    op.drop_table("llm_brief_jobs")

    # Drop added columns
    op.drop_column("audit_check_definitions", "weight")
    op.drop_column("users", "anthropic_api_key_encrypted")
    op.drop_column("pages", "geo_score")
