---
phase: v3-03
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, postgresql, change-monitoring, enums]

# Dependency graph
requires:
  - phase: v3-02-content-audit
    provides: content audit models and migration 0021 (down_revision)
provides:
  - ChangeType enum (9 values)
  - AlertSeverity enum (error/warning/info)
  - ChangeAlertRule model (global, unique per change_type)
  - ChangeAlert model (alert history per site + crawl job)
  - DigestSchedule model (per-site weekly digest schedule)
  - Alembic migration 0022 with 9 seeded default alert rules
affects: [v3-03-02, v3-03-03, v3-03-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SAEnum with native_enum=False (VARCHAR storage) to avoid PG enum DDL lock-in
    - Global config table pattern: ChangeAlertRule has no site_id (global rules only)
    - Per-site schedule pattern: DigestSchedule unique on site_id, day/hour/minute fields for redbeat cron

key-files:
  created:
    - app/models/change_monitoring.py
    - alembic/versions/0022_add_change_monitoring_tables.py
    - tests/test_change_monitoring_models.py
  modified: []

key-decisions:
  - "ChangeAlertRule is global (no site_id): same rules apply to all sites, severity configurable globally"
  - "9 default rules seeded in migration: page_404/noindex_added/schema_removed=error, title/h1/canonical/meta=warning, content/new_page=info"
  - "DigestSchedule stores day_of_week + hour + minute separately for UI display; cron_expression is derived field for redbeat"

patterns-established:
  - "Global config pattern: rule tables without site_id for platform-wide settings (AlertRule is global, DigestSchedule is per-site)"
  - "Change alert history: ChangeAlert records both detection (created_at) and delivery (sent_at nullable)"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-03
---

# Phase v3-03 Plan 01: Models, migration, and seed data for change monitoring

**SQLAlchemy models for change monitoring with ChangeType/AlertSeverity enums, alert rules/history/digest tables, and Alembic migration 0022 seeding 9 default rules**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T07:01:03Z
- **Completed:** 2026-04-03T07:06:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Three SQLAlchemy models: ChangeAlertRule (global), ChangeAlert (history), DigestSchedule (per-site)
- Alembic migration 0022 (down_revision=0021) with two enums and three tables plus 9 seeded default rules
- 5 unit tests covering all enum values and model instantiation

## Task Commits

Each task was committed atomically:

1. **Task 01: Create change_monitoring.py with three models** - `df86ce0` (feat)
2. **Task 02: Create Alembic migration 0022** - `df86ce0` (feat, combined with task 01)
3. **Task 03: Unit tests for change monitoring models** - `df86ce0` (feat, combined)

## Files Created/Modified

- `app/models/change_monitoring.py` - ChangeType, AlertSeverity enums; ChangeAlertRule, ChangeAlert, DigestSchedule models
- `alembic/versions/0022_add_change_monitoring_tables.py` - Migration creating all 3 tables with enums and 9 seeded rules
- `tests/test_change_monitoring_models.py` - 5 unit tests for enums and model fields

## Decisions Made

- ChangeAlertRule uses `native_enum=False` (VARCHAR storage) consistent with Phase 06.1 ProxyType/ProxyStatus pattern — avoids PG enum DDL lock-in
- ChangeAlert.sent_at is nullable (null = detected but not yet dispatched); created_at records detection time
- DigestSchedule.day_of_week uses integer 1-7 (Monday=1, Sunday=7) for compatibility with Python's isoweekday()

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

All created files exist. Commit df86ce0 verified.

## Next Phase Readiness

- Data layer complete; Plan 02 (change detection service) can wire against these models
- ChangeAlertRule seed data available immediately after migration 0022 runs
- DigestSchedule model ready for redbeat integration in Plan 03

---
*Phase: v3-03-change-monitoring*
*Completed: 2026-04-03*
