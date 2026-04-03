"""Gap Analysis router: gap detection, import, keywords, groups, proposals."""
import shutil
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from app.template_engine import templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.gap import GapKeyword, GapProposal
from app.models.site import Site
from app.models.user import User
from app.services import gap_service as gs

router = APIRouter(prefix="/gap", tags=["gap"])


class DetectRequest(BaseModel):
    session_id: str
    competitor_domain: str


class GroupCreate(BaseModel):
    name: str


class GroupAssign(BaseModel):
    keyword_ids: list[str]
    group_id: str


class BulkIds(BaseModel):
    keyword_ids: list[str]


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ---- Score formula ----


@router.get("/score-formula")
async def score_formula(_: User = Depends(require_admin)) -> dict:
    return {"formula": gs.SCORE_FORMULA_DESCRIPTION}


# ---- Page ----


@router.get("/{site_id}", response_class=HTMLResponse)
async def gap_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    site = await _get_site_or_404(db, site_id)
    keywords, total = await gs.list_gap_keywords(db, site_id, limit=200)
    groups = await gs.list_gap_groups(db, site_id)
    proposals = await gs.list_proposals(db, site_id)

    # Get sessions for dropdown
    from app.services.analytics_service import list_sessions
    sessions = await list_sessions(db, site_id)

    avg_score = 0.0
    if keywords:
        scores = [k["potential_score"] for k in keywords if k["potential_score"]]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    return templates.TemplateResponse("gap/index.html", {
        "request": request,
        "site": site,
        "keywords": keywords,
        "total_keywords": total,
        "groups": groups,
        "proposals": proposals,
        "sessions": sessions,
        "avg_score": avg_score,
        "score_formula": gs.SCORE_FORMULA_DESCRIPTION,
    })


# ---- Detection ----


@router.post("/{site_id}/detect")
async def detect_gaps(
    site_id: uuid.UUID,
    body: DetectRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)
    gaps = await gs.detect_gaps_from_session(
        db, site_id, uuid.UUID(body.session_id), body.competitor_domain
    )
    saved = await gs.save_gap_keywords(db, site_id, body.competitor_domain, gaps, source="serp")
    await db.commit()
    return {"gaps_detected": len(gaps), "saved": saved}


@router.post("/{site_id}/import")
async def import_keywords(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    competitor_domain: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)

    suffix = Path(file.filename or "file.csv").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = await gs.import_competitor_keywords(db, site_id, competitor_domain, tmp_path)
        await db.commit()
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---- Keywords ----


@router.get("/{site_id}/keywords", response_model=None)
async def list_keywords(
    site_id: uuid.UUID,
    competitor_domain: str | None = None,
    group_id: str | None = None,
    min_score: float | None = None,
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    items, total = await gs.list_gap_keywords(
        db, site_id,
        competitor_domain=competitor_domain,
        group_id=uuid.UUID(group_id) if group_id else None,
        min_score=min_score,
        limit=limit, offset=offset,
    )
    return {"items": items, "total": total}


@router.delete("/{site_id}/keywords")
async def delete_keywords(
    site_id: uuid.UUID,
    body: BulkIds,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    deleted = await gs.delete_gap_keywords(db, [uuid.UUID(kid) for kid in body.keyword_ids])
    await db.commit()
    return {"deleted": deleted}


# ---- Groups ----


@router.post("/{site_id}/groups")
async def create_group(
    site_id: uuid.UUID,
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    group = await gs.create_gap_group(db, site_id, body.name)
    await db.commit()
    return {"id": str(group.id), "name": group.name}


@router.get("/{site_id}/groups", response_model=None)
async def list_groups(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    groups = await gs.list_gap_groups(db, site_id)
    return [{"id": str(g.id), "name": g.name} for g in groups]


@router.put("/{site_id}/groups/assign")
async def assign_to_group(
    site_id: uuid.UUID,
    body: GroupAssign,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await gs.assign_to_group(
        db, [uuid.UUID(kid) for kid in body.keyword_ids], uuid.UUID(body.group_id)
    )
    await db.commit()
    return {"assigned": count}


@router.delete("/{site_id}/groups/{group_id}")
async def delete_group(
    site_id: uuid.UUID,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    deleted = await gs.delete_gap_group(db, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.commit()
    return {"status": "deleted"}


# ---- Proposals ----


@router.post("/{site_id}/proposals")
async def create_proposals(
    site_id: uuid.UUID,
    body: BulkIds,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    proposals = await gs.create_proposals_from_gaps(
        db, site_id, [uuid.UUID(kid) for kid in body.keyword_ids]
    )
    await db.commit()
    return {"created": len(proposals)}


@router.get("/{site_id}/proposals", response_model=None)
async def list_proposals(
    site_id: uuid.UUID,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    proposals = await gs.list_proposals(db, site_id, status)
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "target_phrase": p.target_phrase,
            "frequency": p.frequency,
            "potential_score": p.potential_score,
            "status": p.status.value if hasattr(p.status, "value") else p.status,
            "notes": p.notes,
        }
        for p in proposals
    ]


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    project_id = body.get("project_id")
    p = await gs.approve_proposal(
        db, proposal_id, uuid.UUID(project_id) if project_id else None
    )
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await db.commit()
    return {"status": "approved"}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    p = await gs.reject_proposal(db, proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await db.commit()
    return {"status": "rejected"}
