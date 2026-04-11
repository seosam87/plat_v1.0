"""Playbook Builder router — Phase 999.8.

Handles:
- /ui/playbooks/blocks        — block library (list + create/edit/delete)
- /ui/playbooks               — playbook template list
- /ui/playbooks/{id}/edit     — drag-and-drop builder
- /ui/playbooks/experts       — expert admin list
- /ui/projects/{pid}/playbooks/apply — apply modal target
- /api/playbook-step-active   — banner fetch endpoint
- /api/project-playbook-steps/{id}/status — step status toggle
- /api/project-playbook-steps/{id}/complete — banner "mark done"

This file is a skeleton created in Plan 01 (data-foundation). Placeholder
GET routes return empty-state templates so the sidebar links work immediately.
Plans 02–05 flesh out CRUD, builder, apply and banner endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_any_authenticated
from app.dependencies import get_db
from app.models.user import User
from app.template_engine import templates

router = APIRouter(tags=["playbooks"])


@router.get("/ui/playbooks/blocks", response_class=HTMLResponse)
async def ui_playbook_blocks(
    request: Request,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Placeholder block library page. Filled in Plan 02."""
    return templates.TemplateResponse(
        request,
        "playbooks/blocks.html",
        {
            "blocks": [],
            "categories": [],
            "experts": [],
            "is_admin": user.role.value == "admin",
        },
    )


@router.get("/ui/playbooks", response_class=HTMLResponse)
async def ui_playbook_templates(
    request: Request,
    user: User = Depends(require_any_authenticated),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Placeholder playbook templates list. Filled in Plan 02/03."""
    return templates.TemplateResponse(
        request,
        "playbooks/index.html",
        {"playbooks": [], "is_admin": user.role.value == "admin"},
    )


@router.get("/ui/playbooks/experts", response_class=HTMLResponse)
async def ui_playbook_experts(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Placeholder expert admin list. Filled in Plan 02."""
    return templates.TemplateResponse(
        request,
        "playbooks/experts.html",
        {"experts": []},
    )
