---
phase: v3-06-site-architecture
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, postgres, models, enum, migration]

# Dependency graph
requires:
  - phase: v3-05
    provides: content gap models/migration pattern
provides:
  - ArchitectureRole enum (8 values) in crawl.py
  - Page.source field (String 20, default "crawl")
  - Page.architecture_role field (SAEnum ArchitectureRole, default unknown)
  - SitemapEntry model (sitemap_entries table)
  - PageLink model (page_links table with index)
  - Alembic migration 0025 for all above
affects: [v3-06-02, v3-06-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ArchitectureRole enum uses native_enum (PostgreSQL ENUM type)
    - SitemapEntry uses UniqueConstraint on (site_id, url)
    - PageLink uses composite index on (site_id, crawl_job_id, source_url)

key-files:
  created:
    - app/models/architecture.py
    - alembic/versions/0025_add_architecture_tables.py
    - tests/test_architecture_models.py
  modified:
    - app/models/crawl.py

key-decisions:
  - "ArchitectureRole uses PostgreSQL ENUM type (native_enum) for performance and type safety"
  - "Page.source is String(20) not enum — crawl/sf_import as free-form values to avoid migrations"
  - "SitemapEntry.status is String(20) not enum — orphan/missing/ok covers current needs, String avoids DDL lock"

patterns-established:
  - "Architecture models split to app/models/architecture.py following existing modular pattern"
  - "Migration uses DO $$ BEGIN ... END $$ to safely create enum if not exists"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-03
---

# Phase v3-06 Plan 01: Models and Migration Summary

**ArchitectureRole enum (8 values), Page.source/architecture_role fields, SitemapEntry + PageLink models, and Alembic migration 0025 for site architecture feature**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-03T08:20:00Z
- **Completed:** 2026-04-03T08:23:49Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments
- Added `ArchitectureRole` enum with 8 values (pillar, service, subservice, article, trigger, authority, link_accelerator, unknown) to crawl.py
- Added `source` (String 20, default "crawl") and `architecture_role` (enum, default unknown) fields to Page model
- Created `app/models/architecture.py` with SitemapEntry (sitemap comparison) and PageLink (internal link graph) models
- Created migration 0025 with safe enum creation, two new tables, composite index on page_links
- Created 5 unit tests covering enum count, enum values, Page field presence, SitemapEntry, PageLink

## Task Commits

Each task was committed atomically:

1. **Task 1: ArchitectureRole enum + Page fields** - `aebd70a` (already in worktree from prior session)
2. **Task 2: architecture.py SitemapEntry + PageLink** - `aebd70a` (already in worktree from prior session)
3. **Task 3: Alembic migration 0025** - `aebd70a` (already in worktree from prior session)
4. **Task 4: Unit tests (5 tests)** - `2d02dcb` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `app/models/crawl.py` - Added ArchitectureRole enum and source/architecture_role fields to Page
- `app/models/architecture.py` - New: SitemapEntry and PageLink models
- `alembic/versions/0025_add_architecture_tables.py` - New: migration adding enum, columns, tables, index
- `tests/test_architecture_models.py` - New: 5 unit tests for models and enum

## Decisions Made
- Page.source is String(20) not enum — "crawl" and "sf_import" as free-form values avoids future migrations when new import sources are added
- SitemapEntry.status is String(20) not enum — orphan/missing/ok are stable but String avoids PG DDL lock-in
- ArchitectureRole uses native PostgreSQL ENUM for type safety and performance (consistent with other enums in the project)

## Deviations from Plan

None - plan executed exactly as written. All 4 tasks were already implemented (Tasks 1-3 in a prior WIP session). Task 4 test file existed with 4 tests; plan required 5 — added 5th test for all enum values.

## Issues Encountered
- Tasks 1-3 were pre-implemented in the worktree from a prior session (commit aebd70a). Task 4 test file had 4 tests instead of required 5; added the missing 5th test for full coverage.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All models and migration in place for v3-06-02 (architecture service layer)
- Page.source ready to distinguish crawl vs sf_import pages
- SitemapEntry model ready for sitemap.xml parsing and comparison logic
- PageLink model ready for internal link graph storage during crawl

## Self-Check: PASSED

All created files verified present. Commits 2d02dcb and aebd70a verified in git log.

---
*Phase: v3-06-site-architecture*
*Completed: 2026-04-03*
