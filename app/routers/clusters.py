"""Cluster router: CRUD + auto-cluster + cannibalization + CSV export."""
import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.keyword import Keyword
from app.models.user import User
from app.services import cluster_service
from app.services import cannibalization_service

router = APIRouter(prefix="/clusters", tags=["clusters"])


class ClusterCreate(BaseModel):
    name: str
    target_url: str | None = None


class ClusterUpdate(BaseModel):
    name: str | None = None
    target_url: str | None = None
    intent: str | None = None


class AssignRequest(BaseModel):
    keyword_ids: list[uuid.UUID]
    cluster_id: uuid.UUID | None = None


@router.post("/sites/{site_id}", status_code=status.HTTP_201_CREATED)
async def create_cluster(
    site_id: uuid.UUID,
    payload: ClusterCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    c = await cluster_service.create_cluster(db, site_id, payload.name, payload.target_url)
    await db.commit()
    return {"id": str(c.id), "name": c.name, "target_url": c.target_url, "intent": c.intent.value}


@router.get("/sites/{site_id}")
async def list_clusters(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    clusters = await cluster_service.list_clusters(db, site_id)
    return [
        {"id": str(c.id), "name": c.name, "target_url": c.target_url, "intent": c.intent.value}
        for c in clusters
    ]


@router.put("/{cluster_id}")
async def update_cluster(
    cluster_id: uuid.UUID,
    payload: ClusterUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    c = await cluster_service.get_cluster(db, cluster_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cluster not found")
    c = await cluster_service.update_cluster(db, c, payload.name, payload.target_url, payload.intent)
    await db.commit()
    return {"id": str(c.id), "name": c.name, "target_url": c.target_url, "intent": c.intent.value}


@router.delete("/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cluster(
    cluster_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    c = await cluster_service.get_cluster(db, cluster_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cluster not found")
    await cluster_service.delete_cluster(db, c)
    await db.commit()


@router.post("/assign")
async def assign_keywords(
    payload: AssignRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await cluster_service.assign_keywords_to_cluster(
        db, payload.keyword_ids, payload.cluster_id
    )
    await db.commit()
    return {"assigned": count, "cluster_id": str(payload.cluster_id) if payload.cluster_id else None}


@router.post("/sites/{site_id}/auto-cluster")
async def auto_cluster(
    site_id: uuid.UUID,
    min_shared: int = 3,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    proposals = await cluster_service.auto_cluster_serp_intersection(db, site_id, min_shared)
    return {"proposals": proposals, "count": len(proposals)}


@router.get("/sites/{site_id}/cannibalization")
async def cannibalization(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    items = await cluster_service.detect_cannibalization(db, site_id)
    return {"cannibalization": items, "count": len(items)}


class ResolveRequest(BaseModel):
    keyword: str
    urls: list[str]
    resolution_type: str
    primary_url: str


class StatusUpdateRequest(BaseModel):
    status: str


@router.post("/sites/{site_id}/cannibalization/resolve", status_code=status.HTTP_201_CREATED)
async def create_cannibalization_resolve(
    site_id: uuid.UUID,
    payload: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Create a resolution proposal for a cannibalized keyword."""
    r = await cannibalization_service.create_resolution(
        db,
        site_id=site_id,
        keyword=payload.keyword,
        competing_urls=payload.urls,
        resolution_type=payload.resolution_type,
        primary_url=payload.primary_url,
    )
    await db.commit()
    return {
        "id": str(r.id),
        "keyword_phrase": r.keyword_phrase,
        "resolution_type": r.resolution_type.value if hasattr(r.resolution_type, "value") else r.resolution_type,
        "primary_url": r.primary_url,
        "status": r.status.value if hasattr(r.status, "value") else r.status,
        "action_plan": r.action_plan,
    }


@router.get("/sites/{site_id}/cannibalization/resolutions")
async def list_cannibalization_resolutions(
    site_id: uuid.UUID,
    resolution_status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """List all resolution proposals for a site."""
    resolutions = await cannibalization_service.list_resolutions(db, site_id, status=resolution_status)
    return [
        {
            "id": str(r.id),
            "keyword_phrase": r.keyword_phrase,
            "competing_urls": r.competing_urls,
            "resolution_type": r.resolution_type.value if hasattr(r.resolution_type, "value") else r.resolution_type,
            "primary_url": r.primary_url,
            "action_plan": r.action_plan,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "task_id": str(r.task_id) if r.task_id else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in resolutions
    ]


@router.post("/cannibalization/resolutions/{resolution_id}/status")
async def update_resolution_status(
    resolution_id: uuid.UUID,
    payload: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Update status of a cannibalization resolution."""
    r = await cannibalization_service.update_resolution_status(db, resolution_id, payload.status)
    if not r:
        raise HTTPException(status_code=404, detail="Resolution not found")
    await db.commit()
    return {
        "id": str(r.id),
        "status": r.status.value if hasattr(r.status, "value") else r.status,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
    }


@router.post("/cannibalization/resolutions/{resolution_id}/check")
async def check_cannibalization_resolution(
    resolution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Re-check if the cannibalization issue is resolved."""
    result = await cannibalization_service.check_resolution(db, resolution_id)
    return result


@router.get("/sites/{site_id}/intent-mismatches")
async def intent_mismatches(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Find commercial clusters targeting informational pages."""
    items = await cluster_service.detect_intent_mismatches(db, site_id)
    return {"mismatches": items, "count": len(items)}


@router.get("/sites/{site_id}/export.csv")
async def export_keywords_csv(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Export all keywords with cluster labels and page mappings as CSV."""
    from app.models.cluster import KeywordCluster

    keywords = (await db.execute(
        select(Keyword).where(Keyword.site_id == site_id).order_by(Keyword.phrase)
    )).scalars().all()

    cluster_ids = {k.cluster_id for k in keywords if k.cluster_id}
    cluster_map: dict[uuid.UUID, str] = {}
    if cluster_ids:
        clusters = (await db.execute(
            select(KeywordCluster).where(KeywordCluster.id.in_(cluster_ids))
        )).scalars().all()
        cluster_map = {c.id: c.name for c in clusters}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Keyword", "Cluster", "Target URL", "Frequency", "Engine", "Region"])
    for kw in keywords:
        writer.writerow([
            kw.phrase,
            cluster_map.get(kw.cluster_id, "") if kw.cluster_id else "",
            kw.target_url or "",
            kw.frequency or "",
            kw.engine.value if kw.engine else "",
            kw.region or "",
        ])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=keywords_{site_id}.csv"},
    )


# ---- Missing-page detector ----

@router.post("/sites/{site_id}/detect-missing-pages")
async def detect_missing_pages(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Find keywords with no mapped page (no target_url and no cluster target_url).
    Auto-creates SeoTask for each.
    """
    from app.models.cluster import KeywordCluster
    from app.models.task import SeoTask, TaskType, TaskStatus

    keywords = (await db.execute(
        select(Keyword).where(
            Keyword.site_id == site_id,
            Keyword.target_url.is_(None),
        )
    )).scalars().all()

    # Filter: also check cluster target_url
    cluster_ids = {k.cluster_id for k in keywords if k.cluster_id}
    cluster_urls: dict[uuid.UUID, str | None] = {}
    if cluster_ids:
        clusters = (await db.execute(
            select(KeywordCluster).where(KeywordCluster.id.in_(cluster_ids))
        )).scalars().all()
        cluster_urls = {c.id: c.target_url for c in clusters}

    missing = []
    for kw in keywords:
        # Skip if cluster has a target URL
        if kw.cluster_id and cluster_urls.get(kw.cluster_id):
            continue

        # Check if task already exists
        existing = (await db.execute(
            select(SeoTask).where(
                SeoTask.site_id == site_id,
                SeoTask.url == kw.phrase,  # use phrase as identifier
                SeoTask.task_type == TaskType.lost_indexation,  # reuse type for now
                SeoTask.status != TaskStatus.resolved,
            )
        )).scalar_one_or_none()
        if existing:
            continue

        task = SeoTask(
            site_id=site_id,
            task_type=TaskType.lost_indexation,
            url=kw.phrase,
            title=f"Missing page: {kw.phrase}",
            description=f"Keyword '{kw.phrase}' has no mapped target page.",
        )
        db.add(task)
        missing.append(kw.phrase)

    await db.flush()
    await db.commit()
    return {"missing_pages_tasks_created": len(missing), "keywords": missing}
