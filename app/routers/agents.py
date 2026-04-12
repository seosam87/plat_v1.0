"""AI Agent catalogue, CRUD, execution, and HTMX partials (Phase 999.9).

Routes:
- GET  /ui/agents/                     -- catalogue page (full + HTMX grid partial)
- GET  /ui/agents/parse-vars           -- HTMX: parse {{vars}} from template text
- GET  /ui/agents/new                  -- create form
- POST /ui/agents/new                  -- create agent
- GET  /ui/agents/jobs/{job_id}/status -- HTMX poll job status
- GET  /ui/agents/{id}/edit            -- edit form
- POST /ui/agents/{id}/edit            -- update agent
- POST /ui/agents/{id}/delete          -- delete agent
- GET  /ui/agents/{id}/run             -- run page
- POST /ui/agents/{id}/run             -- dispatch Celery job
- POST /ui/agents/{id}/favourite       -- toggle favourite (HTMX)
- POST /ui/agents/{id}/fork            -- fork agent
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.models.user import User
from app.services.agent_service import (
    create_agent,
    create_job,
    delete_agent,
    fork_agent,
    get_agent,
    get_job,
    is_favourited,
    list_agents,
    list_categories,
    parse_template_variables,
    toggle_favourite,
    update_agent,
)
from app.template_engine import templates

router = APIRouter(prefix="/ui/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# GET /ui/agents/ — catalogue page (full page or HTMX grid partial)
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def catalogue(
    request: Request,
    category: str | None = None,
    search: str | None = None,
    favourite: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Agent catalogue with category filter, text search, and favourite mode."""
    categories = await list_categories(db)
    fav_user_id = current_user.id if favourite else None
    agents = await list_agents(
        db,
        category_slug=category,
        search=search,
        favourite_user_id=fav_user_id,
    )

    # Attach _is_favourited attribute to each agent for template use
    for agent in agents:
        agent._is_favourited = await is_favourited(
            db, user_id=current_user.id, agent_id=agent.id
        )

    ctx = {
        "request": request,
        "agents": agents,
        "categories": categories,
        "current_category": category,
        "search_query": search or "",
        "favourite_mode": bool(favourite),
        "current_user": current_user,
    }

    # HTMX request → return grid partial only
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("agents/_agent_card_grid.html", ctx)

    return templates.TemplateResponse("agents/index.html", ctx)


# ---------------------------------------------------------------------------
# GET /ui/agents/parse-vars — HTMX: variable preview from template text
# ---------------------------------------------------------------------------


@router.get("/parse-vars", response_class=HTMLResponse)
async def parse_vars(
    request: Request,
    template: str = "",
) -> HTMLResponse:
    """Parse {{variables}} from template and return badge HTML."""
    variables = parse_template_variables(template)
    if not variables:
        html = (
            '<span class="text-xs text-gray-400">'
            "Переменных не обнаружено. Используйте <code>{{переменная}}</code> в шаблоне запроса."
            "</span>"
        )
    else:
        badges = "".join(
            f'<span class="inline-block px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-600 mr-1 mb-1">'
            f"{{{{{var}}}}}"
            f"</span>"
            for var in variables
        )
        html = badges
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# GET /ui/agents/new — create form
# ---------------------------------------------------------------------------


@router.get("/new", response_class=HTMLResponse)
async def new_agent_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render create agent form."""
    categories = await list_categories(db)
    return templates.TemplateResponse(
        "agents/form.html",
        {
            "request": request,
            "categories": categories,
            "agent": None,
            "is_edit": False,
            "current_user": current_user,
        },
    )


# ---------------------------------------------------------------------------
# POST /ui/agents/new — process create form
# ---------------------------------------------------------------------------


@router.post("/new", response_class=HTMLResponse)
async def create_agent_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Process create agent form submission."""
    form = await request.form()
    name = str(form.get("name", "")).strip()
    description = str(form.get("description", "")).strip()
    icon = str(form.get("icon", "")).strip()
    category_id_raw = form.get("category_id")
    category_id = uuid.UUID(str(category_id_raw)) if category_id_raw else None
    system_prompt = str(form.get("system_prompt", "")).strip()
    user_template = str(form.get("user_template", "")).strip()
    model = str(form.get("model", "claude-haiku-4-5-20251001")).strip()
    temperature = float(form.get("temperature", 0.7))
    max_tokens = int(form.get("max_tokens", 800))
    output_format = str(form.get("output_format", "text")).strip()
    tags_raw = str(form.get("tags", "")).strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
    is_public = form.get("is_public") is not None

    await create_agent(
        db,
        name=name,
        description=description,
        icon=icon,
        category_id=category_id,
        system_prompt=system_prompt,
        user_template=user_template,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        output_format=output_format,
        tags=tags,
        is_public=is_public,
        created_by=current_user.id,
    )
    await db.commit()
    return RedirectResponse(url="/ui/agents/", status_code=302)


