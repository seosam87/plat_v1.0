"""Seed a demo playbook for Phase 999.8 walking-skeleton.

Idempotent: safe to re-run. Checks for ExpertSource(slug='shestakov-demo')
first and skips if it already exists. On a fresh run it creates:

1. One ExpertSource: "Шестаков (демо)"
2. Six PlaybookBlocks across 6 distinct ActionKind values:
   - run_crawl, open_keywords, open_competitors,
     open_content_plan, open_brief, manual_note
3. One published Playbook "SEO для коммерческих страниц (демо)"
   with the 6 blocks attached as ordered PlaybookSteps.

Usage (from repo root):
    python scripts/seed_demo_playbook.py
    # or, inside the api container:
    docker compose exec api python scripts/seed_demo_playbook.py

Exits cleanly if already-applied or if required BlockCategory rows
are missing (run ``alembic upgrade head`` first).
"""
from __future__ import annotations

import asyncio
import os
import sys

# Ensure ``app.*`` is importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

# Importing app.models (and a handful of models referenced by playbook
# foreign keys) registers every ORM class on the shared metadata. Without
# these imports, FKs like playbook_blocks.created_by → users.id fail to
# resolve at flush time.
import app.models  # noqa: F401
import app.models.user  # noqa: F401
import app.models.project  # noqa: F401
from app.models.playbook import (
    ActionKind,
    BlockCategory,
    ExpertSource,
    Playbook,
    PlaybookBlock,
    PlaybookStep,
)


EXPERT_SLUG = "shestakov-demo"
PLAYBOOK_SLUG = "seo-commerce-demo"


BLOCK_SPECS = [
    {
        "title": "Первичный краулинг сайта",
        "slug": "demo-run-crawl",
        "category_slug": "technical",
        "summary_md": (
            "**Шаг 1.** Запустить полный краулинг сайта клиента, чтобы получить "
            "базу URL и выявить технические проблемы."
        ),
        "checklist_md": (
            "- Убедиться что сайт доступен\n"
            "- Настроить расписание краулинга\n"
            "- Проверить robots.txt"
        ),
        "action_kind": ActionKind.run_crawl,
        "estimated_days": 1,
    },
    {
        "title": "Сбор ключевых слов (ядро)",
        "slug": "demo-open-keywords",
        "category_slug": "keywords",
        "summary_md": (
            "**Шаг 2.** Собрать семантическое ядро проекта: страницы + "
            "запросы + позиции."
        ),
        "checklist_md": (
            "- Загрузить ключи из Топвизора\n"
            "- Загрузить ключи из GSC\n"
            "- Объединить и очистить дубли"
        ),
        "action_kind": ActionKind.open_keywords,
        "estimated_days": 3,
    },
    {
        "title": "Анализ топ-5 конкурентов",
        "slug": "demo-open-competitors",
        "category_slug": "competitors",
        "summary_md": (
            "**Шаг 3.** Проанализировать топ-5 конкурентов в нише и собрать "
            "их структуру."
        ),
        "checklist_md": (
            "- Найти 5 прямых конкурентов\n"
            "- Сохранить снимки структуры\n"
            "- Выделить общие блоки"
        ),
        "action_kind": ActionKind.open_competitors,
        "estimated_days": 2,
    },
    {
        "title": "Построение контент-плана",
        "slug": "demo-open-content-plan",
        "category_slug": "content",
        "summary_md": (
            "**Шаг 4.** На основе ядра и анализа конкурентов составить "
            "контент-план на 2 месяца."
        ),
        "checklist_md": (
            "- Сгруппировать запросы по интентам\n"
            "- Приоритизировать по impact\n"
            "- Назначить копирайтера"
        ),
        "action_kind": ActionKind.open_content_plan,
        "estimated_days": 2,
    },
    {
        "title": "ТЗ копирайтеру на первые 5 статей",
        "slug": "demo-open-brief",
        "category_slug": "content",
        "summary_md": (
            "**Шаг 5.** Составить подробные ТЗ копирайтеру для первых 5 "
            "статей из контент-плана."
        ),
        "checklist_md": (
            "- Скелет статьи + заголовки H2/H3\n"
            "- Ключи + LSI\n"
            "- Ссылки на конкурентов"
        ),
        "action_kind": ActionKind.open_brief,
        "estimated_days": 3,
    },
    {
        "title": "Обсудить стратегию с клиентом",
        "slug": "demo-manual-note",
        "category_slug": "regular",
        "summary_md": (
            "**Шаг 6.** Созвон с клиентом: проговорить стратегию, ожидаемые "
            "сроки и KPI."
        ),
        "checklist_md": (
            "- Подготовить презентацию\n"
            "- Согласовать приоритеты\n"
            "- Зафиксировать договорённости"
        ),
        "action_kind": ActionKind.manual_note,
        "estimated_days": 1,
    },
]


