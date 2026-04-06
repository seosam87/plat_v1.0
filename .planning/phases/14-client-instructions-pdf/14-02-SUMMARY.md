---
phase: 14-client-instructions-pdf
plan: 02
subsystem: ui, reporting, celery
tags: [celery, htmx, jinja2, fastapi, pdf, client-reports, sidebar]

# Dependency graph
requires:
  - phase: 14-client-instructions-pdf
    plan: 01
    provides: ClientReport model, generate_client_report(), CRUD helpers, subprocess PDF isolation

provides:
  - generate_client_pdf Celery task with 90s soft limit, subprocess PDF isolation
  - send_client_report_email + send_client_report_telegram delivery Celery tasks
  - FastAPI router (7 endpoints) at /ui/client-reports/* for generate/status/download/deliver/history
  - app/templates/client_reports/index.html main page with generation form + HTMX history
  - app/templates/client_reports/partials/history_table.html history table with download/email/Telegram buttons
  - app/templates/client_reports/partials/generation_status.html polling partial (generating/ready/failed)
  - Sidebar "Клиентские отчёты" section with document-check icon between Контент and Настройки

affects:
  - 14-03 (final plan in phase — uses these routes and templates)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HTMX polling pattern: hx-get status endpoint with hx-trigger='load delay:3s' + outerHTML swap"
    - "HTMX history refresh: HX-Trigger: refreshHistory header from status endpoint triggers hx-trigger='refreshHistory from:body'"
    - "Delivery toast: hx-target='#toast-container' hx-swap='beforeend' for inline success messages"

key-files:
  created:
    - app/tasks/client_report_tasks.py
    - app/routers/client_reports.py
    - app/templates/client_reports/index.html
    - app/templates/client_reports/partials/history_table.html
    - app/templates/client_reports/partials/generation_status.html
  modified:
    - app/main.py
    - app/navigation.py
    - app/templates/components/sidebar.html

key-decisions:
  - "max_retries=1 for generate_client_pdf (heavy task — avoid duplicate generation on retry)"
  - "max_retries=3 for delivery tasks (email/Telegram are idempotent — safe to retry)"
  - "Site resolution order: query param > cookie > first site (graceful default for new users)"

patterns-established:
  - "HTMX status polling: outerHTML swap so spinner div replaces itself when status changes"
  - "HX-Trigger header: refreshHistory sent from status endpoint to update history table without page reload"

requirements-completed: [CPDF-01, CPDF-02]

# Metrics
duration: 12min
completed: 2026-04-06
---

# Phase 14 Plan 02: Client Instructions PDF — Celery Task + Router + UI Templates Summary

**Celery generation task (90s soft limit), 7-endpoint FastAPI router, HTMX-driven templates, and sidebar entry connecting client PDF feature end-to-end**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-06T20:15:00Z
- **Completed:** 2026-04-06T20:27:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- generate_client_pdf Celery task with 90s soft_time_limit dispatches async PDF generation, calls generate_client_report() service from Plan 01, saves PDF bytes to DB via save_report_pdf()
- send_client_report_email and send_client_report_telegram delivery tasks wrap existing smtp_service and telegram_service with 3 retries each
- FastAPI router at /ui/client-reports/ with 7 endpoints: page (GET /), generate (POST /generate), status (GET /status/{id}), download (GET /{id}/download), send-email (POST /{id}/send-email), send-telegram (POST /{id}/send-telegram), history (GET /history)
- HTMX polling: generation_status.html polls /status/{id} every 3s via hx-trigger="load delay:3s", status endpoint sets HX-Trigger: refreshHistory on completion to refresh history table
- Sidebar "Клиентские отчёты" section with document-check Heroicons SVG added between "Контент" and "Настройки" — navigation.py resolve_nav_context() correctly activates section for /ui/client-reports/

## Task Commits

1. **Task 1: Celery tasks + Router endpoints** - `dd88130` (feat)
2. **Task 2: UI templates + sidebar navigation entry** - `81c3d97` (feat)

## Files Created/Modified

- `app/tasks/client_report_tasks.py` — 3 Celery tasks: generate_client_pdf (90s soft limit), send_client_report_email, send_client_report_telegram
- `app/routers/client_reports.py` — FastAPI router with 7 endpoints, HTMX partials, PDF download, delivery dispatch
- `app/main.py` — client_reports_router registered
- `app/templates/client_reports/index.html` — main page with generation form (site selector + 4 checkboxes + CTA) and HTMX history section
- `app/templates/client_reports/partials/history_table.html` — history table with Дата/Сайт/Блоки/Действия columns, empty state, icon-only email/Telegram buttons with aria-labels
- `app/templates/client_reports/partials/generation_status.html` — 3-state partial: generating (polling), ready (download + delivery), failed (error copy)
- `app/navigation.py` — client-reports section at index 5 (after content, before settings)
- `app/templates/components/sidebar.html` — document-check icon case added

## Decisions Made

- max_retries=1 for generate_client_pdf: heavy PDF generation task; retry would double resource usage and risk duplicate PDF records. Single retry on failure with 10s countdown is sufficient.
- max_retries=3 for delivery tasks: email/Telegram dispatch is idempotent (same message resent) and lightweight — 3 retries appropriate for transient network failures.
- Site selection order (query param > cookie > first site): ensures users always see a site on initial page load rather than an empty state requiring extra clicks.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 7 endpoints functional and router registered in app/main.py
- HTMX polling flow complete: generate → status poll → refreshHistory trigger → history table update
- Sidebar navigation correctly activates for /ui/client-reports/ URL
- Plan 14-03 (if any) can build on this router or the feature is ready for production testing

---
*Phase: 14-client-instructions-pdf*
*Completed: 2026-04-06*
