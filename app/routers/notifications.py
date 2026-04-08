"""Notifications router — Phase 17-02.

Endpoints:
- GET /notifications/bell           -- HTMX fragment: unread badge
- GET /notifications/dropdown       -- HTMX fragment: last 10 + auto-mark-read
- GET /notifications                -- Full page with filters and pagination
- POST /notifications/mark-all-read -- Bulk mark all read
- POST /notifications/{id}/dismiss  -- Hard-delete single notification
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select, update, delete, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.models.notification import Notification
from app.models.user import User
from app.template_engine import templates

router = APIRouter(prefix="/notifications", tags=["notifications"])

PAGE_SIZE = 50
DROPDOWN_LIMIT = 10


# ---------------------------------------------------------------------------
# GET /notifications/bell  — HTMX fragment
# ---------------------------------------------------------------------------


@router.get("/bell", response_class=HTMLResponse)
async def bell_fragment(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return the bell badge fragment.

    Context:
    - unread_count: int
    - has_unread_error: bool — True if any unread notification has severity='error'
    """
    result = await db.execute(
        select(
            func.count(Notification.id).label("total"),
            func.count(
                Notification.id
            ).filter(Notification.severity == "error").label("error_count"),
        ).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    )
    row = result.one()
    unread_count = row.total or 0
    has_unread_error = (row.error_count or 0) > 0

    return templates.TemplateResponse(
        request,
        "notifications/_bell.html",
        {
            "unread_count": unread_count,
            "has_unread_error": has_unread_error,
        },
    )


# ---------------------------------------------------------------------------
# GET /notifications/dropdown  — HTMX fragment + auto-mark-read
# ---------------------------------------------------------------------------


@router.get("/dropdown", response_class=HTMLResponse)
async def dropdown_fragment(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return last 10 notifications and mark them as read atomically."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(DROPDOWN_LIMIT)
    )
    notifications = result.scalars().all()

    if notifications:
        ids = [n.id for n in notifications]
        await db.execute(
            update(Notification)
            .where(Notification.id.in_(ids))
            .values(is_read=True)
        )
        await db.commit()
        # Refresh objects so is_read reflects DB state
        for n in notifications:
            n.is_read = True

    return templates.TemplateResponse(
        request,
        "notifications/_dropdown.html",
        {
            "notifications": notifications,
        },
    )


# ---------------------------------------------------------------------------
# GET /notifications  — Full page
# ---------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
async def notifications_index(
    request: Request,
    site_id: Optional[str] = None,
    kind: Optional[str] = None,
    read_state: str = "all",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Full notifications page with filters, grouping by kind, pagination."""
    # Build base query
    base_q = select(Notification).where(Notification.user_id == current_user.id)

    # Parse site_id
    parsed_site_id: Optional[uuid.UUID] = None
    if site_id:
        try:
            parsed_site_id = uuid.UUID(site_id)
            base_q = base_q.where(Notification.site_id == parsed_site_id)
        except ValueError:
            pass

    if kind:
        base_q = base_q.where(Notification.kind == kind)

    if read_state == "unread":
        base_q = base_q.where(Notification.is_read.is_(False))

    # Count total for pagination
    count_q = select(func.count()).select_from(base_q.subquery())
    total_count = (await db.execute(count_q)).scalar() or 0

    # Load page
    offset = (page - 1) * PAGE_SIZE
    result = await db.execute(
        base_q.order_by(Notification.kind, Notification.created_at.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    items = result.scalars().all()

    # Group by kind (D-08)
    groups: dict[str, list[Notification]] = defaultdict(list)
    for n in items:
        groups[n.kind].append(n)

    # Filter bar data: distinct sites and kinds from user's notifications
    sites_result = await db.execute(
        select(Notification.site_id)
        .where(Notification.user_id == current_user.id, Notification.site_id.isnot(None))
        .distinct()
    )
    site_ids_with_notifs = [r[0] for r in sites_result.fetchall()]

    kinds_result = await db.execute(
        select(Notification.kind)
        .where(Notification.user_id == current_user.id)
        .distinct()
    )
    available_kinds = [r[0] for r in kinds_result.fetchall()]

    # Load site names for filter bar
    site_options: list[dict] = []
    if site_ids_with_notifs:
        from app.models.site import Site
        sites_q = select(Site).where(Site.id.in_(site_ids_with_notifs))
        sites_rows = (await db.execute(sites_q)).scalars().all()
        site_options = [{"id": s.id, "name": s.name} for s in sites_rows]

    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)

    return templates.TemplateResponse(
        request,
        "notifications/index.html",
        {
            "groups": dict(groups),
            "site_options": site_options,
            "available_kinds": available_kinds,
            "current_site_id": site_id or "",
            "current_kind": kind or "",
            "current_read_state": read_state,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
        },
    )


# ---------------------------------------------------------------------------
# POST /notifications/mark-all-read  — Bulk mark all read
# ---------------------------------------------------------------------------


@router.post("/mark-all-read", response_class=HTMLResponse)
async def mark_all_read(
    request: Request,
    site_id: Optional[str] = None,
    kind: Optional[str] = None,
    read_state: str = "all",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Mark ALL of current_user's notifications as read. Returns updated _list.html."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()

    # Return updated list fragment with current filters
    base_q = select(Notification).where(Notification.user_id == current_user.id)

    parsed_site_id: Optional[uuid.UUID] = None
    if site_id:
        try:
            parsed_site_id = uuid.UUID(site_id)
            base_q = base_q.where(Notification.site_id == parsed_site_id)
        except ValueError:
            pass

    if kind:
        base_q = base_q.where(Notification.kind == kind)

    if read_state == "unread":
        base_q = base_q.where(Notification.is_read.is_(False))

    count_q = select(func.count()).select_from(base_q.subquery())
    total_count = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * PAGE_SIZE
    result = await db.execute(
        base_q.order_by(Notification.kind, Notification.created_at.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    items = result.scalars().all()

    groups: dict[str, list[Notification]] = defaultdict(list)
    for n in items:
        groups[n.kind].append(n)

    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)

    return templates.TemplateResponse(
        request,
        "notifications/_list.html",
        {
            "groups": dict(groups),
            "current_site_id": site_id or "",
            "current_kind": kind or "",
            "current_read_state": read_state,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
        },
    )


# ---------------------------------------------------------------------------
# POST /notifications/{id}/dismiss  — Hard-delete
# ---------------------------------------------------------------------------


@router.post("/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Hard-delete a single notification. Verifies ownership."""
    n = await db.get(Notification, notification_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    await db.execute(
        delete(Notification).where(Notification.id == notification_id)
    )
    await db.commit()
    return Response(status_code=204)
