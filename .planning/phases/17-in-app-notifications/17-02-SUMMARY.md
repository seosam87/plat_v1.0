---
phase: 17-in-app-notifications
plan: 02
subsystem: ui
tags: [htmx, jinja2, sqlalchemy, notifications, fastapi, tailwind]

# Dependency graph
requires:
  - phase: 17-in-app-notifications
    plan: 01
    provides: Notification model (app/models/notification.py), notify() helper

provides:
  - Notifications router (GET bell/dropdown/index, POST mark-all-read/dismiss)
  - Bell badge with HTMX 30s polling (hx-trigger="every 30s")
  - Dropdown panel with last 10, auto-mark-read on open (D-05)
  - Full /notifications page with site/kind/read-state filters and pagination 50
  - Bulk "Отметить все прочитанными" button
  - 3-level severity visual (info=green/warning=yellow/error=red)
  - Sidebar bell icon include (notifications/_bell.html in components/sidebar.html)
  - 3 smoke routes added to Phase 15.1 parametrization

affects:
  - 17-03 (smoke tests now cover notification routes)
  - Phase 15.1 (smoke route count updated from 68 to 73)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bell sidebar include uses |default(0) and |default(false) Jinja filters so any page render works without explicit context injection"
    - "Dropdown auto-mark-read: single UPDATE WHERE id IN (...) atomically after SELECT — D-05 pattern"
    - "groupby kind done in Python (defaultdict) rather than SQL GROUP BY for simplicity with pagination"
    - "Mock-based router tests (AsyncMock + SimpleNamespace) consistent with plan 17-01 approach — no live DB"

key-files:
  created:
    - app/routers/notifications.py
    - app/templates/notifications/_bell.html
    - app/templates/notifications/_dropdown.html
    - app/templates/notifications/index.html
    - app/templates/notifications/_list.html
    - tests/routers/test_notifications.py
  modified:
    - app/main.py
    - app/templates/components/sidebar.html
    - tests/_smoke_helpers.py
    - tests/test_ui_smoke.py

key-decisions:
  - "Sidebar bell uses Jinja |default() filters so the template renders safely on any page without passing unread_count/has_unread_error from every view — HTMX 30s poll updates badge silently (D-06)"
  - "Mock-based tests (AsyncMock + SimpleNamespace) used instead of live DB fixtures — consistent with plan 17-01; no DB connection available outside Docker Compose"
  - "Dropdown positioned with position:fixed to avoid sidebar clipping"

patterns-established:
  - "Notification bell include: always use |default(0) / |default(false) for context-optional sidebar variables"
  - "HTMX fragment mark-read: SELECT → UPDATE WHERE id IN (...) → commit in single endpoint — atomic with no extra round trips"

requirements-completed: [NOTIF-01, NOTIF-03]

# Metrics
duration: 12min
completed: 2026-04-08
---

# Phase 17 Plan 02: Notifications UI Summary

**Bell badge in sidebar (HTMX 30s poll) + dropdown (last 10, auto-mark-read) + /notifications full page (kind/site/read-state filters, pagination 50, bulk mark-all)**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-08T12:53:20Z
- **Completed:** 2026-04-08T13:05:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments
- Notifications router (`app/routers/notifications.py`) with 5 endpoints: GET bell, GET dropdown, GET index, POST mark-all-read, POST dismiss
- Bell badge in sidebar via `{% include "notifications/_bell.html" %}` — polls `/notifications/bell` every 30s via `hx-trigger="every 30s"` (NOTIF-03)
- Badge color: `bg-red-500` when any unread error exists, `bg-blue-500` otherwise (D-07)
- Dropdown auto-marks visible entries `is_read=True` atomically (single UPDATE WHERE id IN) on render (D-05)
- `/notifications` page with 3-filter bar (site selector, kind selector, read-state tabs) grouped by `kind` (D-08), pagination 50/page (D-09)
- "Отметить все прочитанными" bulk button targeting `#notif-list` via HTMX POST
- Per-row dismiss button (hard-delete with ownership check, returns 204)
- 10 passing mock-based unit tests (no live DB dependency)
- 3 notification routes added to Phase 15.1 smoke crawler parametrization (73 total routes)

