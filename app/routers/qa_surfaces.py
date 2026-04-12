"""QA Surface Tracker — admin UI for managing feature coverage across surfaces.

Routes are under /ui/qa/ prefix. All endpoints require authentication.
Per D-05: discover_routes() called at request time ONLY (never at import time)
to avoid circular import with app.main.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.models.qa_surface import Surface, CheckStatus
from app.services import qa_surface_service as svc
from app.template_engine import templates

router = APIRouter(prefix="/ui/qa", tags=["qa"])

STATUS_COLORS = {
    "not_tested":   {"bg": "#f3f4f6", "text": "#6b7280"},
    "passed":       {"bg": "#d1fae5", "text": "#065f46"},
    "failed":       {"bg": "#fee2e2", "text": "#991b1b"},
    "needs_retest": {"bg": "#fef3c7", "text": "#92400e"},
}

# Russian labels for discovered routes (route.name -> label)
ROUTE_LABELS: dict[str, str] = {
    # Analytics
    "analytics_page": "Аналитика сайта",
    "brief_detail_view": "Просмотр брифа",
    "dead_content_page": "Мёртвый контент",
    "fix_status": "Статус исправления",
    "opportunities_page": "Точки роста",
    "opportunities_detail_cannibal": "Каннибализация — детали",
    "opportunities_detail_gap": "Gap-анализ — детали",
    "opportunities_detail_loss": "Потери позиций — детали",
    "opportunities_cannibal": "Каннибализация",
    "opportunities_gaps": "Gap-анализ",
    "opportunities_losses": "Потери позиций",
    "opportunities_trend": "Тренды",
    "quick_wins_page": "Быстрые победы",
    "quick_wins_table": "Таблица быстрых побед",
    # Architecture, Audit, Bulk, Gap, Intent
    "architecture_page": "Архитектура сайта",
    "audit_page": "Аудит сайта",
    "bulk_page": "Массовые операции",
    "export_keywords": "Экспорт ключевых слов",
    "gap_page": "Gap-анализ",
    "intent_page": "Интент ключевых слов",
    # Mobile
    "mobile_index": "Мобильная — главная",
    "agent_diff_page": "Агент — просмотр diff",
    "auth_link_required": "Авторизация — ссылка",
    "mobile_digest": "Дайджест",
    "mobile_errors": "Ошибки сайта",
    "mobile_errors_content": "Ошибки контента",
    "mobile_errors_sync_status": "Статус синхронизации ошибок",
    "mobile_error_brief_form": "Бриф по ошибке",
    "mobile_errors_show_all": "Все ошибки по типу",
    "mobile_health": "Здоровье сайта",
    "mobile_task_form": "Форма задачи",
    "mobile_pages": "Страницы",
    "mobile_bulk_progress": "Прогресс массовой операции",
    "mobile_bulk_schema_confirm": "Подтверждение Schema",
    "mobile_bulk_toc_confirm": "Подтверждение TOC",
    "mobile_page_detail": "Детали страницы",
    "mobile_page_detail_collapsed": "Детали страницы (свёрнуто)",
    "mobile_page_edit": "Редактирование страницы",
    "mobile_pipeline": "Пайплайн",
    "mobile_positions": "Позиции",
    "mobile_position_check_status": "Статус проверки позиций",
    "mobile_positions_task_form": "Форма проверки позиций",
    "mobile_report_download": "Скачать отчёт",
    "mobile_report_new": "Новый отчёт",
    "mobile_sites": "Список сайтов",
    "mobile_tasks_new": "Новая задача",
    "mobile_tasks_new_form": "Форма новой задачи",
    "mobile_tools_list": "Инструменты",
    "mobile_tool_result": "Результат инструмента",
    "mobile_tool_result_all": "Все результаты инструмента",
    "mobile_tool_job_status": "Статус задачи инструмента",
    "mobile_tool_run_form": "Запуск инструмента",
    "mobile_traffic": "Трафик",
    "mobile_traffic_task_form": "Форма анализа трафика",
    # Metrika, Monitoring, Notifications
    "metrika_page": "Яндекс.Метрика",
    "metrika_widget": "Виджет Метрики",
    "monitoring_page": "Мониторинг изменений",
    "notifications_index": "Уведомления",
    "bell_fragment": "Колокольчик уведомлений",
    "dropdown_fragment": "Выпадающий список уведомлений",
    # Profile
    "profile_page": "Профиль",
    "link_telegram": "Привязка Telegram",
    # Traffic analysis
    "dashboard": "Анализ трафика",
    # Admin
    "ui_admin_audit": "Админ — журнал аудита",
    "ui_admin_groups": "Админ — группы",
    "ui_admin_issues": "Админ — проблемы",
    "ui_admin_parameters": "Админ — параметры",
    "ui_admin_proxy": "Админ — прокси",
    "ui_admin_report_schedule_get": "Админ — расписание отчётов",
    "ui_admin_settings_redirect": "Админ — настройки",
    "ui_admin_users": "Админ — пользователи",
    # Ads
    "ui_ads": "Рекламные объявления",
    # Agents
    "catalogue": "Каталог AI-агентов",
    "job_status": "Статус задачи агента",
    "new_agent_form": "Новый агент",
    "parse_vars": "Парсинг переменных",
    "edit_agent_form": "Редактирование агента",
    "run_agent_page": "Запуск агента",
    # Analytics UI
    "ui_analytics_select": "Аналитика — выбор сайта",
    "ui_analytics": "Аналитика сайта",
    "ui_cannibalization": "Каннибализация",
    # Channel
    "channel_index": "Telegram-канал — посты",
    "channel_new": "Новый пост",
    "channel_edit": "Редактирование поста",
    "channel_preview": "Предпросмотр поста",
    # Client reports
    "client_reports_page": "Клиентские отчёты",
    "report_history": "История отчётов",
    "report_status": "Статус отчёта",
    "download_report": "Скачать отчёт",
    # Clusters, Competitors, Content
    "ui_clusters": "Кластеризация",
    "ui_competitors": "Конкуренты",
    "ui_content_publish": "Публикация контента",
    # Crawl
    "ui_crawl_feed": "Лента изменений краула",
    # CRM
    "client_list": "Список клиентов",
    "client_new_modal": "Новый клиент",
    "client_detail": "Карточка клиента",
    "contact_read_row": "Контакт клиента",
    "contact_edit_form": "Редактирование контакта",
    "documents_tab": "Документы клиента",
    "download_document": "Скачать документ",
    "document_status": "Статус документа",
    "client_edit_modal": "Редактирование клиента",
    "search_unattached_sites": "Поиск свободных сайтов",
    # Dashboard
    "ui_dashboard": "Главная панель",
    "ui_datasources": "Источники данных",
    # Help
    "ui_help": "Справка по модулю",
    # Keywords
    "keyword_suggest_page": "Подбор ключевых слов",
    "export_csv": "Экспорт CSV",
    "suggest_status": "Статус подбора",
    "wordstat_status": "Статус Wordstat",
    "ui_keywords": "Ключевые слова сайта",
    # Metrika UI
    "ui_metrika_select": "Метрика — выбор сайта",
    "ui_metrika": "Яндекс.Метрика",
    # Pipeline
    "ui_pipeline": "WP Пайплайн",
    # Playbooks
    "ui_playbook_templates": "Плейбуки",
    "ui_playbook_blocks": "Блоки плейбуков",
    "ui_playbook_block_media_row": "Медиа-строка блока",
    "ui_playbook_block_new": "Новый блок",
    "ui_playbook_block_edit": "Редактирование блока",
    "ui_playbook_experts": "Эксперты",
    "ui_playbook_new_form": "Новый плейбук",
    "ui_playbook_builder": "Конструктор плейбука",
    "ui_playbook_preview": "Предпросмотр плейбука",
    # Positions
    "ui_positions_select": "Позиции — выбор сайта",
    "ui_positions": "Позиции сайта",
    # Projects
    "ui_projects": "Проекты",
    "ui_kanban": "Kanban-доска",
    "ui_plan": "План проекта",
    "ui_project_playbook_tab": "Плейбук проекта",
    "ui_project_playbook_apply_modal": "Применить плейбук",
    # QA
    "qa_matrix": "QA Матрица покрытия",
    "candidates_page": "Кандидаты маршрутов",
    "view_check_cell": "Ячейка проверки",
    "edit_check_cell": "Редактирование проверки",
    "new_feature_form": "Новый сценарий",
    "edit_feature_form": "Редактирование сценария",
    # Reports
    "ui_reports": "Отчёты проекта",
    # Sites
    "ui_sites": "Список сайтов",
    "ui_create_site_form": "Добавить сайт",
    "ui_site_overview": "Обзор сайта",
    "ui_site_crawl_history": "История краулов",
    "ui_site_detail": "Детали сайта",
    "ui_edit_site_form": "Редактирование сайта",
    "intake_form": "Анкета аудита",
    "refresh_checklist": "Обновить чеклист",
    "ui_site_schedule": "Расписание краулов",
    # Tasks
    "ui_tasks": "Задачи",
    # Templates
    "template_list": "Шаблоны КП",
    "template_new_page": "Новый шаблон",
    "sites_for_client": "Сайты клиента",
    "template_edit_page": "Редактирование шаблона",
    # Tools
    "tools_index": "SEO-инструменты",
    "tool_landing": "Инструмент",
    "tool_results": "Результаты инструмента",
    "tool_job_status": "Статус задачи",
    # Uploads
    "ui_uploads": "Загрузки",
}


# ---------------------------------------------------------------------------
# GET /ui/qa/ — Matrix view
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def qa_matrix(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Render the QA surface matrix: features as rows, surfaces as columns."""
    features = await svc.list_features_with_checks(db)
    return templates.TemplateResponse(request, "qa/index.html", {
        "features": features,
        "surfaces": list(Surface),
        "status_colors": STATUS_COLORS,
        "CheckStatus": CheckStatus,
    })


