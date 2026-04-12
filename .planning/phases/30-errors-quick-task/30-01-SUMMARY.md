---
phase: 30-errors-quick-task
plan: 01
subsystem: database
tags: [yandex-webmaster, celery, sqlalchemy, alembic, postgresql, redis]

# Dependency graph
requires:
  - phase: yandex-webmaster (existing)
    provides: yandex_webmaster_service with token-based API client
  - phase: 28-positions-traffic
    provides: Site model with url field used for domain resolution
provides:
  - YandexError SQLAlchemy model with YandexErrorType and YandexErrorStatus enums
  - Alembic migration 0055 creating yandex_errors table + tasktype enum extension
  - SeoTask.source_error_id FK to yandex_errors
  - fetch_indexing_errors, fetch_crawl_errors, fetch_sanctions, resolve_host_id in yandex_webmaster_service
  - yandex_errors_service with list_errors, count_errors, get_error, last_fetched_at
  - sync_yandex_errors Celery task with upsert + soft-close logic
affects: [30-02, 30-03, errors-ui, site-health]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - postgresql INSERT ON CONFLICT DO UPDATE for idempotent error upsert
    - Redis caching for Yandex user_id (7d TTL) and host_map per user (1d TTL)
    - COMMIT/BEGIN wrapper for ALTER TYPE in Alembic migration (Postgres limitation)
    - Soft-close pattern: mark open rows as resolved when fetched_at < sync_start_time
    - Empty string sentinel for url in sanctions rows to satisfy NOT NULL + unique constraint

key-files:
  created:
    - app/models/yandex_errors.py
    - alembic/versions/0055_add_yandex_errors.py
    - app/services/yandex_errors_service.py
    - app/tasks/yandex_errors_tasks.py
  modified:
    - app/models/task.py
    - app/services/yandex_webmaster_service.py
    - app/celery_app.py

key-decisions:
  - "Use postgresql.ENUM with create_type=False in migration create_table to avoid duplicate type error when SA tries to auto-create types already created via op.execute"
  - "url='' sentinel for sanctions (not URL-based) to satisfy NOT NULL + unique constraint per D-04 RESEARCH pitfall"
  - "Soft-close: set status=resolved for open rows where fetched_at < sync_start_time — preserves user status changes"
  - "host_map cached as JSON dict in Redis key yandex:host_map:{user_id} — single key for all domains per user"

patterns-established:
  - "Yandex upsert pattern: pg_insert on uq_yandex_errors_identity, update fetched_at+detail+title, DO NOT update status"
  - "Celery task Redis result key: yandex_sync:{task_id} TTL 300s for HTMX polling"

requirements-completed: [ERR-01, ERR-02]

# Metrics
duration: 15min
completed: 2026-04-12
---

# Phase 30 Plan 01: Yandex Errors Data Foundation Summary

**YandexError model + migration 0055 + Webmaster API error functions + Celery sync task with upsert/soft-close + DB read service**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-12T00:34:00Z
- **Completed:** 2026-04-12T00:49:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- YandexError model with YandexErrorType (indexing/crawl/sanction) and YandexErrorStatus (open/ignored/resolved) enums, UniqueConstraint on (site_id, error_type, subtype, url) for idempotent upsert
- Migration 0055 applies cleanly: creates yandex_errors table, extends tasktype enum with 3 values (yandex_indexing, yandex_crawl, yandex_sanction) using COMMIT/BEGIN wrapper, adds source_error_id FK to seo_tasks
- sync_yandex_errors Celery task implements full sync flow: resolve host via Redis-cached host_map, fetch 3 error types, upsert with ON CONFLICT DO UPDATE, soft-close stale open rows

## Task Commits

1. **Task 1: YandexError model + Alembic migration 0055 + SeoTask extension** - `b519c37` (feat)
2. **Task 2: Yandex Webmaster API error functions + Celery sync task + errors service** - `11700ce` (feat)

## Files Created/Modified
- `app/models/yandex_errors.py` - YandexError ORM model with enums and UniqueConstraint
- `alembic/versions/0055_add_yandex_errors.py` - Migration creating table, enums, extending tasktype, adding FK
- `app/models/task.py` - Added yandex_indexing, yandex_crawl, yandex_sanction to TaskType; source_error_id FK to SeoTask
- `app/services/yandex_webmaster_service.py` - Added fetch_indexing_errors, fetch_crawl_errors, fetch_sanctions, resolve_host_id
- `app/services/yandex_errors_service.py` - DB read helpers: list_errors, count_errors, get_error, last_fetched_at
- `app/tasks/yandex_errors_tasks.py` - sync_yandex_errors Celery task with max_retries=3
- `app/celery_app.py` - Registered app.tasks.yandex_errors_tasks in include list

## Decisions Made
- Used `postgresql.ENUM(..., create_type=False)` in migration's `create_table` call — SQLAlchemy would otherwise attempt to CREATE the enum type again (after we already created it via `op.execute`), causing DuplicateObject error.
- Sanctions use `url=""` (empty string, not NULL) as sentinel to satisfy both `NOT NULL` constraint and `UniqueConstraint("site_id", "error_type", "subtype", "url")`.
- `host_map` cached as JSON dict per user (`yandex:host_map:{user_id}`) — allows multiple domain lookups without separate Redis keys.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed migration enum type creation conflict**
- **Found during:** Task 1 (migration execution)
- **Issue:** `op.create_table` with `sa.Enum(...)` caused SQLAlchemy to auto-emit `CREATE TYPE` DDL even though types were already created via `op.execute`. DuplicateObject error on migration run.
- **Fix:** Replaced `sa.Enum(...)` in column definitions with `postgresql.ENUM(..., create_type=False)` to prevent double creation.
- **Files modified:** `alembic/versions/0055_add_yandex_errors.py`
- **Verification:** `alembic upgrade head` exits 0, `alembic current` shows 0055 (head)
- **Committed in:** b519c37 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Fix was necessary for migration correctness. No scope creep.

## Issues Encountered
- Database not accessible on localhost — must use `docker compose exec api alembic upgrade head` to run migrations inside the Docker network.

## User Setup Required
None - no external service configuration required for this plan. YANDEX_WEBMASTER_TOKEN already exists in settings.

## Next Phase Readiness
- All backend infrastructure for Yandex errors is complete
- Plans 30-02 and 30-03 (UI) can consume YandexError model, yandex_errors_service, and sync_yandex_errors task
- SeoTask.source_error_id FK available for task creation from errors

---
*Phase: 30-errors-quick-task*
*Completed: 2026-04-12*
