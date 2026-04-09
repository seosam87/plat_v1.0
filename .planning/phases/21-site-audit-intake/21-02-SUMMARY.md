---
phase: 21-site-audit-intake
plan: 02
subsystem: ui
tags: [htmx, jinja2, fastapi, router, templates, intake]

# Dependency graph
requires:
  - phase: 21-01
    provides: SiteIntake model, IntakeService functions, Alembic migration 0044
provides:
  - Intake router at /ui/sites/{id}/intake with 8 endpoints
  - Full-page intake form with 5-tab HTMX layout
  - Section-by-section save (access, goals, analytics, technical, checklist)
  - Verification checklist partial with HTMX refresh
  - Completion flow with confirm dialog and badge update
affects: [21-03, proposal-templates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Intake router follows crm.py pattern: APIRouter prefix + Depends(require_manager_or_above)"
    - "HTMX section save: hx-post + hx-swap=none + HX-Trigger showToast/sectionSaved"
    - "Tab switching JS: switchTab() pattern from crm/detail.html adapted for intake-tab/intake-tab-panel classes"
    - "Checklist refresh: HTMX fragment partial _tab_checklist.html targeted by #checklist-content"

key-files:
  created:
    - app/routers/intake.py
    - app/templates/intake/form.html
    - app/templates/intake/_tab_checklist.html
  modified:
    - app/main.py

key-decisions:
  - "Router path parameters: GET /intake uses uuid.UUID type hint; POST endpoints use str + uuid.UUID() conversion for symmetry with other routers"
  - "db.commit() called in router after each service call (service layer uses flush only)"
  - "Checklist partial served via GET with HX-Trigger header on TemplateResponse"

patterns-established:
  - "intake-tab/intake-tab-panel class naming for switchTab() — does not conflict with crm-tab/crm-tab-panel"
  - "Section tracking via hidden inputs with id=section-{name} updated by sectionSaved HTMX event"

requirements-completed: [INTAKE-01, INTAKE-02, INTAKE-03, INTAKE-04]

# Metrics
duration: 2min
completed: 2026-04-09
---

# Phase 21 Plan 02: Intake Form UI Summary

**FastAPI intake router with 8 endpoints + 5-tab HTMX form (access/goals/analytics/technical/checklist), section-by-section save with toast+checkmark, and live checklist refresh via HTMX partial**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-09T13:50:11Z
- **Completed:** 2026-04-09T13:52:52Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Intake router registered in app/main.py with full CRUD-style section save endpoints
- 5-tab intake form template with client-side tab switching (no page reload)
- Dynamic competitors list in Goals tab (add/remove rows, max 10, JS-driven)
- Checklist tab renders 3-state items (connected/not_configured/unknown) from live DB data
- Completion flow: allSectionsSaved() check, confirm dialog, intakeCompleted event updates badge

## Task Commits

Each task was committed atomically:

1. **Task 1: Intake router with form page and section save endpoints** - `63ad931` (feat)
2. **Task 2: Intake form template with 5-tab layout and HTMX interactions** - `1169cf1` (feat)

**Plan metadata:** (committed with this summary)

## Files Created/Modified
- `app/routers/intake.py` - APIRouter prefix=/ui/sites, 8 endpoints, HX-Trigger JSON responses
- `app/templates/intake/form.html` - Full page, 5 tabs, switchTab JS, addCompetitor JS, section tracking
- `app/templates/intake/_tab_checklist.html` - HTMX refresh partial, 3-state icon+badge per item
- `app/main.py` - Registered intake_router after crm_router

## Decisions Made
- GET /intake/checklist (refresh) uses uuid.UUID path type, POST endpoints use str for consistency with other routers
- db.commit() in router handlers; service functions use flush() — standard pattern established in plan 01
- HX-Trigger on TemplateResponse for checklist refresh (showToast: "Статусы обновлены")

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Intake form fully functional at /ui/sites/{id}/intake
- Plan 21-03 can add intake status badge to site list and site detail pages
- intake_service.get_intake_statuses_for_sites() available for batch site list queries

---
*Phase: 21-site-audit-intake*
*Completed: 2026-04-09*
