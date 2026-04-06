"""Client instruction PDF router: generation, status, download, delivery."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.client_report import ClientReport
from app.models.site import Site
from app.models.user import User
from app.template_engine import templates

router = APIRouter(prefix="/ui/client-reports", tags=["client-reports"])


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/", response_class=HTMLResponse)
async def client_reports_page(
    request: Request,
    site_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Main client reports page with generation form and history."""
    from app.services.client_report_service import get_report_history

    # Load all sites
    result = await db.execute(select(Site).order_by(Site.name))
    sites = result.scalars().all()

    # Resolve selected site: query param > cookie > first site
    selected_site = None
    if site_id:
        selected_site = await db.execute(select(Site).where(Site.id == site_id))
        selected_site = selected_site.scalar_one_or_none()

    if selected_site is None and sites:
        # Try cookie
        cookie_site_id = request.cookies.get("selected_site_id")
        if cookie_site_id:
            try:
                result2 = await db.execute(
                    select(Site).where(Site.id == uuid.UUID(cookie_site_id))
                )
                selected_site = result2.scalar_one_or_none()
            except (ValueError, Exception):
                pass

    if selected_site is None and sites:
        selected_site = sites[0]

    # Load report history for selected site
    reports: list[ClientReport] = []
    if selected_site:
        reports = await get_report_history(db, selected_site.id)

    return templates.TemplateResponse(
        request,
        "client_reports/index.html",
        {
            "sites": sites,
            "site": selected_site,
            "reports": reports,
        },
    )


@router.post("/generate", response_class=HTMLResponse)
async def generate_report(
    request: Request,
    site_id: uuid.UUID = Form(...),
    quick_wins: bool = Form(False),
    audit_errors: bool = Form(False),
    dead_content: bool = Form(False),
    positions: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Start async PDF generation via Celery task."""
    from app.services.client_report_service import create_report_record
    from app.tasks.client_report_tasks import generate_client_pdf

    blocks_config = {
        "quick_wins": quick_wins,
        "audit_errors": audit_errors,
        "dead_content": dead_content,
        "positions": positions,
    }

    # Validate at least one block is selected
    if not any(blocks_config.values()):
        return templates.TemplateResponse(
            request,
            "client_reports/partials/generation_status.html",
            {
                "status": "failed",
                "error": "Выберите хотя бы один блок для генерации отчёта.",
                "report_id": None,
            },
        )

    site = await _get_site_or_404(db, site_id)

    # Create pending record
    report = await create_report_record(db, site_id, blocks_config)

    # Dispatch Celery task
    task = generate_client_pdf.delay(str(report.id), str(site_id), blocks_config)

    # Store task id
    report.celery_task_id = task.id
    await db.commit()

    return templates.TemplateResponse(
        request,
        "client_reports/partials/generation_status.html",
        {
            "status": "generating",
            "report_id": str(report.id),
            "site": site,
        },
    )


@router.get("/status/{report_id}", response_class=HTMLResponse)
async def report_status(
    request: Request,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Poll generation status (HTMX polling endpoint)."""
    result = await db.execute(
        select(ClientReport).where(ClientReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    context = {
        "status": report.status,
        "report_id": str(report.id),
        "report": report,
    }

    response = templates.TemplateResponse(
        request,
        "client_reports/partials/generation_status.html",
        context,
    )

    # Trigger history refresh when ready
    if report.status == "ready":
        response.headers["HX-Trigger"] = "refreshHistory"

    return response


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> Response:
    """Download completed PDF."""
    result = await db.execute(
        select(ClientReport).where(ClientReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "ready" or report.pdf_data is None:
        raise HTTPException(status_code=400, detail="PDF not yet available")

    return Response(
        content=report.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="client-report-{report.id}.pdf"'
        },
    )


@router.post("/{report_id}/send-email", response_class=HTMLResponse)
async def send_report_email(
    request: Request,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Dispatch email delivery task (HTMX)."""
    from app.tasks.client_report_tasks import send_client_report_email

    result = await db.execute(
        select(ClientReport).where(ClientReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report or report.status != "ready":
        raise HTTPException(status_code=400, detail="Report not ready")

    send_client_report_email.delay(str(report_id))

    return HTMLResponse(
        content='<div class="toast toast-success">Отчёт отправлен на email.</div>'
    )


@router.post("/{report_id}/send-telegram", response_class=HTMLResponse)
async def send_report_telegram(
    request: Request,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Dispatch Telegram delivery task (HTMX)."""
    from app.tasks.client_report_tasks import send_client_report_telegram

    result = await db.execute(
        select(ClientReport).where(ClientReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report or report.status != "ready":
        raise HTTPException(status_code=400, detail="Report not ready")

    send_client_report_telegram.delay(str(report_id))

    return HTMLResponse(
        content='<div class="toast toast-success">Отчёт отправлен в Telegram.</div>'
    )


@router.get("/history", response_class=HTMLResponse)
async def report_history(
    request: Request,
    site_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Return history table partial (HTMX)."""
    from app.services.client_report_service import get_report_history

    site = None
    reports: list[ClientReport] = []

    if site_id:
        site = await db.execute(select(Site).where(Site.id == site_id))
        site = site.scalar_one_or_none()
        if site:
            reports = await get_report_history(db, site_id)

    return templates.TemplateResponse(
        request,
        "client_reports/partials/history_table.html",
        {
            "site": site,
            "reports": reports,
        },
    )
