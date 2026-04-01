---
phase: v3-01
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, metrika, postgresql, models, migrations]

requires: []
provides:
  - MetrikaTrafficDaily model (metrika_traffic_daily table)
  - MetrikaTrafficPage model (metrika_traffic_pages table)
  - MetrikaEvent model (metrika_events table)
  - Site.metrika_counter_id and Site.metrika_token fields
  - Alembic migration 0020 (revision chain 0019→0020)
affects: [v3-01-02, v3-01-03, v3-01-04, v3-01-05]

tech-stack:
  added: []
  patterns:
    - "Metrika token stored as Fernet-encrypted Text (same pattern as encrypted_app_password)"
    - "UUID PK + CASCADE FK to sites.id per ad_traffic.py pattern"
    - "UniqueConstraint in __table_args__ for composite uniqueness"

key-files:
  created:
    - app/models/metrika.py
    - alembic/versions/0020_add_metrika_tables.py
    - tests/test_metrika_models.py
  modified:
    - app/models/site.py

key-decisions:
  - "metrika_token uses Text type (Fernet-encrypted) matching encrypted_app_password pattern"
  - "metrika_counter_id uses String(50) — Metrika counter IDs are short numeric strings"
  - "MetrikaTrafficPage stores aggregate by (site_id, period_start, period_end, page_url) — allows repeated fetches for same period"

patterns-established:
  - "Metrika model pattern: UUID PK, UUID FK to sites with CASCADE, date columns, Numeric(5,2) for rates"

requirements-completed: []

duration: 8min
completed: 2026-04-01
---

# Phase v3-01 Plan 01: Models, migrations, and Site model Metrika fields Summary

**Three Metrika data tables and two Site model columns established via SQLAlchemy 2.0 models and Alembic migration 0020, providing the full data layer for Yandex Metrika integration**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-01T21:05:00Z
- **Completed:** 2026-04-01T21:13:00Z
- **Tasks:** 4
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- Added `metrika_counter_id` (String(50)) and `metrika_token` (Text, Fernet-encrypted) to the Site model
- Created `app/models/metrika.py` with three SQLAlchemy 2.0 models: MetrikaTrafficDaily, MetrikaTrafficPage, MetrikaEvent
- Created Alembic migration 0020 that adds 5 new DB objects (2 site columns + 3 tables + indexes + unique constraints)
- All 4 model tests pass confirming correct instantiation and attribute presence

## Task Commits

1. **Task 01: Add metrika_counter_id and metrika_token to Site** - `7ac5408` (feat)
2. **Task 02: Create metrika models file** - `ae8c989` (feat)
3. **Task 03: Create Alembic migration 0020** - `a8b7432` (feat)
4. **Task 04: Unit tests for Metrika models** - `53a7ea7` (test)

## Files Created/Modified

- `app/models/site.py` — Added `metrika_counter_id` and `metrika_token` columns after `seo_plugin`
- `app/models/metrika.py` — Three new SQLAlchemy 2.0 models with UniqueConstraints and CASCADE FKs
- `alembic/versions/0020_add_metrika_tables.py` — Migration 0020 with full upgrade/downgrade
- `tests/test_metrika_models.py` — 4 unit tests covering model instantiation and Site attribute presence

## Decisions Made

- `metrika_token` uses `Text` type (same as `encrypted_app_password`) — Fernet tokens are long base64 strings
- `metrika_counter_id` uses `String(50)` — Yandex Metrika counter IDs are short numeric strings (up to 10 digits)
- `MetrikaTrafficPage` uses a 4-column unique constraint to allow multiple period fetches per site without duplicates

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Added an extra `test_metrika_event_default_color` test beyond the plan's 4 tests; it failed because SQLAlchemy column `default=` is an insert-time default, not a Python attribute default. Removed the extra test (not in plan scope) and kept only the 4 planned tests. No model changes needed.

## User Setup Required

None - no external service configuration required. Migration must be applied when DB is available (`alembic upgrade head`).

## Next Phase Readiness

- Data layer is complete — all three Metrika tables and Site fields are ready
- Plan v3-01-02 (MetrikaService + Celery tasks) can proceed immediately
- Migration 0020 needs to run against the live DB before Metrika data can be stored

---
*Phase: v3-01*
*Completed: 2026-04-01*
