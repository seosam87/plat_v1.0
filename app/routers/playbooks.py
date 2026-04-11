"""Playbook Builder router — Phase 999.8.

Handles:
- /ui/playbooks/blocks                     — block library (list + filter + create/edit/delete)
- /ui/playbooks/blocks/new                 — block create form
- /ui/playbooks/blocks/{id}/edit           — block edit form
- /ui/playbooks/blocks/{id}/delete         — block delete
- /ui/playbooks/blocks/media-row           — HTMX inline-add media row fragment
- /ui/playbooks/experts                    — expert admin list
- /ui/playbooks/experts/new                — expert create
- /ui/playbooks/experts/{id}/edit          — expert update
- /ui/playbooks/experts/{id}/delete        — expert delete
- /ui/playbooks                            — playbook template list (skeleton, Plan 03)
- /ui/playbooks/{id}/edit                  — drag-and-drop builder (Plan 03)
- /ui/projects/{pid}/playbooks/apply       — apply modal (Plan 04)
- /api/playbook-step-active                — banner fetch (Plan 05)
- /api/project-playbook-steps/{id}/status  — step status toggle (Plan 05)

Plan 01 created the skeleton (3 placeholder GETs).
Plan 02 (this wave) fills in block + expert CRUD.
Plan 03 (parallel wave) adds the playbook-template + builder endpoints
         APPENDED AFTER the block section — do not reorder.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_any_authenticated
from app.dependencies import get_db
from app.models.playbook import ActionKind, BlockMediaKind
from app.models.user import User
from app.services import playbook_service as svc
from app.services.playbook_service import (
    BlockCreate,
    BlockMediaCreate,
    BlockUpdate,
    ExpertCreate,
    ExpertUpdate,
)
from app.template_engine import templates

router = APIRouter(tags=["playbooks"])


# ---------------------------------------------------------------------------
# --- Block Library (Plan 02) ---
# ---------------------------------------------------------------------------


@router.get("/ui/playbooks/blocks", response_class=HTMLResponse)
async def ui_playbook_blocks(
    request: Request,
    category_id: uuid.UUID | None = None,
    expert_source_id: uuid.UUID | None = None,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Block library grid + HTMX filter. Any authenticated user can view."""
    blocks = await svc.list_blocks(
        db,
        category_id=category_id,
        expert_source_id=expert_source_id,
    )
    categories = await svc.list_categories(db)
    experts = await svc.list_experts(db)
    is_admin = user.role.value == "admin"
    ctx = {
        "blocks": blocks,
        "categories": categories,
        "experts": experts,
        "is_admin": is_admin,
        "selected_category_id": category_id,
        "selected_expert_id": expert_source_id,
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "playbooks/_block_card_grid.html", ctx
        )
    return templates.TemplateResponse(request, "playbooks/blocks.html", ctx)


