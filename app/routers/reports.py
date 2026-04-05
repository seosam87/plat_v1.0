"""Reports router: dashboard, PDF/Excel export, ad traffic upload + comparison."""
import csv
import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.ad_traffic import AdTraffic
from app.models.keyword import Keyword
from app.models.task import SeoTask
from app.models.user import User
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    return await report_service.dashboard_summary(db)


@router.get("/sites/{site_id}/overview")
async def site_overview(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Aggregated site overview: positions, keywords, tasks, top movers."""
    return await report_service.site_overview(db, site_id)


@router.get("/projects/{project_id}/pdf")
async def export_pdf(
    project_id: uuid.UUID,
    type: str = "brief",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Generate and download a PDF report for a project (brief or detailed)."""
    if type not in ("brief", "detailed"):
        type = "brief"
    pdf_bytes = await report_service.generate_pdf_report(db, project_id, type)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{project_id}_{type}.pdf"'},
    )


@router.get("/projects/{project_id}/excel")
async def export_excel(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    from app.models.project import Project

    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    keywords = (await db.execute(
        select(Keyword).where(Keyword.site_id == project.site_id)
    )).scalars().all()
    kw_data = [{"phrase": k.phrase, "frequency": k.frequency, "region": k.region, "engine": k.engine.value if k.engine else "", "target_url": k.target_url or ""} for k in keywords]

    tasks = (await db.execute(
        select(SeoTask).where(SeoTask.project_id == project_id)
    )).scalars().all()
    tasks_data = [{"title": t.title, "task_type": t.task_type.value, "status": t.status.value, "url": t.url} for t in tasks]

    excel_bytes = report_service.generate_excel_report(project.name, kw_data, tasks_data, [])

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="report_{project_id}.xlsx"'},
    )


# ---- Ad traffic ----

@router.post("/sites/{site_id}/ad-traffic/upload")
async def upload_ad_traffic(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Upload ad traffic CSV (columns: source, date, sessions, conversions, cost)."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    count = 0
    for row in reader:
        try:
            ad = AdTraffic(
                site_id=site_id,
                source=row.get("source", "unknown"),
                traffic_date=date.fromisoformat(row.get("date", "")),
                sessions=int(row.get("sessions", 0)),
                conversions=int(row.get("conversions", 0)),
                cost=float(row.get("cost", 0)),
            )
            db.add(ad)
            count += 1
        except (ValueError, KeyError):
            continue

    await db.flush()
    await db.commit()
    return {"rows_imported": count}


class CompareRequest(BaseModel):
    period_a_start: date
    period_a_end: date
    period_b_start: date
    period_b_end: date


@router.post("/sites/{site_id}/ad-traffic/compare")
async def compare_ad_traffic(
    site_id: uuid.UUID,
    payload: CompareRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    comparison = await report_service.ad_traffic_comparison(
        db, site_id,
        payload.period_a_start, payload.period_a_end,
        payload.period_b_start, payload.period_b_end,
    )
    return {"comparison": comparison}


@router.get("/sites/{site_id}/ad-traffic/trend")
async def ad_traffic_trend(
    site_id: uuid.UUID,
    granularity: str = "weekly",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Return Chart.js-compatible weekly/monthly trend data per source."""
    if granularity not in ("weekly", "monthly"):
        granularity = "weekly"
    return await report_service.ad_traffic_trend(db, site_id, granularity)
