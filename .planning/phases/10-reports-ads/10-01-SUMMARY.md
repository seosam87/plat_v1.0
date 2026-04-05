---
phase: 10-reports-ads
plan: "01"
subsystem: dashboard
tags: [dashboard, redis-cache, per-project-table, performance]
dependency_graph:
  requires: []
  provides: [dashboard_service.projects_table, dashboard:projects_table cache key]
  affects: [app/main.py ui_dashboard handler, app/templates/dashboard/index.html]
tech_stack:
  added: []
  patterns: [Redis cache miss/hit pattern, single-aggregate SQL with CTE]
key_files:
  created:
    - app/services/dashboard_service.py
    - tests/test_dashboard_service.py
  modified:
    - app/config.py
    - app/main.py
    - app/templates/dashboard/index.html
key_decisions:
  - "projects_table() uses ex=CACHE_TTL (constant 300) rather than ex=300 literal — same semantics, clearer intent"
  - "ProjectStatus.archived rows filtered at SQL level to avoid stale archived projects appearing on dashboard"
  - "asyncio.gather() used for projects_table + aggregated_positions + todays_tasks — all three run in parallel"
metrics:
  duration: 203s
  completed_date: "2026-04-05"
  tasks_completed: 2
  files_modified: 5
---

# Phase 10 Plan 01: Dashboard Per-Project Table Summary

Per-project aggregation dashboard replacing N+1 site_overview loop with a single Redis-cached SQL CTE query.

## What Was Built

### Task 1: dashboard_service.py with Redis-cached per-project aggregation (commit 80c1a2e)

- Created `app/services/dashboard_service.py` with `projects_table(db)` function
- Single SQL CTE query: `latest_positions` -> `site_pos` -> project JOIN with task aggregation
- Cache key `dashboard:projects_table` with `ex=CACHE_TTL` (CACHE_TTL = 300s)
- Redis pattern replicates `overview_service._get_redis()` using `settings.REDIS_URL`
- Added `APP_URL: str = "http://localhost:8000"` to `app/config.py` for Telegram digest links (Plan 03)
- Unit tests: cache miss path, cache hit path, empty result — all 3 pass

### Task 2: Dashboard handler and template rewrite (commit 09b9997)

- `ui_dashboard` handler in `app/main.py` replaced N+1 `site_overview` loop with single `projects_table(db)` call
- Removed: `site_overview` import, `sites_overview` loop, `projects_data` ORM query
- `asyncio.gather()` now runs `projects_table`, `aggregated_positions`, `todays_tasks` in parallel
- Template `dashboard/index.html` rewritten: per-project table with columns Project/Site/TOP-3/TOP-10/TOP-30/Open/In-Progress/Status/Actions
- Status badges: emerald=active, amber=paused, gray=completed — Tailwind conditional classes
- Action buttons: Kanban link to `/ui/projects/{id}/kanban`, Report link to `/ui/reports/{id}`
- Zero inline `style=` attributes (verified: `grep -c 'style=' = 0`)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- Report link `/ui/reports/{id}` in dashboard template points to a route that will be built in Plan 02. Link is present as required by plan spec; will 404 until Plan 02 completes.

## Self-Check: PASSED

- `app/services/dashboard_service.py` — FOUND
- `tests/test_dashboard_service.py` — FOUND
- Commit 80c1a2e — FOUND
- Commit 09b9997 — FOUND
- `python -m pytest tests/test_dashboard_service.py` — 3 passed
- `grep -c 'style=' app/templates/dashboard/index.html` — 0
