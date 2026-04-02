"""Audit fix service: generate fixes for failed checks, verify integrity, create pipeline jobs."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditResult
from app.models.wp_content_job import WpContentJob, JobStatus
from app.services.content_audit_service import detect_cta_block
from app.services.content_pipeline import (
    add_heading_ids,
    compute_content_diff,
    extract_headings,
    find_link_opportunities,
    generate_toc_html,
    has_schema_ld,
    inject_schema,
    inject_toc,
    insert_links,
)


# ---- Pure fix generators (no DB) ----


def generate_toc_fix(html: str) -> dict | None:
    """Generate TOC injection fix. Returns None if no headings found."""
    headings = extract_headings(html)
    if not headings:
        return None

    content = add_heading_ids(html, headings)
    toc = generate_toc_html(headings)
    content = inject_toc(content, toc)
    diff = compute_content_diff(html, content)

    return {
        "processed_html": content,
        "toc_html": toc,
        "diff": diff,
        "headings_count": len(headings),
    }


def generate_cta_fix(html: str, cta_template: str) -> dict | None:
    """Generate CTA injection fix. Returns None if CTA already present or no template."""
    if not cta_template:
        return None
    if detect_cta_block(html):
        return None

    content = html + "\n" + cta_template
    diff = compute_content_diff(html, content)

    return {"processed_html": content, "diff": diff}


def generate_schema_fix(html: str, schema_tag: str) -> dict | None:
    """Generate schema injection fix. Returns None if schema already present."""
    if has_schema_ld(html):
        return None

    content = inject_schema(html, schema_tag)
    diff = compute_content_diff(html, content)

    return {"processed_html": content, "diff": diff}


def generate_links_fix(
    html: str, keywords_with_urls: list[dict]
) -> dict | None:
    """Generate internal links fix. Returns None if no opportunities."""
    opportunities = find_link_opportunities(html, keywords_with_urls)
    if not opportunities:
        return None

    content = insert_links(html, opportunities)
    diff = compute_content_diff(html, content)

    return {
        "processed_html": content,
        "diff": diff,
        "links_added": len(opportunities),
    }


# ---- Verification ----

_HEADING_RE = re.compile(r"<h[23][^>]*>", re.I)
_UNCLOSED_SCRIPT_RE = re.compile(r"<script[^>]*>(?:(?!</script>).)*$", re.I | re.DOTALL)


def verify_html_integrity(original: str, processed: str) -> dict:
    """Basic sanity checks on processed HTML.

    Returns {valid: bool, warnings: list[str]}.
    """
    warnings = []

    # Check heading count
    orig_headings = len(_HEADING_RE.findall(original))
    proc_headings = len(_HEADING_RE.findall(processed))
    if orig_headings > 0 and proc_headings < orig_headings:
        warnings.append(
            f"Количество заголовков уменьшилось: {orig_headings} → {proc_headings}"
        )

    # Check for unclosed script tags
    if _UNCLOSED_SCRIPT_RE.search(processed):
        warnings.append("Обнаружен незакрытый <script> тег")

    # Check content length
    if len(original) > 0 and len(processed) < len(original) * 0.8:
        warnings.append(
            f"Контент стал значительно короче: {len(original)} → {len(processed)} символов"
        )

    return {"valid": len(warnings) == 0, "warnings": warnings}


# ---- Pipeline integration (async) ----


async def create_fix_job(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_url: str,
    wp_post_id: int | None,
    original_html: str,
    processed_html: str,
    fix_action: str,
) -> WpContentJob:
    """Create a pipeline job for a fix in awaiting_approval status."""
    diff = compute_content_diff(original_html, processed_html)
    job = WpContentJob(
        site_id=site_id,
        page_url=page_url,
        wp_post_id=wp_post_id,
        original_content=original_html,
        processed_content=processed_html,
        diff_json=diff,
        rollback_payload={
            "original_content": original_html,
            "wp_post_id": wp_post_id,
        },
        status=JobStatus.awaiting_approval,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    return job


async def mark_audit_fixed(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_url: str,
    check_code: str,
    job_id: uuid.UUID,
) -> None:
    """Update audit result to 'fixed' status with pipeline job reference."""
    result = await db.execute(
        select(AuditResult).where(
            AuditResult.site_id == site_id,
            AuditResult.page_url == page_url,
            AuditResult.check_code == check_code,
        )
    )
    ar = result.scalar_one_or_none()
    if ar:
        ar.status = "fixed"
        ar.details = f"Fixed via pipeline job {job_id} on {datetime.now(timezone.utc).isoformat()}"
        ar.wp_content_job_id = job_id
        ar.updated_at = datetime.now(timezone.utc)
        await db.flush()