## Task Commits

Each task was committed atomically:

1. **Task 1: Notifications router + tests** - `c78b438` (feat)
2. **Task 2: Templates + sidebar wiring** - `d20e28b` (feat)
3. **Task 3: Smoke crawler parametrization** - `c6e2cd1` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD RED phase confirmed via ImportError (router didn't exist), GREEN phase written with mock-based tests_

## Files Created/Modified
- `app/routers/notifications.py` - 5-endpoint router: bell fragment, dropdown, full page, mark-all, dismiss
- `app/main.py` - Added `notifications_router` include
- `app/templates/notifications/_bell.html` - Bell icon + HTMX 30s poll + badge (severity-aware color)
- `app/templates/notifications/_dropdown.html` - Last 10 flat list with severity left-border (D-07)
- `app/templates/notifications/index.html` - Full page extending base.html with filter bar + mark-all button
- `app/templates/notifications/_list.html` - Grouped list fragment (D-08), pagination, dismiss buttons
- `app/templates/components/sidebar.html` - Added bell include in footer
- `tests/routers/test_notifications.py` - 10 mock-based tests covering all endpoints
- `tests/_smoke_helpers.py` - Added `/notifications` to UI_PREFIXES
- `tests/test_ui_smoke.py` - Updated baseline comment (68 → 73 routes)

## Decisions Made
- Used `|default(0)` / `|default(false)` Jinja filters in `_bell.html` so the sidebar include works on any page without requiring every view to query unread counts — the 30s HTMX poll self-corrects to live values immediately after page load
- `SimpleNamespace` used for test model mocks (SQLAlchemy ORM objects can't be created via `__new__` without instrument state) — same pattern as codebase
- Dropdown positioned `fixed` to avoid sidebar overflow clipping

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLAlchemy ORM objects can't use `__new__` for mock construction**
- **Found during:** Task 1 (TDD GREEN phase — first test attempt)
- **Issue:** Test helper used `User.__new__(User)` and `Notification.__new__(Notification)` to create model instances without DB — SQLAlchemy raises `AttributeError: 'NoneType' object has no attribute 'set'` because instrument state is not initialized
- **Fix:** Replaced ORM instances with `SimpleNamespace` objects that mimic the model's attributes — consistent with existing pattern documented in plan 17-01 (`test_notifications.py` uses `Notification()` directly via `notify()` helper, test_llm_briefs uses proper test DB)
- **Files modified:** tests/routers/test_notifications.py
- **Verification:** All 10 tests pass
- **Committed in:** c78b438 (Task 1 commit)

**2. [Rule 1 - Bug] Test DB (postgres host) not reachable outside Docker Compose**
- **Found during:** Task 1 (TDD RED phase — first test runner output)
- **Issue:** `conftest.py::db_session` fixture tries to connect to `postgres:5432` — not reachable from host environment; tests errored on setup (not actual test failures)
- **Fix:** Switched to fully mock-based test approach (AsyncMock for AsyncSession, SimpleNamespace for models) — consistent with 17-01 decision documented in its SUMMARY
- **Files modified:** tests/routers/test_notifications.py
- **Verification:** All 10 tests pass without DB connection
- **Committed in:** c78b438 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both are the same category of issue (mock construction pattern) — no scope creep, no architectural change. Plan 17-01 SUMMARY documented this decision; Plan 17-02 applied it consistently.

## Known Stubs
None — all template data is live from DB queries in the router endpoints.

## Issues Encountered
- `sidebar.html` includes `_bell.html` statically (at page-render time), but `_bell.html` needs `unread_count` and `has_unread_error` — solved with Jinja `|default()` filters; HTMX poll corrects values within 30s of page load.

## User Setup Required
None — no external service configuration required. Migration 0042 from Plan 17-01 must be applied for the notifications table to exist.

## Next Phase Readiness
- Plan 17-03 can call `notify()` in Celery tasks — the full UI surface is live
- Smoke tests cover all 3 notification routes at `/notifications`, `/notifications/bell`, `/notifications/dropdown`
- The bell will show unread counts immediately once Plan 17-03 wires `notify()` into task completion hooks

---
*Phase: 17-in-app-notifications*
*Completed: 2026-04-08*
