"""Navigation configuration and active-state resolution for the sidebar layout."""
from __future__ import annotations

import re

NAV_SECTIONS = [
    {
        "id": "overview",
        "label": "Обзор",
        "icon": "chart-bar",
        "url": "/ui/dashboard",
        "admin_only": False,
        "children": [],
    },
    {
        "id": "sites",
        "label": "Сайты",
        "icon": "globe-alt",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "sites-list", "label": "Список сайтов", "url": "/ui/sites"},
            {"id": "sites-crawls", "label": "Краулы", "url": "/ui/sites/{site_id}/crawls"},
            {"id": "sites-schedule", "label": "Расписание", "url": "/ui/sites/{site_id}/schedule"},
        ],
    },
    {
        "id": "positions",
        "label": "Позиции и ключи",
        "icon": "key",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "keywords", "label": "Ключевые слова", "url": "/ui/keywords/{site_id}"},
            {"id": "positions-list", "label": "Позиции", "url": "/ui/positions/{site_id}"},
            {"id": "clusters", "label": "Кластеры", "url": "/ui/clusters/{site_id}"},
            {"id": "cannibalization", "label": "Каннибализация", "url": "/ui/cannibalization/{site_id}"},
            {"id": "intent", "label": "Интент", "url": "/intent/{site_id}"},
            {"id": "bulk", "label": "Массовые операции", "url": "/bulk/{site_id}"},
        ],
    },
    {
        "id": "analytics",
        "label": "Аналитика",
        "icon": "magnifying-glass",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "quick-wins", "label": "Quick Wins", "url": "/analytics/{site_id}/quick-wins"},
            {"id": "workspace", "label": "Воркспейс", "url": "/analytics/sites/{site_id}"},
            {"id": "gap", "label": "Gap-анализ", "url": "/gap/{site_id}"},
            {"id": "architecture", "label": "Архитектура", "url": "/architecture/{site_id}"},
            {"id": "metrika", "label": "Трафик (Metrika)", "url": "/ui/metrika/{site_id}"},
            {"id": "traffic-analysis", "label": "Анализ трафика", "url": "/traffic-analysis/{site_id}"},
            {"id": "competitors", "label": "Конкуренты", "url": "/ui/competitors/{site_id}"},
            {"id": "sites-ads", "label": "Рекламный трафик", "url": "/ui/ads/{site_id}", "admin_only": False},
            {"id": "dead-content", "label": "Мёртвый контент", "url": "/analytics/{site_id}/dead-content"},
            {"id": "opportunities", "label": "Growth Opportunities", "url": "/analytics/{site_id}/opportunities"},
        ],
    },
    {
        "id": "content",
        "label": "Контент",
        "icon": "document-text",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "audit", "label": "Аудит", "url": "/audit/{site_id}"},
            {"id": "pipeline", "label": "Pipeline", "url": "/ui/pipeline/{site_id}"},
            {"id": "publish", "label": "Публикация", "url": "/ui/content-publish/{site_id}"},
            {"id": "projects", "label": "Проекты", "url": "/ui/projects"},
            {"id": "kanban", "label": "Задачи", "url": "/ui/tasks"},
            {"id": "monitoring", "label": "Мониторинг", "url": "/monitoring/{site_id}"},
        ],
    },
    {
        "id": "client-reports",
        "label": "Клиентские отчёты",
        "icon": "document-check",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "client-reports-gen", "label": "Генерация", "url": "/ui/client-reports/"},
        ],
    },
    {
        "id": "keyword-suggest",
        "label": "Keyword Suggest",
        "icon": "light-bulb",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "keyword-suggest-search", "label": "Поиск подсказок", "url": "/ui/keyword-suggest/"},
        ],
    },
    {
        "id": "tools",
        "label": "Инструменты",
        "icon": "wrench",
        "url": "/ui/tools/",
        "admin_only": False,
        "children": [],
    },
    {
        "id": "channel",
        "label": "Telegram-канал",
        "icon": "chat-bubble-left-right",
        "url": "/ui/channel/",
        "admin_only": False,
        "children": [],
    },
    {
        "id": "crm",
        "label": "CRM",
        "icon": "user-group",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "crm-clients", "label": "Клиенты", "url": "/ui/crm/clients"},
            {"id": "crm-templates", "label": "Шаблоны КП", "url": "/ui/templates"},
        ],
    },
    {
        "id": "settings",
        "label": "Настройки",
        "icon": "cog-6-tooth",
        "url": None,
        "admin_only": False,
        "children": [
            {"id": "users", "label": "Пользователи", "url": "/ui/admin/users", "admin_only": True},
            {"id": "groups", "label": "Группы", "url": "/ui/admin/groups", "admin_only": True},
            {"id": "datasources", "label": "Источники данных", "url": "/ui/datasources", "admin_only": False},
            {"id": "proxy", "label": "Прокси", "url": "/ui/admin/proxy", "admin_only": False},
            {"id": "parameters", "label": "Параметры", "url": "/ui/admin/parameters", "admin_only": False},
            {"id": "issues", "label": "Задачи платформы", "url": "/ui/admin/issues", "admin_only": False},
            {"id": "audit-log", "label": "Журнал аудита", "url": "/ui/admin/audit", "admin_only": True},
            {"id": "settings-report-schedule", "label": "Report Schedule", "url": "/ui/admin/report-schedule", "admin_only": True},
        ],
    },
]

