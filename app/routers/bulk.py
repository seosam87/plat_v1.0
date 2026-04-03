"""Bulk Operations router: batch move, assign, delete, export, import."""
import shutil
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.site import Site
from app.models.user import User
from app.services import analytics_service as ans
from app.services import bulk_service as bs

router = APIRouter(prefix="/bulk", tags=["bulk"])
templates = Jinja2Templates(directory="app/templates")


class BulkMoveGroup(BaseModel):
    keyword_ids: list[str]
    group_id: str | None = None


class BulkMoveCluster(BaseModel):
    keyword_ids: list[str]
    cluster_id: str | None = None


class BulkAssignUrl(BaseModel):
    keyword_ids: list[str]
    target_url: str


class BulkDelete(BaseModel):
    keyword_ids: list[str]


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/{site_id}", response_class=HTMLResponse)
async def bulk_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    site = await _get_site_or_404(db, site_id)
    filter_options = await ans.get_filter_options(db, site_id)
    return templates.TemplateResponse("bulk/index.html", {
        "request": request,
        "site": site,
        "filter_options": filter_options,
    })


@router.post("/{site_id}/move-group")
async def move_to_group(
    site_id: uuid.UUID,
    body: BulkMoveGroup,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await bs.bulk_move_to_group(
        db, [uuid.UUID(kid) for kid in body.keyword_ids],
        uuid.UUID(body.group_id) if body.group_id else None,
    )
    await db.commit()
    return {"moved": count}


@router.post("/{site_id}/move-cluster")
async def move_to_cluster(
    site_id: uuid.UUID,
    body: BulkMoveCluster,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await bs.bulk_move_to_cluster(
        db, [uuid.UUID(kid) for kid in body.keyword_ids],
        uuid.UUID(body.cluster_id) if body.cluster_id else None,
    )
    await db.commit()
    return {"moved": count}


@router.post("/{site_id}/assign-url")
async def assign_url(
    site_id: uuid.UUID,
    body: BulkAssignUrl,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await bs.bulk_assign_target_url(
        db, [uuid.UUID(kid) for kid in body.keyword_ids], body.target_url,
    )
    await db.commit()
    return {"assigned": count}


@router.post("/{site_id}/delete")
async def delete_keywords(
    site_id: uuid.UUID,
    body: BulkDelete,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await bs.bulk_delete(db, [uuid.UUID(kid) for kid in body.keyword_ids])
    await db.commit()
    return {"deleted": count}


@router.get("/{site_id}/export")
async def export_keywords(
    site_id: uuid.UUID,
    format: str = "csv",
    search: str | None = None,
    frequency_min: int | None = None,
    frequency_max: int | None = None,
    cluster_id: str | None = None,
    group_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    filters: dict = {}
    if search:
        filters["search"] = search
    if frequency_min is not None:
        filters["frequency_min"] = frequency_min
    if frequency_max is not None:
        filters["frequency_max"] = frequency_max
    if cluster_id:
        filters["cluster_id"] = cluster_id
    if group_id:
        filters["group_id"] = group_id

    if format == "xlsx":
        data = await bs.export_keywords_xlsx(db, site_id, **filters)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=keywords_{site_id}.xlsx"},
        )
    data = await bs.export_keywords_csv(db, site_id, **filters)
    return PlainTextResponse(
        data, media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=keywords_{site_id}.csv"},
    )


@router.post("/{site_id}/import")
async def import_keywords(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    on_duplicate: str = Form("skip"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    suffix = Path(file.filename or "file.csv").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        result = await bs.import_keywords_with_log(
            db, site_id, tmp_path, on_duplicate, user_id=user.id,
        )
        await db.commit()
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)
