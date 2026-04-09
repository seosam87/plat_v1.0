"""CRM router: client list, create/edit modal, CRUD, contacts, interactions."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_any_authenticated, require_manager_or_above
from app.dependencies import get_db
from app.models.client import ClientContact, ClientInteraction
from app.models.site import Site
from app.models.user import User, UserRole
from app.services import client_service
from app.services.audit_service import log_action
from app.template_engine import templates

router = APIRouter(prefix="/ui/crm", tags=["crm"])


async def _get_managers(db: AsyncSession) -> list[User]:
    """Fetch users with admin or manager role for dropdown filters."""
    result = await db.execute(
        select(User).where(User.role.in_([UserRole.admin, UserRole.manager]))
    )
    return list(result.scalars().all())


# ---- Client list page ----


@router.get("/clients", response_class=HTMLResponse)
async def client_list(
    request: Request,
    search: str | None = Query(None),
    manager_id: uuid.UUID | None = Query(None),
    created_from: date | None = Query(None),
    created_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    partial: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_authenticated),
) -> HTMLResponse:
    clients, total = await client_service.list_clients(
        db,
        search=search,
        manager_id=manager_id,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=25,
    )
    managers = await _get_managers(db)
    page_size = 25
    total_pages = max(1, (total + page_size - 1) // page_size)

    ctx = {
        "clients": clients,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "search": search or "",
        "manager_id": manager_id,
        "created_from": created_from,
        "created_to": created_to,
        "managers": managers,
    }

    if partial == "true":
        return templates.TemplateResponse(
            request, "crm/_client_rows.html", ctx
        )
    return templates.TemplateResponse(request, "crm/index.html", ctx)


# ---- Modal fragments ----


@router.get("/clients/new", response_class=HTMLResponse)
async def client_new_modal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    managers = await _get_managers(db)
    return templates.TemplateResponse(
        request, "crm/_modal_client.html", {"client": None, "managers": managers}
    )


@router.get("/clients/{client_id}/edit", response_class=HTMLResponse)
async def client_edit_modal(
    client_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    client = await client_service.get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    managers = await _get_managers(db)
    return templates.TemplateResponse(
        request, "crm/_modal_client.html", {"client": client, "managers": managers}
    )


# ---- CRUD endpoints ----


def _parse_form_data(
    company_name: str,
    legal_name: str,
    inn: str,
    kpp: str,
    phone: str,
    email: str,
    manager_id_str: str,
    notes: str,
) -> dict:
    """Convert form strings to a dict suitable for service layer."""
    mid: uuid.UUID | None = None
    if manager_id_str and manager_id_str.strip():
        try:
            mid = uuid.UUID(manager_id_str.strip())
        except ValueError:
            mid = None
    return {
        "company_name": company_name.strip(),
        "legal_name": legal_name.strip() or None,
        "inn": inn.strip() or None,
        "kpp": kpp.strip() or None,
        "phone": phone.strip() or None,
        "email": email.strip() or None,
        "manager_id": mid,
        "notes": notes.strip() or None,
    }


@router.post("/clients", response_class=HTMLResponse)
async def create_client(
    request: Request,
    company_name: str = Form(...),
    legal_name: str = Form(""),
    inn: str = Form(""),
    kpp: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    manager_id: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    data = _parse_form_data(company_name, legal_name, inn, kpp, phone, email, manager_id, notes)
    client = await client_service.create_client(db, data)
    await log_action(
        db,
        action="create",
        user_id=current_user.id,
        entity_type="client",
        entity_id=str(client.id),
        detail={"company_name": client.company_name},
    )
    await db.commit()
    logger.info("Client created: {} by user {}", client.company_name, current_user.id)
    resp = HTMLResponse(content="", status_code=200)
    resp.headers["HX-Trigger"] = '{"showToast": "\\u041a\\u043b\\u0438\\u0435\\u043d\\u0442 \\u0441\\u043e\\u0437\\u0434\\u0430\\u043d", "closeModal": true, "refreshClientList": true}'
    return resp


@router.put("/clients/{client_id}", response_class=HTMLResponse)
async def update_client(
    client_id: uuid.UUID,
    request: Request,
    company_name: str = Form(...),
    legal_name: str = Form(""),
    inn: str = Form(""),
    kpp: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    manager_id: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    data = _parse_form_data(company_name, legal_name, inn, kpp, phone, email, manager_id, notes)
    client = await client_service.update_client(db, client_id, data)
    await log_action(
        db,
        action="update",
        user_id=current_user.id,
        entity_type="client",
        entity_id=str(client.id),
        detail={"company_name": client.company_name},
    )
    await db.commit()
    logger.info("Client updated: {} by user {}", client.company_name, current_user.id)
    resp = HTMLResponse(content="", status_code=200)
    resp.headers["HX-Trigger"] = '{"showToast": "\\u041a\\u043b\\u0438\\u0435\\u043d\\u0442 \\u043e\\u0431\\u043d\\u043e\\u0432\\u043b\\u0451\\u043d", "closeModal": true, "refreshClientList": true}'
    return resp


@router.delete("/clients/{client_id}", response_class=HTMLResponse)
async def delete_client(
    client_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    await client_service.delete_client(db, client_id)
    await log_action(
        db,
        action="delete",
        user_id=current_user.id,
        entity_type="client",
        entity_id=str(client_id),
    )
    await db.commit()
    logger.info("Client deleted: {} by user {}", client_id, current_user.id)
    # Return refreshed table body
    clients, total = await client_service.list_clients(db, page=1, page_size=25)
    managers = await _get_managers(db)
    page_size = 25
    total_pages = max(1, (total + page_size - 1) // page_size)
    return templates.TemplateResponse(
        request,
        "crm/_client_rows.html",
        {
            "clients": clients,
            "total": total,
            "page": 1,
            "page_size": page_size,
            "total_pages": total_pages,
            "search": "",
            "manager_id": None,
            "created_from": None,
            "created_to": None,
            "managers": managers,
        },
    )


# ---- Client detail page ----


@router.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_detail(
    client_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_authenticated),
) -> HTMLResponse:
    client = await client_service.get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Fetch contacts
    result = await db.execute(
        select(ClientContact)
        .where(ClientContact.client_id == client_id)
        .order_by(ClientContact.name)
    )
    contacts = list(result.scalars().all())

    # Fetch interactions with authors
    interactions, _total = await client_service.list_interactions(
        db, client_id, page=1, page_size=50
    )
    # Prefetch authors for interactions
    author_ids = {i.author_id for i in interactions if i.author_id}
    authors_map: dict[uuid.UUID, User] = {}
    if author_ids:
        author_result = await db.execute(
            select(User).where(User.id.in_(author_ids))
        )
        for u in author_result.scalars().all():
            authors_map[u.id] = u

    # Fetch linked sites
    sites_result = await db.execute(
        select(Site).where(Site.client_id == client_id, Site.is_active == True)  # noqa: E712
    )
    sites = list(sites_result.scalars().all())

    # Fetch counts
    open_task_count = await client_service.get_open_task_count_for_client(db, client_id)
    site_count_result = await db.execute(
        select(func.count(Site.id)).where(
            Site.client_id == client_id, Site.is_active == True  # noqa: E712
        )
    )
    site_count = site_count_result.scalar_one()

    # Fetch manager
    manager: User | None = None
    if client.manager_id:
        manager_result = await db.execute(
            select(User).where(User.id == client.manager_id)
        )
        manager = manager_result.scalar_one_or_none()

    return templates.TemplateResponse(
        request,
        "crm/detail.html",
        {
            "client": client,
            "contacts": contacts,
            "interactions": interactions,
            "authors_map": authors_map,
            "sites": sites,
            "open_task_count": open_task_count,
            "site_count": site_count,
            "manager": manager,
            "current_user": current_user,
        },
    )


# ---- Contact endpoints ----


@router.post("/clients/{client_id}/contacts", response_class=HTMLResponse)
async def create_contact(
    client_id: uuid.UUID,
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    role: str = Form(""),
    telegram_username: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    contact = await client_service.create_contact(
        db,
        client_id=client_id,
        name=name.strip(),
        phone=phone.strip() or None,
        email=email.strip() or None,
        role=role.strip() or None,
        telegram_username=telegram_username.strip() or None,
        notes=notes.strip() or None,
    )
    await log_action(
        db,
        action="create",
        user_id=current_user.id,
        entity_type="client_contact",
        entity_id=str(contact.id),
        detail={"name": contact.name, "client_id": str(client_id)},
    )
    await db.commit()
    logger.info("Contact created: {} for client {} by user {}", contact.name, client_id, current_user.id)
    return templates.TemplateResponse(
        request,
        "crm/_contact_row.html",
        {"contact": contact, "client_id": client_id, "current_user": current_user},
    )


@router.get("/clients/{client_id}/contacts/{contact_id}/edit", response_class=HTMLResponse)
async def contact_edit_form(
    client_id: uuid.UUID,
    contact_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    result = await db.execute(
        select(ClientContact).where(
            ClientContact.id == contact_id,
            ClientContact.client_id == client_id,
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return templates.TemplateResponse(
        request,
        "crm/_contact_edit.html",
        {"contact": contact, "client_id": client_id},
    )


@router.get("/clients/{client_id}/contacts/{contact_id}", response_class=HTMLResponse)
async def contact_read_row(
    client_id: uuid.UUID,
    contact_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_authenticated),
) -> HTMLResponse:
    result = await db.execute(
        select(ClientContact).where(
            ClientContact.id == contact_id,
            ClientContact.client_id == client_id,
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return templates.TemplateResponse(
        request,
        "crm/_contact_row.html",
        {"contact": contact, "client_id": client_id, "current_user": current_user},
    )


@router.put("/clients/{client_id}/contacts/{contact_id}", response_class=HTMLResponse)
async def update_contact(
    client_id: uuid.UUID,
    contact_id: uuid.UUID,
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    role: str = Form(""),
    telegram_username: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    contact = await client_service.update_contact(
        db,
        contact_id,
        client_id,
        name=name.strip(),
        phone=phone.strip() or None,
        email=email.strip() or None,
        role=role.strip() or None,
        telegram_username=telegram_username.strip() or None,
        notes=notes.strip() or None,
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.commit()
    logger.info("Contact updated: {} by user {}", contact_id, current_user.id)
    return templates.TemplateResponse(
        request,
        "crm/_contact_row.html",
        {"contact": contact, "client_id": client_id, "current_user": current_user},
    )


@router.delete("/clients/{client_id}/contacts/{contact_id}", response_class=HTMLResponse)
async def delete_contact(
    client_id: uuid.UUID,
    contact_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    deleted = await client_service.delete_contact(db, contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    await log_action(
        db,
        action="delete",
        user_id=current_user.id,
        entity_type="client_contact",
        entity_id=str(contact_id),
        detail={"client_id": str(client_id)},
    )
    await db.commit()
    logger.info("Contact deleted: {} by user {}", contact_id, current_user.id)
    return HTMLResponse("")


# ---- Interaction endpoints ----


@router.post("/clients/{client_id}/interactions", response_class=HTMLResponse)
async def create_interaction(
    client_id: uuid.UUID,
    request: Request,
    note: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    interaction = await client_service.create_interaction(
        db,
        client_id=client_id,
        author_id=current_user.id,
        note=note.strip(),
    )
    await log_action(
        db,
        action="create",
        user_id=current_user.id,
        entity_type="client_interaction",
        entity_id=str(interaction.id),
        detail={"client_id": str(client_id)},
    )
    await db.commit()
    logger.info("Interaction created for client {} by user {}", client_id, current_user.id)
    return templates.TemplateResponse(
        request,
        "crm/_interaction_entry.html",
        {
            "interaction": interaction,
            "author": current_user,
            "client_id": client_id,
            "current_user": current_user,
        },
    )


@router.put("/clients/{client_id}/interactions/{interaction_id}", response_class=HTMLResponse)
async def update_interaction(
    client_id: uuid.UUID,
    interaction_id: uuid.UUID,
    request: Request,
    note: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    # Fetch the interaction to check ownership
    result = await db.execute(
        select(ClientInteraction).where(ClientInteraction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # Ownership check: author or admin (D-10)
    if current_user.id != interaction.author_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this interaction")

    updated = await client_service.update_interaction(db, interaction_id, note=note.strip())
    if updated is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    await db.commit()

    # Fetch author for display
    author: User | None = None
    if updated.author_id:
        author_result = await db.execute(select(User).where(User.id == updated.author_id))
        author = author_result.scalar_one_or_none()

    logger.info("Interaction updated: {} by user {}", interaction_id, current_user.id)
    return templates.TemplateResponse(
        request,
        "crm/_interaction_entry.html",
        {
            "interaction": updated,
            "author": author,
            "client_id": client_id,
            "current_user": current_user,
        },
    )


@router.delete("/clients/{client_id}/interactions/{interaction_id}", response_class=HTMLResponse)
async def delete_interaction(
    client_id: uuid.UUID,
    interaction_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    # Fetch the interaction to check ownership
    result = await db.execute(
        select(ClientInteraction).where(ClientInteraction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # Ownership check: author or admin (D-10)
    if current_user.id != interaction.author_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this interaction")

    await client_service.delete_interaction(db, interaction_id)
    await log_action(
        db,
        action="delete",
        user_id=current_user.id,
        entity_type="client_interaction",
        entity_id=str(interaction_id),
        detail={"client_id": str(client_id)},
    )
    await db.commit()
    logger.info("Interaction deleted: {} by user {}", interaction_id, current_user.id)
    return HTMLResponse("")