# ---------------------------------------------------------------------------
# GET /ui/agents/jobs/{job_id}/status — HTMX poll job status
# NOTE: must be registered BEFORE /{agent_id}/* routes to avoid UUID ambiguity
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}/status", response_class=HTMLResponse)
async def job_status(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX poll endpoint for agent job status."""
    job = await get_job(db, job_id)
    if not job:
        return HTMLResponse(
            '<div id="agent-run-result">'
            '<div class="bg-red-50 border border-red-200 rounded p-4">'
            '<p class="text-sm text-red-700">Задание не найдено.</p>'
            "</div></div>"
        )
    return templates.TemplateResponse(
        "agents/_agent_job_status.html",
        {"request": request, "job": job, "current_user": current_user},
    )


# ---------------------------------------------------------------------------
# GET /ui/agents/{agent_id}/edit — edit form
# ---------------------------------------------------------------------------


@router.get("/{agent_id}/edit", response_class=HTMLResponse)
async def edit_agent_form(
    request: Request,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render edit agent form."""
    agent = await get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    categories = await list_categories(db)
    return templates.TemplateResponse(
        "agents/form.html",
        {
            "request": request,
            "categories": categories,
            "agent": agent,
            "is_edit": True,
            "current_user": current_user,
        },
    )


# ---------------------------------------------------------------------------
# POST /ui/agents/{agent_id}/edit — process edit form
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/edit", response_class=HTMLResponse)
async def update_agent_submit(
    request: Request,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Process edit agent form submission."""
    form = await request.form()
    name = str(form.get("name", "")).strip()
    description = str(form.get("description", "")).strip()
    icon = str(form.get("icon", "")).strip()
    category_id_raw = form.get("category_id")
    category_id = uuid.UUID(str(category_id_raw)) if category_id_raw else None
    system_prompt = str(form.get("system_prompt", "")).strip()
    user_template = str(form.get("user_template", "")).strip()
    model = str(form.get("model", "claude-haiku-4-5-20251001")).strip()
    temperature = float(form.get("temperature", 0.7))
    max_tokens = int(form.get("max_tokens", 800))
    output_format = str(form.get("output_format", "text")).strip()
    tags_raw = str(form.get("tags", "")).strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
    is_public = form.get("is_public") is not None

    await update_agent(
        db,
        agent_id,
        name=name,
        description=description,
        icon=icon,
        category_id=category_id,
        system_prompt=system_prompt,
        user_template=user_template,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        output_format=output_format,
        tags=tags,
        is_public=is_public,
    )
    await db.commit()
    return RedirectResponse(url="/ui/agents/", status_code=302)


# ---------------------------------------------------------------------------
# POST /ui/agents/{agent_id}/delete — delete agent
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/delete", response_class=HTMLResponse)
async def delete_agent_submit(
    request: Request,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Delete agent and redirect to catalogue."""
    await delete_agent(db, agent_id)
    await db.commit()
    return RedirectResponse(url="/ui/agents/", status_code=302)


# ---------------------------------------------------------------------------
# GET /ui/agents/{agent_id}/run — run page
# ---------------------------------------------------------------------------


@router.get("/{agent_id}/run", response_class=HTMLResponse)
async def run_agent_page(
    request: Request,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render run agent page with variable input form."""
    agent = await get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    variables = parse_template_variables(agent.user_template or "")
    return templates.TemplateResponse(
        "agents/run.html",
        {
            "request": request,
            "agent": agent,
            "variables": variables,
            "current_user": current_user,
        },
    )


# ---------------------------------------------------------------------------
# POST /ui/agents/{agent_id}/run — dispatch LLM job
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/run", response_class=HTMLResponse)
async def run_agent_submit(
    request: Request,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Dispatch a Celery agent job and return HTMX polling div."""
    agent = await get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    form = await request.form()
    variables = parse_template_variables(agent.user_template or "")
    inputs = {var: str(form.get(var, "")) for var in variables}

    job = await create_job(
        db,
        agent_id=agent.id,
        agent_name=agent.name,
        user_id=current_user.id,
        inputs_json=inputs,
    )
    await db.commit()

    from app.tasks.agent_tasks import run_agent_job
    run_agent_job.delay(job.id)

    return HTMLResponse(
        f'<div id="agent-run-result" '
        f'hx-get="/ui/agents/jobs/{job.id}/status" '
        f'hx-trigger="load, every 2s" '
        f'hx-swap="outerHTML" '
        f'aria-live="polite" '
        f'class="mt-4 p-4 border border-gray-200 rounded bg-gray-50 flex items-center gap-3">'
        f'<svg class="animate-spin h-5 w-5 text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">'
        f'<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>'
        f'<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>'
        f"</svg>"
        f'<span class="text-sm text-gray-500">Агент работает...</span>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# POST /ui/agents/{agent_id}/favourite — toggle favourite (HTMX)
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/favourite", response_class=HTMLResponse)
async def toggle_favourite_route(
    request: Request,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Toggle favourite state and return updated star button HTML."""
    now_favourited = await toggle_favourite(
        db, user_id=current_user.id, agent_id=agent_id
    )
    await db.commit()

    if now_favourited:
        colour = "text-amber-400"
        label = "Убрать из избранного"
    else:
        colour = "text-gray-300"
        label = "Добавить в избранное"

    return HTMLResponse(
        f'<button hx-post="/ui/agents/{agent_id}/favourite" '
        f'hx-swap="outerHTML" hx-target="this" '
        f'class="p-1 {colour} hover:text-amber-400 transition-colors" '
        f'aria-label="{label}">'
        f'<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 24 24" class="w-5 h-5">'
        f'<path stroke-linecap="round" stroke-linejoin="round" '
        f'd="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />'
        f"</svg>"
        f"</button>"
    )


# ---------------------------------------------------------------------------
# POST /ui/agents/{agent_id}/fork — fork agent
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/fork", response_class=HTMLResponse)
async def fork_agent_route(
    request: Request,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Fork an agent and redirect to the edit page of the copy."""
    new_agent = await fork_agent(
        db, original_id=agent_id, created_by=current_user.id
    )
    await db.commit()
    return RedirectResponse(url=f"/ui/agents/{new_agent.id}/edit", status_code=302)
