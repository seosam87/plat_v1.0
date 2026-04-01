"""Report generation service: dashboard aggregation, PDF, Excel."""
from __future__ import annotations

import io
from datetime import date

import openpyxl
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ad_traffic import AdTraffic
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.task import SeoTask, TaskStatus


async def dashboard_summary(db: AsyncSession) -> dict:
    """Aggregate dashboard data across all projects."""
    projects = (await db.execute(select(func.count()).select_from(Project))).scalar_one()
    total_keywords = (await db.execute(select(func.count()).select_from(Keyword))).scalar_one()
    open_tasks = (await db.execute(
        select(func.count()).select_from(SeoTask).where(SeoTask.status == TaskStatus.open)
    )).scalar_one()
    in_progress_tasks = (await db.execute(
        select(func.count()).select_from(SeoTask).where(SeoTask.status == TaskStatus.in_progress)
    )).scalar_one()

    return {
        "projects": projects,
        "total_keywords": total_keywords,
        "open_tasks": open_tasks,
        "in_progress_tasks": in_progress_tasks,
    }


def generate_excel_report(
    project_name: str,
    keywords: list[dict],
    tasks: list[dict],
    positions: list[dict],
) -> bytes:
    """Generate a multi-sheet Excel report."""
    wb = openpyxl.Workbook()

    # Positions sheet
    ws_pos = wb.active
    ws_pos.title = "Positions"
    ws_pos.append(["Keyword", "Position", "Delta", "URL", "Engine"])
    for p in positions:
        ws_pos.append([p.get("query", ""), p.get("position"), p.get("delta"), p.get("url", ""), p.get("engine", "")])

    # Keywords sheet
    ws_kw = wb.create_sheet("Keywords")
    ws_kw.append(["Phrase", "Frequency", "Region", "Engine", "Target URL"])
    for k in keywords:
        ws_kw.append([k.get("phrase", ""), k.get("frequency"), k.get("region", ""), k.get("engine", ""), k.get("target_url", "")])

    # Tasks sheet
    ws_tasks = wb.create_sheet("Tasks")
    ws_tasks.append(["Title", "Type", "Status", "URL"])
    for t in tasks:
        ws_tasks.append([t.get("title", ""), t.get("task_type", ""), t.get("status", ""), t.get("url", "")])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


async def ad_traffic_comparison(
    db: AsyncSession,
    site_id,
    period_a_start: date,
    period_a_end: date,
    period_b_start: date,
    period_b_end: date,
) -> list[dict]:
    """Compare ad traffic between two periods."""
    async def _agg(start: date, end: date) -> dict:
        result = await db.execute(
            select(
                AdTraffic.source,
                func.sum(AdTraffic.sessions).label("sessions"),
                func.sum(AdTraffic.conversions).label("conversions"),
                func.sum(AdTraffic.cost).label("cost"),
            )
            .where(AdTraffic.site_id == site_id, AdTraffic.traffic_date.between(start, end))
            .group_by(AdTraffic.source)
        )
        return {r.source: {"sessions": r.sessions, "conversions": r.conversions, "cost": float(r.cost)} for r in result}

    a = await _agg(period_a_start, period_a_end)
    b = await _agg(period_b_start, period_b_end)

    sources = sorted(set(list(a.keys()) + list(b.keys())))
    comparison = []
    for src in sources:
        va = a.get(src, {"sessions": 0, "conversions": 0, "cost": 0})
        vb = b.get(src, {"sessions": 0, "conversions": 0, "cost": 0})

        def _delta(old, new):
            if old == 0:
                return None
            return round((new - old) / old * 100, 1)

        comparison.append({
            "source": src,
            "period_a": va,
            "period_b": vb,
            "delta_sessions_pct": _delta(va["sessions"], vb["sessions"]),
            "delta_conversions_pct": _delta(va["conversions"], vb["conversions"]),
            "delta_cost_pct": _delta(va["cost"], vb["cost"]),
        })

    return comparison