# Build URL-to-nav mapping: regex pattern -> (section_id, child_id, section_label, child_label)
# Replace {site_id} and {project_id} placeholders with regex patterns.
_URL_PATTERN = re.compile(r"\{[^}]+\}")


def _url_to_pattern(url: str) -> re.Pattern[str]:
    """Convert a URL template like /ui/keywords/{site_id} to a compiled regex."""
    # Strip fragment (e.g. #schedules)
    url_path = url.split("#")[0]
    # Escape the URL, then replace placeholders
    escaped = re.escape(url_path)
    # Replace escaped placeholder tokens \{...\} back to UUID matchers
    pattern_str = re.sub(r"\\{[^}]+\\}", r"[0-9a-f\\-]+", escaped)
    return re.compile(r"^" + pattern_str + r"(/.*)?$")


# Build lookup list: (pattern, section_id, child_id, section_label, child_label)
_URL_TO_NAV: list[tuple[re.Pattern[str], str, str | None, str, str | None]] = []

for _section in NAV_SECTIONS:
    if _section["url"] and not _section["children"]:
        # Top-level section (e.g. Обзор)
        _pat = _url_to_pattern(_section["url"])
        _URL_TO_NAV.append((_pat, _section["id"], None, _section["label"], None))
    for _child in _section["children"]:
        if _child.get("url"):
            _pat = _url_to_pattern(_child["url"])
            _URL_TO_NAV.append((_pat, _section["id"], _child["id"], _section["label"], _child["label"]))

# Sort by pattern length descending so more-specific patterns match first
_URL_TO_NAV.sort(key=lambda x: len(x[0].pattern), reverse=True)


def resolve_nav_context(request_path: str) -> dict:
    """Return nav active-state info for the given request path.

    Returns:
        dict with keys:
            active_section: str | None
            active_child: str | None
            breadcrumb_section: str | None
            breadcrumb_child: str | None
    """
    path = request_path.split("?")[0]  # strip query params
    for pattern, section_id, child_id, section_label, child_label in _URL_TO_NAV:
        if pattern.match(path):
            return {
                "active_section": section_id,
                "active_child": child_id,
                "breadcrumb_section": section_label,
                "breadcrumb_child": child_label,
            }
    return {
        "active_section": None,
        "active_child": None,
        "breadcrumb_section": None,
        "breadcrumb_child": None,
    }


def build_sidebar_sections(site_id: str | None, is_admin: bool) -> list[dict]:
    """Build sidebar sections with resolved URLs for the given site_id.

    Replaces {site_id} and {project_id} placeholders with the actual site_id
    (or "#" if None). Filters out admin_only sections for non-admin users.
    Returns a deep-copied list safe to mutate.
    """
    result = []
    for section in NAV_SECTIONS:
        if section["admin_only"] and not is_admin:
            continue
        resolved_section = {
            "id": section["id"],
            "label": section["label"],
            "icon": section["icon"],
            "url": section["url"],
            "admin_only": section["admin_only"],
            "children": [],
        }
        for child in section["children"]:
            if child.get("admin_only", False) and not is_admin:
                continue
            raw_url = child.get("url") or "#"
            needs_site = "{site_id}" in raw_url or "{project_id}" in raw_url
            if site_id is not None:
                resolved_url = raw_url.replace("{site_id}", str(site_id))
                resolved_url = resolved_url.replace("{project_id}", str(site_id))
                disabled = False
            elif needs_site:
                resolved_url = "#"
                disabled = True
            else:
                resolved_url = raw_url
                disabled = False
            resolved_section["children"].append(
                {
                    "id": child["id"],
                    "label": child["label"],
                    "url": resolved_url,
                    "disabled": disabled,
                }
            )
        result.append(resolved_section)
    return result
