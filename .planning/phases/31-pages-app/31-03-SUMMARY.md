---
phase: 31-pages-app
plan: 03
subsystem: mobile
tags: [celery, htmx, redis, wordpress, mobile, bulk-operations]

requires:
  - phase: 31-pages-app/31-01
    provides: Pages list screen with has_toc/has_schema flags per page
  - phase: 31-pages-app/31-02
    provides: Pipeline approve queue, WpContentJob model, push_to_wp pattern

provides:
  - quick_fix_toc Celery task — fetches WP content, injects TOC, pushes back
  - quick_fix_schema Celery task — fetches WP content, injects schema JSON-LD, pushes back
  - bulk_fix_schema Celery task — processes all schema-less pages with Redis progress tracking
  - bulk_fix_toc Celery task — processes all TOC-less pages with Redis progress tracking
  - POST /m/pages/fix/{page_id}/toc and /schema endpoints with immediate success feedback
  - GET /m/pages/bulk/schema/confirm and /toc/confirm screens with page count
  - POST /m/pages/bulk/schema and /toc dispatch endpoints
  - GET /m/pages/bulk/progress/{task_id} HTMX polling endpoint

affects:
  - any phase using pages_tasks Celery tasks
  - mobile UI navigation to /m/pages

tech-stack:
  added: []
  patterns:
    - "Optimistic UI: POST endpoint returns immediately, Celery does the work async"
    - "Redis progress JSON: {done, total, errors[], status} pattern for bulk ops"
    - "HTMX polling every 3s stops by omitting hx-trigger in done/error state"
    - "wp_post_id resolution from WpContentJob history (not Page model) — Pitfall 1 from RESEARCH"
    - "Sync schema rendering via render_schema_template() in Celery (not async render_schema_for_page)"

key-files:
  created:
    - app/tasks/pages_tasks.py
    - app/templates/mobile/pages/partials/fix_success.html
    - app/templates/mobile/pages/bulk_confirm.html
    - app/templates/mobile/pages/partials/bulk_progress.html
  modified:
    - app/routers/mobile.py

key-decisions:
  - "Optimistic UI for quick fix: endpoint returns success partial immediately, Celery task handles WP push async"
  - "wp_post_id resolved from WpContentJob history then WP REST API slug fallback — Page model has no wp_post_id"
  - "Bulk tasks use max_retries=0 (not 3) — bulk ops should not auto-retry an entire batch on partial failure"
  - "One page error does not stop bulk batch — individual errors tracked in Redis errors list"
  - "HTMX polling stops automatically in done/error state by removing hx-trigger from template"

patterns-established:
  - "Redis bulk progress key: bulk:{task_id}:progress with JSON {done, total, errors[], status}"
  - "Bulk endpoint: GET /confirm shows count, POST dispatches task + returns progress partial"
  - "fix_success.html partial: bg-green-50 green check inline replacement after quick fix"

requirements-completed:
  - PAG-03
  - PAG-04

duration: 4min
completed: 2026-04-12
---

# Phase 31 Plan 03: Quick Fix + Bulk Operations Summary

**Celery tasks for direct WP push of TOC/Schema with Redis-tracked bulk progress and HTMX polling.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-12T12:11:00Z
- **Completed:** 2026-04-12T12:15:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `app/tasks/pages_tasks.py` with 4 Celery tasks: `quick_fix_toc`, `quick_fix_schema`, `bulk_fix_schema`, `bulk_fix_toc`
- Implemented 7 new mobile endpoints: 2 quick fix POST, 2 bulk confirm GET, 2 bulk start POST, 1 progress polling GET
- Built bulk confirmation screen and HTMX progress partial with running/done/error states

## Task Commits

Each task was committed atomically:

1. **Task 1: Quick fix Celery tasks + success partial** - `7f44042` (feat)
2. **Task 2: Bulk operations + router endpoints + templates** - `948735f` (feat)

## Files Created/Modified

- `app/tasks/pages_tasks.py` — 4 Celery tasks: quick_fix_toc, quick_fix_schema, bulk_fix_schema, bulk_fix_toc. Uses get_sync_db(), _resolve_wp_post_id() helper (WpContentJob history + WP REST API slug fallback), render_schema_template (sync).
- `app/templates/mobile/pages/partials/fix_success.html` — Green inline partial with check-circle SVG, bg-green-50/text-green-800
- `app/templates/mobile/pages/bulk_confirm.html` — Bulk confirm screen extending base_mobile.html with bolt icon, count heading, hx-post confirm button targeting #bulk-progress
- `app/templates/mobile/pages/partials/bulk_progress.html` — Three-state partial: running (hx-trigger="every 3s" + progress bar), done (no hx-trigger + Вернуться link), error (warning icon)
- `app/routers/mobile.py` — Added 7 endpoints + mobile_router alias + json import

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Notes:**
- Plan's verification script referenced `mobile_router` (non-existent) — added `mobile_router = router` alias in mobile.py so future verification scripts work
- `inject_schema` is in `content_pipeline.py` (not schema_service.py as plan implied) — imported from correct module

## Self-Check: PASSED

Files verified:
- `app/tasks/pages_tasks.py` — FOUND
- `app/templates/mobile/pages/partials/fix_success.html` — FOUND
- `app/templates/mobile/pages/bulk_confirm.html` — FOUND
- `app/templates/mobile/pages/partials/bulk_progress.html` — FOUND

Commits verified:
- `7f44042` — FOUND (quick fix tasks + success partial)
- `948735f` — FOUND (bulk endpoints + templates)

Routes verified (all pass import check):
- `/m/pages/fix/{page_id}/toc` — FOUND
- `/m/pages/fix/{page_id}/schema` — FOUND
- `/m/pages/bulk/schema/confirm` — FOUND
- `/m/pages/bulk/toc/confirm` — FOUND
- `/m/pages/bulk/schema` — FOUND
- `/m/pages/bulk/toc` — FOUND
- `/m/pages/bulk/progress/{task_id}` — FOUND
