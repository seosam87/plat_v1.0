"""Analytics Workspace router: keyword filters, sessions, SERP, competitors, briefs."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from app.template_engine import templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.analytics import AnalysisSession, CompetitorPageData, ContentBrief
from app.models.site import Site
from app.models.user import User
from app.services import analytics_service as ans
from app.services import brief_service as bs
from app.services import serp_analysis_service as sas

router = APIRouter(prefix="/analytics", tags=["analytics"])


class SessionCreate(BaseModel):
    name: str
    keyword_ids: list[str]
    filters_applied: dict | None = None


class CompetitorCrawlRequest(BaseModel):
    mode: str = "light"
    domain: str | None = None


class BriefCreate(BaseModel):
    target_url: str | None = None
    structure_notes: str | None = None


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


async def _get_session_or_404(db: AsyncSession, session_id: uuid.UUID) -> AnalysisSession:
    session = await ans.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ---- Page ----


@router.get("/sites/{site_id}", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    site = await _get_site_or_404(db, site_id)
    filter_options = await ans.get_filter_options(db, site_id)
    sessions = await ans.list_sessions(db, site_id)
    briefs = await bs.list_briefs(db, site_id)
    return templates.TemplateResponse("analytics/index.html", {
        "request": request,
        "site": site,
        "filter_options": filter_options,
        "sessions": sessions,
        "briefs": briefs,
    })


# ---- Filter ----


@router.get("/sites/{site_id}/keywords", response_model=None)
async def filter_keywords(
    site_id: uuid.UUID,
    search: str | None = None,
    frequency_min: int | None = None,
    frequency_max: int | None = None,
    position_min: int | None = None,
    position_max: int | None = None,
    intent: str | None = None,
    cluster_id: str | None = None,
    group_id: str | None = None,
    region: str | None = None,
    engine: str | None = None,
    has_target_url: bool | None = None,
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    items, total = await ans.filter_keywords(
        db, site_id,
        search=search,
        frequency_min=frequency_min,
        frequency_max=frequency_max,
        position_min=position_min,
        position_max=position_max,
        intent=intent,
        cluster_id=uuid.UUID(cluster_id) if cluster_id else None,
        group_id=uuid.UUID(group_id) if group_id else None,
        region=region,
        engine=engine,
        has_target_url=has_target_url,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/sites/{site_id}/filter-options")
async def filter_options(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    return await ans.get_filter_options(db, site_id)


# ---- Sessions ----


@router.post("/sites/{site_id}/sessions")
async def create_session(
    site_id: uuid.UUID,
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)
    session = await ans.create_session(
        db, site_id, body.name, body.keyword_ids, body.filters_applied
    )
    await db.commit()
    return {"id": str(session.id), "keyword_count": session.keyword_count}


@router.get("/sites/{site_id}/sessions", response_model=None)
async def list_sessions(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    sessions = await ans.list_sessions(db, site_id)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "keyword_count": s.keyword_count,
            "competitor_domain": s.competitor_domain,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    session = await _get_session_or_404(db, session_id)
    keywords = await ans.get_session_keywords(db, session_id)
    return {
        "id": str(session.id),
        "name": session.name,
        "status": session.status.value if hasattr(session.status, "value") else session.status,
        "keyword_count": session.keyword_count,
        "competitor_domain": session.competitor_domain,
        "filters_applied": session.filters_applied,
        "keywords": keywords,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    deleted = await ans.delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.commit()
    return {"status": "deleted"}


# ---- Workflow triggers ----


@router.post("/sessions/{session_id}/check-positions")
async def trigger_check_positions(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_session_or_404(db, session_id)
    from app.tasks.analytics_tasks import check_group_positions
    task = check_group_positions.delay(str(session_id))
    return {"task_id": task.id, "status": "started"}


@router.post("/sessions/{session_id}/parse-serp")
async def trigger_serp_parse(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_session_or_404(db, session_id)
    from app.tasks.analytics_tasks import parse_group_serp
    task = parse_group_serp.delay(str(session_id))
    return {"task_id": task.id, "status": "started"}


@router.post("/sessions/{session_id}/crawl-competitor")
async def trigger_competitor_crawl(
    session_id: uuid.UUID,
    body: CompetitorCrawlRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    session = await _get_session_or_404(db, session_id)
    if body.domain:
        await ans.set_session_competitor(db, session_id, body.domain)
        await db.commit()
    if not session.competitor_domain and not body.domain:
        raise HTTPException(status_code=400, detail="No competitor domain set")
    from app.tasks.analytics_tasks import crawl_competitor_pages
    task = crawl_competitor_pages.delay(str(session_id), body.mode)
    return {"task_id": task.id, "status": "started", "mode": body.mode}


@router.post("/sessions/{session_id}/set-competitor")
async def set_competitor(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    body = await request.json()
    domain = body.get("domain", "")
    if not domain:
        raise HTTPException(status_code=400, detail="domain required")
    await ans.set_session_competitor(db, session_id, domain)
    await db.commit()
    return {"status": "updated", "competitor_domain": domain}


# ---- Results ----


@router.get("/sessions/{session_id}/serp-summary")
async def serp_summary(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    session = await _get_session_or_404(db, session_id)
    site = await _get_site_or_404(db, session.site_id)
    our_domain = site.url.replace("https://", "").replace("http://", "").split("/")[0]
    return await sas.get_session_serp_summary(db, session_id, our_domain)


@router.get("/sessions/{session_id}/competitor-data", response_model=None)
async def competitor_data(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    result = await db.execute(
        select(CompetitorPageData).where(CompetitorPageData.session_id == session_id)
    )
    pages = result.scalars().all()
    return [
        {
            "url": p.url,
            "domain": p.domain,
            "title": p.title,
            "h1": p.h1,
            "meta_description": p.meta_description,
            "word_count": p.word_count,
            "has_schema": p.has_schema,
            "has_toc": p.has_toc,
            "internal_link_count": p.internal_link_count,
            "headings_json": p.headings_json,
            "crawl_mode": p.crawl_mode,
        }
        for p in pages
    ]


@router.get("/sessions/{session_id}/comparison", response_model=None)
async def comparison(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Our pages vs competitor side-by-side comparison."""
    session = await _get_session_or_404(db, session_id)

    # Get competitor pages
    comp_result = await db.execute(
        select(CompetitorPageData).where(CompetitorPageData.session_id == session_id)
    )
    comp_pages = comp_result.scalars().all()

    # Get our pages (from crawl data matching keyword target_urls)
    from app.models.crawl import Page
    from app.models.keyword import Keyword

    kw_uuids = [uuid.UUID(kid) for kid in session.keyword_ids]
    kw_result = await db.execute(
        select(Keyword.target_url).where(
            Keyword.id.in_(kw_uuids), Keyword.target_url != None  # noqa: E711
        ).distinct()
    )
    our_urls = [r[0] for r in kw_result.all() if r[0]]

    our_pages = []
    for url in our_urls[:20]:
        page = (await db.execute(
            select(Page).where(Page.site_id == session.site_id, Page.url == url)
            .order_by(Page.crawled_at.desc()).limit(1)
        )).scalar_one_or_none()
        if page:
            our_pages.append({
                "url": page.url,
                "title": page.title,
                "h1": page.h1,
                "meta_description": page.meta_description,
                "has_schema": page.has_schema,
                "has_toc": page.has_toc,
                "word_count": page.word_count,
                "internal_link_count": page.internal_link_count,
            })

    return {
        "our_pages": our_pages,
        "competitor_pages": [
            {
                "url": p.url,
                "title": p.title,
                "h1": p.h1,
                "meta_description": p.meta_description,
                "has_schema": p.has_schema,
                "has_toc": p.has_toc,
                "word_count": p.word_count,
                "internal_link_count": p.internal_link_count,
            }
            for p in comp_pages
        ],
        "competitor_domain": session.competitor_domain,
    }


