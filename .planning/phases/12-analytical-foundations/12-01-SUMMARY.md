---
phase: 12-analytical-foundations
plan: 01
subsystem: database
tags: [url-normalization, postgresql, sqlalchemy, alembic, celery, position-tracking, analytics]

# Dependency graph
requires: []
provides:
  - normalize_url() utility in app/utils/url_normalize.py — strips UTM, normalizes http/https/slash/fragment
  - KeywordLatestPosition SQLAlchemy model with uq_klp_keyword_engine unique constraint
  - Alembic migration 0037 creating keyword_latest_positions table with ix_klp_site_position index
  - refresh_latest_positions() in position_service.py — UPSERT via INSERT ON CONFLICT
  - Auto-refresh triggered at end of write_positions_batch()
affects:
  - 12-02-quick-wins-dead-content
  - 12-03-error-impact-growth-opportunities
  - Any plan that JOINs pages / metrika_traffic_pages / keyword_positions

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "URL normalization: normalize_url() as single entry point before all cross-table JOINs"
    - "Flat cache table pattern: keyword_latest_positions refreshed via UPSERT after every batch write"
    - "INSERT ... ON CONFLICT DO UPDATE for idempotent refresh (no DELETE + re-INSERT)"

key-files:
  created:
    - app/utils/__init__.py
    - app/utils/url_normalize.py
    - app/models/keyword_latest_position.py
    - alembic/versions/0037_add_keyword_latest_positions.py
    - tests/test_url_normalize.py
    - tests/test_keyword_latest_positions.py
  modified:
    - app/models/__init__.py
    - app/services/position_service.py

key-decisions:
  - "normalize_url() uses stdlib only (urllib.parse) — no external dependency needed"
  - "http->https upgrade is unconditional — all production sites use HTTPS; matching against http URLs is always a normalization artifact"
  - "Non-UTM query params preserved and sorted alphabetically for deterministic output"
  - "keyword_latest_positions uses INSERT ON CONFLICT (not DELETE+INSERT) for atomicity and performance"
  - "refresh_latest_positions() scoped to site_id to avoid cross-site data contamination and enable parallelism"
  - "DB integration tests included but require Docker stack (postgres hostname); structural tests run without DB"

patterns-established:
  - "normalize_url pattern: import from app.utils.url_normalize, call before JOIN between pages/metrika/positions"
  - "Flat-table refresh pattern: call refresh_latest_positions(db, site_id) after any bulk position write"

requirements-completed: [INFRA-V2-01, INFRA-V2-02]

# Metrics
duration: 25min
completed: 2026-04-06
---

# Phase 12 Plan 01: Analytical Foundations Summary

**normalize_url() stdlib utility + keyword_latest_positions flat cache table replacing DISTINCT ON partition scans at 100K keywords**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-06T13:20:00Z
- **Completed:** 2026-04-06T13:45:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Implemented `normalize_url()` with 8 normalization rules: http→https, UTM stripping, trailing slash, fragment removal, scheme/host lowercasing, file extension detection, None/empty passthrough, non-UTM param preservation
- Created `KeywordLatestPosition` model with `uq_klp_keyword_engine` unique constraint and `ix_klp_site_position` index for Quick Wins range queries
- Added `refresh_latest_positions()` using `INSERT ... ON CONFLICT DO UPDATE` — single SQL statement, idempotent, scoped to site_id
- Wired refresh call into `write_positions_batch()` so every position check batch automatically updates the flat cache
- 14 pure-function tests for normalize_url, 7 tests for keyword_latest_positions (3 structural + 4 DB integration)

## Task Commits

1. **Task 1: normalize_url utility with tests** — `9741157` (feat)
2. **Task 2: keyword_latest_positions table, model, migration, position_service integration** — `6375181` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `app/utils/__init__.py` — Module init for app.utils package
- `app/utils/url_normalize.py` — normalize_url() function, stdlib only
- `app/models/keyword_latest_position.py` — KeywordLatestPosition SQLAlchemy model
- `app/models/__init__.py` — Registers KeywordLatestPosition import
- `alembic/versions/0037_add_keyword_latest_positions.py` — Migration: CREATE TABLE + indexes, depends_on 0036
- `app/services/position_service.py` — Added refresh_latest_positions(); wired into write_positions_batch()
- `tests/test_url_normalize.py` — 14 test cases for normalize_url
- `tests/test_keyword_latest_positions.py` — 7 tests: 3 structural (no DB), 4 integration (require Docker stack)

## Decisions Made

- Used stdlib `urllib.parse` only for normalize_url — no external dependency, zero performance overhead
- http→https upgrade is unconditional: production sites always use HTTPS, any http URL in data is a normalization artifact
- Non-UTM params sorted alphabetically for deterministic output, enabling string equality comparisons downstream
- `INSERT ON CONFLICT DO UPDATE` chosen over DELETE+INSERT: atomic, no gap in cache visibility, PostgreSQL-native
- `refresh_latest_positions()` scoped to `site_id` to enable safe parallelism (multiple sites can refresh concurrently)
- DB integration tests designed for Docker stack execution; 3 structural tests verified locally without DB

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- DB integration tests cannot run without the Docker Compose stack (postgres hostname not resolvable outside containers). This is the standard pattern across all existing tests in this codebase — structural/unit tests run locally, integration tests require `docker compose up`. The 3 structural tests and all 14 normalize_url tests pass locally.

## User Setup Required

None — no external service configuration required. Run `alembic upgrade 0037` to apply the migration when deploying.

## Next Phase Readiness

- `normalize_url()` is ready for import in Phase 12 analytical queries
- `keyword_latest_positions` table + refresh pipeline are ready; migration 0037 must be applied before Phase 12 analytical queries can use the flat table
- Phase 12 Plan 02 (Quick Wins + Dead Content) can now use `SELECT FROM keyword_latest_positions` instead of DISTINCT ON scans

---
*Phase: 12-analytical-foundations*
*Completed: 2026-04-06*
