"""Content Audit router: audit pages, check definitions, schema templates, CTA."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from app.template_engine import templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.audit import AuditCheckDefinition, SchemaTemplate
from app.models.crawl import Page
from app.models.site import Site
from app.models.user import User
from app.models.wp_content_job import JobStatus
from app.services import content_audit_service as cas
from app.services import schema_service as ss
from app.services import audit_fix_service as afs

router = APIRouter(prefix="/audit", tags=["audit"])


class ContentTypeUpdate(BaseModel):
    content_type: str


class FixRequest(BaseModel):
    page_url: str
    fix_action: str
    wp_post_id: int | None = None


class CheckCreate(BaseModel):
    code: str
    name: str
    applies_to: str = "unknown"
    severity: str = "warning"
    auto_fixable: bool = False
    fix_action: str | None = None


class TemplateCreate(BaseModel):
    schema_type: str
    name: str
    template_json: str


class CtaUpdate(BaseModel):
    cta_html: str


async def _get_site_or_404(
    db: AsyncSession, site_id: uuid.UUID
) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ---- Page endpoints ----


@router.get("/{site_id}", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    site_id: uuid.UUID,
    search: str = "",
    content_type: str = "all",
    status: str = "all",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Main audit page for a site."""
    site = await _get_site_or_404(db, site_id)

    # Get latest crawl pages (deduplicated by URL)
    result = await db.execute(
        select(Page)
        .where(Page.site_id == site_id, Page.http_status == 200)
        .order_by(Page.crawled_at.desc())
    )
    all_pages = result.scalars().all()
    seen_urls: set[str] = set()
    unique_pages = []
    for p in all_pages:
        if p.url not in seen_urls:
            seen_urls.add(p.url)
            unique_pages.append(p)

    # Get audit results
    page_urls = [p.url for p in unique_pages]
    audit_results = await cas.get_audit_results_for_site(db, site_id, page_urls)

    # Build results lookup: {url: {check_code: status}}
    results_map: dict[str, dict[str, str]] = {}
    for ar in audit_results:
        results_map.setdefault(ar.page_url, {})[ar.check_code] = ar.status

    # Get check definitions
    check_defs = await cas.get_check_definitions(db)

    # Get schema templates
    schema_templates = await ss.get_all_templates(db, site_id)

    # Pagination
    per_page = 50
    total = len(unique_pages)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_pages = unique_pages[start:end]

    # Count stats
    pages_with_issues = sum(
        1 for url in page_urls
        if any(v in ("fail", "warning") for v in results_map.get(url, {}).values())
    )
    pages_all_pass = sum(
        1 for url in page_urls
        if results_map.get(url) and all(v == "pass" for v in results_map[url].values())
    )
    pages_unchecked = total - len(set(r.page_url for r in audit_results))

    return templates.TemplateResponse(
        "audit/index.html",
        {
            "request": request,
            "site": site,
            "pages": paginated_pages,
            "results_map": results_map,
            "check_defs": check_defs,
            "schema_templates": schema_templates,
            "total_pages": total,
            "pages_with_issues": pages_with_issues,
            "pages_all_pass": pages_all_pass,
            "pages_unchecked": pages_unchecked,
            "current_page": page,
            "per_page": per_page,
            "search": search,
            "content_type_filter": content_type,
            "status_filter": status,
        },
    )