async def seed(session: AsyncSession) -> None:
    # 1. Idempotency check — bail early on repeat runs.
    existing = await session.execute(
        select(ExpertSource).where(ExpertSource.slug == EXPERT_SLUG)
    )
    if existing.scalar_one_or_none() is not None:
        print(
            f"Seed already applied (ExpertSource '{EXPERT_SLUG}' exists). "
            "Skipping."
        )
        return

    # 2. Pull the 8 seeded BlockCategory rows by slug (installed by
    #    alembic migration 0054 in Plan 01).
    result = await session.execute(select(BlockCategory))
    cats_by_slug = {c.slug: c for c in result.scalars().all()}
    required = {cat["category_slug"] for cat in BLOCK_SPECS}
    missing = required - set(cats_by_slug.keys())
    if missing:
        print(
            f"ERROR: missing BlockCategory slugs: {sorted(missing)}. "
            "Run `alembic upgrade head` first.",
            file=sys.stderr,
        )
        return

    # 3. ExpertSource.
    expert = ExpertSource(
        name="Шестаков (демо)",
        slug=EXPERT_SLUG,
        bio_md=(
            "**Демо-эксперт** для walking-skeleton Phase 999.8. "
            "Не реальный человек."
        ),
        external_url="https://example.com/shestakov-demo",
    )
    session.add(expert)
    await session.flush()

    # 4. PlaybookBlocks tied to the expert.
    created_blocks: list[PlaybookBlock] = []
    for idx, spec in enumerate(BLOCK_SPECS):
        block = PlaybookBlock(
            title=spec["title"],
            slug=spec["slug"],
            category_id=cats_by_slug[spec["category_slug"]].id,
            expert_source_id=expert.id,
            summary_md=spec["summary_md"],
            checklist_md=spec["checklist_md"],
            action_kind=spec["action_kind"],
            prerequisites=[],
            estimated_days=spec["estimated_days"],
            display_order=idx * 10,
        )
        session.add(block)
        created_blocks.append(block)
    await session.flush()

    # 5. Playbook template with the 6 blocks as ordered steps.
    playbook = Playbook(
        name="SEO для коммерческих страниц (демо)",
        slug=PLAYBOOK_SLUG,
        description_md=(
            "Демо-плейбук для walking-skeleton Phase 999.8. Проводит через "
            "6 основных шагов запуска SEO-проекта."
        ),
        is_published=True,
    )
    session.add(playbook)
    await session.flush()

    for idx, block in enumerate(created_blocks):
        session.add(
            PlaybookStep(
                playbook_id=playbook.id,
                block_id=block.id,
                position=idx,
                note_md=None,
            )
        )

    await session.commit()
    print(
        f"Seeded: 1 ExpertSource, {len(created_blocks)} PlaybookBlocks, "
        f"1 Playbook ({len(created_blocks)} steps)."
    )


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed(session)
        except Exception as exc:  # pragma: no cover - debug aid
            print(f"ERROR: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
