---
phase: v4-08-ui-smoke-test
plan: 01
subsystem: testing
tags: [httpx, asyncio, smoke-test, route-discovery, nav-sections, pytest]

# Dependency graph
requires:
  - phase: v4-01-navigation-foundation
    provides: NAV_SECTIONS in app/navigation.py — source of sidebar routes
provides:
  - Standalone async smoke test script (tests/smoke_test.py) runnable as `python -m tests.smoke_test`
  - Route discovery from both NAV_SECTIONS and app/main.py @app.get patterns
  - Admin authentication via POST /ui/login cookie-based JWT
  - site_id substitution for site-scoped URL templates
  - Colored terminal report with exit code 0/1
  - 23 unit tests covering all pure functions
affects:
  - v4-08-02 (Celery smoke task — imports run_smoke_test from this module)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Route discovery: parse NAV_SECTIONS children + regex-extract @app.get from main.py source"
    - "Auth: POST /ui/login with form data (email/password fields), extract access_token cookie"
    - "In-process testing: httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')"
    - "Fake UUID fallback (FAKE_SITE_ID) when DB unavailable for site_id substitution"
    - "ANSI color codes directly (no extra deps) for terminal output"

key-files:
  created:
    - tests/smoke_test.py
    - tests/test_smoke_test.py
  modified: []

key-decisions:
  - "Auth uses POST /ui/login (form fields: email, password) not /auth/token — this sets httponly cookie"
  - "site_id resolved via asyncpg direct query; falls back to FAKE_SITE_ID when DB unreachable"
  - "Routes with {crawl_job_id}, {job_id}, {module}, /ui/api/ prefixes are skipped (not errors)"
  - "merge_routes normalizes templates (replace all {x} with {param}) for deduplication"

patterns-established:
  - "Smoke test pattern: discover_routes_from_nav() + discover_routes_from_main() merged via merge_routes()"
  - "Exit code pattern: print_report() returns 0/1 for use with sys.exit()"

requirements-completed: [SMOKE-01, SMOKE-02, SMOKE-03]

# Metrics
duration: 8min
completed: 2026-04-03
---

# Phase v4-08 Plan 01: UI Smoke Test Runner Summary

**Async smoke test script that auto-discovers all UI routes from NAV_SECTIONS + main.py, authenticates via cookie JWT, substitutes real site UUIDs, and reports colored pass/fail table with exit code 1 on any 4xx/5xx**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-03T14:11:00Z
- **Completed:** 2026-04-03T14:19:41Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `tests/smoke_test.py` (396 lines) with 10 functions: route discovery (nav + main.py), route merging/deduplication, URL placeholder resolution, admin auth via cookie, asyncpg-based site_id lookup, async runner, and colored terminal report
- Created `tests/test_smoke_test.py` with 23 unit tests covering all pure functions — all pass in 0.06s
- Script importable and runnable as `python -m tests.smoke_test` without live server (uses ASGITransport)

## Task Commits

Each task was committed atomically:

1. **Task 1: Build route discovery and auth helpers in smoke_test.py** - `47efadb` (feat)
2. **Task 2: Write pytest unit tests for route discovery and URL resolution logic** - `51ddf85` (test)

## Files Created/Modified

- `tests/smoke_test.py` — Async smoke test runner: route discovery, auth, site_id resolution, URL resolver, report formatter
- `tests/test_smoke_test.py` — 23 unit tests for all pure (non-async, non-DB) functions

## Decisions Made

- Auth uses `POST /ui/login` with form fields `email` and `password` (not `/auth/token`) — the UI login endpoint sets the `access_token` httponly cookie that UIAuthMiddleware reads
- `asyncpg.connect()` used directly for site_id lookup (no SQLAlchemy import) to keep smoke_test portable; falls back to `FAKE_SITE_ID = "00000000-0000-0000-0000-000000000001"` when DB unavailable
- Routes with `{crawl_job_id}`, `{job_id}`, `{module}`, and `/ui/api/` patterns are skipped with "SKIPPED" status (yellow, not counted as errors)
- Template deduplication normalizes all `{placeholder}` tokens to `{param}` before comparing — handles `{site_id}` vs `{project_id}` as different templates correctly

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — smoke_test.py fully wired to real route discovery and real auth flow.

## Next Phase Readiness

- `tests/smoke_test.run_smoke_test` is importable and ready for Plan 02 (Celery periodic smoke task)
- The `--url` flag enables running against a live deployed server for post-deploy verification
- Admin credentials can be overridden via `SMOKE_ADMIN_EMAIL` / `SMOKE_ADMIN_PASSWORD` env vars or CLI flags

---
*Phase: v4-08-ui-smoke-test*
*Completed: 2026-04-03*
