---
phase: v3-07-bulk-operations
plan: "02"
subsystem: ui
tags: [bulk, htmx, jinja2, fastapi, keyword-management]

# Dependency graph
requires:
  - phase: v3-07-01
    provides: bulk_service.py with batch move/assign/delete, CSV/XLSX export, audit-logged import
provides:
  - FastAPI bulk router with 7 endpoints (GET page, POST move-group, POST move-cluster, POST assign-url, POST delete, GET export, POST import)
  - Jinja2 bulk/index.html with select-all checkbox table, actions bar, export buttons, and import form
  - Router registered in main.py, button added to sites/detail.html
affects: [v3-07, keyword-management, site-detail]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bulk action pattern: JS Set tracks selected IDs, fetch() posts JSON arrays to backend endpoints"
    - "Filter reuse: bulk page uses /analytics/sites/{site_id}/keywords endpoint for keyword loading"

key-files:
  created:
    - app/routers/bulk.py
    - app/templates/bulk/index.html
  modified:
    - app/main.py
    - app/templates/sites/detail.html

key-decisions:
  - "Bulk page reuses /analytics/sites/{site_id}/keywords filter endpoint — avoids duplicating filter logic"
  - "Selected IDs stored in JS Set() — efficient add/remove on checkbox toggle, no DOM scanning on submit"
  - "Export endpoints use direct GET links (not HTMX) — triggers browser file download natively"

patterns-established:
  - "Select-all + batch-action pattern: #select-all checkbox + .kw-cb class + selectedIds Set()"
  - "Import form: multipart FormData posted with fetch(), status shown inline without page reload"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-03
---

# Phase v3-07 Plan 02: Bulk Router and UI Summary

**FastAPI bulk router (7 endpoints) and Jinja2 UI with select-all keyword table, batch group/cluster/URL actions, CSV/XLSX export, and file import with duplicate-mode selector**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T08:40:20Z
- **Completed:** 2026-04-03T08:45:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Bulk router with all 7 required endpoints registered at `/bulk/{site_id}/*`, all protected by `require_admin`
- Full-featured bulk operations page with filter bar, scrollable keyword table with select-all checkbox, sticky actions bar showing selected count, group/cluster/URL assignment controls with confirmation on delete
- Export section with direct CSV and XLSX download links; import section with file picker, on_duplicate selector (skip/update/replace), and inline status message with counts
- Router registered in main.py and "Массовые операции" button added to sites/detail.html quick actions

## Task Commits

Each task was committed atomically:

1. **Task 01: Create bulk router** — included in `843858b` (feat: add bulk operations router, 7 endpoints, UI with select-all and batch actions)
2. **Task 02: Create bulk operations page template** — included in `843858b`
3. **Task 03: Register router and add button** — included in `843858b`

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `app/routers/bulk.py` — 7 route handlers: page GET, move-group POST, move-cluster POST, assign-url POST, delete POST, export GET (csv/xlsx), import POST (multipart)
- `app/templates/bulk/index.html` — full bulk operations UI with Jinja2, select-all JS pattern, filter bar, export/import sections, all copy in Russian
- `app/main.py` — bulk_router import and `app.include_router(bulk_router)` registration; `/bulk` added to help module map
- `app/templates/sites/detail.html` — "Массовые операции" button linking to `/bulk/{site.id}`

## Decisions Made

- Bulk page reuses `/analytics/sites/{site_id}/keywords` endpoint rather than duplicating filter logic — clean separation, single source of truth for keyword filtering
- Selected IDs stored in a JS `Set()` for O(1) add/remove on checkbox toggle, serialized to array on action submit
- Export links are plain `<a href="...">` tags triggering browser file download — no fetch() needed, no response handling complexity

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase v3-07 is now complete: bulk_service.py (wave 1) + bulk router + bulk UI (wave 2)
- Bulk operations page is accessible from every site's detail page
- Ready for next phase work

---
*Phase: v3-07-bulk-operations*
*Completed: 2026-04-03*
