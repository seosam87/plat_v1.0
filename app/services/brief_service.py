"""Content brief service: generate ТЗ from analysis session data."""
from __future__ import annotations

import csv
import io
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import (
    AnalysisSession,
    CompetitorPageData,
    ContentBrief,
    SessionStatus,
)
from app.models.keyword import Keyword


# ---- Pure functions ----


def build_heading_structure(
    competitor_headings: list[list[dict]],
    keywords: list[str],
) -> list[dict]:
    """Build recommended heading structure from competitor data and keywords.

    competitor_headings: list of [{"level": 2|3, "text": str}] per competitor page.
    keywords: list of keyword phrases for H3 suggestions.

    Returns [{level, text, source}].
    """
    # Count H2 patterns across competitors
    h2_counter: Counter = Counter()
    for page_headings in competitor_headings:
        for h in page_headings:
            if h.get("level") == 2:
                h2_counter[h["text"].strip()] += 1

    # H2s appearing on 2+ competitors
    common_h2s = [text for text, count in h2_counter.most_common(10) if count >= 2]

    # If no common H2s, take top H2s from first competitor
    if not common_h2s and competitor_headings:
        common_h2s = [
            h["text"].strip()
            for h in competitor_headings[0]
            if h.get("level") == 2
        ][:5]

    result: list[dict] = []
    for h2 in common_h2s:
        result.append({"level": 2, "text": h2, "source": "competitor"})

    # Add keyword-based H3 suggestions
    for kw in keywords[:10]:
        if kw and len(kw) > 3:
            result.append({"level": 3, "text": kw.capitalize(), "source": "keyword"})

    return result


def suggest_seo_fields(
    keyword_phrase: str,
    site_name: str,
    competitor_titles: list[str] | None = None,
) -> dict:
    """Generate recommended SEO fields."""
    # Title: keyword + site name, max 60
    title_candidate = f"{keyword_phrase} — {site_name}"
    if len(title_candidate) > 60:
        title_candidate = f"{keyword_phrase[:55]}..."

    # H1: keyword, max 70
    h1_candidate = keyword_phrase[:70]

    # Meta description: template, max 160
    meta_candidate = f"{keyword_phrase}. Подробная информация, актуальные данные и рекомендации от {site_name}."
    if len(meta_candidate) > 160:
        meta_candidate = meta_candidate[:157] + "..."

    return {
        "title": title_candidate,
        "h1": h1_candidate,
        "meta_description": meta_candidate,
    }


def format_brief_text(brief: dict) -> str:
    """Format a content brief dict as readable plain text."""
    lines = [
        f"ТЗ: {brief.get('title', '')}",
        f"URL: {brief.get('target_url', '—')}",
        f"Дата: {brief.get('created_at', '')}",
        "",
        "== SEO-поля ==",
        f"Title: {brief.get('recommended_title', '—')}",
        f"H1: {brief.get('recommended_h1', '—')}",
        f"Meta Description: {brief.get('recommended_meta', '—')}",
        "",
    ]

    # Keywords
    keywords = brief.get("keywords_json", [])
    lines.append(f"== Ключевые слова ({len(keywords)}) ==")
    for kw in keywords:
        freq = kw.get("frequency", "")
        freq_str = f" — {freq}" if freq else ""
        lines.append(f"  {kw.get('phrase', '')}{freq_str}")
    lines.append("")

    # Headings
    headings = brief.get("headings_json", [])
    if headings:
        lines.append("== Структура заголовков ==")
        for h in headings:
            indent = "  " if h.get("level", 2) == 3 else ""
            lines.append(f"{indent}H{h.get('level', 2)}: {h.get('text', '')}")
        lines.append("")

    # Structure
    if brief.get("structure_notes"):
        lines.append("== Место в структуре ==")
        lines.append(brief["structure_notes"])
        lines.append("")

    # Competitor data
    if brief.get("competitor_data_json"):
        lines.append("== Данные конкурентов ==")
        comp = brief["competitor_data_json"]
        if isinstance(comp, dict):
            for k, v in comp.items():
                lines.append(f"  {k}: {v}")
        lines.append("")

    return "\n".join(lines)


# ---- Async DB functions ----


