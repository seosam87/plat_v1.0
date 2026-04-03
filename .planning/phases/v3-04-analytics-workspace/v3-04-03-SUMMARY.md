---
phase: v3-04-analytics-workspace
plan: "03"
subsystem: analytics
tags: [celery, serp, competitor-detection, site-classification, playwright]

requires:
  - phase: v3-04-01
    provides: AnalysisSession, SessionSerpResult, CompetitorPageData, ContentBrief models and migration 0023

provides:
  - serp_analysis_service.py: classify_site_type, analyze_serp_results, extract_domain, save_serp_results, get_session_serp_summary, get_top_competitor
  - analytics_tasks.py: check_group_positions, parse_group_serp, crawl_competitor_pages Celery tasks
  - tests/test_serp_analysis_service.py: 10 unit tests for SERP analysis functions

affects:
  - v3-04-04 (brief generation uses SERP summary and competitor data)
  - v3-04-05 (analytics router triggers these Celery tasks)

tech-stack:
  added: []
  patterns:
    - "Pure analysis functions (classify_site_type, analyze_serp_results) separate from async DB functions — testable without DB"
    - "Celery tasks use asyncio.new_event_loop() + loop.run_until_complete() pattern for async DB operations"
    - "analyze_serp_results uses Counter for domain frequency tracking; deduplicates per keyword with seen_domains set"

key-files:
  created:
    - app/services/serp_analysis_service.py
    - app/tasks/analytics_tasks.py
    - tests/test_serp_analysis_service.py
  modified: []

key-decisions:
  - "Pure functions (classify_site_type, analyze_serp_results) are fully synchronous for easy testing without DB/Celery infrastructure"
  - "crawl_competitor_pages capped at 20 URLs per session to avoid excessive Playwright usage"
  - "parse_group_serp limited to first 50 keywords per session for performance"
  - "Top competitor auto-set by analyze_serp_results using Counter-based domain frequency; our_domain excluded via parameter"

patterns-established:
  - "SERP domain classification: aggregator > informational (domain list + URL path patterns) > commercial (default)"
  - "Celery async task pattern: sync task wrapper -> asyncio.new_event_loop() -> async inner function with async_session_factory"

requirements-completed: []

duration: 5min
completed: 2026-04-03
---

# Phase v3-04 Plan 03: Group Position Check and SERP Parsing Tasks Summary

**SERP analysis service with domain classification (aggregator/informational/commercial), competitor detection via frequency analysis, and three Celery tasks (check_group_positions, parse_group_serp, crawl_competitor_pages) for the analytics workspace workflow**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T07:29:36Z
- **Completed:** 2026-04-03T07:34:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created `serp_analysis_service.py` with pure classification functions (`classify_site_type`, `analyze_serp_results`) and async DB helpers (`save_serp_results`, `get_session_serp_summary`, `get_top_competitor`)
- Created `analytics_tasks.py` with three Celery tasks covering the full group analysis workflow: position check → SERP parse → competitor crawl
- Created `tests/test_serp_analysis_service.py` with 10 unit tests covering aggregator classification, informational URL patterns, commercial default, domain extraction, and SERP analysis with our-domain exclusion

## Task Commits

All tasks were committed atomically in a prior batch execution:

1. **Task 1: serp_analysis_service.py** - `b9b5930` (feat)
2. **Task 2: analytics_tasks.py** - `b9b5930` (feat)
3. **Task 3: test_serp_analysis_service.py** - `b9b5930` (feat)

## Files Created/Modified

- `app/services/serp_analysis_service.py` - SERP analysis service: site classification, competitor detection, async DB helpers
- `app/tasks/analytics_tasks.py` - Three Celery tasks: check_group_positions, parse_group_serp, crawl_competitor_pages
- `tests/test_serp_analysis_service.py` - 10 unit tests for pure analysis functions

## Decisions Made

- Pure functions (classify_site_type, analyze_serp_results) are synchronous for testability without DB/Celery infrastructure
- `parse_group_serp` limited to 50 keywords; `crawl_competitor_pages` capped at 20 URLs per session
- `analyze_serp_results` excludes our own domain via `our_domain` parameter; top competitor is highest-frequency domain after exclusion
- Domain classification priority: aggregator check first, then informational domains/URL patterns, commercial as default

## Deviations from Plan

None - plan executed exactly as written (code already committed in batch `b9b5930`).

## Issues Encountered

None - all three files were already implemented and committed in a prior batch execution (`b9b5930: feat(v3-04-02/03/04)`).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SERP analysis service is ready for use in brief generation (plan 04) and the analytics router (plan 05)
- `get_session_serp_summary()` and `get_top_competitor()` are available for the brief service to consume
- All three Celery tasks registered in `celery_app.py` include list

---
*Phase: v3-04-analytics-workspace*
*Completed: 2026-04-03*
