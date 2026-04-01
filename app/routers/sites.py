import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import site_service
from app.services import wp_service as wp_svc

from app.tasks.crawl_tasks import crawl_site as _crawl_site_task

router = APIRouter(prefix="/sites", tags=["sites"])


class SiteCreate(BaseModel):
    name: str
    url: str
    wp_username: str
    app_password: str


class SiteUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    wp_username: str | None = None
    app_password: str | None = None


class SiteOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    wp_username: str
    connection_status: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> SiteOut:
    site = await site_service.create_site(
        db,
        name=payload.name,
        url=payload.url,
        wp_username=payload.wp_username,
        app_password=payload.app_password,
        actor_id=current_user.id,
    )
    return SiteOut.model_validate(site)


@router.get("", response_model=list[SiteOut])
async def list_sites(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[SiteOut]:
    sites = await site_service.get_sites(db)
    return [SiteOut.model_validate(s) for s in sites]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SiteOut:
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteOut.model_validate(site)


@router.put("/{site_id}", response_model=SiteOut)
async def update_site(
    site_id: uuid.UUID,
    payload: SiteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> SiteOut:
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    site = await site_service.update_site(
        db, site,
        name=payload.name,
        url=payload.url,
        wp_username=payload.wp_username,
        app_password=payload.app_password,
        actor_id=current_user.id,
    )
    return SiteOut.model_validate(site)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    await site_service.delete_site(db, site, actor_id=current_user.id)


def _status_badge(site_id: str, connection_status: str) -> str:
    css_classes = {"connected": "badge-connected", "failed": "badge-failed", "unknown": "badge-unknown"}
    css_class = css_classes.get(connection_status, "badge-unknown")
    return (
        f'<span id="status-{site_id}" class="badge {css_class}">'
        f"{connection_status}</span>"
    )


@router.patch("/{site_id}/status", response_model=SiteOut)
async def set_site_status(
    site_id: uuid.UUID,
    active: bool,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    site = await site_service.set_active_status(db, site, active, actor_id=current_user.id)
    if request.headers.get("HX-Request"):
        status_val = site.connection_status.value if hasattr(site.connection_status, "value") else site.connection_status
        disable_btn = (
            f'<form class="inline"><button class="btn btn-sm" style="background:#ef4444;color:white;margin-left:.5rem" '
            f'hx-patch="/sites/{site.id}/status?active=false" hx-target="closest tr" hx-swap="outerHTML" '
            f'hx-confirm="Disable this site?">Disable</button></form>'
            if site.is_active else
            f'<form class="inline"><button class="btn btn-sm" style="background:#22c55e;color:white;margin-left:.5rem" '
            f'hx-patch="/sites/{site.id}/status?active=true" hx-target="closest tr" hx-swap="outerHTML">Enable</button></form>'
        )
        return HTMLResponse(
            f"<tr>"
            f"<td>{site.name}</td>"
            f'<td><a href="{site.url}" target="_blank">{site.url}</a></td>'
            f"<td>{site.wp_username}</td>"
            f'<td><span id="status-{site.id}" class="badge badge-{status_val}">{status_val}</span></td>'
            f"<td>{'Yes' if site.is_active else 'No'}</td>"
            f"<td><form class='inline'><button class='btn btn-sm btn-verify' "
            f"hx-post='/sites/{site.id}/verify' hx-target='#status-{site.id}' hx-swap='outerHTML'>Verify</button></form>"
            f"{disable_btn}</td>"
            f"</tr>"
        )
    return SiteOut.model_validate(site)


@router.post("/{site_id}/crawl", status_code=status.HTTP_202_ACCEPTED)
async def trigger_crawl(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Trigger an async crawl for a site. Returns 202 with task_id."""
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    task = _crawl_site_task.delay(str(site_id))
    return {"task_id": task.id, "site_id": str(site_id)}


@router.post("/{site_id}/verify", response_class=HTMLResponse)
async def verify_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    new_status = await wp_svc.verify_connection(site)
    await site_service.set_connection_status(db, site, new_status)
    return HTMLResponse(_status_badge(str(site_id), new_status.value))
