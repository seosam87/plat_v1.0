---
phase: 17-in-app-notifications
plan: 03
subsystem: notifications
tags: [celery, notifications, python, async, sqlalchemy]

# Dependency graph
requires:
  - phase: 17-in-app-notifications
    plan: 01
    provides: notify() async helper in app/services/notifications.py (D-01 signature)
provides:
  - notify() wiring in 6 Celery task files (crawl, position, client_report, audit, suggest, llm)
  - D-02 guard pattern: user_id-present fires notify(), absent logs debug skip
  - Real in-app notifications for LLM brief events (only file with user_id in scope today)
  - change_monitoring_service.py debug skip + TODO(Phase 18) for future user scoping
  - 8 integration tests pinning D-02 skip behaviour and LLM happy/failure paths
affects:
  - 17-02 (bell UI feed — will see llm_brief.ready/failed events immediately)
  - Phase 18+ (plumbing user_id into crawl/position/audit/suggest/client_report task signatures)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-02 notify guard: if user_id is not None: await notify(...) else: logger.debug('no user scope...')"
    - "Sync Celery tasks use asyncio.run() + AsyncSessionLocal() to call async notify()"
    - "LLM task calls notify() directly in async _run_enhance since session is already available"
    - "sys.modules mock for anthropic in tests (package not installed in test env)"

key-files:
  created:
    - tests/tasks/test_notify_wiring.py
  modified:
    - app/tasks/crawl_tasks.py
    - app/tasks/position_tasks.py
    - app/tasks/client_report_tasks.py
    - app/tasks/audit_tasks.py
    - app/tasks/suggest_tasks.py
    - app/tasks/llm_tasks.py
    - app/services/change_monitoring_service.py

key-decisions:
  - "Only llm_tasks.py fires real notify() calls today — it loads user from DB, all other tasks lack user_id in their signatures"
  - "Sync tasks (crawl, position, suggest) embed asyncio.run() + AsyncSessionLocal wrapper inside if user_id is not None: block — dead code today, ready for future wiring"
  - "client_report_tasks.py uses existing async _run() context so await notify() is used directly in the if block"
  - "audit_tasks.py uses loop.run_until_complete() since the event loop is already open in run_site_audit"
  - "Test for anthropic module uses sys.modules.setdefault() mock since anthropic package is not installed in test env"
  - "change_monitoring_service.py gets TODO(Phase 18) comment referencing ChangeAlertRule.owner_id for future per-user monitoring alerts"

patterns-established:
  - "notify() wiring guard: _user_id = None; if _user_id is not None: [async notify call]; else: logger.debug('no user scope...')"

requirements-completed: [NOTIF-02]

# Metrics
duration: 12min
completed: 2026-04-08
---

# Phase 17 Plan 03: Notify() Wiring Summary

**notify() import + D-02 guard pattern wired into 6 Celery task files and monitoring dispatcher; LLM brief is the only task with live user_id scope, firing real llm_brief.ready / llm_brief.failed notifications; all other tasks scaffold the guard ready for future user_id plumbing**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-08T12:53:37Z
- **Completed:** 2026-04-08T13:05:16Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 8

## Accomplishments
- 7 files import `notify` (6 task files + change_monitoring_service.py)
- 15 total `notify(` call sites in the 6 task files (happy path + exception handlers per file)
- llm_tasks.py fires real `await notify()` calls using `user.id` loaded from DB — `kind=llm_brief.ready` (success) and `kind=llm_brief.failed` (permanent Anthropic errors)
- All 5 other task files implement the D-02 guard pattern with `_user_id = None` sentinel — calls silently skip at runtime, code is ready when callers plumb user_id through
- `change_monitoring_service.py::dispatch_immediate_alerts()` logs debug skip with `TODO(Phase 18)` comment for ChangeAlertRule.owner_id path
- `app/tasks/report_tasks.py` untouched (Beat-scheduled digests, explicitly out of scope)
- `app/models/site.py` untouched — owner_id was NOT added (per D-02 scope constraint)
- 8 passing integration tests: 2 LLM happy/fail, 5 D-02 skip, 1 monitoring dispatcher skip

## Task Commits

Each task was committed atomically (TDD cycle):

1. **Task 1 (RED): test_notify_wiring.py — failing tests** - `94b168a` (test)
2. **Task 1 (GREEN): 7-file implementation** - `a7c2b6c` (feat)

**Plan metadata:** (docs commit follows)

_Note: Task 1 and Task 2 from plan treated as RED→GREEN TDD cycle. Tests and implementation committed separately._

