---
phase: 29-reports-tools
plan: "03"
subsystem: mobile-tools
tags: [mobile, tools, notifications, htmx, celery]
one_liner: "Mobile tool result view (top-20 + XLSX + paginated modal) + in-app notify() wired in all 6 tool Celery tasks via _send_mobile_notify helper"

dependency_graph:
  requires:
    - 29-02  # TOOL_REGISTRY, _get_tool_models, _result_to_row, _EXPORT_HEADERS, Job models
    - 17-in-app-notifications  # notify() service + Notification model
  provides:
    - GET /m/tools/{slug}/jobs/{job_id}  # mobile result view (TLS-01 complete)
    - GET /m/tools/{slug}/jobs/{job_id}/all  # paginated modal
    - tool.completed notifications for all 6 tools (TLS-02)
  affects:
    - app/routers/mobile.py
    - app/services/mobile_tools_service.py
    - app/tasks/commerce_check_tasks.py
    - app/tasks/meta_parse_tasks.py
    - app/tasks/relevant_url_tasks.py
    - app/tasks/paa_tasks.py
    - app/tasks/wordstat_batch_tasks.py
    - app/tasks/brief_tasks.py

tech_stack:
  added: []
  patterns:
    - "asyncio.run(_send_mobile_notify(...)) from sync Celery task — safe prefork pattern (from suggest_tasks.py)"
    - "HTMX bottom-sheet modal via hx-get + hx-swap=innerHTML into #modal-slot"
    - "Reuse existing /ui/tools/{slug}/{job_id}/export endpoint for XLSX download"
    - "_result_to_row(result, slug) — real signature is (result, slug), not (slug, result)"

key_files:
  created:
    - app/templates/mobile/tools/result.html
    - app/templates/mobile/tools/partials/result_modal.html
  modified:
    - app/routers/mobile.py  # +2 endpoints: mobile_tool_result, mobile_tool_result_all
    - app/services/mobile_tools_service.py  # +3 helpers: get_top_results, count_results, get_paginated_results
    - app/tasks/commerce_check_tasks.py
    - app/tasks/meta_parse_tasks.py
    - app/tasks/relevant_url_tasks.py
    - app/tasks/paa_tasks.py
    - app/tasks/wordstat_batch_tasks.py
    - app/tasks/brief_tasks.py

decisions:
  - "_result_to_row(result, slug) — plan had args reversed; used actual signature from tools.py"
  - "Imports (_result_to_row, _EXPORT_HEADERS, get_job_for_user) done locally inside endpoint functions to avoid circular imports"
  - "_send_mobile_notify helper duplicated in all 6 task files by design — avoids cross-task coupling"
  - "brief_tasks.py: BriefJob imported inside try/except block (already available at module level via step1-4 functions)"

metrics:
  duration_minutes: 10
  completed_date: "2026-04-11"
  tasks_total: 2
  tasks_completed: 2
  files_created: 2
  files_modified: 10
---

# Phase 29 Plan 03: Tool Result View + Mobile Notify Summary

## Objective

Реализован TLS-02 и завершён TLS-01: мобильное view результатов `/m/tools/{slug}/jobs/{job_id}` + in-app notify() во всех 6 tool Celery tasks.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Mobile result endpoints + top-20 helper + templates | 43e662f | mobile.py, mobile_tools_service.py, result.html, result_modal.html |
| 2 | Add notify() to 6 tool Celery tasks | a66cd06 | 6 × app/tasks/*.py |

## What Was Built

### Task 1: Mobile Result View

- `GET /m/tools/{slug}/jobs/{job_id}` (`mobile_tool_result`) — summary card (status badge + total count), top-20 result rows, "Скачать XLSX" link to existing desktop export, "Показать все" HTMX button
- `GET /m/tools/{slug}/jobs/{job_id}/all` (`mobile_tool_result_all`) — bottom-sheet modal with full paginated results (page_size=50), "Показать ещё" loads next page replacing modal via `hx-swap="outerHTML"`
- `mobile_tools_service.py` extended: `get_top_results`, `count_results`, `get_paginated_results`
- Template `result.html`: green/red status badge, empty state "Результатов нет. Запустите инструмент с данными.", back link "← {tool.name}"
- Template `result_modal.html`: full results in bottom-sheet, close button, paginated load

### Task 2: In-App Notifications (TLS-02)

`_send_mobile_notify` helper added to all 6 task files:

| File | slug | Title |
|------|------|-------|
| commerce_check_tasks.py | commercialization | Проверка коммерциализации завершена |
| meta_parse_tasks.py | meta-parser | Парсер мета-тегов завершён |
| relevant_url_tasks.py | relevant-url | Поиск релевантного URL завершён |
| paa_tasks.py | paa | PAA-парсер завершён |
| wordstat_batch_tasks.py | wordstat-batch | Wordstat пакет завершён |
| brief_tasks.py | brief | Копирайтерское ТЗ готово |

Each notification: `kind=tool.completed`, `link_url=/m/tools/{slug}/jobs/{job_id}`, wrapped in `try/except` so failure never breaks task return.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong argument order for _result_to_row**
- **Found during:** Task 1, reading tools.py
- **Issue:** Plan specified `_result_to_row(slug, result)` but actual function signature is `_result_to_row(result, slug)`
- **Fix:** Used correct signature `_result_to_row(r, slug)` in both mobile endpoints
- **Files modified:** app/routers/mobile.py

**2. [Rule 2 - Pattern] Local imports inside endpoint functions**
- **Found during:** Task 1
- **Issue:** Plan showed top-level imports `from app.routers.tools import _result_to_row, _EXPORT_HEADERS`. These already exist as module-level lazy imports in tools.py; pulling them at mobile.py top-level risks circular imports at startup
- **Fix:** Kept imports inside each endpoint function body (consistent with existing mobile.py pattern for all tool imports)
- **Files modified:** app/routers/mobile.py

## Known Stubs

None — all endpoints are fully wired: real DB queries, real job lookup, real result rows.

## Verification

- [x] GET /m/tools/{slug}/jobs/{job_id} renders summary card + top-20 result rows
- [x] Скачать XLSX button links to /ui/tools/{slug}/{job_id}/export?format=xlsx
- [x] Показать все button opens modal via HTMX with paginated full results
- [x] Показать ещё button loads next page within modal
- [x] All 6 tool tasks gained the notify helper without changing their return values
- [x] All 6 task files parse cleanly (AST verified)
- [x] All imports succeed in test environment
