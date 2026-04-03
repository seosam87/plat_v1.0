---
phase: v4-08-ui-smoke-test-agent
plan: "02"
subsystem: tasks/monitoring
tags: [celery, smoke-test, telegram, testing]
dependency_graph:
  requires:
    - v4-08-01  # tests/smoke_test.py with run_smoke_test()
  provides:
    - run_ui_smoke_test Celery task
  affects:
    - app/celery_app.py
tech_stack:
  added: []
  patterns:
    - Celery task wrapping async function via asyncio.run()
    - Module-level service imports for mock-patchability in tests
key_files:
  created:
    - app/tasks/smoke_tasks.py
    - tests/test_smoke_tasks.py
  modified:
    - app/celery_app.py
decisions:
  - Module-level imports for telegram_service (not lazy) enable clean unittest.mock patching
  - Skipped entries (skipped=True) excluded from error count — only real failures count
  - Error list capped at 20 items to respect Telegram 4096-char message limit
metrics:
  duration: "~2 min"
  completed: "2026-04-03"
  tasks_completed: 2
  files_changed: 3
---

# Phase v4-08 Plan 02: Celery Smoke Task with Telegram Reporting Summary

**One-liner:** Celery task `run_ui_smoke_test` wraps `run_smoke_test()` via `asyncio.run()`, formats pass/fail HTML for Telegram, and is registered in `celery_app.py` include list.

## What Was Built

A Celery task that can be triggered on-demand or on a schedule to run the UI smoke test and push results to Telegram without requiring SSH access.

### Files Created

**`app/tasks/smoke_tasks.py`** (75 lines)
- `run_ui_smoke_test(self, base_url=None)` task with `name="app.tasks.smoke_tasks.run_ui_smoke_test"`
- `queue="default"`, `soft_time_limit=120`, `time_limit=180`, `max_retries=1`
- Calls `asyncio.run(run_smoke_test(base_url=base_url))` to bridge async → sync
- Formats two message variants: PASSED (all OK) and FAILED (lists up to 20 failing URLs with HTTP status)
- Skips Telegram send and logs locally when `is_configured()` returns False
- On runner exception: sends Telegram error alert, retries once after 10s

**`tests/test_smoke_tasks.py`** (65 lines)
- 4 unit tests covering: task registration, success path, error path (URL+status in message), no-Telegram behavior
- Uses `unittest.mock.patch` on module-level names; calls `.run()` to bypass Celery machinery

### Files Modified

**`app/celery_app.py`**
- Added `"app.tasks.smoke_tasks"` to the `include=[...]` list after `intent_tasks`

## Verification

```
python -c "from app.tasks.smoke_tasks import run_ui_smoke_test; print(run_ui_smoke_test.name)"
# app.tasks.smoke_tasks.run_ui_smoke_test

python -m pytest tests/test_smoke_tasks.py -v
# 4 passed

python -m pytest tests/test_smoke_test.py tests/test_smoke_tasks.py -v
# 27 passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed lazy import preventing mock.patch from working**
- **Found during:** Task 2 test run
- **Issue:** `send_message_sync` and `is_configured` were imported inside the function body (lazy imports), making `patch("app.tasks.smoke_tasks.send_message_sync", ...)` raise `AttributeError` since the module had no such attribute at patch time.
- **Fix:** Moved `from app.services.telegram_service import is_configured, send_message_sync` to module-level imports.
- **Files modified:** `app/tasks/smoke_tasks.py`
- **Commit:** fbe2dc8

**2. [Rule 1 - Bug] Fixed registration test — explicit module import required**
- **Found during:** Task 2 test run (test_run_ui_smoke_test_registered)
- **Issue:** `celery_app` was already cached in `sys.modules` from a prior import without `smoke_tasks` loaded, so `celery_app.tasks` didn't include the smoke task until `smoke_tasks` was explicitly imported.
- **Fix:** Added `import app.tasks.smoke_tasks` before the assertion in `test_run_ui_smoke_test_registered`.
- **Files modified:** `tests/test_smoke_tasks.py`
- **Commit:** fbe2dc8

## Commits

| Hash | Message |
|------|---------|
| c7a187a | feat(v4-08-02): create run_ui_smoke_test Celery task with Telegram reporting |
| fbe2dc8 | feat(v4-08-02): register smoke_tasks in celery_app and add 4 unit tests |

## Known Stubs

None. The task is fully wired: smoke_test runner → Celery task → Telegram service.
