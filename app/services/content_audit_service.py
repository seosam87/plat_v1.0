"""Content audit service: check engine, HTML detection, classification, DB helpers."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditCheckDefinition, AuditResult
from app.models.crawl import ContentType


# ---- Pure detection functions (no DB) ----

_AUTHOR_CLASS_RE = re.compile(
    r'class="[^"]*\bauthor[-_]?(box|info|block|bio|meta)?\b', re.I
)
_AUTHOR_REL_RE = re.compile(r'rel=["\']author["\']', re.I)

_RELATED_CLASS_RE = re.compile(
    r'class="[^"]*\b(related[-_]?posts?|yarpp[-_]?related|similar[-_]?posts?'
    r"|crp_related|jp-relatedposts)\b",
    re.I,
)
_RELATED_TEXT_RE = re.compile(
    r"(Похожие статьи|Читайте также|Related [Pp]osts|Вам также может понравиться)",
    re.I,
)

_CTA_CLASS_RE = re.compile(
    r'class="[^"]*\bcta[-_]?(block|section|banner|widget)?\b', re.I
)
_CTA_TEXT_RE = re.compile(
    r"(Заказать|Оставить заявку|Купить|Получить консультацию|Записаться|Узнать цену)",
    re.I,
)


def detect_author_block(html: str) -> bool:
    """Check rendered HTML for author block patterns."""
    return bool(_AUTHOR_CLASS_RE.search(html) or _AUTHOR_REL_RE.search(html))


def detect_related_posts(html: str) -> bool:
    """Check rendered HTML for related posts block."""
    return bool(_RELATED_CLASS_RE.search(html) or _RELATED_TEXT_RE.search(html))


def detect_cta_block(html: str) -> bool:
    """Check rendered HTML for CTA block."""
    return bool(_CTA_CLASS_RE.search(html) or _CTA_TEXT_RE.search(html))


def classify_content_type(page_type: str, url: str) -> str:
    """Determine content_type from page_type and URL patterns."""
    if page_type == "product":
        return ContentType.commercial.value
    if page_type == "article":
        return ContentType.informational.value
    if page_type == "category":
        return ContentType.commercial.value
    if page_type == "landing":
        commercial_patterns = ("/uslugi/", "/services/", "/price/", "/catalog/", "/shop/")
        if any(p in url.lower() for p in commercial_patterns):
            return ContentType.commercial.value
        return ContentType.informational.value
    return ContentType.unknown.value


def check_internal_links(internal_link_count: int, min_links: int = 1) -> bool:
    """Return True if page has at least min_links internal links."""
    return internal_link_count >= min_links


# ---- Check engine ----

_CHECK_RUNNERS: dict[str, callable] = {
    "toc_present": lambda html, pd: pd.get("has_toc", False),
    "schema_present": lambda html, pd: pd.get("has_schema", False),
    "author_block": lambda html, pd: detect_author_block(html),
    "related_posts": lambda html, pd: detect_related_posts(html),
    "cta_present": lambda html, pd: detect_cta_block(html),
    "internal_links": lambda html, pd: check_internal_links(
        pd.get("internal_link_count", 0)
    ),
    "noindex_check": lambda html, pd: not pd.get("has_noindex", False),
}


def run_checks_for_page(
    html: str, page_data: dict, check_definitions: list[dict]
) -> list[dict]:
    """Run all applicable checks against a page.

    Args:
        html: Rendered page HTML.
        page_data: Dict with keys: has_toc, has_schema, has_noindex,
                   internal_link_count, content_type, page_type, url.
        check_definitions: List of dicts from AuditCheckDefinition rows.

    Returns:
        List of {check_code, status, details}.
    """
    results = []
    page_ct = page_data.get("content_type", "unknown")

    for chk in check_definitions:
        if not chk.get("is_active", True):
            continue

        applies_to = chk.get("applies_to", "unknown")
        if applies_to != "unknown" and applies_to != page_ct:
            continue

        code = chk["code"]
        runner = _CHECK_RUNNERS.get(code)
        if not runner:
            continue

        passed = runner(html, page_data)
        severity = chk.get("severity", "warning")

        if passed:
            status = "pass"
        else:
            status = "fail" if severity == "error" else "warning"

        results.append({"check_code": code, "status": status, "details": None})

    return results


# ---- Async DB functions ----


async def get_active_checks(db: AsyncSession) -> list[AuditCheckDefinition]:
    """Fetch all active check definitions ordered by sort_order."""
    result = await db.execute(
        select(AuditCheckDefinition)
        .where(AuditCheckDefinition.is_active == True)  # noqa: E712
        .order_by(AuditCheckDefinition.sort_order)
    )
    return list(result.scalars().all())


async def save_audit_results(
    db: AsyncSession, site_id: uuid.UUID, page_url: str, results: list[dict]
) -> None:
    """Upsert audit results for a page."""
    for r in results:
        stmt = insert(AuditResult).values(
            id=uuid.uuid4(),
            site_id=site_id,
            page_url=page_url,
            check_code=r["check_code"],
            status=r["status"],
            details=r.get("details"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_audit_result_site_page_check",
            set_={
                "status": stmt.excluded.status,
                "details": stmt.excluded.details,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await db.execute(stmt)
    await db.flush()


async def get_audit_results_for_site(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_urls: list[str] | None = None,
) -> list[AuditResult]:
    """Fetch audit results, optionally filtered by URL list."""
    q = select(AuditResult).where(AuditResult.site_id == site_id)
    if page_urls is not None:
        q = q.where(AuditResult.page_url.in_(page_urls))
    q = q.order_by(AuditResult.page_url, AuditResult.check_code)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_content_type(
    db: AsyncSession, page_id: uuid.UUID, content_type: str
) -> None:
    """Update a page's content_type field."""
    from app.models.crawl import Page
    from sqlalchemy import update

    await db.execute(
        update(Page).where(Page.id == page_id).values(content_type=content_type)
    )
    await db.flush()


