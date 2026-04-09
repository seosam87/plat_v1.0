"""Templates router: CRUD + clone + preview for ProposalTemplate."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_any_authenticated
from app.dependencies import get_db
from app.models.client import Client
from app.models.proposal_template import TemplateType
from app.models.site import Site
from app.models.user import User
from app.services import template_service
from app.services.template_variable_resolver import (
    render_template_preview,
    resolve_template_variables,
)
from app.template_engine import templates

router = APIRouter(prefix="/ui/templates", tags=["templates"])


# ---- Helper ----


async def _get_all_clients(db: AsyncSession) -> list[Client]:
    """Return all non-deleted clients ordered by company name."""
    result = await db.execute(
        select(Client)
        .where(Client.is_deleted == False)  # noqa: E712
        .order_by(Client.company_name)
    )
    return list(result.scalars().all())


# ---- LIST (all authenticated) ----


@router.get("", response_class=HTMLResponse)
async def template_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_authenticated),
) -> HTMLResponse:
    """List all proposal templates as a card grid."""
    tmpl_list = await template_service.list_templates(db)
    return templates.TemplateResponse(
        request,
        "proposal_templates/index.html",
        {"templates": tmpl_list, "current_user": current_user},
    )


# ---- SITES dependent select (no template_id param — must be before /{template_id} routes) ----


@router.get("/sites", response_class=HTMLResponse)
async def sites_for_client(
    request: Request,
    client_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_authenticated),
) -> HTMLResponse:
    """Return <select> options for sites belonging to a client (HTMX dependent select)."""
    result = await db.execute(
        select(Site)
        .where(Site.client_id == client_id, Site.is_active == True)  # noqa: E712
        .order_by(Site.url)
    )
    sites = list(result.scalars().all())
    options_html = "\n".join(
        f'<option value="{s.id}">{s.url}</option>' for s in sites
    )
    return HTMLResponse(
        content=f'<select id="site-select" name="site_id" style="padding:0.4rem 0.5rem;border:1px solid #d1d5db;border-radius:6px;font-size:0.875rem;flex:1;">'
        f'<option value="">-- выберите сайт --</option>'
        f"{options_html}"
        f"</select>"
    )


# ---- PREVIEW (no template_id param — must be before /{template_id} routes) ----


@router.post("/preview", response_class=HTMLResponse)
async def template_preview(
    request: Request,
    body: str = Form(""),
    client_id: str = Form(""),
    site_id: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_authenticated),
) -> HTMLResponse:
    """Render a template preview with resolved variables. Returns raw HTML (no base.html wrapper)."""
    try:
        client_uuid = uuid.UUID(client_id)
        site_uuid = uuid.UUID(site_id)
    except (ValueError, AttributeError):
        return HTMLResponse(
            content='<p style="color:#dc2626;padding:24px;font-family:monospace;">Ошибка: укажите корректный клиент и сайт для превью.</p>'
        )

    context = await resolve_template_variables(db, client_uuid, site_uuid)
    rendered = render_template_preview(body, context)
    return HTMLResponse(content=rendered)


# ---- NEW TEMPLATE PAGE (admin only) ----


@router.get("/new", response_class=HTMLResponse)
async def template_new_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Render the create-template editor page."""
    clients = await _get_all_clients(db)
    return templates.TemplateResponse(
        request,
        "proposal_templates/edit.html",
        {"template": None, "clients": clients, "sites": [], "current_user": current_user},
    )


# ---- CREATE (admin only) ----


@router.post("", response_class=HTMLResponse)
async def template_create(
    request: Request,
    name: str = Form(...),
    template_type: str = Form(...),
    description: str = Form(""),
    body: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Create a new proposal template and redirect to its edit page."""
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название шаблона обязательно")

    try:
        template_type_enum = TemplateType(template_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Неверный тип шаблона: {template_type}")

    new = await template_service.create_template(
        db,
        name=name,
        template_type=template_type_enum,
        description=description.strip() or None,
        body=body,
        created_by_id=current_user.id,
    )
    await db.commit()
    logger.info("Template created: {} ({}) by user {}", new.id, name, current_user.id)
    return RedirectResponse(url=f"/ui/templates/{new.id}/edit", status_code=303)


# ---- EDIT PAGE (admin only — {template_id} after fixed routes) ----


@router.get("/{template_id}/edit", response_class=HTMLResponse)
async def template_edit_page(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Render the edit-template editor page."""
    template = await template_service.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    clients = await _get_all_clients(db)
    return templates.TemplateResponse(
        request,
        "proposal_templates/edit.html",
        {"template": template, "clients": clients, "sites": [], "current_user": current_user},
    )


# ---- UPDATE (admin only) ----


@router.post("/{template_id}", response_class=HTMLResponse)
async def template_update(
    template_id: uuid.UUID,
    request: Request,
    name: str = Form(...),
    template_type: str = Form(...),
    description: str = Form(""),
    body: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Save changes to an existing template (HTMX form submit)."""
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название шаблона обязательно")

    try:
        template_type_enum = TemplateType(template_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Неверный тип шаблона: {template_type}")

    updated = await template_service.update_template(
        db,
        template_id,
        name=name,
        template_type=template_type_enum,
        description=description.strip() or None,
        body=body,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.commit()
    logger.info("Template updated: {} by user {}", template_id, current_user.id)

    resp = HTMLResponse(content="<span>Сохранено</span>", status_code=200)
    resp.headers["HX-Trigger"] = json.dumps({"showToast": "Шаблон сохранён"})
    return resp


# ---- DELETE (admin only) ----


@router.delete("/{template_id}", response_class=HTMLResponse)
async def template_delete(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Hard-delete a template and redirect to list."""
    deleted = await template_service.delete_template(db, template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.commit()
    logger.info("Template deleted: {} by user {}", template_id, current_user.id)

    resp = HTMLResponse(content="", status_code=200)
    resp.headers["HX-Trigger"] = json.dumps({"showToast": "Шаблон удалён"})
    resp.headers["HX-Redirect"] = "/ui/templates"
    return resp


# ---- CLONE (admin only) ----


@router.post("/{template_id}/clone", response_class=HTMLResponse)
async def template_clone(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Clone a template and redirect to the clone's edit page."""
    clone = await template_service.clone_template(
        db, template_id, created_by_id=current_user.id
    )
    if clone is None:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.commit()
    logger.info("Template cloned: {} -> {} by user {}", template_id, clone.id, current_user.id)

    resp = HTMLResponse(content="", status_code=200)
    resp.headers["HX-Trigger"] = json.dumps(
        {"showToast": "Шаблон скопирован — откройте его для редактирования"}
    )
    resp.headers["HX-Redirect"] = f"/ui/templates/{clone.id}/edit"
    return resp
