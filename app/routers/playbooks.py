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

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_any_authenticated
from app.dependencies import get_db
from app.models.playbook import (
    ActionKind,
    BlockMediaKind,
    PlaybookCategory,
    ProjectPlaybookStepStatus,
)
from app.models.user import User
from app.services import playbook_service as svc
from app.services.playbook_hints import compute_hints_for_playbook
from app.services.playbook_service import (
    BlockCreate,
    BlockMediaCreate,
    BlockUpdate,
    ExpertCreate,
    ExpertUpdate,
    PlaybookCreate,
    PlaybookUpdate,
)
from app.template_engine import templates

router = APIRouter(tags=["playbooks"])


# ---------------------------------------------------------------------------
# --- Block Library (Plan 02) ---
# ---------------------------------------------------------------------------


@router.get("/ui/playbooks/blocks", response_class=HTMLResponse)
async def ui_playbook_blocks(
    request: Request,
    category_id: str | None = None,
    expert_source_id: str | None = None,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Block library grid + HTMX filter. Any authenticated user can view.

    Phase 999.8 Plan 06 (Gap A): accept ``str | None`` for filter params and
    coerce manually. FastAPI's automatic ``uuid.UUID | None`` parsing 422s when
    one slot is a valid uuid and the other is an empty string (sent by the
    sibling ``hx-include`` dropdown), which broke the category+expert filter.
    """
    def _parse_uuid(raw: str | None) -> uuid.UUID | None:
        if not raw:
            return None
        try:
            return uuid.UUID(raw)
        except (ValueError, TypeError):
            return None

    category_uuid = _parse_uuid(category_id)
    expert_uuid = _parse_uuid(expert_source_id)

    blocks = await svc.list_blocks(
        db,
        category_id=category_uuid,
        expert_source_id=expert_uuid,
    )
    categories = await svc.list_categories(db)
    experts = await svc.list_experts(db)
    is_admin = user.role.value == "admin"
    ctx = {
        "blocks": blocks,
        "categories": categories,
        "experts": experts,
        "is_admin": is_admin,
        "selected_category_id": category_uuid,
        "selected_expert_id": expert_uuid,
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
    try:
        media = _parse_media_rows(form)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректный URL в ссылках: {e.errors()[0].get('msg', 'проверьте формат')}",
        )
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
    try:
        media = _parse_media_rows(form)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректный URL в ссылках: {e.errors()[0].get('msg', 'проверьте формат')}",
        )
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
# --- Playbook Template Builder (Plan 03) ---
# ---------------------------------------------------------------------------


@router.get("/ui/playbooks", response_class=HTMLResponse)
async def ui_playbook_templates(
    request: Request,
    category: str | None = None,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Playbook template list grid with optional category filter."""
    cat_enum = PlaybookCategory(category) if category else None
    playbooks = await svc.list_playbooks(db, category=cat_enum)
    is_admin = user.role.value == "admin"
    return templates.TemplateResponse(
        request,
        "playbooks/index.html",
        {
            "playbooks": playbooks,
            "is_admin": is_admin,
            "selected_category": category,
            "all_categories": list(PlaybookCategory),
        },
    )


@router.get("/ui/playbooks/new", response_class=HTMLResponse)
async def ui_playbook_new_form(
    request: Request,
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """Return the inline 'create template' form fragment (admin only)."""
    return templates.TemplateResponse(
        request,
        "playbooks/_new_form.html",
        {"all_categories": list(PlaybookCategory)},
    )


@router.post("/ui/playbooks/new")
async def ui_playbook_create(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Persist a new playbook template and redirect to the builder."""
    form = await request.form()
    data = PlaybookCreate(
        name=form["name"],
        description_md=form.get("description_md") or None,
        category=(
            PlaybookCategory(form["category"]) if form.get("category") else None
        ),
        is_published=form.get("is_published") == "on",
    )
    playbook = await svc.create_playbook(db, data, created_by=user.id)
    return RedirectResponse(
        f"/ui/playbooks/{playbook.id}/edit", status_code=303
    )


@router.get("/ui/playbooks/{playbook_id}/edit", response_class=HTMLResponse)
async def ui_playbook_builder(
    request: Request,
    playbook_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Drag-and-drop builder page for a single playbook template."""
    playbook = await svc.get_playbook_with_steps(db, playbook_id)
    if playbook is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    blocks = await svc.list_blocks(db)
    categories = await svc.list_categories(db)
    return templates.TemplateResponse(
        request,
        "playbooks/builder.html",
        {
            "playbook": playbook,
            "library_blocks": blocks,
            "categories": categories,
            "all_categories": list(PlaybookCategory),
        },
    )


@router.post("/ui/playbooks/{playbook_id}/meta")
async def ui_playbook_update_meta(
    request: Request,
    playbook_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Save playbook metadata (name / category / is_published) via HTMX."""
    form = await request.form()
    data = PlaybookUpdate(
        name=form["name"],
        description_md=form.get("description_md") or None,
        category=(
            PlaybookCategory(form["category"]) if form.get("category") else None
        ),
        is_published=form.get("is_published") == "on",
    )
    pb = await svc.update_playbook(db, playbook_id, data)
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return HTMLResponse(
        "<div class='text-xs text-emerald-600'>Сохранено</div>"
    )


@router.post(
    "/ui/playbooks/{playbook_id}/steps/add",
    response_class=HTMLResponse,
)
async def ui_playbook_add_step(
    request: Request,
    playbook_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Append a block as a new step and return the rendered step row."""
    form = await request.form()
    block_id = uuid.UUID(form["block_id"])
    step = await svc.add_step(db, playbook_id, block_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return templates.TemplateResponse(
        request,
        "playbooks/_step_row_builder.html",
        {"step": step, "playbook_id": playbook_id},
    )


@router.delete("/ui/playbooks/{playbook_id}/steps/{step_id}")
async def ui_playbook_remove_step(
    playbook_id: uuid.UUID,
    step_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single step from the playbook template."""
    ok = await svc.remove_step(db, step_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Step not found")
    return HTMLResponse("", status_code=200)


@router.post("/ui/playbooks/{playbook_id}/steps/reorder")
async def ui_playbook_reorder_steps(
    playbook_id: uuid.UUID,
    payload: dict = Body(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Persist a new step ordering.

    Body: `{"order": ["uuid1", "uuid2", ...]}` — list must be a complete
    permutation of the playbook's existing step IDs.
    """
    order = [uuid.UUID(sid) for sid in payload.get("order", [])]
    ok = await svc.reorder_steps(db, playbook_id, order)
    if not ok:
        raise HTTPException(
            status_code=400, detail="Invalid order — id set mismatch"
        )
    return {"status": "ok"}


@router.put(
    "/ui/playbooks/{playbook_id}/steps/{step_id}/move",
    response_class=HTMLResponse,
)
async def ui_playbook_move_step(
    request: Request,
    playbook_id: uuid.UUID,
    step_id: uuid.UUID,
    direction: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Keyboard-accessible up/down move. Re-renders the full step list."""
    if direction not in ("up", "down"):
        raise HTTPException(
            status_code=400, detail="direction must be up or down"
        )
    await svc.move_step(db, playbook_id, step_id, direction)
    pb = await svc.get_playbook_with_steps(db, playbook_id)
    return templates.TemplateResponse(
        request,
        "playbooks/_builder_step_list.html",
        {"playbook": pb},
    )


@router.post("/ui/playbooks/{playbook_id}/steps/{step_id}/note")
async def ui_playbook_update_step_note(
    request: Request,
    playbook_id: uuid.UUID,
    step_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Save a per-step markdown note (blur auto-save)."""
    form = await request.form()
    await svc.update_step_note(db, step_id, form.get("note_md"))
    return HTMLResponse("", status_code=204)


@router.post("/ui/playbooks/{playbook_id}/clone")
async def ui_playbook_clone(
    playbook_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deep-clone a playbook template and redirect to the new builder."""
    new_pb = await svc.clone_playbook(db, playbook_id, created_by=user.id)
    if new_pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return RedirectResponse(
        f"/ui/playbooks/{new_pb.id}/edit", status_code=303
    )


@router.post("/ui/playbooks/{playbook_id}/delete")
async def ui_playbook_delete(
    playbook_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a playbook template (cascades to PlaybookStep rows)."""
    ok = await svc.delete_playbook(db, playbook_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return RedirectResponse("/ui/playbooks", status_code=303)


# ---------------------------------------------------------------------------
# --- Apply + Hints + Step Route (Plan 04) ---
# ---------------------------------------------------------------------------
# Owned by Plan 999.8-04 (apply-and-project-tab). Endpoints bind a Playbook
# template to a Project via copy-on-apply (D-12), render the project-page
# playbook tab, and toggle step status via HTMX.
#
# `/api/playbook-step-route` was moved here from Plan 05 during the
# plan-checker pass because the Task 3 template (openPlaybookStep JS)
# calls it to resolve the target URL. Keeping it in the same plan avoids
# a non-deterministic Wave-3 ordering between Plans 04 and 05.
#
# Banner endpoints (`/api/playbook-step-active`,
# `/api/project-playbook-steps/{id}/complete`) remain owned by Plan 05.
# ---------------------------------------------------------------------------


@router.get(
    "/ui/projects/{project_id}/playbooks/apply-modal",
    response_class=HTMLResponse,
)
async def ui_project_playbook_apply_modal(
    request: Request,
    project_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Return the apply-playbook modal HTML fragment (admin only)."""
    playbooks = await svc.list_playbooks(db, only_published=True)
    return templates.TemplateResponse(
        request,
        "playbooks/_apply_modal.html",
        {"project_id": project_id, "playbooks": playbooks},
    )


@router.get(
    "/ui/playbooks/{playbook_id}/preview", response_class=HTMLResponse
)
async def ui_playbook_preview(
    request: Request,
    playbook_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Lightweight preview fragment used by the apply modal dropdown."""
    pb = await svc.get_playbook_with_steps(db, playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    total_days = sum((s.block.estimated_days or 0) for s in pb.steps)
    return HTMLResponse(
        '<div class="text-sm text-gray-600">'
        f'<p class="mb-2">{pb.description_md or ""}</p>'
        f'<p class="text-xs text-gray-500">{len(pb.steps)} шагов · ~{total_days} дней</p>'
        "</div>"
    )


@router.post("/ui/projects/{project_id}/playbooks/apply")
async def ui_project_playbook_apply(
    request: Request,
    project_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Copy-on-apply a Playbook template to this project.

    Returns an HX-Refresh header so the modal closes and the Kanban
    page fully reloads. kanban.html reads the URL hash on load and
    auto-activates the #playbook tab, so the user lands on the new
    ProjectPlaybook card immediately.
    """
    form = await request.form()
    try:
        playbook_id = uuid.UUID(form["playbook_id"])
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid playbook_id: {e}")
    pp = await svc.apply_playbook(db, project_id, playbook_id, applied_by=user.id)
    if pp is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    # HX-Refresh triggers a full page reload regardless of current URL
    # (HX-Redirect is a no-op when target URL == current URL, which happens
    # because switchProjectTab() already wrote #playbook into history via
    # replaceState). kanban.html already auto-activates the #playbook tab on
    # page load, so the reload lands in the right place.
    return HTMLResponse(
        "",
        status_code=200,
        headers={"HX-Refresh": "true"},
    )


@router.get(
    "/ui/projects/{project_id}/playbook-tab", response_class=HTMLResponse
)
async def ui_project_playbook_tab(
    request: Request,
    project_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Render the project's Playbook tab panel.

    Computes hint + blocked state server-side so the template renders
    without extra round-trips. `blocked` resolves PlaybookBlock UUIDs
    from `prerequisites` to the step that shares that block_id within
    THIS ProjectPlaybook (prereqs reference block_id, not step_id).
    """
    project_playbooks = await svc.list_project_playbooks(db, project_id)
    site_id = await svc.get_project_site_id(db, project_id)

    hints: dict[uuid.UUID, bool] = {}
    blocked: dict[uuid.UUID, bool] = {}

    for pp in project_playbooks:
        pp_hints = await compute_hints_for_playbook(
            db,
            list(pp.steps),
            site_id=site_id,
            project_id=project_id,
        )
        hints.update(pp_hints)

        # Build block_id → status map to resolve prereqs cheaply.
        step_status_by_block = {s.block_id: s.status for s in pp.steps}
        for s in pp.steps:
            prereqs = s.prerequisites or []
            if not prereqs:
                blocked[s.id] = False
                continue
            unmet = []
            for block_uuid in prereqs:
                try:
                    as_uuid = (
                        block_uuid
                        if isinstance(block_uuid, uuid.UUID)
                        else uuid.UUID(str(block_uuid))
                    )
                except (ValueError, TypeError):
                    continue
                if step_status_by_block.get(as_uuid) != ProjectPlaybookStepStatus.done:
                    unmet.append(as_uuid)
            blocked[s.id] = len(unmet) > 0

    is_admin = user.role.value == "admin"
    return templates.TemplateResponse(
        request,
        "projects/_playbook_tab.html",
        {
            "project_id": project_id,
            "project_playbooks": project_playbooks,
            "hints": hints,
            "blocked": blocked,
            "is_admin": is_admin,
        },
    )


@router.post(
    "/api/project-playbook-steps/{step_id}/status", response_class=HTMLResponse
)
async def api_project_step_status(
    request: Request,
    step_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Cycle status (open → in_progress → done → open) and re-render row."""
    step = await svc.cycle_step_status(db, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    pp = await svc.get_project_playbook(db, step.project_playbook_id)
    project_id = pp.project_id if pp else None
    return templates.TemplateResponse(
        request,
        "projects/_playbook_project_step.html",
        {
            "step": step,
            "project_id": project_id,
            "blocked": False,
            "hint": False,
            "hints": {step.id: False},
            "blocked_map": {step.id: False},
            "is_admin": user.role.value == "admin",
        },
    )


@router.post("/api/project-playbook-steps/{step_id}/open-action")
async def api_project_step_open_action(
    step_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Mark `opened_at` + transition open → in_progress.

    Called by `openPlaybookStep()` (Plan 04 Task 3 JS) before navigation.
    Fire-and-forget; non-blocking client-side.
    """
    step = await svc.open_step_action(db, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    return {
        "status": "ok",
        "step_id": str(step_id),
        "opened_at": step.opened_at.isoformat() if step.opened_at else None,
    }


@router.get("/api/playbook-step-route")
async def api_playbook_step_route(
    step_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a ProjectPlaybookStep to its target UI URL.

    Walks ProjectPlaybookStep → ProjectPlaybook → Project → site_id,
    then calls `svc.resolve_action_route()` (which uses
    `ACTION_KIND_TO_ROUTE` per CONTEXT.md D-02). Returns
    `{"url": str | null}` where `null` means "manual_note" or an
    unmapped action kind — the caller shows a Russian notice.

    Owned by Plan 04 (moved from Plan 05 during planning — Task 3
    template depends on it, so it must ship in the same wave).
    """
    step = await svc.get_project_step(db, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    pp = step.project_playbook
    if pp is None:
        raise HTTPException(status_code=404, detail="Project playbook missing")
    site_id = await svc.get_project_site_id(db, pp.project_id)
    url = svc.resolve_action_route(
        step.block.action_kind.value,
        project_id=pp.project_id,
        site_id=site_id,
    )
    return {"url": url}


@router.post("/api/project-playbook-steps/{step_id}/note")
async def api_project_step_note(
    request: Request,
    step_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Save a per-step markdown note (blur auto-save for manual_note)."""
    form = await request.form()
    await svc.update_project_step_note(db, step_id, form.get("note_md"))
    return HTMLResponse("", status_code=204)


@router.post("/ui/project-playbooks/{pp_id}/archive")
async def ui_project_playbook_archive(
    pp_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Archive an applied ProjectPlaybook (admin only)."""
    pp = await svc.get_project_playbook(db, pp_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="ProjectPlaybook not found")
    project_id = pp.project_id
    ok = await svc.archive_project_playbook(db, pp_id)
    if not ok:
        raise HTTPException(status_code=404, detail="ProjectPlaybook not found")
    return RedirectResponse(
        f"/ui/projects/{project_id}/kanban#playbook", status_code=303
    )


# ---------------------------------------------------------------------------
# --- Banner Endpoints (Plan 05) ---
# ---------------------------------------------------------------------------
#
# These 2 endpoints feed the global playbook banner (D-16/D-17). They
# intentionally use direct SQLAlchemy queries rather than going through
# ``playbook_service`` because Plan 05 runs in parallel with Plan 04 and
# we must not depend on service helpers that the other wave is adding.
#
# The third banner-related route ``/api/playbook-step-route`` lives in
# Plan 04 (it was moved there during revision because Plan 04's builder
# template needs it in the same wave).


@router.get("/api/playbook-step-active")
async def api_playbook_step_active(
    step_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Return the minimal step payload the banner JS needs to render.

    Called from ``static/js/playbook_banner.js`` on every page load when
    ``sessionStorage.active_playbook_step`` is present. Returns 404 if the
    step has been deleted so the banner JS can clear its state silently.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.playbook import (
        PlaybookBlock,
        ProjectPlaybook,
        ProjectPlaybookStep,
    )

    result = await db.execute(
        select(ProjectPlaybookStep)
        .options(
            selectinload(ProjectPlaybookStep.block),
            selectinload(ProjectPlaybookStep.project_playbook).selectinload(
                ProjectPlaybook.steps
            ),
        )
        .where(ProjectPlaybookStep.id == step_id)
    )
    step = result.scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")

    pp = step.project_playbook
    total = len(pp.steps) if pp is not None and pp.steps else 0
    # Position is 0-indexed in DB; UI wants 1-indexed "Шаг N/M".
    display_position = (step.position or 0) + 1
    block_title = step.block.title if step.block is not None else ""
    action_kind_value = (
        step.block.action_kind.value if step.block is not None else ""
    )
    return {
        "step_id": str(step.id),
        "project_playbook_id": str(step.project_playbook_id),
        "project_id": str(pp.project_id) if pp is not None else None,
        "title": block_title,
        "position": display_position,
        "total": total,
        "playbook_name": pp.name if pp is not None else "",
        "status": step.status.value,
        "action_kind": action_kind_value,
    }


@router.post("/api/project-playbook-steps/{step_id}/complete")
async def api_project_step_complete(
    step_id: uuid.UUID,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Mark a ProjectPlaybookStep as done from the banner CTA.

    D-20: any authenticated user with project access may complete a step.
    Stamps ``completed_at`` and flips status to ``done``. Returns the
    ``project_id`` so the banner JS can redirect back to the project
    playbook tab.
    """
    from datetime import datetime

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.playbook import (
        ProjectPlaybook,
        ProjectPlaybookStep,
        ProjectPlaybookStepStatus,
    )

    result = await db.execute(
        select(ProjectPlaybookStep)
        .options(
            selectinload(ProjectPlaybookStep.project_playbook),
        )
        .where(ProjectPlaybookStep.id == step_id)
    )
    step = result.scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")

    step.status = ProjectPlaybookStepStatus.done
    if step.completed_at is None:
        step.completed_at = datetime.utcnow()
    await db.flush()

    project_id = (
        str(step.project_playbook.project_id)
        if step.project_playbook is not None
        else None
    )
    return {"status": "ok", "project_id": project_id}
