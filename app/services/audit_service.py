"""Audit service: audit logging + content audit check engine, HTML detection,
content_type classification, and DB persistence helpers.

The module has two responsibilities:
1. Audit log writes (log_action) — used throughout the codebase.
2. Content audit check engine (detect_*, classify_content_type, run_checks_for_page)
   and async DB helpers — used by the content audit pipeline.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditCheckDefinition, AuditResult
from app.models.audit_log import AuditLog
from app.models.crawl import ContentType


# ---------------------------------------------------------------------------
# Audit log (existing functionality — do not remove)
# ---------------------------------------------------------------------------


async def log_action(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> None:
    """Write an audit log entry in the current transaction.
    Does not commit — the caller's session commit persists the entry.
    If the calling operation rolls back, this entry rolls back too.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail_json=detail,
    )
    db.add(entry)


# ---------------------------------------------------------------------------
# Pure detection functions (no DB, fully unit-testable)
# ---------------------------------------------------------------------------

_AUTHOR_CLASS_RE = re.compile(
    r'class=["\'][^"\']*\bauthor[-_]?(box|info|block|bio|meta|card|wrap|section)?\b',
    re.IGNORECASE,
)
_AUTHOR_POST_RE = re.compile(
    r'class=["\'][^"\']*\bpost[-_]?author\b', re.IGNORECASE
)
_AUTHOR_ENTRY_RE = re.compile(
    r'class=["\'][^"\']*\bentry[-_]?author\b', re.IGNORECASE
)
_AUTHOR_REL_RE = re.compile(r'rel=["\']author["\']', re.IGNORECASE)
_AUTHOR_VCARD_RE = re.compile(
    r'class=["\'][^"\']*\bvcard[^"\']*author\b', re.IGNORECASE
)

_RELATED_CLASS_RE = re.compile(
    r'class=["\'][^"\']*\b(related[-_]?posts?|yarpp[-_]?related|'
    r'jp[-_]?relatedposts|crp[-_]?related|similar[-_]?posts?)\b',
    re.IGNORECASE,
)
_RELATED_TEXT_RE = re.compile(
    r"Похожие статьи|Читайте также|Related Posts?|Вам также может понравиться|"
    r"Похожие записи|Рекомендуем прочитать",
    re.IGNORECASE,
)

_CTA_CLASS_RE = re.compile(
    r'class=["\'][^"\']*\bcta[-_]?(block|section|banner|widget|button|wrap)?\b',
    re.IGNORECASE,
)
_CTA_ACTION_RE = re.compile(r'class=["\'][^"\']*\bcall[-_]?to[-_]?action\b', re.IGNORECASE)
_CTA_TEXT_RE = re.compile(
    r"Заказать|Оставить заявку|Купить|Получить консультацию|"
    r"Связаться с нами|Получить предложение",
    re.IGNORECASE,
)

_COMMERCIAL_URL_RE = re.compile(
    r"/uslugi/|/services?/|/price[s]?/|/catalog[ue]?/|/shop/|/buy/|/order/|/tarif[fy]?/",
    re.IGNORECASE,
)

# Map check code → runner (html, page_data) -> bool
_CHECK_RUNNERS: dict[str, Any] = {}  # populated after function definitions


def detect_author_block(html: str) -> bool:
    """Detect author block presence in rendered HTML via CSS class and rel patterns."""
    return bool(
        _AUTHOR_CLASS_RE.search(html)
        or _AUTHOR_POST_RE.search(html)
        or _AUTHOR_ENTRY_RE.search(html)
        or _AUTHOR_REL_RE.search(html)
        or _AUTHOR_VCARD_RE.search(html)
    )


def detect_related_posts(html: str) -> bool:
    """Detect related posts block presence via CSS class and text patterns."""
    return bool(_RELATED_CLASS_RE.search(html) or _RELATED_TEXT_RE.search(html))


def detect_cta_block(html: str) -> bool:
    """Detect CTA (call-to-action) block presence via CSS class and button text patterns."""
    return bool(
        _CTA_CLASS_RE.search(html)
        or _CTA_ACTION_RE.search(html)
        or _CTA_TEXT_RE.search(html)
    )


def classify_content_type(page_type: str, url: str) -> str:
    """Determine content_type from page_type and URL patterns.

    Returns a ContentType value string: 'informational', 'commercial', or 'unknown'.
    """
    if page_type == "product":
        return ContentType.commercial.value
    if page_type == "article":
        return ContentType.informational.value
    if page_type == "category":
        return ContentType.commercial.value
    if page_type == "landing":
        if _COMMERCIAL_URL_RE.search(url):
            return ContentType.commercial.value
        return ContentType.informational.value
    return ContentType.unknown.value