@router.post("/{site_id}/run")
async def trigger_audit(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Trigger batch audit via Celery task."""
    site = await _get_site_or_404(db, site_id)
    from app.tasks.audit_tasks import run_site_audit

    task = run_site_audit.delay(str(site_id))
    return {"task_id": task.id, "status": "started"}


@router.post("/{site_id}/run-single")
async def run_single_audit(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Run audit on a single page URL."""
    site = await _get_site_or_404(db, site_id)
    body = await request.json()
    page_url = body.get("page_url", "")

    if not page_url:
        raise HTTPException(status_code=400, detail="page_url required")

    # Get page data from latest crawl
    result = await db.execute(
        select(Page)
        .where(Page.site_id == site_id, Page.url == page_url)
        .order_by(Page.crawled_at.desc())
        .limit(1)
    )
    page_row = result.scalar_one_or_none()
    if not page_row:
        raise HTTPException(status_code=404, detail="Page not found in crawl data")

    # Fetch HTML from WP if possible
    html = ""
    try:
        from app.tasks.wp_content_tasks import _fetch_wp_content

        html = _fetch_wp_content(str(site_id), page_row.url) or ""
    except Exception:
        pass

    page_data = {
        "has_toc": page_row.has_toc,
        "has_schema": page_row.has_schema,
        "has_noindex": page_row.has_noindex,
        "internal_link_count": page_row.internal_link_count,
        "content_type": page_row.content_type.value
        if hasattr(page_row.content_type, "value")
        else page_row.content_type,
        "page_type": page_row.page_type.value
        if hasattr(page_row.page_type, "value")
        else page_row.page_type,
        "url": page_row.url,
    }

    checks = await cas.get_check_definitions(db)
    results = cas.run_checks_for_page(html, page_data, checks)
    await cas.save_audit_results(db, site_id, page_url, results)
    await db.commit()

    return {"page_url": page_url, "results": results}


@router.put("/{site_id}/pages/{page_id}/content-type")
async def set_content_type(
    site_id: uuid.UUID,
    page_id: uuid.UUID,
    body: ContentTypeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Manually set content_type for a page."""
    await cas.update_content_type(db, page_id, body.content_type)
    await db.commit()
    return {"status": "updated"}


# ---- Check definition endpoints ----


@router.get("/checks", response_model=None)
async def list_checks(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    return await cas.get_check_definitions(db)


@router.post("/checks")
async def create_check(
    body: CheckCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    check = await cas.create_check_definition(
        db,
        code=body.code,
        name=body.name,
        applies_to=body.applies_to,
        severity=body.severity,
        auto_fixable=body.auto_fixable,
        fix_action=body.fix_action,
    )
    await db.commit()
    return {"id": str(check.id), "code": check.code}


@router.put("/checks/{check_id}")
async def update_check(
    check_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    body = await request.json()
    check = await cas.update_check_definition(db, check_id, **body)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    await db.commit()
    return {"status": "updated", "id": str(check.id)}


@router.delete("/checks/{check_id}")
async def deactivate_check(
    check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    check = await cas.update_check_definition(db, check_id, is_active=False)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    await db.commit()
    return {"status": "deactivated"}


# ---- Schema template endpoints ----


@router.get("/{site_id}/templates", response_model=None)
async def list_templates(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    tpls = await ss.get_all_templates(db, site_id)
    return [
        {
            "id": str(t.id),
            "site_id": str(t.site_id) if t.site_id else None,
            "schema_type": t.schema_type,
            "name": t.name,
            "template_json": t.template_json,
            "is_default": t.is_default,
        }
        for t in tpls
    ]


@router.post("/{site_id}/templates")
async def create_template(
    site_id: uuid.UUID,
    body: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    tpl = await ss.create_site_template(
        db, site_id, body.schema_type, body.name, body.template_json
    )
    await db.commit()
    return {"id": str(tpl.id), "schema_type": tpl.schema_type}


@router.delete("/{site_id}/templates/{template_id}")
async def delete_template(
    site_id: uuid.UUID,
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    deleted = await ss.delete_site_template(db, template_id)
    if not deleted:
        raise HTTPException(status_code=400, detail="Cannot delete system default template")
    await db.commit()
    return {"status": "deleted"}


# ---- CTA endpoint ----


@router.put("/{site_id}/cta")
async def save_cta(
    site_id: uuid.UUID,
    body: CtaUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    site = await _get_site_or_404(db, site_id)
    site.cta_template_html = body.cta_html
    await db.flush()
    await db.commit()
    return {"status": "saved"}


# ---- Audit results endpoint ----


@router.get("/{site_id}/results", response_model=None)
async def get_results(
    site_id: uuid.UUID,
    page_url: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    urls = [page_url] if page_url else None
    results = await cas.get_audit_results_for_site(db, site_id, urls)
    return [
        {
            "id": str(r.id),
            "page_url": r.page_url,
            "check_code": r.check_code,
            "status": r.status,
            "details": r.details,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in results
    ]


# ---- Fix endpoints ----


_FIX_ACTION_TO_CHECK = {
    "inject_toc": "toc_present",
    "inject_schema": "schema_present",
    "inject_cta": "cta_present",
    "inject_links": "internal_links",
}


async def _get_fix_result(
    db: AsyncSession, site_id: uuid.UUID, body: FixRequest
) -> dict:
    """Generate a fix result for preview or apply."""
    site = await _get_site_or_404(db, site_id)

    # Fetch HTML
    html = ""
    try:
        from app.tasks.wp_content_tasks import _fetch_wp_content
        html = _fetch_wp_content(str(site_id), body.page_url) or ""
    except Exception:
        pass

    if not html:
        return {"error": "Could not fetch page HTML"}

    fix_result = None
    if body.fix_action == "inject_toc":
        fix_result = afs.generate_toc_fix(html)
    elif body.fix_action == "inject_cta":
        fix_result = afs.generate_cta_fix(html, site.cta_template_html or "")
    elif body.fix_action == "inject_schema":
        # Get page data for schema rendering
        page_result = await db.execute(
            select(Page)
            .where(Page.site_id == site_id, Page.url == body.page_url)
            .order_by(Page.crawled_at.desc())
            .limit(1)
        )
        page_row = page_result.scalar_one_or_none()
        if page_row:
            ct = page_row.content_type.value if hasattr(page_row.content_type, "value") else page_row.content_type
            pt = page_row.page_type.value if hasattr(page_row.page_type, "value") else page_row.page_type
            page_data = ss.get_page_data_for_schema(
                title=page_row.title or "",
                url=page_row.url,
                description=page_row.meta_description or "",
                site_name=site.name,
            )
            schema_tag = await ss.render_schema_for_page(db, site_id, page_data, ct, pt)
            if schema_tag:
                fix_result = afs.generate_schema_fix(html, schema_tag)
    elif body.fix_action == "inject_links":
        from app.models.keyword import Keyword
        kws = (await db.execute(
            select(Keyword).where(
                Keyword.site_id == site_id,
                Keyword.target_url != None,
            )
        )).scalars().all()
        kw_urls = [{"phrase": k.phrase, "url": k.target_url} for k in kws if k.target_url]
        if kw_urls:
            fix_result = afs.generate_links_fix(html, kw_urls)

    if not fix_result:
        return {"error": "No fix available for this action"}

    integrity = afs.verify_html_integrity(html, fix_result["processed_html"])
    return {
        "original_html": html,
        "fix_result": fix_result,
        "integrity": integrity,
    }


@router.post("/{site_id}/fix/preview")
async def fix_preview(
    site_id: uuid.UUID,
    body: FixRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Generate a fix preview without applying."""
    result = await _get_fix_result(db, site_id, body)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "diff": result["fix_result"]["diff"],
        "valid": result["integrity"]["valid"],
        "warnings": result["integrity"]["warnings"],
    }


@router.post("/{site_id}/fix/apply")
async def fix_apply(
    site_id: uuid.UUID,
    body: FixRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Apply a fix — create pipeline job in awaiting_approval."""
    result = await _get_fix_result(db, site_id, body)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    job = await afs.create_fix_job(
        db,
        site_id=site_id,
        page_url=body.page_url,
        wp_post_id=body.wp_post_id,
        original_html=result["original_html"],
        processed_html=result["fix_result"]["processed_html"],
        fix_action=body.fix_action,
    )

    check_code = _FIX_ACTION_TO_CHECK.get(body.fix_action)
    if check_code:
        await afs.mark_audit_fixed(db, site_id, body.page_url, check_code, job.id)

    await db.commit()
    return {"job_id": str(job.id), "status": "awaiting_approval"}


@router.post("/{site_id}/fix/apply-and-approve")
async def fix_apply_and_approve(
    site_id: uuid.UUID,
    body: FixRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Apply fix + auto-approve + dispatch push."""
    result = await _get_fix_result(db, site_id, body)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    job = await afs.create_fix_job(
        db,
        site_id=site_id,
        page_url=body.page_url,
        wp_post_id=body.wp_post_id,
        original_html=result["original_html"],
        processed_html=result["fix_result"]["processed_html"],
        fix_action=body.fix_action,
    )
    job.status = JobStatus.approved
    await db.flush()

    check_code = _FIX_ACTION_TO_CHECK.get(body.fix_action)
    if check_code:
        await afs.mark_audit_fixed(db, site_id, body.page_url, check_code, job.id)

    await db.commit()

    from app.tasks.wp_content_tasks import push_to_wp
    task = push_to_wp.delay(str(job.id))

    return {"job_id": str(job.id), "status": "approved", "push_task_id": task.id}