# ---- Briefs ----


@router.post("/sessions/{session_id}/brief")
async def create_brief(
    session_id: uuid.UUID,
    body: BriefCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    brief = await bs.generate_brief(db, session_id, body.target_url, body.structure_notes)
    await db.commit()
    return {"id": str(brief.id), "title": brief.title}


@router.get("/briefs/{brief_id}")
async def get_brief(
    brief_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    brief = await bs.get_brief(db, brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    return {
        "id": str(brief.id),
        "title": brief.title,
        "target_url": brief.target_url,
        "recommended_title": brief.recommended_title,
        "recommended_h1": brief.recommended_h1,
        "recommended_meta": brief.recommended_meta,
        "keywords_json": brief.keywords_json,
        "headings_json": brief.headings_json,
        "structure_notes": brief.structure_notes,
        "competitor_data_json": brief.competitor_data_json,
        "created_at": brief.created_at.isoformat() if brief.created_at else None,
    }


@router.get("/briefs/{brief_id}/view", response_class=HTMLResponse)
async def brief_detail_view(
    request: Request,
    brief_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTML detail view for a content brief (Phase 16 LLM-04).

    Renders brief metadata + AI Suggestions block (visible when user has Anthropic key).
    Does NOT modify brief_service.py — LLM-03 invariant.
    """
    from sqlalchemy import select as _select
    from app.models.llm_brief_job import LLMBriefJob

    brief = await bs.get_brief(db, brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")

    # Check for latest accepted LLM job for auto-show on reload
    accepted_job_result = await db.execute(
        _select(LLMBriefJob)
        .where(LLMBriefJob.brief_id == brief_id, LLMBriefJob.status == "accepted")
        .order_by(LLMBriefJob.created_at.desc())
        .limit(1)
    )
    accepted_job = accepted_job_result.scalar_one_or_none()

    return templates.TemplateResponse(
        request,
        "analytics/brief_detail.html",
        {
            "brief": brief,
            "current_user": current_user,
            "accepted_job": accepted_job,
        },
    )


@router.get("/briefs/{brief_id}/export", response_class=PlainTextResponse)
async def export_brief(
    brief_id: uuid.UUID,
    format: str = "text",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    if format == "csv":
        content = await bs.export_brief_csv(db, brief_id)
        return PlainTextResponse(content, media_type="text/csv",
                                  headers={"Content-Disposition": f"attachment; filename=brief_{brief_id}.csv"})
    content = await bs.export_brief_text(db, brief_id)
    if not content:
        raise HTTPException(status_code=404, detail="Brief not found")
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8",
                              headers={"Content-Disposition": f"attachment; filename=brief_{brief_id}.txt"})


@router.get("/sites/{site_id}/briefs", response_model=None)
async def list_briefs(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    briefs = await bs.list_briefs(db, site_id)
    return [
        {
            "id": str(b.id),
            "title": b.title,
            "target_url": b.target_url,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in briefs
    ]


@router.delete("/briefs/{brief_id}")
async def delete_brief(
    brief_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    deleted = await bs.delete_brief(db, brief_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Brief not found")
    await db.commit()
    return {"status": "deleted"}


# ---- Session export ----


@router.get("/sessions/{session_id}/export", response_class=PlainTextResponse)
async def export_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    keywords = await ans.get_session_keywords(db, session_id)
    if not keywords:
        raise HTTPException(status_code=404, detail="Session not found or empty")
    csv_str = ans.export_session_keywords_csv(keywords)
    return PlainTextResponse(
        csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"},
    )