## Files Created/Modified
- `tests/tasks/test_notify_wiring.py` - 8 integration tests: LLM happy-path, LLM failure-path, 5 skip-on-no-scope tests (crawl/position/audit/suggest/client_pdf), monitoring dispatcher skip
- `app/tasks/crawl_tasks.py` - import notify; D-02 guard in happy-path + SoftTimeLimitExceeded + Exception handlers (3 notify() sites)
- `app/tasks/position_tasks.py` - import notify; D-02 guard in check_positions happy-path; _send_drop_alerts debug skip + TODO(Phase 18)
- `app/tasks/client_report_tasks.py` - import notify; D-02 guard in _run() async context for both ready and failed paths
- `app/tasks/audit_tasks.py` - import notify; D-02 guard in run_site_audit happy-path and exception handler
- `app/tasks/suggest_tasks.py` - import notify; D-02 guard at end of fetch_suggest_keywords
- `app/tasks/llm_tasks.py` - import notify; REAL await notify() in _run_enhance (success) and _mark_failed (failure); user_id from loaded user object
- `app/services/change_monitoring_service.py` - import notify; debug skip + TODO(Phase 18) in dispatch_immediate_alerts()

## Decisions Made
- Only llm_tasks.py has live user_id scope (loads User from DB) — all other tasks get D-02 guard with `_user_id = None` sentinel
- For sync tasks (crawl, position, suggest): asyncio.run() wrapper inside `if user_id is not None:` block — dead code today, ready for activation
- For async tasks (client_report): `await notify()` directly inside `_run()` async function, inside `if user_id is not None:` block
- audit_tasks.py reuses the already-open event loop via `loop.run_until_complete()` to avoid nested asyncio.run() issues
- anthropic module mocked at `sys.modules` level in test file since package is not installed in the test environment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] anthropic module not installed in test environment**
- **Found during:** Task 2 RED phase (first test run failed with ModuleNotFoundError)
- **Issue:** `app/tasks/llm_tasks._run_enhance` imports from `anthropic` inside function body; `ModuleNotFoundError: No module named 'anthropic'` raised at test collection time when the anthropic import executes
- **Fix:** Added `sys.modules.setdefault("anthropic", _ANTHROPIC_MOCK)` at module level in test file, building a minimal mock with the exact exception classes llm_tasks checks for (`AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, `APIConnectionError`, `APITimeoutError`, `RateLimitError`, `APIStatusError`)
- **Files modified:** tests/tasks/test_notify_wiring.py
- **Verification:** All 8 tests pass with mock in place
- **Committed in:** 94b168a (test commit), then a7c2b6c (feat commit)

**2. [Rule 1 - Bug] patch targets for monitoring dispatcher test used wrong module path**
- **Found during:** Task 2 (test_monitoring_dispatch_skips_inapp failed with AttributeError)
- **Issue:** `send_message_sync` and `format_change_alert` are imported inside `dispatch_immediate_alerts()` function body, not at module level in change_monitoring_service.py — patching `app.services.change_monitoring_service.send_message_sync` raised AttributeError
- **Fix:** Changed patch targets to `app.services.telegram_service.send_message_sync` and `app.services.telegram_service.format_change_alert` (the canonical locations of these functions)
- **Files modified:** tests/tasks/test_notify_wiring.py
- **Verification:** test_monitoring_dispatch_skips_inapp passes, Telegram assert works correctly
- **Committed in:** a7c2b6c (feat commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both auto-fixes necessary for test correctness. No scope creep.

## Issues Encountered
- `asyncio.run()` cannot be called inside an already-running event loop — audit_tasks.py uses `loop.run_until_complete()` to reuse the open loop instead of `asyncio.run()`
- The `generate_client_pdf` task wraps everything in `asyncio.run(_run())` — the notify() guard was placed inside `_run()` where the async `AsyncSessionLocal` context is already available

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 17-02 (bell UI) can display `llm_brief.ready` and `llm_brief.failed` events immediately
- When future phases add `user_id` to crawl/position/audit/suggest/client_report task signatures, the notify() calls will automatically fire (remove the `_user_id = None` sentinel and pass the real user_id)
- Monitoring alerts (change_monitoring_service) require Phase 18 CRM work to add `ChangeAlertRule.owner_id` before they can emit in-app notifications

## Known Stubs
- `_user_id = None` sentinels in 5 task files (crawl, position, client_report, audit, suggest) — intentional D-02 stub, tracks that user_id is not yet plumbed into these task signatures. Will activate when callers are updated in post-Phase 17 work.

---
*Phase: 17-in-app-notifications*
*Completed: 2026-04-08*
