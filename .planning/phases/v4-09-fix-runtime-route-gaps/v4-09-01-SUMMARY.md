---
phase: v4-09-fix-runtime-route-gaps
plan: 01
subsystem: ui
tags: [htmx, jinja2, templates, routing, 405-fix]

requires:
  - phase: v4-07-settings-section
    provides: admin/settings.html superseded by proxy.html + parameters.html
  - phase: v4-03-section-sites
    provides: sites list page at /ui/sites and schedule route @app.post
provides:
  - Crawl schedule form submits via hx-post matching backend @app.post route
  - All 14 site-scoped templates link to /ui/sites (GET-accessible list page)
  - Orphaned admin/settings.html removed from codebase
affects: []

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - app/templates/sites/schedule.html
    - app/templates/analytics/index.html
    - app/templates/audit/index.html
    - app/templates/architecture/index.html
    - app/templates/bulk/index.html
    - app/templates/clusters/index.html
    - app/templates/gap/index.html
    - app/templates/intent/index.html
    - app/templates/keywords/index.html
    - app/templates/metrika/index.html
    - app/templates/monitoring/index.html
    - app/templates/pipeline/publish.html
    - app/templates/positions/index.html
    - app/templates/traffic_analysis/index.html
    - app/templates/sites/edit.html

key-decisions:
  - "No new decisions - strictly bug fix and cleanup per audit findings"

patterns-established: []

requirements-completed: [SITE-V4-02, SITE-V4-03]

duration: 10min
completed: 2026-04-04
---

# Phase v4-09 Plan 01: Fix Runtime Route Gaps Summary

**Fix crawl schedule 405 (hx-put to hx-post) and back-to-site navigation 405 (14 templates redirected to /ui/sites) plus orphaned settings.html deletion**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-04T16:59:02Z
- **Completed:** 2026-04-04T17:09:02Z
- **Tasks:** 2
- **Files modified:** 16 (15 edited + 1 deleted)

## Accomplishments
- Fixed SITE-V4-02: crawl schedule form now uses hx-post matching the backend @app.post route, eliminating 405 Method Not Allowed
- Fixed SITE-V4-03: all 14 site-scoped templates now link back to /ui/sites (the GET-accessible sites list) instead of /ui/sites/{id} (DELETE-only endpoint)
- Deleted orphaned admin/settings.html (200 lines, 74 inline styles) superseded by proxy.html + parameters.html in Phase v4-07

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix crawl schedule hx-put to hx-post and fix back-to-site links in all 14 templates** - `168e671` (fix)
2. **Task 2: Delete orphaned admin/settings.html** - `481e9c8` (chore)

## Files Created/Modified
- `app/templates/sites/schedule.html` - Changed hx-put to hx-post for crawl schedule select
- `app/templates/analytics/index.html` - Fixed 2 back-to-site links (breadcrumb + button)
- `app/templates/audit/index.html` - Fixed 1 back-to-site button link
- `app/templates/architecture/index.html` - Fixed 1 back-to-site button link
- `app/templates/bulk/index.html` - Fixed 1 back-to-site button link
- `app/templates/clusters/index.html` - Fixed 1 breadcrumb link (site_id variant)
- `app/templates/gap/index.html` - Fixed 1 back-to-site button link
- `app/templates/intent/index.html` - Fixed 1 breadcrumb link (site_id variant)
- `app/templates/keywords/index.html` - Fixed 1 breadcrumb link (site_id variant)
- `app/templates/metrika/index.html` - Fixed 1 breadcrumb link
- `app/templates/monitoring/index.html` - Fixed 1 back-to-site button link
- `app/templates/pipeline/publish.html` - Fixed 1 breadcrumb link
- `app/templates/positions/index.html` - Fixed 1 breadcrumb link (site_id variant)
- `app/templates/traffic_analysis/index.html` - Fixed 1 back-to-site button link
- `app/templates/sites/edit.html` - Fixed Cancel button link
- `app/templates/admin/settings.html` - Deleted (orphaned file)

## Decisions Made
None - followed plan as specified. Strictly bug fixes and cleanup per milestone audit findings.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both SITE-V4-02 and SITE-V4-03 gaps from v1.0 milestone audit are closed
- Zero 405 errors on crawl schedule save and back-to-site navigation
- No blockers for subsequent phases

---
*Phase: v4-09-fix-runtime-route-gaps*
*Completed: 2026-04-04*
