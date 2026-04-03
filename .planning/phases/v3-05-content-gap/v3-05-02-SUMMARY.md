---
phase: v3-05-content-gap
plan: "02"
subsystem: api
tags: [gap-analysis, scoring, parser, csv, xlsx, proposals, content-plan]

requires:
  - phase: v3-05-01
    provides: GapKeyword, GapGroup, GapProposal models and migration 0024

provides:
  - gap_service.py with full CRUD, scoring, detection, import, and proposal management
  - gap_parser.py for CSV/XLSX competitor keyword files (keys.so, Topvisor, generic)
  - compute_potential_score() pure function with frequency × position-factor formula
  - detect_gaps_from_session() SERP-based gap detection
  - import_competitor_keywords() file-based import pipeline
  - GapGroup/GapKeyword/GapProposal CRUD service layer
  - approve_proposal() with optional ContentPlanItem creation
  - 10 unit tests for scoring and parsing

affects: [v3-05-03, any future gap UI or reporting phase]

tech-stack:
  added: []
  patterns:
    - "Pure scoring function (compute_potential_score) separate from async DB layer"
    - "parse_gap_file uses find_column() for multi-format column auto-detection"
    - "PostgreSQL upsert via on_conflict_do_update for gap keyword idempotency"
    - "Proposal approve creates ContentPlanItem only if project_id provided"

key-files:
  created:
    - app/services/gap_service.py
    - app/parsers/gap_parser.py
    - tests/test_gap_service.py
  modified: []

key-decisions:
  - "SCORE_FORMULA_DESCRIPTION constant in service for display in UI tooltips"
  - "detect_gaps_from_session uses extract_domain() from serp_analysis_service to normalize URLs"
  - "import_competitor_keywords infers source ('csv_import'/'xlsx_import') from file extension"

patterns-established:
  - "Gap service follows async session pattern consistent with other services"
  - "All gap keyword mutations flush but do not commit — caller owns transaction"

requirements-completed: []

duration: 5min
completed: 2026-04-03
---

# Phase v3-05 Plan 02: Gap Service Summary

**Gap analysis service with frequency × position scoring, SERP/file detection, group CRUD, proposal workflow, and multi-format parser (keys.so, Topvisor, generic CSV/XLSX)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T08:01:35Z
- **Completed:** 2026-04-03T08:06:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created `gap_service.py` with `compute_potential_score()`, `detect_gaps_from_session()`, `import_competitor_keywords()`, group/keyword/proposal CRUD — all async
- Created `gap_parser.py` supporting keys.so Russian headers, Topvisor export format, and generic English format via `find_column()` auto-detection
- Created `tests/test_gap_service.py` with 10 passing unit tests covering all score bands, all parser formats, and formula description constant

## Task Commits

Each task was committed atomically:

1. **Task 01: Create gap_service.py** - `de9bfa5` (feat)
2. **Task 02: Create gap_parser.py for CSV/XLSX import** - `de9bfa5` (feat)
3. **Task 03: Unit tests for gap service and parser** - `de9bfa5` (feat)

## Files Created/Modified

- `app/services/gap_service.py` - Full gap analysis service: scoring, SERP detection, file import, group/keyword/proposal management
- `app/parsers/gap_parser.py` - Multi-format competitor keyword parser with column auto-detection
- `tests/test_gap_service.py` - 10 unit tests: 5 scoring, 4 parser format, 1 formula description

## Decisions Made

- `SCORE_FORMULA_DESCRIPTION` constant kept in service module for display in UI scoring tooltips
- `detect_gaps_from_session` uses `extract_domain()` from `serp_analysis_service` to normalize competitor domain comparisons
- `import_competitor_keywords` infers source string (`'csv_import'` / `'xlsx_import'`) from file extension automatically

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Gap service layer complete; ready for Plan 03 (gap router, UI endpoints, and site detail integration)
- All scoring and import functions are pure or async — easily testable in router integration tests

---
*Phase: v3-05-content-gap*
*Completed: 2026-04-03*
