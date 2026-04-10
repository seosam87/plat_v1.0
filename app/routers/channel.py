"""Channel router — Telegram channel post management UI.

Endpoints:
- GET  /ui/channel/          -- list page with filters and pagination
- GET  /ui/channel/new       -- new post form
- POST /ui/channel/          -- create draft post
- GET  /ui/channel/{post_id} -- edit/view post
- POST /ui/channel/{post_id} -- update post content
- DELETE /ui/channel/{post_id}          -- delete post
- POST /ui/channel/{post_id}/publish    -- publish to Telegram immediately
- POST /ui/channel/{post_id}/schedule   -- schedule for future publishing
- POST /ui/channel/{post_id}/pin        -- toggle pin state
- GET  /ui/channel/{post_id}/preview    -- render content preview (HTMX partial)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.models.user import User
from app.services import channel_service
from app.template_engine import templates

router = APIRouter(prefix="/ui/channel", tags=["channel"])

PER_PAGE = 50


# ---------------------------------------------------------------------------
# GET /  — list page
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def channel_index(
    request: Request,
    status: str | None = None,
    sort: str = "created_at_desc",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    posts, total = await channel_service.list_posts(
        db, status=status, sort=sort, page=page, per_page=PER_PAGE
    )
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    return templates.TemplateResponse(
        request,
        "channel/index.html",
        {
            "posts": posts,
            "total": total,
            "current_status": status or "",
            "current_sort": sort,
            "page": page,
            "pages": pages,
        },
    )


# ---------------------------------------------------------------------------
# GET /new  — new post form
# ---------------------------------------------------------------------------


@router.get("/new", response_class=HTMLResponse)
async def channel_new(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "channel/edit.html",
        {"post": None},
    )


# ---------------------------------------------------------------------------
# POST /  — create post
# ---------------------------------------------------------------------------


@router.post("/", response_class=HTMLResponse)
async def channel_create(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    post = await channel_service.create_post(db, title=title, content=content, user_id=current_user.id)
    return Response(
        status_code=302,
        headers={"Location": f"/ui/channel/{post.id}"},
    )


# ---------------------------------------------------------------------------
# GET /{post_id}  — edit page
# ---------------------------------------------------------------------------


@router.get("/{post_id}", response_class=HTMLResponse)
async def channel_edit(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    post = await channel_service.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return templates.TemplateResponse(
        request,
        "channel/edit.html",
        {"post": post},
    )


# ---------------------------------------------------------------------------
# POST /{post_id}  — update post
# ---------------------------------------------------------------------------


@router.post("/{post_id}", response_class=HTMLResponse)
async def channel_update(
    request: Request,
    post_id: int,
    title: str = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    post = await channel_service.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        from app.models.channel_post import PostStatus
        if post.status == PostStatus.published:
            await channel_service.edit_published(db, post_id=post_id, content=content)
        else:
            await channel_service.update_post(db, post_id=post_id, title=title, content=content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        status_code=302,
        headers={"Location": f"/ui/channel/{post_id}"},
    )


# ---------------------------------------------------------------------------
# DELETE /{post_id}  — delete post
# ---------------------------------------------------------------------------


@router.delete("/{post_id}")
async def channel_delete(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    await channel_service.delete_post(db, post_id)
    return Response(
        status_code=200,
        headers={"HX-Redirect": "/ui/channel/"},
        content="",
    )


# ---------------------------------------------------------------------------
# POST /{post_id}/publish  — publish to Telegram
# ---------------------------------------------------------------------------


@router.post("/{post_id}/publish", response_class=HTMLResponse)
async def channel_publish(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    try:
        post = await channel_service.publish_post(db, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return templates.TemplateResponse(
        request,
        "channel/_post_row.html",
        {"post": post},
    )


# ---------------------------------------------------------------------------
# POST /{post_id}/schedule  — schedule for future publishing
# ---------------------------------------------------------------------------


@router.post("/{post_id}/schedule", response_class=HTMLResponse)
async def channel_schedule(
    request: Request,
    post_id: int,
    scheduled_at: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    try:
        # Parse datetime-local input (e.g. "2026-04-15T14:30")
        dt = datetime.fromisoformat(scheduled_at)
        # Treat as UTC if no timezone info
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        post = await channel_service.schedule_post(db, post_id, scheduled_at=dt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return templates.TemplateResponse(
        request,
        "channel/_post_row.html",
        {"post": post},
    )


# ---------------------------------------------------------------------------
# POST /{post_id}/pin  — toggle pin
# ---------------------------------------------------------------------------


@router.post("/{post_id}/pin", response_class=HTMLResponse)
async def channel_pin(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    try:
        post = await channel_service.toggle_pin(db, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return templates.TemplateResponse(
        request,
        "channel/_post_row.html",
        {"post": post},
    )


# ---------------------------------------------------------------------------
# GET /{post_id}/preview  — render Markdown preview (HTMX partial)
# ---------------------------------------------------------------------------


@router.get("/{post_id}/preview", response_class=HTMLResponse)
async def channel_preview(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    post = await channel_service.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    rendered = _render_content(post.content)
    return templates.TemplateResponse(
        request,
        "channel/_preview.html",
        {"rendered_content": rendered},
    )


def _render_content(content: str) -> str:
    """Render post content to HTML for preview. Uses markdown if available."""
    if not content:
        return ""
    try:
        import markdown
        return markdown.markdown(content, extensions=["nl2br"])
    except ImportError:
        return content.replace("\n", "<br>")
