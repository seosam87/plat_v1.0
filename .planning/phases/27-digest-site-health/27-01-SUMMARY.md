---
phase: 27-digest-site-health
plan: 01
subsystem: mobile-ui
tags: [fastapi, jinja2, htmx, async, sqlalchemy, mobile, digest]

requires:
  - phase: 26-mobile-foundation
    provides: base_mobile.html, /m/ router, bottom nav, Telegram WebApp auth

provides:
  - mobile_digest_service.py with 6 async query functions
  - /m/digest route and digest.html template
  - get_mobile_site_health() for Plan 02 health card

affects: [27-02-site-health, 28-mobile-positions]

tech-stack:
  added: []
  patterns: [async service layer for mobile queries, partition-safe KeywordPosition queries with checked_at cutoff]

key-files:
  created:
    - app/services/mobile_digest_service.py
    - app/templates/mobile/digest.html
  modified:
    - app/routers/mobile.py

key-decisions:
  - "Standalone async service, no imports from sync morning_digest_service.py"
  - "Both /m/ and /m/digest render the same digest page"
  - "Used sent_at for alert ordering (dispatched alerts only)"

patterns-established:
  - "Mobile service pattern: async functions returning list[dict] for template rendering"
  - "Digest block pattern: section > h2 > if/else items/empty > chevron rows"

requirements-completed: [DIG-01, DIG-02]

duration: 2min
completed: 2026-04-10
---

# Phase 27 Plan 01: Mobile Digest Summary

**Async mobile digest service with 4-block /m/digest page (position changes, crawl errors, alerts, overdue tasks) plus site health query for Plan 02**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-10T17:14:20Z
- **Completed:** 2026-04-10T17:16:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created mobile_digest_service.py with 6 async functions covering both digest and health card
- Built digest.html template with 4 ordered blocks, empty states, deep links to desktop /ui/ pages
- Added /m/digest route and updated /m/ homepage to render digest directly

## Task Commits

Each task was committed atomically:

1. **Task 1: Create mobile_digest_service.py** - `90d7149` (feat)
2. **Task 2: Create digest.html and /m/digest route** - `f64cd50` (feat)

## Files Created/Modified
- `app/services/mobile_digest_service.py` - 6 async query functions (build_mobile_digest, get_top_position_changes, get_recent_crawl_errors, get_recent_alerts, get_overdue_tasks, get_mobile_site_health)
- `app/templates/mobile/digest.html` - Digest page template with 4 blocks, empty states, touch-friendly rows
- `app/routers/mobile.py` - Added /m/digest route, updated /m/ to render digest

## Decisions Made
- Standalone async service: no imports from sync morning_digest_service.py to avoid event loop blocking
- Both /m/ and /m/digest render the same digest page (bottom nav points to /m/)
- Used sent_at for alert ordering since alerts need to be dispatched to be relevant
- Russian short date formatting via simple month map (not locale-dependent)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- get_mobile_site_health() is ready for Plan 02 (health card page)
- digest.html pattern established for other mobile pages to follow

---
*Phase: 27-digest-site-health*
*Completed: 2026-04-10*
