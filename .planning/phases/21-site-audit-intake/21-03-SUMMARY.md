---
phase: 21-site-audit-intake
plan: "03"
subsystem: ui
tags: [jinja2, htmx, intake, site-list, site-detail, badges]

# Dependency graph
requires:
  - phase: 21-01
    provides: intake_service.get_intake_statuses_for_sites and get_or_create_intake, SiteIntake model with IntakeStatus enum
provides:
  - Intake status column in site list table (green checkmark / gray dash, linked)
  - Intake badge section in site detail page (complete / draft / absent states)
  - Batch prefetch of intake statuses for site list (no N+1)
  - SELECT-only intake fetch on site detail (no auto-create on detail view)
affects: [21-02, phase-22, proposal-templates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Batch prefetch pattern: collect site_ids first, then single query to intake_service, pass dict to template"
    - "SELECT-only intake read on detail page: use sa_select(SiteIntake).where(...) directly, not get_or_create"
    - "Three-state badge pattern in Jinja2: complete (green d1fae5) / draft (badge-unknown) / absent (accent link)"

key-files:
  created: []
  modified:
    - app/main.py
    - app/templates/sites/index.html
    - app/templates/sites/detail.html

key-decisions:
  - "SELECT-only intake read on site detail to avoid auto-creating intake records on detail view (only create on intake form visit)"
  - "Batch prefetch intake_statuses in ui_sites endpoint using get_intake_statuses_for_sites to avoid N+1"

patterns-established:
  - "Intake status shown as linked SVG checkmark (complete) or gray dash (draft/absent) in list tables"
  - "Intake badge row placed immediately after client badge row in site detail header area"

requirements-completed: [INTAKE-05]

# Metrics
duration: 4min
completed: 2026-04-09
---

# Phase 21 Plan 03: Site Audit Intake — UI Integration Summary

**Intake status badges wired into site list (batch-prefetched Intake column) and site detail (3-state badge below client row)**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-09T13:50:00Z
- **Completed:** 2026-04-09T13:51:28Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Site list `/ui/sites` now shows Intake column: green SVG checkmark for complete, gray dash for draft/absent, both linked to intake form
- Site detail `/ui/sites/{id}` now shows intake badge row below client badge with three states (complete green, draft gray, absent accent link)
- Batch prefetch via `intake_service.get_intake_statuses_for_sites` prevents N+1 on site list
- SELECT-only intake read on detail page (no implicit intake record creation on site detail visits)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add intake status to site list page** - `ad64d8f` (feat)
2. **Task 2: Add intake badge and link to site detail page** - `174c98f` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/main.py` - Added intake_statuses batch prefetch in ui_sites; added SELECT-only SiteIntake fetch in ui_site_overview
- `app/templates/sites/index.html` - Added Intake column header and status cell with SVG checkmark / gray dash
- `app/templates/sites/detail.html` - Added intake badge section (3 states) below client badge row

## Decisions Made
- SELECT-only intake read on site detail (not get_or_create) — per plan guidance: only create intake record when user explicitly visits the intake form (21-02)
- Batch prefetch pattern used for site list to avoid N+1 queries

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Site list and detail pages fully wired with intake status badges
- All intake status indicators link to `/ui/sites/{id}/intake` (the intake form built in plan 21-02)
- Phase 21 complete: model (01), form (02), list/detail badges (03)

---
*Phase: 21-site-audit-intake*
*Completed: 2026-04-09*