async def generate_brief(
    db: AsyncSession,
    session_id: uuid.UUID,
    target_url: str | None = None,
    structure_notes: str | None = None,
) -> ContentBrief:
    """Generate a content brief from an analysis session."""
    session = await db.execute(
        select(AnalysisSession).where(AnalysisSession.id == session_id)
    )
    sess = session.scalar_one()

    # Get keywords
    kw_uuids = [uuid.UUID(kid) for kid in sess.keyword_ids]
    kw_result = await db.execute(
        select(Keyword).where(Keyword.id.in_(kw_uuids))
    )
    keywords = kw_result.scalars().all()
    keywords_json = [
        {"phrase": k.phrase, "frequency": k.frequency}
        for k in keywords
    ]

    # Get competitor page data
    comp_result = await db.execute(
        select(CompetitorPageData).where(CompetitorPageData.session_id == session_id)
    )
    comp_pages = comp_result.scalars().all()

    # Build heading structure from competitor data
    competitor_headings = [p.headings_json or [] for p in comp_pages if p.headings_json]
    kw_phrases = [k.phrase for k in keywords]
    headings = build_heading_structure(competitor_headings, kw_phrases)

    # Suggest SEO fields
    top_keyword = keywords[0].phrase if keywords else "Страница"
    # Get site name
    from app.models.site import Site
    site_result = await db.execute(select(Site).where(Site.id == sess.site_id))
    site = site_result.scalar_one()

    competitor_titles = [p.title for p in comp_pages if p.title]
    seo = suggest_seo_fields(top_keyword, site.name, competitor_titles)

    # Competitor summary
    comp_summary = {}
    if comp_pages:
        comp_summary = {
            "domain": sess.competitor_domain or "",
            "pages_analyzed": len(comp_pages),
            "avg_word_count": round(
                sum(p.word_count or 0 for p in comp_pages) / len(comp_pages)
            ) if comp_pages else 0,
            "has_schema_pct": round(
                sum(1 for p in comp_pages if p.has_schema) / len(comp_pages) * 100
            ),
            "has_toc_pct": round(
                sum(1 for p in comp_pages if p.has_toc) / len(comp_pages) * 100
            ),
        }

    brief = ContentBrief(
        session_id=session_id,
        site_id=sess.site_id,
        title=f"ТЗ: {top_keyword}",
        target_url=target_url,
        recommended_title=seo["title"],
        recommended_h1=seo["h1"],
        recommended_meta=seo["meta_description"],
        keywords_json=keywords_json,
        headings_json=headings,
        structure_notes=structure_notes,
        competitor_data_json=comp_summary,
    )
    db.add(brief)
    await db.flush()

    # Update session status
    sess.status = SessionStatus.brief_created
    await db.flush()

    return brief


async def get_brief(db: AsyncSession, brief_id: uuid.UUID) -> ContentBrief | None:
    result = await db.execute(select(ContentBrief).where(ContentBrief.id == brief_id))
    return result.scalar_one_or_none()


async def list_briefs(db: AsyncSession, site_id: uuid.UUID) -> list[ContentBrief]:
    result = await db.execute(
        select(ContentBrief)
        .where(ContentBrief.site_id == site_id)
        .order_by(ContentBrief.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_brief(db: AsyncSession, brief_id: uuid.UUID) -> bool:
    brief = await get_brief(db, brief_id)
    if not brief:
        return False
    await db.delete(brief)
    await db.flush()
    return True


async def export_brief_text(db: AsyncSession, brief_id: uuid.UUID) -> str:
    """Export brief as formatted text."""
    brief = await get_brief(db, brief_id)
    if not brief:
        return ""
    return format_brief_text({
        "title": brief.title,
        "target_url": brief.target_url,
        "created_at": brief.created_at.strftime("%Y-%m-%d") if brief.created_at else "",
        "recommended_title": brief.recommended_title,
        "recommended_h1": brief.recommended_h1,
        "recommended_meta": brief.recommended_meta,
        "keywords_json": brief.keywords_json,
        "headings_json": brief.headings_json,
        "structure_notes": brief.structure_notes,
        "competitor_data_json": brief.competitor_data_json,
    })


async def export_brief_csv(db: AsyncSession, brief_id: uuid.UUID) -> str:
    """Export brief keywords as CSV."""
    brief = await get_brief(db, brief_id)
    if not brief:
        return ""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Phrase", "Frequency"])
    for kw in brief.keywords_json or []:
        writer.writerow([kw.get("phrase", ""), kw.get("frequency", "")])
    return output.getvalue()
