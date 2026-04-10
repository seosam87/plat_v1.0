"""Tools router: TOOL_REGISTRY dispatch, 7 route handlers for Phase 24-25 tools."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from celery import chain as celery_chain
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import openpyxl

from app.dependencies import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.rate_limit import limiter
from app.template_engine import templates

router = APIRouter(prefix="/ui/tools", tags=["tools"])

# Tool metadata — models and tasks populated by Plans 02-04.
# form_field: HTML textarea name attribute
# input_col: Job model column for storing input list
# count_col: Job model column for input count
TOOL_REGISTRY: dict[str, dict] = {
    "commercialization": {
        "name": "Проверка коммерциализации",
        "description": "Анализ коммерциализации поисковой выдачи по ключевым фразам",
        "input_type": "phrases",
        "form_field": "phrases",
        "input_col": "input_phrases",
        "count_col": "phrase_count",
        "limit": 200,
        "cta": "Проверить коммерциализацию",
        "slug": "commercialization",
        "has_domain_field": False,
    },
    "meta-parser": {
        "name": "Парсер мета-тегов",
        "description": "Извлечение title, description, H1, H2 и canonical с указанных URL",
        "input_type": "urls",
        "form_field": "urls",
        "input_col": "input_urls",
        "count_col": "url_count",
        "limit": 500,
        "cta": "Запустить парсинг",
        "slug": "meta-parser",
        "has_domain_field": False,
    },
    "relevant-url": {
        "name": "Поиск релевантного URL",
        "description": "Поиск релевантных страниц домена в ТОП-10 Яндекса по ключевым фразам",
        "input_type": "phrases",
        "form_field": "phrases",
        "input_col": "input_phrases",
        "count_col": "phrase_count",
        "limit": 100,
        "cta": "Найти релевантные URL",
        "slug": "relevant-url",
        "has_domain_field": True,
    },
    "brief": {
        "name": "Копирайтерское ТЗ",
        "description": "Анализ ТОП-10 выдачи: сбор H2, тематических слов и статистики страниц",
        "input_type": "phrases",
        "form_field": "phrases",
        "input_col": "input_phrases",
        "count_col": "phrase_count",
        "limit": 50,
        "cta": "Создать ТЗ",
        "slug": "brief",
        "has_domain_field": False,
    },
}

# Export column headers per tool
_EXPORT_HEADERS: dict[str, list[str]] = {
    "commercialization": ["Фраза", "Коммерциализация", "Интент", "Геозависимость", "Локализация"],
    "meta-parser": ["URL", "Статус", "Title", "Description", "H1", "Robots", "Canonical"],
    "relevant-url": ["Фраза", "URL", "Позиция", "Топ-3 конкурента"],
    "brief": ["Показатель", "Значение"],  # Brief uses sectioned XLSX export
}


def _get_tool_models(slug: str):
    """Lazy-import tool models to avoid circular imports."""
    if slug == "commercialization":
        from app.models.commerce_check_job import CommerceCheckJob, CommerceCheckResult
        return CommerceCheckJob, CommerceCheckResult
    elif slug == "meta-parser":
        from app.models.meta_parse_job import MetaParseJob, MetaParseResult
        return MetaParseJob, MetaParseResult
    elif slug == "relevant-url":
        from app.models.relevant_url_job import RelevantUrlJob, RelevantUrlResult
        return RelevantUrlJob, RelevantUrlResult
    elif slug == "brief":
        from app.models.brief_job import BriefJob, BriefResult
        return BriefJob, BriefResult
    raise HTTPException(status_code=404, detail="Unknown tool")


def _get_tool_task(slug: str):
    """Lazy-import tool task to avoid circular imports."""
    if slug == "commercialization":
        from app.tasks.commerce_check_tasks import run_commerce_check
        return run_commerce_check
    elif slug == "meta-parser":
        from app.tasks.meta_parse_tasks import run_meta_parse
        return run_meta_parse
    elif slug == "relevant-url":
        from app.tasks.relevant_url_tasks import run_relevant_url
        return run_relevant_url
    elif slug == "brief":
        # Brief uses a 4-step chain — caller must handle this specially
        # Returns None to signal chain dispatch in tool_submit
        return None
    raise HTTPException(status_code=404, detail="Unknown tool")


def _result_to_row(result, slug: str) -> list:
    """Convert a result ORM row to a list of cell values for export.

    Brief results use a sectioned XLSX export and should never reach this path.
    """
    if slug == "brief":
        # Brief export uses a multi-section XLSX — this path should not be reached
        return []
    if slug == "commercialization":
        return [
            getattr(result, "phrase", ""),
            getattr(result, "commercialization", ""),
            getattr(result, "intent", ""),
            "Да" if getattr(result, "geo_dependent", False) else "Нет",
            "Да" if getattr(result, "localized", False) else "Нет",
        ]
    elif slug == "meta-parser":
        return [
            getattr(result, "input_url", ""),
            getattr(result, "status_code", ""),
            getattr(result, "title", ""),
            getattr(result, "meta_description", ""),
            getattr(result, "h1", ""),
            getattr(result, "robots", ""),
            getattr(result, "canonical", ""),
        ]
    elif slug == "relevant-url":
        competitors = getattr(result, "top_competitors", None) or []
        return [
            getattr(result, "phrase", ""),
            getattr(result, "url", "") or "Не найден",
            getattr(result, "position", "") or "",
            ", ".join(competitors) if competitors else "",
        ]
    return []


# ---------------------------------------------------------------------------
# 1. GET / — tools index: card grid with job count badges
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse, name="tools_index")
async def tools_index(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Tools index page with 3 tool cards and per-user job count badges."""
    from app.models.brief_job import BriefJob
    from app.models.commerce_check_job import CommerceCheckJob
    from app.models.meta_parse_job import MetaParseJob
    from app.models.relevant_url_job import RelevantUrlJob

    job_counts: dict[str, int] = {}
    for slug, model_cls in [
        ("commercialization", CommerceCheckJob),
        ("meta-parser", MetaParseJob),
        ("relevant-url", RelevantUrlJob),
        ("brief", BriefJob),
    ]:
        result = await db.execute(
            select(func.count(model_cls.id)).where(model_cls.user_id == user.id)
        )
        job_counts[slug] = result.scalar() or 0

    tools = []
    for slug, info in TOOL_REGISTRY.items():
        tools.append({**info, "job_count": job_counts.get(slug, 0)})

    return templates.TemplateResponse(
        request,
        "tools/index.html",
        {"tools": tools},
    )


