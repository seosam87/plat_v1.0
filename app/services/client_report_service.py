"""Client instruction PDF service.

Aggregates data from Quick Wins, audit errors (impact scores), Dead Content,
and position statistics into a context dict. Renders the Jinja2 PDF template
and generates PDF bytes via subprocess-isolated WeasyPrint.

Decision references (Phase 14 CONTEXT.md):
  D-01: Configurable blocks via blocks_config dict
  D-02: TOP-N limit per block (TOP_N = 20)
  D-03: Summary box at top of report
  D-05: Problems grouped by type
  D-07: Russian instruction templates per problem type (7 standard types)
  D-12: WeasyPrint subprocess isolation
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_report import ClientReport
from app.services.subprocess_pdf import render_pdf_in_subprocess

# TOP-N limit per block (D-02, Claude's discretion: 20)
TOP_N = 20

# Russian instruction templates per problem type (D-07)
# Keys match check_code values from error_impact_scores and quick_wins issue types
INSTRUCTION_TEMPLATES: dict[str, dict[str, str]] = {
    "404": {
        "label": "Ошибки 404",
        "instruction": (
            "Настройте редирект 301 на актуальный URL или восстановите страницу "
            "для следующих адресов:"
        ),
    },
    "noindex": {
        "label": "Страницы с noindex",
        "instruction": (
            "Проверьте meta robots и настройки плагина SEO. Снимите noindex "
            "со следующих страниц, если индексация желательна:"
        ),
    },
    "missing_toc": {
        "label": "Отсутствует TOC",
        "instruction": (
            "Добавьте оглавление (Table of Contents) через плагин или шорткод "
            "на следующих страницах:"
        ),
    },
    "missing_schema": {
        "label": "Нет schema.org",
        "instruction": (
            "Добавьте разметку schema.org (Article, FAQ, Product или Service) "
            "через Yoast \u2192 Custom Schema на следующих страницах:"
        ),
    },
    "thin_content": {
        "label": "Тонкий контент",
        "instruction": (
            "Расширьте объём страниц: добавьте экспертные блоки, FAQ, примеры "
            "или кейсы. Минимальный объём \u2014 800 слов:"
        ),
    },
    "low_internal_links": {
        "label": "Мало внутренних ссылок",
        "instruction": (
            "Добавьте 2\u20133 внутренних ссылки на следующие страницы "
            "из смежных материалов сайта:"
        ),
    },
    "dead_content": {
        "label": "Мёртвый контент",
        "instruction": (
            "Для каждой страницы выберите действие согласно рекомендации: "
            "объединить с другой страницей, настроить редирект, переписать или удалить:"
        ),
    },
}

# Map quick_wins issue flags to instruction template keys
_QUICK_WINS_ISSUE_MAP: dict[str, str] = {
    "has_toc": "missing_toc",       # flag False = missing TOC
    "has_schema": "missing_schema", # flag False = missing schema
    "has_low_links": "low_internal_links",
    "has_thin_content": "thin_content",
}

# Map audit check_code prefixes/values to instruction template keys
_AUDIT_CODE_MAP: dict[str, str] = {
    "404": "404",
    "noindex": "noindex",
    "missing_toc": "missing_toc",
    "missing_schema": "missing_schema",
    "thin_content": "thin_content",
    "low_links": "low_internal_links",
    "low_internal_links": "low_internal_links",
}


# ---------------------------------------------------------------------------
# Data aggregation
# ---------------------------------------------------------------------------


async def gather_report_data(
    db: AsyncSession,
    site_id: uuid.UUID,
    blocks_config: dict[str, bool],
) -> dict[str, Any]:
    """Aggregate report data from all requested blocks.

    Args:
        db: Async database session.
        site_id: Site UUID to aggregate for.
        blocks_config: Dict with boolean flags for each data block:
            {"quick_wins": True, "audit_errors": True, "dead_content": True, "positions": True}

    Returns:
        Dict with keys: summary, problem_groups, positions (may be empty dict if not requested).
    """
    from app.services.quick_wins_service import get_quick_wins
    from app.services.dead_content_service import get_dead_content
    from app.services.report_service import site_overview

    problem_groups: list[dict[str, Any]] = []
    total_pages_checked = 0
    total_problems = 0
    critical_count = 0

    # --- Block: Quick Wins ---
    if blocks_config.get("quick_wins"):
        try:
            qw_items = await get_quick_wins(db, site_id)
            total_pages_checked += len(qw_items)

            # Group by issue type
            issue_buckets: dict[str, list[dict]] = {}
            for item in qw_items:
                if not item.get("has_toc"):
                    issue_buckets.setdefault("missing_toc", []).append(item)
                if not item.get("has_schema"):
                    issue_buckets.setdefault("missing_schema", []).append(item)
                if item.get("has_low_links"):
                    issue_buckets.setdefault("low_internal_links", []).append(item)
                if item.get("has_thin_content"):
                    issue_buckets.setdefault("thin_content", []).append(item)

            for issue_key, pages in issue_buckets.items():
                tpl = INSTRUCTION_TEMPLATES.get(issue_key)
                if not tpl:
                    continue
                shown = pages[:TOP_N]
                overflow = max(0, len(pages) - TOP_N)
                total_problems += len(pages)
                group_pages = [
                    {
                        "url": p.get("url", ""),
                        "title": p.get("url", ""),  # quick wins don't have title field
                        "metric": f"позиция {p.get('avg_position', '—'):.1f}"
                        if isinstance(p.get("avg_position"), (int, float))
                        else "—",
                    }
                    for p in shown
                ]
                problem_groups.append(
                    {
                        "label": tpl["label"],
                        "instruction": tpl["instruction"],
                        "pages": group_pages,
                        "overflow": overflow,
                    }
                )
        except Exception as exc:
            logger.warning("Failed to load quick wins data", error=str(exc))

    # --- Block: Audit Errors ---
    if blocks_config.get("audit_errors"):
        try:
            rows = (
                await db.execute(
                    text(
                        "SELECT page_url, check_code, severity, impact_score "
                        "FROM error_impact_scores "
                        "WHERE site_id = :site_id "
                        "ORDER BY impact_score DESC"
                    ),
                    {"site_id": site_id},
                )
            ).mappings().all()

            audit_buckets: dict[str, list[dict]] = {}
            for row in rows:
                check_code = row["check_code"]
                tpl_key = _AUDIT_CODE_MAP.get(check_code, check_code)
                if tpl_key not in INSTRUCTION_TEMPLATES:
                    continue
                audit_buckets.setdefault(tpl_key, []).append(dict(row))
                if row["severity"] == "critical":
                    critical_count += 1

            for issue_key, pages in audit_buckets.items():
                # Skip if already covered by quick_wins block (avoid duplicates)
                already_shown = any(
                    g["label"] == INSTRUCTION_TEMPLATES[issue_key]["label"]
                    for g in problem_groups
                )
                if already_shown:
                    continue
                tpl = INSTRUCTION_TEMPLATES[issue_key]
                shown = pages[:TOP_N]
                overflow = max(0, len(pages) - TOP_N)
                total_problems += len(pages)
                group_pages = [
                    {
                        "url": p["page_url"],
                        "title": p["page_url"],
                        "metric": f"impact {p.get('impact_score', 0)}",
                    }
                    for p in shown
                ]
                problem_groups.append(
                    {
                        "label": tpl["label"],
                        "instruction": tpl["instruction"],
                        "pages": group_pages,
                        "overflow": overflow,
                    }
                )
        except Exception as exc:
            logger.warning("Failed to load audit errors data", error=str(exc))

    # --- Block: Dead Content ---
    if blocks_config.get("dead_content"):
        try:
            dc_result = await get_dead_content(db, site_id)
            dc_pages = dc_result.get("pages", [])
            total_pages_checked += len(dc_pages)
            total_problems += len(dc_pages)

            tpl = INSTRUCTION_TEMPLATES["dead_content"]
            shown = dc_pages[:TOP_N]
            overflow = max(0, len(dc_pages) - TOP_N)
            group_pages = [
                {
                    "url": p.get("url", ""),
                    "title": p.get("recommendation", ""),
                    "metric": p.get("recommendation_reason", ""),
                }
                for p in shown
            ]
            if shown:
                problem_groups.append(
                    {
                        "label": tpl["label"],
                        "instruction": tpl["instruction"],
                        "pages": group_pages,
                        "overflow": overflow,
                    }
                )
        except Exception as exc:
            logger.warning("Failed to load dead content data", error=str(exc))

    # --- Block: Positions ---
    positions: dict[str, Any] = {}
    if blocks_config.get("positions"):
        try:
            positions = await site_overview(db, site_id)
        except Exception as exc:
            logger.warning("Failed to load positions data", error=str(exc))

    # --- Summary (D-03) ---
    if critical_count == 0:
        assessment = "Критических проблем не обнаружено."
    elif critical_count <= 3:
        assessment = f"Обнаружено {critical_count} критических проблемы — требуют приоритетного внимания."
    else:
        assessment = f"Обнаружено {critical_count} критических проблем — необходимо срочное исправление."

    summary = {
        "total_pages": total_pages_checked,
        "total_problems": total_problems,
        "critical_count": critical_count,
        "assessment": assessment,
    }

    return {
        "summary": summary,
        "problem_groups": problem_groups,
        "positions": positions,
    }


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


async def generate_client_report(
    db: AsyncSession,
    site_id: uuid.UUID,
    blocks_config: dict[str, bool],
) -> bytes:
    """Aggregate data, render Jinja2 template, generate PDF via subprocess.

    Args:
        db: Async database session.
        site_id: Site UUID to generate report for.
        blocks_config: Dict with boolean flags for each data block.

    Returns:
        PDF bytes.

    Raises:
        RuntimeError: If PDF rendering fails.
    """
    from app.models.site import Site

    # Fetch site info
    site = (
        await db.execute(select(Site).where(Site.id == site_id))
    ).scalar_one_or_none()
    site_name = site.name if site else "Unknown"
    site_url = site.url if site else ""

    # Aggregate data
    report_data = await gather_report_data(db, site_id, blocks_config)

    # Build block names for meta line
    block_labels = []
    if blocks_config.get("quick_wins"):
        block_labels.append("Quick Wins")
    if blocks_config.get("audit_errors"):
        block_labels.append("Ошибки аудита")
    if blocks_config.get("dead_content"):
        block_labels.append("Мёртвый контент")
    if blocks_config.get("positions"):
        block_labels.append("Позиции")
    block_names = ", ".join(block_labels) if block_labels else "все блоки"

    report_date = datetime.now(timezone.utc).strftime("%d.%m.%Y")

    context = {
        "site_name": site_name,
        "site_url": site_url,
        "report_date": report_date,
        "block_names": block_names,
        "summary": report_data["summary"],
        "problem_groups": report_data["problem_groups"],
        "positions": report_data["positions"],
    }

    # Render Jinja2 template
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    template = env.get_template("reports/client_instructions.html")
    rendered_html = template.render(**context)

    # Generate PDF in subprocess (D-12: subprocess isolation to prevent memory leak)
    loop = asyncio.get_event_loop()
    pdf_bytes: bytes = await loop.run_in_executor(
        None, render_pdf_in_subprocess, rendered_html
    )
    logger.info(
        "Client report PDF generated",
        site_id=str(site_id),
        pdf_size=len(pdf_bytes),
    )
    return pdf_bytes


# ---------------------------------------------------------------------------
# CRUD helpers for ClientReport records
# ---------------------------------------------------------------------------


async def create_report_record(
    db: AsyncSession,
    site_id: uuid.UUID,
    blocks_config: dict[str, bool],
) -> ClientReport:
    """Create a new ClientReport record in 'pending' status.

    Args:
        db: Async database session.
        site_id: Site UUID.
        blocks_config: Selected block flags.

    Returns:
        Newly created (and flushed) ClientReport instance.
    """
    report = ClientReport(
        site_id=site_id,
        blocks_config=blocks_config,
        status="pending",
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def save_report_pdf(
    db: AsyncSession,
    report_id: uuid.UUID,
    pdf_bytes: bytes,
) -> None:
    """Persist PDF bytes and mark report as ready.

    Args:
        db: Async database session.
        report_id: ClientReport UUID to update.
        pdf_bytes: Rendered PDF bytes.
    """
    report = (
        await db.execute(
            select(ClientReport).where(ClientReport.id == report_id)
        )
    ).scalar_one_or_none()
    if report is None:
        logger.error("save_report_pdf: report not found", report_id=str(report_id))
        return
    report.pdf_data = pdf_bytes
    report.status = "ready"
    await db.flush()


async def mark_report_failed(
    db: AsyncSession,
    report_id: uuid.UUID,
    error: str,
) -> None:
    """Mark report as failed with an error message.

    Args:
        db: Async database session.
        report_id: ClientReport UUID to update.
        error: Error description string (truncated to 500 chars).
    """
    report = (
        await db.execute(
            select(ClientReport).where(ClientReport.id == report_id)
        )
    ).scalar_one_or_none()
    if report is None:
        logger.error("mark_report_failed: report not found", report_id=str(report_id))
        return
    report.status = "failed"
    report.error_message = error[:500]
    await db.flush()


async def get_report_history(
    db: AsyncSession,
    site_id: uuid.UUID,
) -> list[ClientReport]:
    """Fetch the last 50 reports for a site, newest first.

    Args:
        db: Async database session.
        site_id: Site UUID.

    Returns:
        List of ClientReport instances ordered by created_at desc.
    """
    result = await db.execute(
        select(ClientReport)
        .where(ClientReport.site_id == site_id)
        .order_by(ClientReport.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def get_report_by_id(
    db: AsyncSession,
    report_id: uuid.UUID,
) -> ClientReport | None:
    """Fetch a single ClientReport by its UUID.

    Args:
        db: Async database session.
        report_id: ClientReport UUID.

    Returns:
        ClientReport instance or None if not found.
    """
    result = await db.execute(
        select(ClientReport).where(ClientReport.id == report_id)
    )
    return result.scalar_one_or_none()
