"""Traffic Analysis router: Metrika analysis, log upload, bot detection, anomalies."""
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.site import Site
from app.models.traffic_analysis import BotPattern, TrafficAnalysisSession, TrafficVisit, VisitSource
from app.models.user import User
from app.services import traffic_analysis_service as tas

router = APIRouter(prefix="/traffic-analysis", tags=["traffic-analysis"])
templates = Jinja2Templates(directory="app/templates")


class AnalyzeRequest(BaseModel):
    date_from: str
    date_to: str


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/{site_id}", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    site = await _get_site_or_404(db, site_id)
    sessions = (await db.execute(
        select(TrafficAnalysisSession)
        .where(TrafficAnalysisSession.site_id == site_id)
        .order_by(TrafficAnalysisSession.created_at.desc())
        .limit(10)
    )).scalars().all()

    return templates.TemplateResponse("traffic_analysis/index.html", {
        "request": request, "site": site, "sessions": sessions,
    })


@router.post("/{site_id}/analyze-metrika")
async def analyze_metrika(
    site_id: uuid.UUID,
    body: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    site = await _get_site_or_404(db, site_id)

    # Load Metrika daily data
    from app.services.metrika_service import get_daily_traffic
    daily = await get_daily_traffic(db, site_id, body.date_from, body.date_to)

    if not daily:
        return {"error": "No Metrika data for this period"}

    # Detect anomalies
    visits_by_day = [{"date": d["date"], "visits": d["visits"]} for d in daily]
    anomaly_result = tas.detect_anomalies(visits_by_day)

    # Create session
    session = TrafficAnalysisSession(
        site_id=site_id,
        name=f"Метрика: {body.date_from} — {body.date_to}",
        period_start=date.fromisoformat(body.date_from),
        period_end=date.fromisoformat(body.date_to),
        source_type="metrika",
        total_visits=sum(d["visits"] for d in daily),
        organic_visits=sum(d["visits"] for d in daily),
        anomaly_detected=anomaly_result["anomaly_detected"],
    )
    db.add(session)
    await db.flush()
    await db.commit()

    return {
        "session_id": str(session.id),
        "total_visits": session.total_visits,
        "anomaly_detected": session.anomaly_detected,
        "anomaly_days": anomaly_result.get("anomaly_days", []),
        "baseline_avg": anomaly_result.get("baseline_avg", 0),
    }


@router.post("/{site_id}/upload-log")
async def upload_log(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)
    content = (await file.read()).decode("utf-8", errors="replace")
    parsed = tas.parse_access_log(content)

    if not parsed:
        return {"error": "Could not parse log file"}

    # Get bot patterns
    bot_result = await db.execute(select(BotPattern).where(BotPattern.is_active == True))  # noqa: E712
    bot_patterns = [{"pattern_type": p.pattern_type, "pattern_value": p.pattern_value, "is_active": True} for p in bot_result.scalars().all()]

    # Classify visits
    bot_count = 0
    for v in parsed:
        classification = tas.classify_visit(v.get("user_agent", ""), v.get("ip_address", ""), v.get("referer", ""), bot_patterns)
        v["is_bot"] = classification["is_bot"]
        v["source"] = classification["source"]
        v["bot_reason"] = classification["bot_reason"]
        if classification["is_bot"]:
            bot_count += 1

    # Determine period from parsed timestamps
    timestamps = [v.get("timestamp") for v in parsed if v.get("timestamp")]
    period_start = min(timestamps).date() if timestamps else date.today()
    period_end = max(timestamps).date() if timestamps else date.today()

    # Create session
    session = TrafficAnalysisSession(
        site_id=site_id,
        name=f"Access log: {file.filename}",
        period_start=period_start,
        period_end=period_end,
        source_type="access_log",
        total_visits=len(parsed),
        bot_visits=bot_count,
        organic_visits=len(parsed) - bot_count,
    )
    db.add(session)
    await db.flush()

    # Persist individual visit rows for dashboard queries
    for v in parsed:
        visit = TrafficVisit(
            session_id=session.id,
            timestamp=v.get("timestamp", datetime.utcnow()),
            page_url=v.get("page_url", v.get("url", "/")),
            source=v.get("source", VisitSource.organic),
            referer=v.get("referer"),
            user_agent=v.get("user_agent"),
            ip_address=v.get("ip_address"),
            is_bot=v.get("is_bot", False),
            bot_reason=v.get("bot_reason"),
        )
        db.add(visit)

    await db.commit()

    return {
        "session_id": str(session.id),
        "total": len(parsed),
        "bots": bot_count,
        "humans": len(parsed) - bot_count,
    }


@router.get("/{site_id}/sessions", response_model=None)
async def list_sessions(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    result = await db.execute(
        select(TrafficAnalysisSession)
        .where(TrafficAnalysisSession.site_id == site_id)
        .order_by(TrafficAnalysisSession.created_at.desc())
    )
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "source_type": s.source_type,
            "total_visits": s.total_visits,
            "bot_visits": s.bot_visits,
            "anomaly_detected": s.anomaly_detected,
            "period": f"{s.period_start} — {s.period_end}",
        }
        for s in result.scalars().all()
    ]


