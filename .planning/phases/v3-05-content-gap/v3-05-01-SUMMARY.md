---
phase: v3-05
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, gap-analysis, content-gap, postgres]

# Dependency graph
requires:
  - phase: v3-04
    provides: content_plan_items table (FK target for GapProposal.content_plan_item_id)
provides:
  - gap_keywords table — competitor keywords not in our set
  - gap_groups table — manual grouping of gap keywords
  - gap_proposals table — content plan proposals pending approval
  - ProposalStatus enum (pending/approved/rejected)
  - Migration 0024 with upgrade/downgrade
affects:
  - v3-05-02 (gap service/routes use these models)
  - v3-05-03 (gap UI reads GapKeyword, GapProposal)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GapKeyword.source string field (not enum) supports 'serp', 'csv_import', 'xlsx_import' for future extensibility"
    - "ProposalStatus as Python str enum + SAEnum for PG native enum"
    - "UniqueConstraint on (site_id, competitor_domain, phrase) prevents duplicate gap keywords"

key-files:
  created:
    - app/models/gap.py
    - alembic/versions/0024_add_content_gap_tables.py
    - tests/test_gap_models.py
  modified: []

key-decisions:
  - "GapKeyword.source uses String(50) not enum — accommodates future import sources without migrations"
  - "GapProposal.content_plan_item_id FK SET NULL so deleting content plan items doesn't cascade-delete proposals"

patterns-established:
  - "Gap analysis data isolated in app/models/gap.py with dedicated migration"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-04-03
---

# Phase v3-05 Plan 01: Models and migration Summary

**Three SQLAlchemy 2.0 models for content gap analysis — GapKeyword, GapGroup, GapProposal with ProposalStatus enum — plus Alembic migration 0024 and 4 unit tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-03T07:51:36Z
- **Completed:** 2026-04-03T07:54:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- GapKeyword model with competitor_domain, phrase, potential_score, source, and unique constraint
- GapGroup model for manual keyword grouping with FK on GapKeyword
- GapProposal model with ProposalStatus enum (pending/approved/rejected) and optional content_plan_item_id FK
- Alembic migration 0024 creates all 3 tables with proper indexes and downgrade support

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/models/gap.py** - `0f50622` (feat)
2. **Task 2: Create Alembic migration 0024** - `0f50622` (feat)
3. **Task 3: Unit tests for gap models** - `0f50622` (feat)

_Note: All three tasks committed together in feat(v3-05-01): add gap analysis models and migration 0024_

## Files Created/Modified
- `app/models/gap.py` - GapKeyword, GapGroup, GapProposal models with ProposalStatus enum
- `alembic/versions/0024_add_content_gap_tables.py` - Migration creating gap_keywords, gap_groups, gap_proposals tables
- `tests/test_gap_models.py` - 4 unit tests covering enum values, field assignment for all three models

## Decisions Made
- GapKeyword.source uses String(50) rather than enum — avoids future migrations for new import sources
- ProposalStatus uses native PG enum via SAEnum for DB-level constraint enforcement

## Deviations from Plan

None - plan executed exactly as written. Files were already committed from a prior run.

## Issues Encountered
None - all 4 tests pass, all acceptance criteria verified.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Data layer complete for gap analysis
- Ready for v3-05-02: gap service and CRUD routes using these models
- Migration 0024 must run before v3-05-02 routes are deployed

---
*Phase: v3-05-content-gap*
*Completed: 2026-04-03*
