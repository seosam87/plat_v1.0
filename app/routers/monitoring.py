"""Change Monitoring router: alert rules, alert history, digest schedule."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from app.template_engine import templates
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.change_monitoring import ChangeAlert, ChangeAlertRule, DigestSchedule
from app.models.site import Site
from app.models.user import User
from app.services import digest_service as ds

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class DigestScheduleUpdate(BaseModel):
    is_active: bool
    day_of_week: int = 1
    hour: int = 9
    minute: int = 0


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ---- Alert rules list (must be declared before /{site_id} to avoid
# being captured as a UUID path param) ----


@router.get("/rules", response_model=None)
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    result = await db.execute(select(ChangeAlertRule).order_by(ChangeAlertRule.change_type))
    return [
        {
            "id": str(r.id),
            "change_type": r.change_type.value,
            "severity": r.severity.value,
            "is_active": r.is_active,
            "description": r.description,
        }
        for r in result.scalars().all()
    ]


@router.get("/{site_id}", response_class=HTMLResponse)
async def monitoring_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Main monitoring page for a site."""
    site = await _get_site_or_404(db, site_id)

    # Alert rules
    rules_result = await db.execute(
        select(ChangeAlertRule).order_by(ChangeAlertRule.change_type)
    )
    rules = rules_result.scalars().all()

    # Recent alerts for this site (last 50)
    alerts_result = await db.execute(
        select(ChangeAlert)
        .where(ChangeAlert.site_id == site_id)
        .order_by(ChangeAlert.created_at.desc())
        .limit(50)
    )
    alerts = alerts_result.scalars().all()

    # Counts by severity (last 7 days)
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    count_result = await db.execute(
        select(ChangeAlert.severity, func.count())
        .where(ChangeAlert.site_id == site_id, ChangeAlert.created_at >= cutoff)
        .group_by(ChangeAlert.severity)
    )
    severity_counts = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in count_result.all()}

    # Digest schedule
    digest_sched = await ds.get_digest_schedule(db, site_id)

    return templates.TemplateResponse(
        "monitoring/index.html",
        {
            "request": request,
            "site": site,
            "rules": rules,
            "alerts": alerts,
            "error_count": severity_counts.get("error", 0),
            "warning_count": severity_counts.get("warning", 0),
            "total_count": sum(severity_counts.values()),
            "digest_schedule": digest_sched,
        },
    )


# ---- Alert rules (global) ----


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    body = await request.json()
    result = await db.execute(select(ChangeAlertRule).where(ChangeAlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in body.items():
        if hasattr(rule, k):
            setattr(rule, k, v)
    await db.flush()
    await db.commit()
    return {"status": "updated"}


# ---- Alert history ----


@router.get("/{site_id}/alerts", response_model=None)
async def list_alerts(
    site_id: uuid.UUID,
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    q = (
        select(ChangeAlert)
        .where(ChangeAlert.site_id == site_id)
        .order_by(ChangeAlert.created_at.desc())
        .limit(100)
    )
    if severity:
        q = q.where(ChangeAlert.severity == severity)
    result = await db.execute(q)
    return [
        {
            "id": str(a.id),
            "change_type": a.change_type.value if hasattr(a.change_type, "value") else a.change_type,
            "severity": a.severity.value if hasattr(a.severity, "value") else a.severity,
            "page_url": a.page_url,
            "details": a.details,
            "sent_at": a.sent_at.isoformat() if a.sent_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in result.scalars().all()
    ]


@router.get("/{site_id}/alerts/count")
async def alert_counts(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(ChangeAlert.severity, func.count())
        .where(ChangeAlert.site_id == site_id, ChangeAlert.created_at >= cutoff)
        .group_by(ChangeAlert.severity)
    )
    counts = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in result.all()}
    return counts


# ---- Digest ----


@router.get("/{site_id}/digest-schedule")
async def get_digest_schedule(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    sched = await ds.get_digest_schedule(db, site_id)
    if not sched:
        return {"is_active": False, "day_of_week": 1, "hour": 9, "minute": 0}
    return {
        "is_active": sched.is_active,
        "day_of_week": sched.day_of_week,
        "hour": sched.hour,
        "minute": sched.minute,
        "cron_expression": sched.cron_expression,
    }


@router.put("/{site_id}/digest-schedule")
async def update_digest_schedule(
    site_id: uuid.UUID,
    body: DigestScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)
    sched = await ds.upsert_digest_schedule(
        db, site_id, body.is_active, body.day_of_week, body.hour, body.minute
    )
    await db.commit()
    return {"status": "saved", "cron_expression": sched.cron_expression}


@router.post("/{site_id}/digest/send")
async def send_digest_now(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)
    from app.tasks.digest_tasks import send_weekly_digest
    task = send_weekly_digest.delay(str(site_id))
    return {"task_id": task.id, "status": "started"}