def check_internal_links(internal_link_count: int, min_links: int = 1) -> bool:
    """Return True if page has at least min_links internal links."""
    return internal_link_count >= min_links


def run_checks_for_page(
    html: str,
    page_data: dict[str, Any],
    check_definitions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run all active checks against a page and return results.

    Args:
        html: Rendered HTML content of the page.
        page_data: Dict with keys: has_toc, has_schema, has_noindex,
                   internal_link_count, content_type, page_type, url.
        check_definitions: List of check definition dicts with keys:
                           code, is_active, applies_to, severity.

    Returns:
        List of dicts: {check_code, status, details}.
        status is 'pass', 'fail', or 'warning'.
    """
    results = []
    content_type = page_data.get("content_type", "unknown")
    if hasattr(content_type, "value"):
        content_type = content_type.value

    check_runners = {
        "toc_present": lambda h, pd: bool(pd.get("has_toc", False)),
        "schema_present": lambda h, pd: bool(pd.get("has_schema", False)),
        "author_block": lambda h, pd: detect_author_block(h),
        "related_posts": lambda h, pd: detect_related_posts(h),
        "cta_present": lambda h, pd: detect_cta_block(h),
        "internal_links": lambda h, pd: check_internal_links(pd.get("internal_link_count", 0)),
        "noindex_check": lambda h, pd: not pd.get("has_noindex", False),
    }

    for chk in check_definitions:
        if not chk.get("is_active", True):
            continue

        applies_to = chk.get("applies_to", "unknown")
        if hasattr(applies_to, "value"):
            applies_to = applies_to.value
        if applies_to not in ("unknown", content_type):
            continue

        code = chk["code"]
        runner = check_runners.get(code)
        if runner is None:
            continue

        passed = runner(html, page_data)
        severity = chk.get("severity", "warning")
        status = "pass" if passed else ("fail" if severity == "error" else "warning")

        results.append({"check_code": code, "status": status, "details": None})

    return results


# ---------------------------------------------------------------------------
# Async DB functions
# ---------------------------------------------------------------------------


async def get_active_checks(db: AsyncSession) -> list[AuditCheckDefinition]:
    """Fetch all active check definitions ordered by sort_order."""
    result = await db.execute(
        select(AuditCheckDefinition)
        .where(AuditCheckDefinition.is_active.is_(True))
        .order_by(AuditCheckDefinition.sort_order)
    )
    return list(result.scalars().all())


async def save_audit_results(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_url: str,
    results: list[dict[str, Any]],
) -> None:
    """Upsert audit results for a page via ON CONFLICT DO UPDATE."""
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
    """Fetch audit results for a site, optionally filtered by URL list.

    Ordered by page_url, check_code.
    """
    q = (
        select(AuditResult)
        .where(AuditResult.site_id == site_id)
        .order_by(AuditResult.page_url, AuditResult.check_code)
    )
    if page_urls is not None:
        q = q.where(AuditResult.page_url.in_(page_urls))
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_content_type(
    db: AsyncSession,
    page_id: uuid.UUID,
    content_type: str,
) -> None:
    """Update a page's content_type field."""
    from app.models.crawl import Page
    from sqlalchemy import update as sa_update

    await db.execute(
        sa_update(Page).where(Page.id == page_id).values(content_type=content_type)
    )
    await db.flush()


async def classify_and_update_pages(
    db: AsyncSession,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
) -> int:
    """Classify all pages of a crawl job and update their content_type.

    Returns count of pages classified.
    """
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
        p.content_type = ct
        count += 1
    await db.flush()
    return count


async def get_check_definitions(db: AsyncSession) -> list[dict[str, Any]]:
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
    db: AsyncSession,
    check_id: uuid.UUID,
    **fields: Any,
) -> AuditCheckDefinition | None:
    """Update a check definition by ID.

    Accepted fields: name, description, is_active, severity, sort_order.
    Returns the updated object or None if not found.
    """
    result = await db.execute(
        select(AuditCheckDefinition).where(AuditCheckDefinition.id == check_id)
    )
    check = result.scalar_one_or_none()
    if check is None:
        return None
    allowed_fields = {"name", "description", "is_active", "severity", "sort_order"}
    for k, v in fields.items():
        if k in allowed_fields:
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
    """Create a new user-defined check definition.

    Returns the created object.
    """
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
