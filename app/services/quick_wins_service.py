"""Quick Wins service: surfaces high-ROI pages ranked by opportunity score.

Quick Wins = pages with positions 4-20 that have unfixed SEO issues.
Opportunity score = (21 - avg_position) * weekly_traffic

Higher score = closer to page 1 AND more traffic = highest ROI fix.

Design decisions (per 12-02-PLAN.md):
- URL normalization done in Python (normalize_url) to match across tables
- Issue filters: missing_toc, missing_schema, low_links (inlinks < 3), thin_content (words < 300)
- Batch fix creates WpContentJob in 'pending' status for the existing pipeline
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl import ContentType, Page
from app.models.wp_content_job import JobStatus, WpContentJob
from app.utils.url_normalize import normalize_url

# Thresholds for issue detection (D-01)
LOW_LINKS_THRESHOLD = 3
THIN_CONTENT_THRESHOLD = 300

# Position range for Quick Wins
POSITION_MIN = 4
POSITION_MAX = 20


async def get_quick_wins(
    db: AsyncSession,
    site_id: uuid.UUID,
    issue_type: str | None = None,
    content_type: str | None = None,
) -> list[dict]:
    """Return pages ranked 4-20 with unfixed SEO issues, sorted by opportunity score desc.

    Args:
        db: Async database session.
        site_id: Site to query.
        issue_type: Optional filter — one of: missing_toc, missing_schema, low_links, thin_content.
        content_type: Optional filter — one of: informational, commercial, unknown.

    Returns:
        List of dicts with keys:
            page_id, url, opportunity_score, has_toc, has_schema,
            has_low_links, has_thin_content, avg_position,
            weekly_traffic, content_type
    """
    # Step 1: Get all KLP rows for this site in position range 4-20
    klp_result = await db.execute(
        text(
            "SELECT url, AVG(position) AS avg_position "
            "FROM keyword_latest_positions "
            "WHERE site_id = :site_id "
            "  AND position >= :pos_min "
            "  AND position <= :pos_max "
            "GROUP BY url "
            "HAVING AVG(position) >= :pos_min AND AVG(position) <= :pos_max"
        ),
        {"site_id": site_id, "pos_min": POSITION_MIN, "pos_max": POSITION_MAX},
    )
    klp_rows = klp_result.fetchall()

    if not klp_rows:
        return []

    # Step 2: Normalize KLP URLs and build lookup: normalized_url -> avg_position
    klp_by_norm: dict[str, float] = {}
    for row in klp_rows:
        norm = normalize_url(row[0])
        if norm:
            # If multiple raw URLs normalize to same URL, keep lowest avg_position (best rank)
            if norm not in klp_by_norm or row[1] < klp_by_norm[norm]:
                klp_by_norm[norm] = float(row[1])

    if not klp_by_norm:
        return []

    # Step 3: Get latest crawl pages for this site matching those normalized URLs
    pages_result = await db.execute(
        select(Page).where(Page.site_id == site_id)
    )
    pages = pages_result.scalars().all()

    # Build lookup: normalized_url -> Page (prefer most recent crawl — last wins is fine for now)
    page_by_norm: dict[str, Page] = {}
    for page in pages:
        norm = normalize_url(page.url)
        if norm and norm in klp_by_norm:
            # Keep the page if we don't have one yet, or prefer more recent crawled_at
            if norm not in page_by_norm or page.crawled_at > page_by_norm[norm].crawled_at:
                page_by_norm[norm] = page

    if not page_by_norm:
        return []

    # Step 4: Get weekly traffic from metrika_traffic_pages (last 7 days)
    cutoff = date.today() - timedelta(days=7)
    traffic_result = await db.execute(
        text(
            "SELECT page_url, SUM(visits) AS weekly_traffic "
            "FROM metrika_traffic_pages "
            "WHERE site_id = :site_id AND period_end >= :cutoff "
            "GROUP BY page_url"
        ),
        {"site_id": site_id, "cutoff": cutoff},
    )
    traffic_rows = traffic_result.fetchall()

    # Build traffic lookup: normalized_url -> weekly_traffic
    traffic_by_norm: dict[str, int] = {}
    for row in traffic_rows:
        norm = normalize_url(row[0])
        if norm:
            traffic_by_norm[norm] = traffic_by_norm.get(norm, 0) + int(row[1])

    # Step 5: Build results
    results = []
    for norm_url, page in page_by_norm.items():
        avg_pos = klp_by_norm[norm_url]
        weekly_traffic = traffic_by_norm.get(norm_url, 0)
        opportunity_score = (21 - avg_pos) * weekly_traffic

        has_low_links = bool(
            page.inlinks_count is not None and page.inlinks_count < LOW_LINKS_THRESHOLD
        )
        has_thin_content = bool(
            page.word_count is not None and page.word_count < THIN_CONTENT_THRESHOLD
        )

        # Step 6: Only include pages with at least one unfixed issue
        has_any_issue = (
            not page.has_toc
            or not page.has_schema
            or has_low_links
            or has_thin_content
        )
        if not has_any_issue:
            continue

        # Step 7: Apply issue_type filter
        if issue_type:
            if issue_type == "missing_toc" and page.has_toc:
                continue
            elif issue_type == "missing_schema" and page.has_schema:
                continue
            elif issue_type == "low_links" and not has_low_links:
                continue
            elif issue_type == "thin_content" and not has_thin_content:
                continue

        # Step 8: Apply content_type filter
        if content_type:
            if page.content_type.value != content_type:
                continue

        results.append(
            {
                "page_id": page.id,
                "url": page.url,
                "opportunity_score": opportunity_score,
                "has_toc": page.has_toc,
                "has_schema": page.has_schema,
                "has_low_links": has_low_links,
                "has_thin_content": has_thin_content,
                "avg_position": round(avg_pos, 1),
                "weekly_traffic": weekly_traffic,
                "content_type": page.content_type.value,
            }
        )

    # Step 9: Sort by opportunity_score DESC
    results.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return results


async def dispatch_batch_fix(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_ids: list[uuid.UUID],
    fix_types: list[str],
) -> dict:
    """Create WpContentJob records in pending status for selected pages.

    For each page_id × fix_type combination, creates a pipeline job
    if the page actually needs that fix.

    Args:
        db: Async database session.
        site_id: Site the pages belong to.
        page_ids: List of Page UUIDs to fix.
        fix_types: List of fix types to apply: "toc", "schema", "links".

    Returns:
        {"dispatched": N, "skipped": M} counts.
    """
    if not page_ids or not fix_types:
        return {"dispatched": 0, "skipped": 0}

    # Load pages
    pages_result = await db.execute(
        select(Page).where(Page.id.in_(page_ids), Page.site_id == site_id)
    )
    pages = pages_result.scalars().all()

    dispatched = 0
    skipped = 0

    for page in pages:
        for fix_type in fix_types:
            # Check if page actually needs this fix
            needs_fix = False
            fix_action = fix_type

            if fix_type == "toc" and not page.has_toc:
                needs_fix = True
                fix_action = "toc"
            elif fix_type == "schema" and not page.has_schema:
                needs_fix = True
                fix_action = "schema"
            elif fix_type == "links":
                has_low_links = (
                    page.inlinks_count is not None
                    and page.inlinks_count < LOW_LINKS_THRESHOLD
                )
                if has_low_links:
                    needs_fix = True
                    fix_action = "links"

            if needs_fix:
                job = WpContentJob(
                    site_id=site_id,
                    page_url=page.url,
                    wp_post_id=None,
                    status=JobStatus.pending,
                    original_content=None,
                    processed_content=None,
                    diff_json=None,
                )
                db.add(job)
                dispatched += 1
            else:
                skipped += 1

    await db.flush()
    return {"dispatched": dispatched, "skipped": skipped}