@router.get("/ui/playbooks/blocks/new", response_class=HTMLResponse)
async def ui_playbook_block_new(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Render the block create form (admin only)."""
    categories = await svc.list_categories(db)
    experts = await svc.list_experts(db)
    return templates.TemplateResponse(
        request,
        "playbooks/block_form.html",
        {
            "block": None,
            "categories": categories,
            "experts": experts,
            "action_kinds": list(ActionKind),
            "media_kinds": list(BlockMediaKind),
            "form_action": "/ui/playbooks/blocks/new",
            "is_admin": True,
        },
    )


@router.post("/ui/playbooks/blocks/new")
async def ui_playbook_block_create(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Persist a new block from the create form (admin only)."""
    form = await request.form()
    data = BlockCreate(
        title=form["title"],
        category_id=uuid.UUID(form["category_id"]),
        expert_source_id=(
            uuid.UUID(form["expert_source_id"])
            if form.get("expert_source_id")
            else None
        ),
        summary_md=form["summary_md"],
        checklist_md=form.get("checklist_md") or None,
        action_kind=ActionKind(form["action_kind"]),
        estimated_days=(
            int(form["estimated_days"]) if form.get("estimated_days") else None
        ),
        display_order=int(form.get("display_order") or 0),
    )
    media = _parse_media_rows(form)
    await svc.create_block(db, data, media, created_by=user.id)
    return RedirectResponse("/ui/playbooks/blocks", status_code=303)


@router.get("/ui/playbooks/blocks/{block_id}/edit", response_class=HTMLResponse)
async def ui_playbook_block_edit(
    request: Request,
    block_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Render the block edit form pre-populated from DB (admin only)."""
    block = await svc.get_block(db, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    categories = await svc.list_categories(db)
    experts = await svc.list_experts(db)
    return templates.TemplateResponse(
        request,
        "playbooks/block_form.html",
        {
            "block": block,
            "categories": categories,
            "experts": experts,
            "action_kinds": list(ActionKind),
            "media_kinds": list(BlockMediaKind),
            "form_action": f"/ui/playbooks/blocks/{block_id}/edit",
            "is_admin": True,
        },
    )


@router.post("/ui/playbooks/blocks/{block_id}/edit")
async def ui_playbook_block_update(
    request: Request,
    block_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Persist block updates (admin only)."""
    form = await request.form()
    data = BlockUpdate(
        title=form["title"],
        category_id=uuid.UUID(form["category_id"]),
        expert_source_id=(
            uuid.UUID(form["expert_source_id"])
            if form.get("expert_source_id")
            else None
        ),
        summary_md=form["summary_md"],
        checklist_md=form.get("checklist_md") or None,
        action_kind=ActionKind(form["action_kind"]),
        estimated_days=(
            int(form["estimated_days"]) if form.get("estimated_days") else None
        ),
        display_order=int(form.get("display_order") or 0),
    )
    media = _parse_media_rows(form)
    block = await svc.update_block(db, block_id, data, media)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    return RedirectResponse("/ui/playbooks/blocks", status_code=303)


@router.post("/ui/playbooks/blocks/{block_id}/delete")
async def ui_playbook_block_delete(
    block_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a block (admin only). Cascades to BlockMedia via FK."""
    ok = await svc.delete_block(db, block_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Block not found")
    return RedirectResponse("/ui/playbooks/blocks", status_code=303)


@router.get("/ui/playbooks/blocks/media-row", response_class=HTMLResponse)
async def ui_playbook_block_media_row(
    request: Request,
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """Return a single blank media row fragment for inline HTMX add."""
    return templates.TemplateResponse(
        request,
        "playbooks/_block_media_row.html",
        {
            "media_kinds": list(BlockMediaKind),
            "media": None,
        },
    )


def _parse_media_rows(form) -> list[BlockMediaCreate]:
    """Parse array-style media_* form fields into BlockMediaCreate rows.

    Empty URL rows are skipped so users can remove a media entry by blanking
    the URL input without needing JS. Title defaults to the URL when empty.
    Invalid URLs raise Pydantic ValidationError (caught by FastAPI → 422).
    """
    out: list[BlockMediaCreate] = []
    if not hasattr(form, "getlist"):
        return out
    kinds = form.getlist("media_kind")
    urls = form.getlist("media_url")
    titles = form.getlist("media_title")
    descs = form.getlist("media_description")
    for i in range(len(urls)):
        url = (urls[i] or "").strip()
        if not url:
            continue
        kind_str = kinds[i] if i < len(kinds) and kinds[i] else "article"
        title = (titles[i] if i < len(titles) else "") or url
        desc = (descs[i] if i < len(descs) else None) or None
        out.append(
            BlockMediaCreate(
                kind=BlockMediaKind(kind_str),
                url=url,
                title=title,
                description_md=desc,
            )
        )
    return out


# ---------------------------------------------------------------------------
# --- Expert Admin (Plan 02) ---
# ---------------------------------------------------------------------------


@router.get("/ui/playbooks/experts", response_class=HTMLResponse)
async def ui_playbook_experts(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Expert admin list (admin only per D-15)."""
    experts = await svc.list_experts(db)
    counts = {
        e.id: await svc.count_blocks_by_expert(db, e.id) for e in experts
    }
    return templates.TemplateResponse(
        request,
        "playbooks/experts.html",
        {
            "experts": experts,
            "block_counts": counts,
            "is_admin": True,
        },
    )


@router.post("/ui/playbooks/experts/new")
async def ui_playbook_expert_create(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = ExpertCreate(
        name=form["name"],
        bio_md=form.get("bio_md") or None,
        external_url=form.get("external_url") or None,
    )
    await svc.create_expert(db, data)
    return RedirectResponse("/ui/playbooks/experts", status_code=303)


@router.post("/ui/playbooks/experts/{expert_id}/edit")
async def ui_playbook_expert_update(
    request: Request,
    expert_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = ExpertUpdate(
        name=form["name"],
        bio_md=form.get("bio_md") or None,
        external_url=form.get("external_url") or None,
    )
    expert = await svc.update_expert(db, expert_id, data)
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert not found")
    return RedirectResponse("/ui/playbooks/experts", status_code=303)


@router.post("/ui/playbooks/experts/{expert_id}/delete")
async def ui_playbook_expert_delete(
    expert_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ok = await svc.delete_expert(db, expert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Expert not found")
    return RedirectResponse("/ui/playbooks/experts", status_code=303)


# ---------------------------------------------------------------------------
# --- Playbook templates list (Plan 01 placeholder — Plan 03 fills in) ---
# ---------------------------------------------------------------------------


@router.get("/ui/playbooks", response_class=HTMLResponse)
async def ui_playbook_templates(
    request: Request,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Placeholder playbook templates list. Filled in by Plan 03."""
    return templates.TemplateResponse(
        request,
        "playbooks/index.html",
        {"playbooks": [], "is_admin": user.role.value == "admin"},
    )