@router.get("/sessions/{session_id}")
async def session_detail(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    result = await db.execute(
        select(TrafficAnalysisSession).where(TrafficAnalysisSession.id == session_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": str(s.id), "name": s.name, "source_type": s.source_type,
        "total_visits": s.total_visits, "bot_visits": s.bot_visits,
        "organic_visits": s.organic_visits, "anomaly_detected": s.anomaly_detected,
    }


@router.get("/sessions/{session_id}/visits")
async def session_visits(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Visit data for Chart.js timeline."""
    result = await db.execute(
        select(TrafficVisit)
        .where(TrafficVisit.session_id == session_id)
        .order_by(TrafficVisit.timestamp)
        .limit(5000)
    )
    visits = result.scalars().all()
    return [
        {
            "timestamp": v.timestamp.isoformat(),
            "page_url": v.page_url,
            "source": v.source.value if v.source else "organic",
            "is_bot": v.is_bot,
            "bot_reason": v.bot_reason,
            "referer": v.referer,
            "user_agent": v.user_agent,
            "ip_address": v.ip_address,
            "geo_country": v.geo_country,
        }
        for v in visits
    ]


@router.get("/sessions/{session_id}/anomalies")
async def session_anomalies(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Anomaly detection results for a session."""
    result = await db.execute(
        select(TrafficAnalysisSession).where(TrafficAnalysisSession.id == session_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load visits grouped by day
    visits_result = await db.execute(
        select(TrafficVisit)
        .where(TrafficVisit.session_id == session_id)
        .order_by(TrafficVisit.timestamp)
    )
    visits = visits_result.scalars().all()

    from collections import Counter
    daily: Counter = Counter()
    for v in visits:
        day = v.timestamp.date().isoformat()
        daily[day] += 1

    visits_by_day = [{"date": d, "visits": c} for d, c in sorted(daily.items())]
    anomaly_result = tas.detect_anomalies(visits_by_day)

    return {
        "anomaly_detected": s.anomaly_detected or anomaly_result["anomaly_detected"],
        "anomaly_days": anomaly_result["anomaly_days"],
        "baseline_avg": anomaly_result["baseline_avg"],
        "std_dev": anomaly_result["std_dev"],
        "visits_by_day": visits_by_day,
    }


@router.get("/sessions/{session_id}/bots")
async def session_bots(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Bot-flagged visits for a session."""
    result = await db.execute(
        select(TrafficVisit)
        .where(TrafficVisit.session_id == session_id, TrafficVisit.is_bot == True)  # noqa: E712
        .order_by(TrafficVisit.timestamp.desc())
        .limit(1000)
    )
    visits = result.scalars().all()
    return [
        {
            "timestamp": v.timestamp.isoformat(),
            "ip_address": v.ip_address,
            "user_agent": v.user_agent,
            "referer": v.referer,
            "page_url": v.page_url,
            "bot_reason": v.bot_reason,
        }
        for v in visits
    ]


@router.get("/sessions/{session_id}/injections")
async def session_injections(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Injection patterns detected for a session."""
    visits_result = await db.execute(
        select(TrafficVisit)
        .where(TrafficVisit.session_id == session_id)
        .limit(10000)
    )
    visits = visits_result.scalars().all()
    visits_dicts = [
        {
            "referer": v.referer,
            "ip_address": v.ip_address,
            "geo_country": v.geo_country,
            "page_url": v.page_url,
            "source": v.source.value if v.source else "organic",
        }
        for v in visits
    ]
    patterns = tas.detect_injection_patterns(visits_dicts)
    sources = tas.analyze_traffic_sources(visits_dicts)
    return {
        "patterns": patterns,
        "source_summary": {
            "organic": sources["organic"],
            "direct": sources["direct"],
            "referral": sources["referral"],
            "bot": sources["bot"],
            "injection": sources["injection"],
        },
        "top_referers": list(sources["by_referer"].items())[:10],
        "top_landings": list(sources["by_landing"].items())[:10],
    }
