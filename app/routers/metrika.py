"""Metrika router: traffic dashboard, data fetch, events CRUD, settings."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.site import Site
from app.models.user import User
from app.services import metrika_service
from app.services import site_service
from app.services.crypto_service import encrypt
from app.tasks.metrika_tasks import fetch_metrika_data

router = APIRouter(prefix="/metrika", tags=["metrika"])

templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class MetrikaSettingsUpdate(BaseModel):
    counter_id: str
    token: str


class MetrikaFetchRequest(BaseModel):
    date1: str | None = None
    date2: str | None = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{site_id}/widget", response_class=HTMLResponse)
async def metrika_widget(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial: traffic summary widget for site overview."""
    site = await site_service.get_site(db, site_id)
    if not site or not site.metrika_counter_id:
        return HTMLResponse("")  # hidden entirely if not configured

    date_to = date.today()
    date_from = date_to - timedelta(days=30)

    daily = await metrika_service.get_daily_traffic(db, site_id, date_from, date_to)

    if not daily:
        # Configured but no data fetched yet
        return templates.TemplateResponse(
            request,
            "metrika/_widget.html",
            {"site": site, "has_data": False, "totals": None, "sparkline_data": []},
        )

    # Compute 30-day totals
    total_visits = sum(d["visits"] for d in daily)
    avg_bounce = round(sum(d.get("bounce_rate") or 0 for d in daily) / max(len(daily), 1), 1)
    avg_depth = round(sum(d.get("page_depth") or 0 for d in daily) / max(len(daily), 1), 1)
    avg_dur = int(sum(d.get("avg_duration_seconds") or 0 for d in daily) / max(len(daily), 1))

    totals = {
        "visits": total_visits,
        "bounce_rate": avg_bounce,
        "page_depth": avg_depth,
        "avg_duration_seconds": avg_dur,
    }
    sparkline_data = [d["visits"] for d in daily]

    return templates.TemplateResponse(
        request,
        "metrika/_widget.html",
        {"site": site, "has_data": True, "totals": totals, "sparkline_data": sparkline_data},
    )