# ---------------------------------------------------------------------------
# 2. GET /{slug}/ — tool landing: input form + previous jobs list
# ---------------------------------------------------------------------------
@router.get("/{slug}/", response_class=HTMLResponse, name="tool_landing")
async def tool_landing(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    registry = TOOL_REGISTRY[slug]
    JobModel, _ResultModel = _get_tool_models(slug)

    stmt = (
        select(JobModel)
        .where(JobModel.user_id == user.id)
        .order_by(JobModel.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return templates.TemplateResponse(
        request,
        f"tools/{slug}/index.html",
        {
            "tool": registry,
            "jobs": jobs,
            "slug": slug,
        },
    )


# ---------------------------------------------------------------------------
# 3. POST /{slug}/ — tool submit: validate, create job, dispatch, redirect
# ---------------------------------------------------------------------------
@router.post("/{slug}/", response_class=HTMLResponse, name="tool_submit")
@limiter.limit("10/minute")
async def tool_submit(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    registry = TOOL_REGISTRY[slug]

    form_data = await request.form()
    raw_text = form_data.get(registry["form_field"], "") or ""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

    limit = registry["limit"]
    if len(lines) == 0:
        raise HTTPException(status_code=422, detail="Список не может быть пустым")
    if len(lines) > limit:
        raise HTTPException(status_code=422, detail=f"Превышен лимит: {limit} строк")

    JobModel, _ResultModel = _get_tool_models(slug)

    job_kwargs: dict = {
        "id": uuid.uuid4(),
        "status": "pending",
        "user_id": user.id,
        "created_at": datetime.now(timezone.utc),
        registry["input_col"]: lines,
        registry["count_col"]: len(lines),
    }

    if registry.get("has_domain_field"):
        domain = form_data.get("domain", "") or ""
        job_kwargs["target_domain"] = domain.strip()

    job = JobModel(**job_kwargs)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    job_id_str = str(job.id)

    if slug == "brief":
        # Brief tool uses a 4-step Celery chain — dispatch via .si() (immutable signatures)
        from app.tasks.brief_tasks import (
            run_brief_step1_serp,
            run_brief_step2_crawl,
            run_brief_step3_aggregate,
            run_brief_step4_finalize,
        )
        celery_chain(
            run_brief_step1_serp.si(job_id_str),
            run_brief_step2_crawl.si(job_id_str),
            run_brief_step3_aggregate.si(job_id_str),
            run_brief_step4_finalize.si(job_id_str),
        ).delay()
    else:
        task_fn = _get_tool_task(slug)
        task_fn.delay(job_id_str)

    return RedirectResponse(f"/ui/tools/{slug}/{job.id}", status_code=303)


# ---------------------------------------------------------------------------
# 4. GET /{slug}/{job_id}/status — HTMX polling partial
# ---------------------------------------------------------------------------
@router.get("/{slug}/{job_id}/status", response_class=HTMLResponse, name="tool_job_status")
async def tool_job_status(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    JobModel, _ResultModel = _get_tool_models(slug)

    stmt = select(JobModel).where(JobModel.id == job_id, JobModel.user_id == user.id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return templates.TemplateResponse(
        request,
        f"tools/{slug}/partials/job_status.html",
        {"job": job, "slug": slug},
    )


# ---------------------------------------------------------------------------
# 5. GET /{slug}/{job_id}/export — CSV/XLSX download
# ---------------------------------------------------------------------------
@router.get("/{slug}/{job_id}/export", name="tool_export")
async def tool_export(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    format: str = Query(default="csv"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    JobModel, ResultModel = _get_tool_models(slug)

    stmt = select(JobModel).where(JobModel.id == job_id, JobModel.user_id == user.id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    stmt_results = select(ResultModel).where(ResultModel.job_id == job_id)
    res = await db.execute(stmt_results)
    rows = res.scalars().all()

    headers_row = _EXPORT_HEADERS.get(slug, [])

    # Brief uses a special multi-section XLSX export
    if slug == "brief":
        if format != "xlsx":
            raise HTTPException(status_code=400, detail="Brief экспортируется только в формате XLSX")
        brief_result = rows[0] if rows else None
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Brief"
        if brief_result:
            ws.append(["Показатель", "Значение"])
            ws.append(["Страниц собрано", brief_result.pages_crawled or 0])
            ws.append(["Страниц попыток", brief_result.pages_attempted or 0])
            ws.append(["Средняя длина текста", brief_result.avg_text_length or 0])
            ws.append(["Среднее число H2", float(brief_result.avg_h2_count or 0)])
            ws.append(["Коммерциализация %", brief_result.commercialization_pct or 0])
            ws.append([])
            ws.append(["Заголовки H2 (облако)"])
            ws.append(["Текст", "Частота"])
            for item in (brief_result.h2_cloud or []):
                ws.append([item.get("text", ""), item.get("count", 0)])
            ws.append([])
            ws.append(["Тематические слова"])
            ws.append(["Слово", "Частота"])
            for item in (brief_result.thematic_words or []):
                ws.append([item.get("word", ""), item.get("freq", 0)])
            ws.append([])
            ws.append(["Варианты заголовков страниц"])
            for title in (brief_result.title_suggestions or []):
                ws.append([title])
            ws.append([])
            ws.append(["Сниппеты (хайлайты)"])
            for hl in (brief_result.highlights or []):
                ws.append([hl])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        filename = f"brief-{job_id}.xlsx"
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = slug
        ws.append(headers_row)
        for row in rows:
            ws.append(_result_to_row(row, slug))
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        filename = f"{slug}-results-{job_id}.xlsx"
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Default: CSV with UTF-8 BOM
    output = io.StringIO()
    writer = csv.writer(output)
    output.write("\ufeff")  # UTF-8 BOM for Excel compatibility
    writer.writerow(headers_row)
    for row in rows:
        writer.writerow(_result_to_row(row, slug))
    output.seek(0)
    filename = f"{slug}-results-{job_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# 6. DELETE /{slug}/{job_id} — delete job + results
# ---------------------------------------------------------------------------
@router.delete("/{slug}/{job_id}", name="tool_delete")
async def tool_delete(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    JobModel, ResultModel = _get_tool_models(slug)

    # Verify ownership
    stmt = select(JobModel).where(JobModel.id == job_id, JobModel.user_id == user.id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete results first (cascade)
    await db.execute(delete(ResultModel).where(ResultModel.job_id == job_id))
    await db.execute(delete(JobModel).where(JobModel.id == job_id))
    await db.commit()

    headers = {}
    if request.headers.get("HX-Request"):
        headers["HX-Trigger"] = f"jobDeleted-{job_id}"
    return Response(status_code=200, headers=headers)


# ---------------------------------------------------------------------------
# 7. GET /{slug}/{job_id} — results page (LAST — generic catch-all)
# ---------------------------------------------------------------------------
@router.get("/{slug}/{job_id}", response_class=HTMLResponse, name="tool_results")
async def tool_results(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    registry = TOOL_REGISTRY[slug]
    JobModel, ResultModel = _get_tool_models(slug)

    stmt = select(JobModel).where(JobModel.id == job_id, JobModel.user_id == user.id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    results_rows = []
    if job.status in ("complete", "partial"):
        stmt_results = select(ResultModel).where(ResultModel.job_id == job_id)
        res = await db.execute(stmt_results)
        results_rows = res.scalars().all()

    return templates.TemplateResponse(
        request,
        f"tools/{slug}/results.html",
        {
            "tool": registry,
            "job": job,
            "results": results_rows,
            "slug": slug,
            "export_headers": _EXPORT_HEADERS.get(slug, []),
        },
    )
