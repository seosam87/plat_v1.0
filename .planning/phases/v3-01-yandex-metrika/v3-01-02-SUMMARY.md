---
phase: v3-01
plan: "02"
subsystem: api
tags: [yandex-metrika, httpx, celery, sqlalchemy, postgresql, upsert, async]

# Dependency graph
requires:
  - phase: v3-01-01
    provides: MetrikaTrafficDaily, MetrikaTrafficPage, MetrikaEvent models and DB tables
provides:
  - metrika_service.py with API client (fetch_daily_traffic, fetch_page_traffic) and DB helpers (save/get snapshots, event CRUD)
  - fetch_metrika_data Celery task for on-demand fetch triggered by button click
  - compute_period_delta pure function for cross-period page comparison
affects: [v3-01-03, v3-01-04, v3-01-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sync Celery task wrapping async event loop (asyncio.new_event_loop) — same pattern as position_tasks.py"
    - "PostgreSQL upsert via sqlalchemy.dialects.postgresql.insert + on_conflict_do_update"
    - "OAuth token header: Authorization: OAuth {token}"
    - "URL normalization via urlsplit._replace(query='', fragment='').geturl()"

key-files:
  created:
    - app/services/metrika_service.py
    - app/tasks/metrika_tasks.py
    - tests/test_metrika_service.py
  modified:
    - app/celery_app.py

key-decisions:
  - "fetch_daily_traffic uses bytime endpoint with group=day; metrics include users alongside visits/bounce_rate/page_depth/avg_duration_seconds"
  - "fetch_page_traffic paginates with offset; URL normalization strips query params via urlsplit"
  - "Celery task uses asyncio.new_event_loop() inside sync task body — matches established position_tasks pattern"
  - "Rate limit retry: 60s countdown on HTTP 420/429, 10s on other errors, max_retries=3"

patterns-established:
  - "Pattern: Metrika API always uses ORGANIC_FILTER constant — never fetch all traffic without it"
  - "Pattern: DB functions return list[dict] (not ORM objects) for API/template consumption"

requirements-completed: []

# Metrics
duration: 8min
completed: 2026-04-01
---

# Phase v3-01 Plan 02: Metrika service layer and Celery task Summary

**Yandex Metrika API client with organic-filtered daily and per-page traffic fetch, PostgreSQL upsert snapshots, period delta computation, and Celery on-demand task with exponential retry**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-01T21:04:28Z
- **Completed:** 2026-04-01T21:12:00Z
- **Tasks:** 4
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- Created `metrika_service.py` with 10 functions: 2 API client (daily/page), 4 DB helpers (save/get daily+page), 1 pure computation (delta), 3 event CRUD
- Created `metrika_tasks.py` Celery task `fetch_metrika_data` with max_retries=3, rate-limit backoff, and internal async event loop
- Registered task in `celery_app.py` include list
- 3 unit tests for `compute_period_delta` covering basic delta, empty inputs, and sort order — all passing

## Task Commits

1. **Task 1: Create metrika_service.py** - `8d525c2` (feat)
2. **Task 2: Create Celery task** - `18b3a05` (feat)
3. **Task 3: Register in celery_app.py** - `77fce68` (feat)
4. **Task 4: Unit tests** - `09f37ff` (test)

## Files Created/Modified

- `app/services/metrika_service.py` — Full Metrika API client and DB layer (438 lines)
- `app/tasks/metrika_tasks.py` — Celery on-demand fetch task with retry logic
- `app/celery_app.py` — Added `"app.tasks.metrika_tasks"` to include list
- `tests/test_metrika_service.py` — 3 unit tests for compute_period_delta

## Decisions Made

- `fetch_daily_traffic` uses the `bytime` endpoint with `group=day` for chart-ready daily rows; includes `users` metric alongside the 4 core metrics
- URL normalization in `fetch_page_traffic` uses `urlsplit._replace(query='', fragment='').geturl()` to strip all query params consistently
- Celery task follows existing `asyncio.new_event_loop()` pattern from `position_tasks.py` — no new infrastructure needed
- Rate-limit (HTTP 420/429) gets 60s backoff; all other errors get 10s backoff; hard cap of 3 retries per project constraint

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required (token decryption uses existing crypto_service/Fernet pattern).

## Next Phase Readiness

- Service layer is complete and importable — Plan 03 (router + endpoints) can import directly from `metrika_service`
- Celery task is registered and ready to be triggered via `fetch_metrika_data.delay(site_id, date1, date2)`
- `compute_period_delta` is tested and ready for use in the comparison UI view

---
*Phase: v3-01-yandex-metrika*
*Completed: 2026-04-01*

## Self-Check: PASSED

All files present and all commits verified.
