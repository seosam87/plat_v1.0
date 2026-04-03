---
phase: v3-03-change-monitoring
plan: "03"
subsystem: celery, notifications, scheduling
tags: [celery-beat, redbeat, telegram, digest, cron, weekly-digest]

# Dependency graph
requires:
  - phase: v3-03-01
    provides: DigestSchedule model and change_alerts table
  - phase: v3-03-02
    provides: format_weekly_digest in telegram_service.py and ChangeAlert writes

provides:
  - digest_service.py with build_digest, send_digest, upsert_digest_schedule, compute_digest_cron
  - digest_tasks.py with send_weekly_digest Celery task
  - Per-site redbeat schedule registration and boot-time restore
  - 6 unit tests covering cron computation and Telegram digest formatting

affects: [v3-03-04, any plan involving weekly digest delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "compute_digest_cron pure helper for testable cron generation (day 1..7 → cron 1..0)"
    - "restore_digest_schedules_from_db pattern: sync DB read on Beat startup to survive Redis FLUSHALL"
    - "build_digest (sync for Celery) + upsert_digest_schedule (async for FastAPI) separation"

key-files:
  created:
    - app/services/digest_service.py
    - app/tasks/digest_tasks.py
    - tests/test_digest_service.py
  modified:
    - app/celery_app.py

key-decisions:
  - "compute_digest_cron extracted as pure helper: enables unit testing without DB or Redis"
  - "cron day_of_week conversion: user passes 1=Mon..7=Sun; cron uses 0=Sun; formula is day % 7"
  - "restore_digest_schedules_from_db called from existing beat_init signal in celery_app.py"

patterns-established:
  - "Pure cron helper pattern: extract computation from DB functions for unit testability"
  - "Dual-mode service: sync functions for Celery tasks, async functions for FastAPI endpoints"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-03
---

# Phase v3-03 Plan 03: Weekly Digest Celery Beat Task and Schedule Management Summary

**Weekly digest service with per-site redbeat scheduling, cron computation helper, and send_weekly_digest Celery task wired into beat_init restore**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T08:00:00Z
- **Completed:** 2026-04-03T08:05:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Digest service with build_digest (collects changes for past N days, groups by severity), send_digest (formats + sends via Telegram), and schedule management via redbeat
- Celery task send_weekly_digest registered in celery_app.py include list with 2 retries, soft_time_limit=60
- Boot-time restore: restore_digest_schedules_from_db called from existing beat_init signal
- 6 unit tests pass: 4 cron expression tests and 2 Telegram format tests

## Task Commits

Each task was committed atomically:

1. **Task 01: digest_service.py** - `9f83079` (feat)
2. **Task 02: digest_tasks.py + celery_app.py** - `9f83079` (feat)
3. **Task 03: tests/test_digest_service.py** - `9f83079` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `app/services/digest_service.py` - Digest builder, send_digest, schedule management, redbeat registration
- `app/tasks/digest_tasks.py` - send_weekly_digest Celery task
- `tests/test_digest_service.py` - 6 unit tests for cron computation and Telegram formatting
- `app/celery_app.py` - Added digest_tasks to include list and restore_digest_schedules_from_db to beat_init

## Decisions Made
- `compute_digest_cron` extracted as pure helper for testability: `day_of_week % 7` maps 1..7 to 1..0 (Sun=0 in cron)
- Existing `beat_init.connect` signal in celery_app.py extended to call `restore_digest_schedules_from_db`
- Tasks 01-03 committed together as all three files were created simultaneously in the WIP commit

## Deviations from Plan

None - plan executed exactly as written. All three files were already present and correct from a prior WIP commit (`9f83079`).

## Issues Encountered
- Tests require environment variables (DATABASE_URL, REDIS_URL, SECRET_KEY, FERNET_KEY) due to conftest.py importing app.main. Tests passed when run with minimal dummy values pointing to non-existent services (pure unit tests don't hit the DB).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- digest_service.py and send_weekly_digest task are ready for use by plan v3-03-04 (monitoring router + UI with on-demand digest button)
- DigestSchedule upsert endpoint can be wired from site admin settings in plan 04

## Self-Check: PASSED

- FOUND: app/services/digest_service.py
- FOUND: app/tasks/digest_tasks.py
- FOUND: tests/test_digest_service.py
- FOUND: .planning/phases/v3-03-change-monitoring/v3-03-03-SUMMARY.md
- FOUND: commit 9f83079 (feat(v3-03-03): add digest service, Celery Beat task, and redbeat schedule management)
- Tests: 6 passed in 0.03s

---
*Phase: v3-03-change-monitoring*
*Completed: 2026-04-03*