@router.get("/ui/metrika", response_class=HTMLResponse)
async def ui_metrika_redirect(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Redirect /ui/metrika to the first site's traffic page."""
    from fastapi.responses import RedirectResponse
    sites = await site_service.get_sites(db)
    if not sites:
        return HTMLResponse("<p>Нет сайтов. Сначала добавьте сайт.</p>", status_code=200)
    return RedirectResponse(f"/ui/metrika/{sites[0].id}")


@router.get("/ui/metrika/{site_id}", response_class=HTMLResponse)
async def ui_metrika_page(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Render the Metrika traffic dashboard page at /ui/metrika/{site_id}."""
    site = await site_service.get_site(db, site_id)
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    daily_data: list[dict] = []
    page_data: list[dict] = []
    events: list = []

    if site.metrika_counter_id:
        date_to = date.today() - timedelta(days=1)
        date_from = date_to - timedelta(days=29)

        daily_data = await metrika_service.get_daily_traffic(db, site_id, date_from, date_to)
        page_data = await metrika_service.get_page_traffic(db, site_id, date_from, date_to)
        events = await metrika_service.get_events(db, site_id)

    return templates.TemplateResponse(
        request,
        "metrika/index.html",
        {
            "site": site,
            "daily_data": daily_data,
            "page_data": page_data,
            "events": events,
        },
    )


@router.get("/{site_id}", response_class=HTMLResponse)
async def metrika_page(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Render the Metrika traffic dashboard page."""
    site = await _get_site_or_404(db, site_id)

    daily_data: list[dict] = []
    page_data: list[dict] = []
    events: list = []

    if site.metrika_counter_id:
        # Default period: last 30 days
        date_to = date.today() - timedelta(days=1)
        date_from = date_to - timedelta(days=29)

        daily_data = await metrika_service.get_daily_traffic(
            db, site_id, date_from, date_to
        )
        page_data = await metrika_service.get_page_traffic(
            db, site_id, date_from, date_to
        )
        events = await metrika_service.get_events(db, site_id)

    return templates.TemplateResponse(
        request,
        "metrika/index.html",
        {
            "site": site,
            "daily_data": daily_data,
            "page_data": page_data,
            "events": events,
        },
    )


@router.post("/{site_id}/fetch")
async def trigger_fetch(
    site_id: uuid.UUID,
    payload: MetrikaFetchRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Dispatch a Celery task to fetch Metrika data for a date range."""
    site = await _get_site_or_404(db, site_id)

    if not site.metrika_counter_id or not site.metrika_token:
        raise HTTPException(
            status_code=400,
            detail="Metrika counter ID and token must be configured before fetching data.",
        )

    # Defaults: date1 = 90 days ago, date2 = yesterday
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    date1 = payload.date1 or (date.today() - timedelta(days=90)).isoformat()
    date2 = payload.date2 or yesterday

    task = fetch_metrika_data.delay(str(site_id), date1, date2)
    return {"status": "queued", "task_id": task.id}


@router.get("/{site_id}/daily")
async def get_daily(
    site_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Return daily traffic data for chart rendering."""
    rows = await metrika_service.get_daily_traffic(db, site_id, date_from, date_to)

    labels = [r["date"] for r in rows]
    visits = [r["visits"] for r in rows]
    bounce_rate = [r["bounce_rate"] for r in rows]
    page_depth = [r["page_depth"] for r in rows]
    avg_duration = [r["avg_duration_seconds"] for r in rows]

    return {
        "labels": labels,
        "visits": visits,
        "bounce_rate": bounce_rate,
        "page_depth": page_depth,
        "avg_duration": avg_duration,
    }


@router.get("/{site_id}/pages")
async def get_pages(
    site_id: uuid.UUID,
    period_start: date,
    period_end: date,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Return per-page traffic data for the given period."""
    return await metrika_service.get_page_traffic(db, site_id, period_start, period_end)


@router.get("/{site_id}/compare")
async def compare_periods(
    site_id: uuid.UUID,
    a_start: date,
    a_end: date,
    b_start: date,
    b_end: date,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Compare traffic between two periods, returning delta rows."""
    rows_a = await metrika_service.get_page_traffic(db, site_id, a_start, a_end)
    rows_b = await metrika_service.get_page_traffic(db, site_id, b_start, b_end)
    return metrika_service.compute_period_delta(rows_a, rows_b)


@router.post("/{site_id}/events", response_class=HTMLResponse)
async def create_event(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Create a new chart event and return updated events list partial."""
    form = await request.form()
    event_date_str = form.get("event_date", "")
    label = str(form.get("label", "")).strip()
    color = str(form.get("color", "#7c3aed")).strip()

    if not event_date_str or not label:
        raise HTTPException(status_code=400, detail="event_date and label are required")

    try:
        event_date = date.fromisoformat(str(event_date_str))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_date format. Use YYYY-MM-DD.")

    await metrika_service.create_event(db, site_id, event_date, label, color)
    await db.commit()

    events = await metrika_service.get_events(db, site_id)
    return templates.TemplateResponse(
        request,
        "metrika/_events_list.html",
        {"events": events, "site_id": site_id},
    )


@router.delete("/{site_id}/events/{event_id}", status_code=status.HTTP_200_OK)
async def delete_event(
    site_id: uuid.UUID,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> str:
    """Delete an event; HTMX removes the element via hx-swap='outerHTML'."""
    deleted = await metrika_service.delete_event(db, event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.commit()
    return ""


@router.put("/{site_id}/settings")
async def update_settings(
    site_id: uuid.UUID,
    payload: MetrikaSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Save Metrika counter ID and encrypted OAuth token for a site."""
    site = await _get_site_or_404(db, site_id)

    site.metrika_counter_id = payload.counter_id.strip()
    site.metrika_token = encrypt(payload.token)

    await db.commit()
    return {"status": "saved"}