async def classify_and_update_pages(
    db: AsyncSession, site_id: uuid.UUID, crawl_job_id: uuid.UUID
) -> int:
    """Classify content_type for all pages of a crawl job."""
    from app.models.crawl import Page

    result = await db.execute(
        select(Page).where(
            Page.site_id == site_id,
            Page.crawl_job_id == crawl_job_id,
        )
    )
    pages = result.scalars().all()
    count = 0
    for p in pages:
        pt = p.page_type.value if hasattr(p.page_type, "value") else p.page_type
        ct = classify_content_type(pt, p.url)
        if ct != "unknown" or (hasattr(p.content_type, "value") and p.content_type.value == "unknown"):
            p.content_type = ct
            count += 1
    await db.flush()
    return count


async def get_check_definitions(db: AsyncSession) -> list[dict]:
    """Fetch all check definitions as list of dicts for the UI."""
    result = await db.execute(
        select(AuditCheckDefinition).order_by(AuditCheckDefinition.sort_order)
    )
    checks = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "code": c.code,
            "name": c.name,
            "description": c.description,
            "applies_to": c.applies_to.value if hasattr(c.applies_to, "value") else c.applies_to,
            "is_active": c.is_active,
            "severity": c.severity,
            "auto_fixable": c.auto_fixable,
            "fix_action": c.fix_action,
            "sort_order": c.sort_order,
        }
        for c in checks
    ]


async def update_check_definition(
    db: AsyncSession, check_id: uuid.UUID, **fields
) -> AuditCheckDefinition | None:
    """Update a check definition."""
    result = await db.execute(
        select(AuditCheckDefinition).where(AuditCheckDefinition.id == check_id)
    )
    check = result.scalar_one_or_none()
    if not check:
        return None
    for k, v in fields.items():
        if hasattr(check, k):
            setattr(check, k, v)
    await db.flush()
    return check


async def create_check_definition(
    db: AsyncSession,
    code: str,
    name: str,
    applies_to: str = "unknown",
    severity: str = "warning",
    auto_fixable: bool = False,
    fix_action: str | None = None,
) -> AuditCheckDefinition:
    """Create a new user-defined check definition."""
    check = AuditCheckDefinition(
        code=code,
        name=name,
        applies_to=applies_to,
        severity=severity,
        auto_fixable=auto_fixable,
        fix_action=fix_action,
    )
    db.add(check)
    await db.flush()
    return check
