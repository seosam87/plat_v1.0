---
phase: v3-04
plan: "04"
subsystem: api
tags: [brief, content-brief, seo, python, sqlalchemy, pytest]

# Dependency graph
requires:
  - phase: v3-04-01
    provides: ContentBrief, AnalysisSession, CompetitorPageData models and migration 0023

provides:
  - brief_service.py with generate_brief, build_heading_structure, suggest_seo_fields, format_brief_text
  - get_brief, list_briefs, delete_brief, export_brief_text, export_brief_csv async DB functions
  - 8 unit tests covering pure functions (heading structure, SEO fields, text formatting)

affects: [v3-04-05, v3-04-06, v3-04-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure functions (build_heading_structure, suggest_seo_fields, format_brief_text) for testability without DB"
    - "Competitor H2 common-pattern extraction: heading text appearing on 2+ pages is included in recommended structure"
    - "SEO field length enforcement: title<=60, h1<=70, meta<=160 at generation time"

key-files:
  created:
    - app/services/brief_service.py
    - tests/test_brief_service.py
  modified: []

key-decisions:
  - "Pure functions separate from async DB layer — enables unit testing without database fixtures"
  - "Heading structure: common H2 threshold is 2+ competitors; keywords become H3 suggestions"
  - "SEO meta template is Russian-language with site name (template-based, no LLM)"

patterns-established:
  - "Brief generation: load session → get keywords → get competitor pages → build headings → suggest SEO → insert ContentBrief → update session status"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-04-03
---

# Phase v3-04 Plan 04: Content Brief Service Summary

**Template-based ТЗ generator producing SEO fields, keyword list, heading structure from competitor analysis and session keywords — with text and CSV export.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-03T07:29:54Z
- **Completed:** 2026-04-03T07:32:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `brief_service.py` with pure functions and async DB layer for generating ContentBrief records
- `build_heading_structure()` extracts common H2 patterns (2+ competitors) and suggests keyword-based H3s
- `suggest_seo_fields()` enforces SEO length limits (title<=60, h1<=70, meta<=160)
- `format_brief_text()` renders all sections: SEO fields, keywords+frequency, headings, structure notes, competitor summary
- `export_brief_text` and `export_brief_csv` for file export
- 8 unit tests all passing, no DB required for pure function tests

## Task Commits

Both tasks were completed in a prior bulk commit:

1. **Task 01: Create brief_service.py** - `b9b5930` (feat)
2. **Task 02: Unit tests for brief generation** - `b9b5930` (feat)

## Files Created/Modified

- `app/services/brief_service.py` - Content brief service: pure functions + async DB CRUD + export
- `tests/test_brief_service.py` - 8 unit tests for pure functions (no DB needed)

## Decisions Made

- Pure functions (`build_heading_structure`, `suggest_seo_fields`, `format_brief_text`) separated from async DB functions — enables fast unit tests without database setup
- Competitor H2 threshold is 2+ occurrences across competitor pages; falls back to first competitor's H2s when no common ones found
- Brief title field stores "ТЗ: {top_keyword}" as display name; actual SEO title is `recommended_title`

## Deviations from Plan

None - plan executed exactly as written. Both files were already implemented and all 8 tests pass.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ContentBrief creation and export fully functional
- Ready for v3-04-05 (brief router/UI) and v3-04-06/07 (further analytics endpoints)
- `generate_brief(db, session_id)` is the main entry point for the router layer

## Self-Check: PASSED

All created files found on disk. Commit b9b5930 verified in git log.

---
*Phase: v3-04-analytics-workspace*
*Completed: 2026-04-03*
