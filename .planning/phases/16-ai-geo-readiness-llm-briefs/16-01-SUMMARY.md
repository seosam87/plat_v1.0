---
phase: 16-ai-geo-readiness-llm-briefs
plan: 01
subsystem: audit
tags: [geo, llm, beautifulsoup, alembic, postgres, schema-org, robots-txt]

# Dependency graph
requires:
  - phase: 15.1-ui-smoke-crawler
    provides: "crawl pipeline and audit infrastructure (audit_check_definitions, AuditResult, content_audit_service)"
provides:
  - "9 rule-based GEO readiness check functions in app/services/llm/geo_checks.py"
  - "GEO_WEIGHTS dict (9 codes summing to 100) and compute_geo_score()"
  - "pages.geo_score column populated after each audit run"
  - "llm_brief_jobs and llm_usage tables ready for Plan 03/04"
  - "users.anthropic_api_key_encrypted column for per-user key storage"
  - "audit_check_definitions.weight column for weighted check scoring"
affects:
  - "16-02: GEO audit table UI (reads pages.geo_score, filters by geo_* codes)"
  - "16-03: LLM infrastructure (uses llm_brief_jobs, llm_usage tables)"
  - "content_audit_service callers: geo_* runners now active in _CHECK_RUNNERS"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GEO check functions: pure (html: str, page_data: dict) -> bool, no DB, testable in isolation"
    - "GEO_CHECK_RUNNERS dict merged into existing _CHECK_RUNNERS via **spread operator"
    - "compute_geo_score() sums GEO_WEIGHTS for passed geo_* results"
    - "save_audit_results() accepts optional page_id to persist geo_score on Page row"
    - "TDD flow: RED commit (test) → GREEN commit (feat) with inline HTML fixture strings"

key-files:
  created:
    - app/services/llm/__init__.py
    - app/services/llm/geo_checks.py
    - alembic/versions/0041_phase16_geo_and_llm.py
    - tests/test_geo_checks.py
  modified:
    - app/models/crawl.py
    - app/services/content_audit_service.py

key-decisions:
  - "weight column added to audit_check_definitions (was missing from existing table; required by acceptance criteria select sum(weight))"
  - "test file placed at tests/test_geo_checks.py not tests/services/ — project has flat test layout, no services/ subdir"
  - "save_audit_results() extended with optional page_id parameter (non-breaking) rather than creating a separate function"
  - "anthropic_api_key_encrypted stored as column on users (simpler path per researcher recommendation in CONTEXT D-02)"

patterns-established:
  - "Pattern: geo_* check functions are pure functions testable without Docker/DB using inline HTML fixture strings"
  - "Pattern: GEO_CHECK_RUNNERS spread into _CHECK_RUNNERS allows runners to coexist with zero modification of existing dispatch logic"

requirements-completed: [GEO-01, GEO-02]

# Metrics
duration: 6min
completed: 2026-04-08
---

# Phase 16 Plan 01: GEO Check Functions, Migration, and Audit Wiring Summary

**9 rule-based GEO readiness checks (BeautifulSoup + regex, 0-100 score) wired into existing audit pipeline via GEO_CHECK_RUNNERS; migration 0041 adds pages.geo_score, llm_brief_jobs, llm_usage, and seeds 9 weighted rows into audit_check_definitions.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-08T10:19:02Z
- **Completed:** 2026-04-08T10:25:00Z
- **Tasks:** 2 completed
- **Files modified:** 6

## Accomplishments

- 9 GEO check functions implemented in `app/services/llm/geo_checks.py`: FAQPage schema, Article+Author, BreadcrumbList, answer-first paragraph, update date, H2 questions, external citations, AI robots, summary block
- Migration 0041 applied cleanly: pages.geo_score, users.anthropic_api_key_encrypted, audit_check_definitions.weight, llm_brief_jobs, llm_usage tables — all in one migration as planned
- 45 unit tests passing; 24 existing content_audit_service tests pass (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: GEO failing tests** - `dd0fba3` (test)
2. **Task 1 GREEN: GEO check functions + weights module** - `83c315b` (feat)
3. **Task 2: Alembic migration + content_audit_service wiring** - `3c679be` (feat)

_TDD Task 1 has two commits: test (RED) then feat (GREEN)._

## Files Created/Modified

- `app/services/llm/__init__.py` - Package marker for LLM services
- `app/services/llm/geo_checks.py` - 9 check functions, GEO_WEIGHTS, compute_geo_score, GEO_CHECK_RUNNERS
- `alembic/versions/0041_phase16_geo_and_llm.py` - Migration: pages.geo_score, users.anthropic_api_key_encrypted, audit_check_definitions.weight, llm_brief_jobs, llm_usage, 9 geo_* seed rows
- `app/models/crawl.py` - Page.geo_score: Mapped[int | None] column added
- `app/services/content_audit_service.py` - GEO_CHECK_RUNNERS merged into _CHECK_RUNNERS; compute_geo_score wired into save_audit_results; import added
- `tests/test_geo_checks.py` - 45 unit tests for all 9 check functions + score computation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added weight column to audit_check_definitions**
- **Found during:** Task 2 migration design
- **Issue:** The existing `audit_check_definitions` table had no `weight` column, but the plan's acceptance criteria required `SELECT sum(weight) FROM audit_check_definitions WHERE code LIKE 'geo_%'` to return 100
- **Fix:** Added `op.add_column("audit_check_definitions", sa.Column("weight", sa.Integer(), nullable=True))` to migration 0041, seeded 9 rows with their weights
- **Files modified:** `alembic/versions/0041_phase16_geo_and_llm.py`
- **Commit:** 3c679be

**2. [Rule 1 - Bug] Test fixture word count was 57, not >60**
- **Found during:** Task 1 GREEN phase - test_geo_answer_first_too_long failed
- **Issue:** `_ANSWER_FIRST_TOO_LONG_HTML` fixture had only 57 words (below 60 limit) and also contained "is" verb — so the check passed instead of failing
- **Fix:** Rewrote the fixture to have 62 words with no verb matches
- **Files modified:** `tests/test_geo_checks.py`
- **Commit:** 83c315b

**3. [Deviation - File placement] Test file at tests/test_geo_checks.py not tests/services/**
- **Found during:** Task 1 - checking project test layout
- **Issue:** Plan specified `tests/services/test_geo_checks.py` but the project uses a flat `tests/` layout with no `services/` subdirectory
- **Fix:** Created file at `tests/test_geo_checks.py` matching project conventions
- **Impact:** None — test discovery works correctly

## Self-Check: PASSED
