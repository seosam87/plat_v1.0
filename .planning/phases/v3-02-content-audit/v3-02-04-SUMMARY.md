---
phase: v3-02-content-audit
plan: "04"
subsystem: ui
tags: [fastapi, htmx, jinja2, celery, audit, content-audit, tailwind]

# Dependency graph
requires:
  - phase: v3-02-01
    provides: ContentType enum, AuditCheckDefinition, AuditResult, SchemaTemplate models
  - phase: v3-02-02
    provides: audit_service check engine, classification functions, DB helpers
  - phase: v3-02-03
    provides: schema_service JSON-LD render, CRUD, template selection

provides:
  - FastAPI audit router with 13+ endpoints (GET/POST/PUT/DELETE for pages, checks, templates, CTA)
  - Celery task run_site_audit for batch page auditing (up to 200 pages)
  - Jinja2+HTMX audit/index.html with filterable page table, check status, CTA editor, schema templates
  - Site detail "Аудит контента" button linking to per-site audit page
  - Audit router registered in main.py with /audit prefix

affects: [v3-02-05, pipeline-integration, content-audit-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Audit router follows metrika.py pattern: _get_site_or_404, require_admin, Jinja2Templates"
    - "Celery audit task uses asyncio.new_event_loop() async inner function pattern"
    - "Client-side filtering via filterTable() JS — no server round-trip on filter change"
    - "HTMX hx-post for triggering Celery task; JS reload after delay for result"

key-files:
  created:
    - app/routers/audit.py
    - app/tasks/audit_tasks.py
    - app/templates/audit/index.html
  modified:
    - app/main.py
    - app/templates/sites/detail.html
    - app/celery_app.py

key-decisions:
  - "Audit router imports content_audit_service (not audit_service) for check engine — content_audit_service is dedicated check engine, audit_service retained for audit_log writes"
  - "Batch audit dispatched as Celery task (run_site_audit) to avoid blocking UI — runs up to 200 pages"
  - "Client-side filter (filterTable) avoids server round-trip; all page data encoded as data-* attributes on TR elements"

patterns-established:
  - "Per-site audit page accessed via /audit/{site_id} — router returns HTML directly, no redirect needed"
  - "Schema template modal pattern: JS editTemplate() opens fixed-position overlay, saveTemplate() POSTs to API"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-02
---

# Phase v3-02 Plan 04: Audit Router, UI Page, and Site Detail Integration Summary

**FastAPI audit router (13 endpoints), Celery batch audit task, and full-featured Jinja2+HTMX audit UI with per-page check status, content_type editor, CTA textarea, and schema template manager**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-02T07:41:00Z
- **Completed:** 2026-04-02T07:41:22Z
- **Tasks:** 4
- **Files modified:** 6

## Accomplishments
- FastAPI audit router at `/audit/{site_id}` with full CRUD for pages, check definitions, schema templates, and CTA
- Celery `run_site_audit` task processes up to 200 pages: classify → fetch HTML → run checks → save results
- Audit UI page with summary stats (total/issues/pass/unchecked), filterable page table with check status icons, check definitions collapsible, CTA editor, schema template manager with modal
- "Аудит контента" button added to site detail Quick Actions and audit router registered in main.py

## Task Commits

Each task was committed atomically:

1. **Task 01: Create audit router with all endpoints** - `7858876` (feat)
2. **Task 02: Create Celery task for batch audit** - `7858876` (feat)
3. **Task 03: Create audit page template with filters and checklist** - `7858876` (feat)
4. **Task 04: Register audit router in main.py and add Аудит button to site detail** - `7858876` (feat)

**Plan metadata:** (this commit — docs)

_Note: All 4 tasks committed together in a single atomic commit `7858876`._

## Files Created/Modified
- `app/routers/audit.py` - 13+ endpoints: main audit page, run/run-single, content_type update, checks CRUD, schema template CRUD, CTA save, results JSON, fix preview/apply/approve
- `app/tasks/audit_tasks.py` - Celery run_site_audit task with asyncio inner function
- `app/templates/audit/index.html` - Full audit UI with filter bar, pages table, check status icons, CTA textarea, schema template modal
- `app/main.py` - Import and register audit_router; `/audit` already in _HELP_MODULE_MAP
- `app/templates/sites/detail.html` - "Аудит контента" button in Quick Actions
- `app/celery_app.py` - `app.tasks.audit_tasks` added to include list

## Decisions Made
- Audit router imports `content_audit_service` (dedicated check engine module) not `audit_service` (which handles audit_log writes) — separation of responsibilities
- All 4 tasks committed together since they were implemented as a cohesive unit

## Deviations from Plan

None — plan executed as written. All acceptance criteria pass.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Audit router and UI fully operational; v3-02-05 (fix workflow) can consume `/audit/{site_id}/fix/*` endpoints
- All audit infrastructure in place for content fix pipeline integration

---
*Phase: v3-02-content-audit*
*Completed: 2026-04-02*
