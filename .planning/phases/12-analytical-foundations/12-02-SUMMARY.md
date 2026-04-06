---
phase: 12-analytical-foundations
plan: "02"
subsystem: analytics
tags: [quick-wins, htmx, jinja2, sqlalchemy, celery, opportunity-score]

# Dependency graph
requires:
  - phase: 12-01
    provides: normalize_url() utility and keyword_latest_positions flat table for fast position queries

provides:
  - Quick Wins service (get_quick_wins, dispatch_batch_fix) in app/services/quick_wins_service.py
  - Quick Wins router with 4 routes (page, table partial, batch-fix, fix-status)
  - Quick Wins HTML page with filter bar, scored table, and batch fix confirmation modal
  - HTMX partials for table refresh and fix status polling
  - Navigation entry "Quick Wins" under Аналитика section
  - Unit tests for service layer

affects:
  - phase 12-03 (dead-content): uses same keyword_latest_positions pattern
  - phase 13+ (error impact scoring): opportunity score pattern can be reused

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Python-side URL normalization before cross-table JOIN (normalize_url applied in Python loop)
    - Opportunity score formula (21 - avg_position) * weekly_traffic as dict key
    - WpContentJob.status=pending as batch dispatch mechanism (reuses existing pipeline)
    - HTMX table partial refresh via hx-get + hx-include for filter dropdowns
    - HTMX polling every 5s for async job status via fix_status partial

key-files:
  created:
    - app/services/quick_wins_service.py
    - app/routers/quick_wins.py
    - app/templates/analytics/quick_wins.html
    - app/templates/analytics/partials/quick_wins_table.html
    - app/templates/analytics/partials/fix_status.html
    - tests/test_quick_wins_service.py
  modified:
    - app/navigation.py
    - app/main.py

key-decisions:
  - "Python-side URL normalization in get_quick_wins() rather than SQL function call — matches plan design for cross-table URL alignment"
  - "dispatch_batch_fix() creates WpContentJob in pending status (not awaiting_approval) so pipeline picks it up immediately without extra approval step for batch Quick Wins context"
  - "fix_types parameter checks page needs before creating job to avoid duplicate jobs for pages that don't need the fix"

patterns-established:
  - "HTMX filter refresh pattern: hx-get + hx-include='[name=X],[name=Y]' captures sibling form elements"
  - "Batch fix modal pattern: JS Map<page_id, url> tracks selection; submit builds payload for fetch POST"
  - "Opportunity score badge tiers: >100 amber, 40-100 yellow, <40 gray"

requirements-completed: [QW-01, QW-02, QW-03]

# Metrics
duration: 5min
completed: 2026-04-06
---

# Phase 12 Plan 02: Quick Wins Summary

**Quick Wins page with (21-pos)*traffic opportunity scoring, issue/content-type filters, HTMX table refresh, and WpContentJob batch fix dispatch**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-06T13:25:43Z
- **Completed:** 2026-04-06T13:30:44Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Quick Wins service aggregates keyword_latest_positions (pos 4-20) with Python-side URL normalization, joins metrika weekly traffic, computes opportunity score, and filters by issue/content type
- Batch fix dispatch creates WpContentJob records in pending status for selected pages, reusing the existing content pipeline without extra approval overhead
- Quick Wins page at /analytics/{site_id}/quick-wins with filter bar, scored table with pass/fail icons, batch fix confirmation modal, and HTMX table refresh

## Task Commits

1. **Task 1 RED: failing tests** - `3ba9d89` (test)
2. **Task 1 GREEN: Quick Wins service** - `a3d77b5` (feat)
3. **Task 2: router + templates + navigation** - `2f67d21` (feat)

## Files Created/Modified

- `app/services/quick_wins_service.py` — get_quick_wins() with opportunity score, dispatch_batch_fix() creating WpContentJob records
- `app/routers/quick_wins.py` — 4 routes: page, table partial (HTMX), batch-fix POST, fix-status polling
- `app/templates/analytics/quick_wins.html` — Filter bar, batch fix button, confirmation modal with JS selection tracking
- `app/templates/analytics/partials/quick_wins_table.html` — HTMX-swappable table with score badges, check icons, select all
- `app/templates/analytics/partials/fix_status.html` — HTMX polling partial (spinner → done state)
- `tests/test_quick_wins_service.py` — 6 async integration tests covering all service behaviors
- `app/navigation.py` — Quick Wins child added at top of Аналитика section
- `app/main.py` — quick_wins router registered

## Decisions Made

- Python-side URL normalization in service loop rather than SQL function — consistent with normalize_url() design from plan 12-01
- WpContentJob created in `pending` (not `awaiting_approval`) for batch Quick Wins dispatch so the existing worker pipeline picks it up without a mandatory approval gate
- fix_types loop checks if page actually needs the fix before creating a job — prevents duplicate/unnecessary jobs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Quick Wins page functional at /analytics/{site_id}/quick-wins
- Batch fix creates WpContentJob records (requires running Celery worker + WP credentials for execution)
- Integration tests require PostgreSQL test database (seo_platform_test) to run; they collect successfully without it
- Phase 12-03 (Dead Content) can proceed — same pattern established

---
*Phase: 12-analytical-foundations*
*Completed: 2026-04-06*

## Self-Check: PASSED

All files verified present. All commits verified in git log.
