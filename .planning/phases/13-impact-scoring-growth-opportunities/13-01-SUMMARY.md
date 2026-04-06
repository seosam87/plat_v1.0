---
phase: 13-impact-scoring-growth-opportunities
plan: "01"
subsystem: database
tags: [celery, sqlalchemy, alembic, postgresql, impact-scoring, audit, metrika]

# Dependency graph
requires:
  - phase: 12-analytical-foundations
    provides: normalize_url() utility and keyword_latest_positions pattern used for URL matching

provides:
  - ErrorImpactScore SQLAlchemy model (error_impact_scores table)
  - Alembic migration 0038 creating error_impact_scores table
  - impact_score_service with SEVERITY_WEIGHTS, compute_single_impact_score, build_impact_rows, upsert_impact_scores, get_impact_scores_for_site, get_max_impact_score_by_url
  - compute_impact_scores Celery task (queue=default, retry=3)
  - Automatic trigger of impact scoring after every site audit

affects:
  - 13-02 (growth opportunities page will query error_impact_scores for display)
  - 13-03 (impact score Kanban integration uses get_max_impact_score_by_url)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SEVERITY_WEIGHTS dict pattern for audit severity mapping (warning=1, error=3, critical=5)"
    - "build_impact_rows() pure function for testable score computation without DB"
    - "DISTINCT ON (page_url) ORDER BY period_end DESC for latest Metrika traffic per URL"
    - "Post-audit Celery trigger via delayed import inside async function to avoid circular imports"

key-files:
  created:
    - app/models/impact_score.py
    - alembic/versions/0038_add_error_impact_scores.py
    - app/services/impact_score_service.py
    - app/tasks/impact_tasks.py
    - tests/test_impact_score_service.py
  modified:
    - app/models/__init__.py
    - app/tasks/audit_tasks.py
    - app/celery_app.py

key-decisions:
  - "severity_weight: warning=1, error=3, critical=5 per D-02/D-03 from phase context"
  - "Pure function build_impact_rows() separates score computation from DB I/O — enables unit testing without DB"
  - "normalize_url() applied to both audit URLs and Metrika URLs to ensure cross-table matching"
  - "DISTINCT ON (page_url) ORDER BY period_end DESC selects latest Metrika period per URL efficiently"
  - "impact_tasks registered in celery_app.include to ensure worker discovery"
  - "AsyncSessionLocal used (not async_session_factory which is not exported by database.py)"

patterns-established:
  - "Pre-computation pattern: Celery task stores derived data in dedicated table for fast dashboard queries"
  - "Post-audit trigger: import inside async inner function to avoid circular imports with celery_app"

requirements-completed: [IMP-01]

# Metrics
duration: 15min
completed: 2026-04-06
---

# Phase 13 Plan 01: Error Impact Scoring Backend Summary

**ErrorImpactScore pre-computation backend: SQLAlchemy model, Alembic migration 0038, service with pure compute functions + pg_insert upsert, and Celery task joining audit_results + metrika_traffic_pages via normalize_url to produce severity_weight x monthly_traffic scores, triggered automatically after each audit**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-06T14:08:00Z
- **Completed:** 2026-04-06T14:13:15Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Created ErrorImpactScore model with unique constraint (site_id, page_url, check_code) and descending impact_score index for fast dashboard ordering
- Built impact_score_service with testable pure functions (SEVERITY_WEIGHTS, compute_single_impact_score, build_impact_rows) and async DB functions (upsert_impact_scores, get_impact_scores_for_site, get_max_impact_score_by_url)
- Created compute_impact_scores Celery task with retry=3 that JOINs audit_results + audit_check_definitions for severity, uses DISTINCT ON to get latest Metrika traffic per URL, normalizes URLs via normalize_url(), then bulk upserts
- Wired automatic post-audit trigger in audit_tasks.py so every audit run refreshes impact scores

## Task Commits

Each task was committed atomically:

1. **Task 1: ErrorImpactScore model + migration + impact_score_service with tests** - `77bceb3` (feat)
2. **Task 2: Celery task compute_impact_scores + audit completion trigger** - `a7430de` (feat)

**Deviation fix:** `ffe68ae` (fix: register impact_tasks in Celery app include list)

## Files Created/Modified
- `app/models/impact_score.py` - ErrorImpactScore model with UniqueConstraint and descending index
- `alembic/versions/0038_add_error_impact_scores.py` - Migration creating error_impact_scores table (depends_on 0037)
- `app/models/__init__.py` - Registered ErrorImpactScore import
- `app/services/impact_score_service.py` - SEVERITY_WEIGHTS, compute/build pure functions, async upsert/query functions
- `app/tasks/impact_tasks.py` - compute_impact_scores Celery task with async implementation
- `app/tasks/audit_tasks.py` - Added compute_impact_scores.delay(site_id) trigger after audit completion
- `app/celery_app.py` - Registered app.tasks.impact_tasks in include list
- `tests/test_impact_score_service.py` - 16 unit tests covering all pure functions

## Decisions Made
- severity_weight values (warning=1, error=3, critical=5) follow D-02/D-03 from phase 13 context
- Pure function build_impact_rows() separates score computation from DB I/O — all 16 unit tests run without a database connection
- normalize_url() applied to both audit URLs and Metrika traffic URLs to ensure URLs with UTM params, http://, or missing trailing slashes still match correctly
- Used AsyncSessionLocal (the actual exported name) rather than async_session_factory which does not exist in database.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Registered impact_tasks in Celery app include list**
- **Found during:** Task 2 (Celery task creation)
- **Issue:** New task module not registered in celery_app.py include list — Celery workers would not discover or execute compute_impact_scores
- **Fix:** Added "app.tasks.impact_tasks" to the include list in celery_app.py
- **Files modified:** app/celery_app.py
- **Verification:** python -c "from app.tasks.impact_tasks import compute_impact_scores; print(compute_impact_scores.name)" exits 0
- **Committed in:** ffe68ae (separate fix commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Registration required for task to be executable by workers. No scope creep.

## Issues Encountered
- database.py exports `AsyncSessionLocal` but several existing tasks import `async_session_factory` (a non-existent alias). Used `AsyncSessionLocal` in the new task. Pre-existing inconsistency, not introduced by this plan.

## Known Stubs
None — all functions are fully implemented. Score computation, DB upsert, and Celery trigger are all wired end-to-end.

## User Setup Required
None - no external service configuration required. Impact scores will be automatically computed after the next audit run.

## Next Phase Readiness
- error_impact_scores table and pre-computation pipeline are ready for use in phase 13 plan 02 (growth opportunities page)
- get_max_impact_score_by_url() is available for Kanban integration in plan 03
- No blockers

---
*Phase: 13-impact-scoring-growth-opportunities*
*Completed: 2026-04-06*
