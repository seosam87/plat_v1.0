---
phase: 17-in-app-notifications
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, celery, notifications, postgresql]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: User model (users table FK target)
  - phase: 02-site-management
    provides: Site model (sites table FK target)
provides:
  - Notification SQLAlchemy model with all D-03 fields and 3 DB indexes
  - Alembic migration 0042 creating notifications table
  - notify() async helper in app/services/notifications.py (D-01 signature)
  - cleanup_old_notifications Celery task with nightly Beat schedule at 03:00
  - 8 unit tests covering notify() and cleanup task
affects:
  - 17-02 (bell UI, feed router — imports from app.models.notification and app.services.notifications)
  - 17-03 (Celery task wiring — calls notify() at task finalization)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Notification helper: caller owns transaction (db.flush() inside notify, db.commit() by caller)"
    - "Celery cleanup tasks: asyncio.new_event_loop() wrapping async _impl() for sync Celery entry point"
    - "Python-side ORM defaults: override __init__ with kwargs.setdefault() for attributes needed pre-flush"
    - "Static beat_schedule in celery_app.conf.update() for fixed nightly tasks (not redbeat)"

key-files:
  created:
    - app/models/notification.py
    - alembic/versions/0042_notifications.py
    - app/services/notifications.py
    - app/tasks/notification_tasks.py
    - tests/services/test_notifications.py
    - tests/tasks/test_notification_cleanup.py
  modified:
    - app/models/__init__.py
    - app/celery_app.py

key-decisions:
  - "Python __init__ override used in Notification model so is_read=False and severity='info' are available on object construction before flush (SQLAlchemy server_default only applies at DB INSERT time)"
  - "Tests use mock-based approach (AsyncMock) since live DB is unavailable in this environment — consistent with existing test patterns in the codebase"
  - "cleanup_old_notifications added to static beat_schedule (not redbeat) since it has no user-configurable schedule"

patterns-established:
  - "notify() helper: always db.flush() inside, caller commits — allows batching multiple notifications in one transaction"
  - "Celery Beat: static nightly tasks go in celery_app.conf.beat_schedule; dynamic user-configured tasks use redbeat"

requirements-completed: [NOTIF-02]

# Metrics
duration: 4min
completed: 2026-04-08
---

# Phase 17 Plan 01: Notification Foundation Summary

**SQLAlchemy Notification model (D-03 fields + 3 indexes), Alembic migration 0042, notify() helper (D-01 signature), nightly cleanup Celery task wired into Beat at 03:00**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-08T12:46:30Z
- **Completed:** 2026-04-08T12:50:53Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Notification model with all D-03 fields: id (UUID PK), user_id (FK→users), kind (varchar 64), title (varchar 200), body (text), link_url (varchar 500), site_id (FK→sites nullable), severity (varchar 16), is_read (bool), created_at (timestamptz)
- Alembic migration 0042 with 3 indexes: (user_id, is_read), (user_id, created_at DESC), (site_id)
- notify() helper matching D-01 signature exactly — flush-only, caller commits
- cleanup_old_notifications task + beat_schedule entry 'notifications-cleanup-nightly' at crontab(hour=3)
- 8 passing unit tests (4 for notify(), 4 for cleanup task + beat registration)

## Task Commits

Each task was committed atomically:

1. **Task 1: Notification model + Alembic migration** - `91c525c` (feat)
2. **Task 2: notify() helper, cleanup task, Celery Beat schedule, tests** - `8213e6c` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks executed as RED→GREEN cycle with mock-based tests_

## Files Created/Modified
- `app/models/notification.py` - Notification SQLAlchemy model with D-03 fields, __init__ override for Python-side defaults
- `alembic/versions/0042_notifications.py` - DDL migration: create_table('notifications') + 3 indexes, downgrade: drop_table
- `app/services/notifications.py` - notify() async helper (D-01 signature), flush-only pattern
- `app/tasks/notification_tasks.py` - cleanup_old_notifications Celery task, DELETE WHERE created_at < NOW() - 30 days
- `app/celery_app.py` - Added notification_tasks include, beat_schedule entry, crontab import
- `app/models/__init__.py` - Registered Notification model
- `tests/services/test_notifications.py` - 4 tests: insert row, site_id FK, severity=error, severity=warning
- `tests/tasks/test_notification_cleanup.py` - 4 tests: DELETE SQL check, count accuracy, zero rows, beat registration

## Decisions Made
- Used `__init__` override with `kwargs.setdefault()` in Notification model to make `is_read=False` and `severity='info'` available on construction before DB flush — SQLAlchemy's `server_default` only applies at INSERT time, not on Python object creation
- Used `server_default` in migration (not Python `default=`) so DB has proper DDL defaults for direct SQL inserts
- Tests are fully mock-based (AsyncMock for DB session) since the live PostgreSQL is not accessible in the CI/dev environment here — pattern is consistent with existing codebase tests like test_suggest_tasks.py
- Static `beat_schedule` in celery_app.conf.update() for the nightly cleanup (fixed schedule, not user-configurable); dynamic user schedules continue to use redbeat

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python-side model defaults not set before flush**
- **Found during:** Task 1 (TDD RED phase revealed is_read=None on construction)
- **Issue:** SQLAlchemy `default=False` on `mapped_column` only sets the INSERT SQL default — newly-constructed ORM objects have `None` for is_read and severity until flushed to DB
- **Fix:** Added `__init__` override with `kwargs.setdefault()` for `is_read` and `severity`; changed column to `server_default` in both model and migration for DB-side correctness
- **Files modified:** app/models/notification.py, alembic/versions/0042_notifications.py
- **Verification:** test_notify_inserts_row asserts `n.is_read is False` without a DB connection — passes
- **Committed in:** 91c525c (Task 1 commit)

**2. [Rule 1 - Bug] Patch target for AsyncSessionLocal was module-local lazy import**
- **Found during:** Task 2 (test for cleanup task failed with AttributeError on patch target)
- **Issue:** `AsyncSessionLocal` is imported inside `_cleanup()` function body, so patching `app.tasks.notification_tasks.AsyncSessionLocal` fails — it doesn't exist at module level
- **Fix:** Changed patch target to `app.database.AsyncSessionLocal` (the canonical location)
- **Files modified:** tests/tasks/test_notification_cleanup.py
- **Verification:** All 4 cleanup tests pass with corrected patch path
- **Committed in:** 8213e6c (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
- `alembic upgrade head` not executable in this environment (no DB connection from container host) — migration was verified syntactically and by model import. Will apply cleanly when running inside Docker Compose context.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 02 can import `from app.models.notification import Notification` and `from app.services.notifications import notify` — both importable and tested
- Plan 03 (Celery task wiring) can call `await notify(db, user_id=..., kind=...)` following D-02 guard pattern documented in app/services/notifications.py docstring
- Migration 0042 must be applied via `alembic upgrade head` inside the running Docker Compose stack before plan 02 routes are tested

---
*Phase: 17-in-app-notifications*
*Completed: 2026-04-08*
