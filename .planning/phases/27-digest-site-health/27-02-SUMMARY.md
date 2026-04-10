---
phase: 27-digest-site-health
plan: 02
subsystem: mobile-ui
tags: [fastapi, jinja2, htmx, async, sqlalchemy, mobile, health-card, celery]

requires:
  - phase: 27-digest-site-health
    provides: mobile_digest_service.py with get_mobile_site_health(), base_mobile.html, /m/ router

provides:
  - /m/health/{site_id} page with 6 operational metrics and color indicators
  - POST /m/health/{site_id}/crawl endpoint triggering Celery crawl
  - Inline task creation form via GET task-form + POST tasks endpoints
  - _format_health_metrics() display formatting helper

affects: [28-mobile-positions]

tech-stack:
  added: []
  patterns: [health metric color-to-display mapping in route handler, HTMX 2.0 hx-disabled-elt for double-tap prevention]

key-files:
  created:
    - app/templates/mobile/health.html
    - app/templates/mobile/partials/task_form.html
  modified:
    - app/routers/mobile.py

key-decisions:
  - "Service returns 'color' key; route maps to 'status' for template via _format_health_metrics()"
  - "Raw values from service formatted to Russian display strings in route handler (not in service)"

patterns-established:
  - "Health metric formatting: service returns raw data + color, route formats display strings"
  - "HTMX action pattern: hx-post with hx-swap=none + hx-on::after-request for toast feedback"

requirements-completed: [HLT-01, HLT-02]

duration: 2min
completed: 2026-04-10
---

# Phase 27 Plan 02: Site Health Card Summary

**Mobile health card page with 6 color-coded operational metrics, Celery crawl trigger, and inline HTMX task creation form**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-10T18:16:21Z
- **Completed:** 2026-04-10T18:18:22Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created health.html template with 6 metric cards showing green/yellow/red/grey status dots
- Added 4 health card routes to mobile.py (GET health, POST crawl, GET task-form, POST tasks)
- Built inline task creation form with HTMX partial loading and toast feedback

## Task Commits

Each task was committed atomically:

1. **Task 1: Create health.html template and task_form.html partial** - `c75fbc7` (feat) — cherry-picked from prior session
2. **Task 2: Add health card routes and action endpoints to mobile.py** - `15e5dec` (feat)

## Files Created/Modified
- `app/templates/mobile/health.html` - Health card page with 6 metric cards, crawl button, task form slot
- `app/templates/mobile/partials/task_form.html` - Inline task creation form fragment (HTMX partial)
- `app/routers/mobile.py` - 4 new endpoints: mobile_health, mobile_trigger_crawl, mobile_task_form, mobile_create_task

## Decisions Made
- Service returns `color` key but template expects `status` — added `_format_health_metrics()` helper in mobile.py to map keys and format display strings
- Raw metric values (integers, enum values, datetime objects) formatted to Russian display strings in the route handler rather than the service layer, keeping the service pure data

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adapted service response key mapping**
- **Found during:** Task 2
- **Issue:** Plan assumed service returns `status` key per metric, but actual service (from Plan 01) returns `color` key
- **Fix:** Created `_format_health_metrics()` helper to map `color` -> `status` and format raw values to display strings
- **Files modified:** app/routers/mobile.py
- **Verification:** grep confirms correct key usage in route handler

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary adaptation to actual service interface. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Health card page complete, ready for mobile positions phase (28)
- Pattern established: HTMX partials for inline forms with toast feedback

---
*Phase: 27-digest-site-health*
*Completed: 2026-04-10*
