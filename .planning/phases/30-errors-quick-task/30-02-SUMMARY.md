---
phase: 30-errors-quick-task
plan: "02"
subsystem: mobile-ui
tags: [mobile, errors, yandex-webmaster, htmx, jinja2, celery, seotask]
dependency_graph:
  requires: ["30-01"]
  provides: ["/m/errors UI", "inline brief form", "Ошибки nav tab"]
  affects: ["app/routers/mobile.py", "app/templates/base_mobile.html"]
tech_stack:
  added: []
  patterns:
    - HTMX outerHTML swap for inline form expansion
    - HTMX every-3s polling for Celery task progress
    - Cookie persistence for site selection
    - Source FK pattern (source_error_id) on SeoTask
key_files:
  created:
    - app/templates/mobile/errors/index.html
    - app/templates/mobile/errors/partials/errors_content.html
    - app/templates/mobile/errors/partials/section.html
    - app/templates/mobile/errors/partials/brief_form.html
    - app/templates/mobile/errors/partials/brief_result.html
    - app/templates/mobile/errors/partials/sync_progress.html
  modified:
    - app/routers/mobile.py
    - app/templates/base_mobile.html
decisions:
  - "Used get_sites(db) without user filter (sites are not user-scoped in this app)"
  - "Used get_accessible_projects(db, user) for project selection in brief form"
  - "Cancel button uses onclick=window.location.reload() per plan simplicity guidance"
metrics:
  duration: 10
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_modified: 8
---

# Phase 30 Plan 02: Errors UI Summary

**One-liner:** /m/errors page with site dropdown, 3 Yandex error sections, HTMX sync polling, and inline SeoTask brief form with source_error_id FK.

## What Was Built

7 router endpoints added to `app/routers/mobile.py` under `/m/errors`:
- `GET /m/errors` — main page with site dropdown, HX-Request detects partial refresh
- `POST /m/errors/sync` — triggers `sync_yandex_errors.delay(site_id)`, returns polling partial
- `GET /m/errors/sync/status/{task_id}` — polls Redis `yandex_sync:{task_id}`, falls back to Celery AsyncResult
- `GET /m/errors/content` — reloads all 3 sections after sync completes
- `GET /m/errors/{error_type}/all` — paginated full list (20 per page) for Показать все
- `GET /m/errors/{error_id}/brief/form` — inline form partial (outerHTML swap)
- `POST /m/errors/{error_id}/brief` — creates SeoTask with `source_error_id` FK, returns success confirmation

6 Jinja2 templates created under `app/templates/mobile/errors/`:
- `index.html` — extends base_mobile.html, includes errors_content.html, has sync slot
- `partials/errors_content.html` — renders 3 sections with SVG icons via Jinja2 `with` blocks
- `partials/section.html` — single section: error rows with Составить ТЗ button, Показать все link
- `partials/brief_form.html` — inline form with priority radio group, project select, cancel button
- `partials/brief_result.html` — green success banner with link to task detail
- `partials/sync_progress.html` — 3-state polling partial (running/done/error), triggers section reload on done

Bottom nav in `base_mobile.html` updated: "Ещё" `<button>` replaced with "Ошибки" `<a href="/m/errors">` using Heroicons exclamation-triangle (24x24, stroke-width 1.5).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1    | 0b5d839 | feat(30-02): router endpoints for /m/errors + bottom nav update |
| 2    | 628f1fe | feat(30-02): Jinja2 templates for /m/errors page and partials |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Site model has no user_id field**
- **Found during:** Task 1
- **Issue:** Plan specified `select(Site).where(Site.user_id == user.id)` but Site model has no `user_id` column — sites are not user-scoped in this codebase
- **Fix:** Used `get_sites(db)` (same pattern as mobile_positions and mobile_traffic endpoints)
- **Files modified:** app/routers/mobile.py

**2. [Rule 1 - Bug] Project model has no direct user_id FK**
- **Found during:** Task 1
- **Issue:** Plan specified `select(Project).where(Project.user_id == user.id)` but Project uses a `project_users` association table (many-to-many)
- **Fix:** Used `get_accessible_projects(db, user)` matching the existing pattern in mobile_report_new endpoint
- **Files modified:** app/routers/mobile.py

## Known Stubs

None — all data is wired to live service calls.

## Self-Check: PASSED

- app/templates/mobile/errors/index.html: FOUND
- app/templates/mobile/errors/partials/errors_content.html: FOUND
- app/templates/mobile/errors/partials/section.html: FOUND
- app/templates/mobile/errors/partials/brief_form.html: FOUND
- app/templates/mobile/errors/partials/brief_result.html: FOUND
- app/templates/mobile/errors/partials/sync_progress.html: FOUND
- Commit 0b5d839: FOUND
- Commit 628f1fe: FOUND
