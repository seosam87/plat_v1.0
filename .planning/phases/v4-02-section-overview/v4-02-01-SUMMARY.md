---
phase: v4-02-section-overview
plan: "01"
subsystem: api
tags: [redis, sqlalchemy, celery, dashboard, positions, tasks, caching]

# Dependency graph
requires:
  - phase: v4-01-navigation-foundation
    provides: FastAPI app structure, existing ui_dashboard route in app/main.py
provides:
  - overview_service.aggregated_positions(): cross-site TOP-3/10/100 + weekly trend with Redis 300s cache
  - overview_service.todays_tasks(): overdue + in-progress tasks list (max 20)
  - ui_dashboard handler enriched with pos_summary and tasks_today context variables
affects:
  - v4-02-02 (template phase that consumes pos_summary and tasks_today)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Redis cache-aside pattern with 300s TTL for heavy aggregate SQL queries"
    - "asyncio.gather() for parallel DB + Redis calls in route handlers"
    - "DISTINCT ON (keyword_id, engine) ORDER BY checked_at DESC for latest-position queries"

key-files:
  created:
    - app/services/overview_service.py
    - tests/test_overview_service.py
  modified:
    - app/main.py

key-decisions:
  - "Cache key dashboard:agg_positions with 300s TTL — prevents re-running heavy cross-site aggregate SQL on every dashboard load"
  - "asyncio.gather() in ui_dashboard runs aggregated_positions and todays_tasks concurrently with existing data fetches"
  - "todays_tasks includes status IN (open, assigned, in_progress, review) filtered by in_progress OR due_date <= today — not just overdue"

patterns-established:
  - "Cache-aside in service layer: check Redis → if miss run SQL → store JSON → return; always aclose() in finally"
  - "Unit tests mock _get_redis with async side_effect to avoid real Redis connection in CI"

requirements-completed:
  - OVR-01
  - OVR-02
  - OVR-03

# Metrics
duration: 8min
completed: 2026-04-03
---

# Phase v4-02 Plan 01: Overview Service Summary

**Cross-site position aggregation (TOP-3/10/100 + weekly trend) and today's tasks service with Redis 300s cache, wired into ui_dashboard via asyncio.gather**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-03T14:44:57Z
- **Completed:** 2026-04-03T14:52:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- New `overview_service.py` with `aggregated_positions()` (Redis-cached) and `todays_tasks()` (DB query)
- `aggregated_positions()` uses DISTINCT ON CTE to get the latest position per keyword per engine, aggregates TOP-3/10/100 and 7-day trend counts across all sites
- `todays_tasks()` returns up to 20 overdue or in-progress tasks sorted by due_date then priority
- `ui_dashboard` route updated to call both functions in parallel via `asyncio.gather` and pass results to template

## Task Commits

Each task was committed atomically:

1. **Task 1: Create overview_service with aggregated_positions and todays_tasks** - `770afdf` (feat)
2. **Task 2: Wire overview_service into ui_dashboard route** - `7358841` (feat)

## Files Created/Modified
- `app/services/overview_service.py` - New service: aggregated_positions (Redis-cached) + todays_tasks
- `tests/test_overview_service.py` - 6 unit tests covering cache hit/miss, overdue logic, empty result
- `app/main.py` - ui_dashboard updated to call both new functions and pass pos_summary/tasks_today to template

## Decisions Made
- Used `asyncio.gather()` to run `aggregated_positions` and `todays_tasks` concurrently inside `ui_dashboard` for performance
- Stored Redis cache as JSON string using `json.dumps`/`json.loads` with decode_responses=True client
- `is_overdue` defined as `due_date < today` (strictly before) — tasks due today are "due" but not "overdue"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed cache hit test mock pattern**
- **Found during:** Task 1 verification
- **Issue:** `patch(..., return_value=redis_mock)` doesn't work for async functions returning a mock; the real `_get_redis` was called
- **Fix:** Changed to `patch(..., side_effect=_fake_get_redis)` with an async function returning the mock
- **Files modified:** tests/test_overview_service.py
- **Verification:** All 6 tests pass (was 1 failed before fix)
- **Committed in:** 770afdf (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test mock setup)
**Impact on plan:** Minor test infrastructure fix only. Service implementation matches plan exactly.

## Issues Encountered
- Mock patching for async `_get_redis` required `side_effect` with an async callable, not `return_value`. Fixed inline.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `pos_summary` (top3, top10, top100, trend_up, trend_down) and `tasks_today` (list of dicts) are available in the dashboard template context
- Phase v4-02-02 (template update) can consume these variables immediately
- No blockers

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: v4-02-section-overview*
*Completed: 2026-04-03*