# ---------------------------------------------------------------------------
# GET /ui/qa/features/new — Create feature form
# ---------------------------------------------------------------------------

@router.get("/features/new", response_class=HTMLResponse)
async def new_feature_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Render the create-feature form."""
    return templates.TemplateResponse(request, "qa/feature_form.html", {
        "feature": None,
        "mode": "create",
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/features — Create feature
# ---------------------------------------------------------------------------

@router.post("/features", response_class=HTMLResponse)
async def create_feature(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    retest_days: int = Form(30),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Create a new FeatureSurface and redirect to matrix."""
    await svc.create_feature_surface(db, slug, name, description or None, retest_days)
    return RedirectResponse("/ui/qa/", status_code=303)


# ---------------------------------------------------------------------------
# GET /ui/qa/features/{feature_surface_id} — Edit feature form
# ---------------------------------------------------------------------------

@router.get("/features/{feature_surface_id}", response_class=HTMLResponse)
async def edit_feature_form(
    request: Request,
    feature_surface_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Render the edit-feature form."""
    feature = await svc.get_feature_by_id(db, feature_surface_id)
    return templates.TemplateResponse(request, "qa/feature_form.html", {
        "feature": feature,
        "mode": "edit",
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/features/{feature_surface_id} — Update feature
# ---------------------------------------------------------------------------

@router.post("/features/{feature_surface_id}", response_class=HTMLResponse)
async def update_feature(
    request: Request,
    feature_surface_id: uuid.UUID,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    retest_days: int = Form(30),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Update a FeatureSurface and redirect to matrix."""
    await svc.update_feature_surface(db, feature_surface_id, name, slug, description or None, retest_days)
    return RedirectResponse("/ui/qa/", status_code=303)


# ---------------------------------------------------------------------------
# POST /ui/qa/features/{feature_surface_id}/delete — Delete feature
# ---------------------------------------------------------------------------

@router.post("/features/{feature_surface_id}/delete", response_class=HTMLResponse)
async def delete_feature(
    request: Request,
    feature_surface_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Delete a FeatureSurface (cascade deletes checks) and redirect to matrix."""
    await svc.delete_feature_surface(db, feature_surface_id)
    return RedirectResponse("/ui/qa/", status_code=303)


# ---------------------------------------------------------------------------
# GET /ui/qa/checks/{surface_check_id}/edit — HTMX partial: inline check edit
# ---------------------------------------------------------------------------

@router.get("/checks/{surface_check_id}/edit", response_class=HTMLResponse)
async def edit_check_cell(
    request: Request,
    surface_check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Return the edit mode for an inline check cell (HTMX partial)."""
    check = await svc.get_check_by_id(db, surface_check_id)
    return templates.TemplateResponse(request, "qa/_check_cell.html", {
        "check": check,
        "statuses": list(CheckStatus),
        "mode": "edit",
        "status_colors": STATUS_COLORS,
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/checks/{surface_check_id}/mark-tested — Mark check tested
# ---------------------------------------------------------------------------

@router.post("/checks/{surface_check_id}/mark-tested", response_class=HTMLResponse)
async def mark_tested(
    request: Request,
    surface_check_id: uuid.UUID,
    status: str = Form(...),
    tested_by: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Mark a surface check as tested and return updated cell partial."""
    tester = tested_by or getattr(user, "username", None)
    updated_check = await svc.mark_check_tested(
        db, surface_check_id, CheckStatus(status), notes or None, tester
    )
    return templates.TemplateResponse(request, "qa/_check_cell.html", {
        "check": updated_check,
        "mode": "view",
        "status_colors": STATUS_COLORS,
    })


# ---------------------------------------------------------------------------
# GET /ui/qa/checks/{surface_check_id} — HTMX partial: restore view cell
# ---------------------------------------------------------------------------

@router.get("/checks/{surface_check_id}", response_class=HTMLResponse)
async def view_check_cell(
    request: Request,
    surface_check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Return the view mode for an inline check cell (HTMX cancel restore)."""
    check = await svc.get_check_by_id(db, surface_check_id)
    return templates.TemplateResponse(request, "qa/_check_cell.html", {
        "check": check,
        "mode": "view",
        "status_colors": STATUS_COLORS,
    })


# ---------------------------------------------------------------------------
# GET /ui/qa/candidates — Route discovery page
# ---------------------------------------------------------------------------

@router.get("/candidates", response_class=HTMLResponse)
async def candidates_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Discover app routes and present them for grouping into user flows.

    Per D-05 and RESEARCH.md pitfall #1: imports happen inside function body
    to avoid circular import with app.main at module level.
    """
    import sys
    import os
    from app.main import app as _app
    # Ensure tests/ is importable (may not be on sys.path in production)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from tests._smoke_helpers import discover_routes
    routes = discover_routes(_app)
    return templates.TemplateResponse(request, "qa/candidates.html", {
        "routes": routes,
        "surfaces": list(Surface),
        "route_labels": ROUTE_LABELS,
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/candidates/save — Save selected routes as a new user flow
# ---------------------------------------------------------------------------

@router.post("/candidates/save", response_class=HTMLResponse)
async def save_candidate(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    retest_days: int = Form(30),
    routes: list[str] = Form([]),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Save selected route candidates as a new FeatureSurface user flow."""
    # Combine routes into description context if provided
    combined_description = description or None
    if routes:
        route_list = "\n".join(routes)
        if combined_description:
            combined_description = f"{combined_description}\n\nRoutes:\n{route_list}"
        else:
            combined_description = f"Routes:\n{route_list}"
    await svc.create_feature_surface(db, slug, name, combined_description, retest_days)
    return RedirectResponse("/ui/qa/", status_code=303)
