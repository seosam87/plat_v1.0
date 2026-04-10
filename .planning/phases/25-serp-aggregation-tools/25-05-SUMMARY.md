---
phase: 25-serp-aggregation-tools
plan: 05
subsystem: ui
tags: [fastapi, htmx, jinja2, celery, pytest, tools, pagination]

requires:
  - phase: 25-01
    provides: Brief job model, brief task chain, tools router skeleton
  - phase: 25-03
    provides: PAAJob model, paa task
  - phase: 25-04
    provides: WordstatBatchJob model, wordstat task

provides:
  - Unified job history page across all 6 tools with server-side pagination
  - hx-delete delete button with hx-confirm dialog in unified table
  - POST /{slug}/rerun/{job_id} endpoint creating new job with same input
  - Parametrized pytest suite covering all 6 tool slugs (41 tests)

affects: [phase-25-complete, tools-section]

tech-stack:
  added: []
  patterns:
    - "Unified multi-model job history via in-memory merge + sort pattern (no DB union)"
    - "HTMX rerun: returns HX-Redirect header for HTMX requests, 303 for browser"
    - "Rerun dispatches Brief via celery_chain .si(), others via task_fn.delay()"

key-files:
  created: []
  modified:
    - app/routers/tools.py
    - app/templates/tools/index.html
    - tests/test_tools_router.py

key-decisions:
  - "Unified job history uses in-memory merge across 6 model queries rather than DB UNION to avoid raw SQL"
  - "HTMX rerun endpoint returns HX-Redirect header; standard browser gets 303 redirect"
  - "Rerun copies input_col and count_col; also copies has_domain_field/has_region_field optional fields"

patterns-established:
  - "Multi-model pagination: query each model separately, merge list in Python, slice by page"
  - "HTMX action endpoints: check HX-Request header to return HX-Redirect vs 303"

requirements-completed: [BRIEF-01, PAA-01, FREQ-01]

duration: 4min
completed: 2026-04-10
---

# Phase 25 Plan 05: Tools Section — Unified History + Re-run Summary

**Unified job history across all 6 tools with server-side pagination, hx-confirm delete, and re-run endpoint that dispatches new job with same input (41 router tests passing)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-10T12:43:49Z
- **Completed:** 2026-04-10T12:47:06Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `tools_index` now queries all 6 tool job models, merges and sorts by created_at desc, paginates 20/page with ?page=N and ?tool= filter
- POST `/{slug}/rerun/{job_id}` creates a new job copying input_col/count_col (and optional domain/region), dispatches Brief via 4-step celery_chain, others via task_fn.delay()
- `app/templates/tools/index.html` extended with unified table: Инструмент / Статус / Кол-во / Создано / Действия columns, Смотреть link, Повторить задание button, Удалить hx-confirm delete
- 41 pytest tests passing: parametrized landing/submit/limits for all 6 slugs, brief region capture, brief chain .si() dispatch, wordstat OAuth warning, rerun creates job, rerun 404

## Task Commits

1. **Task 1: Unified job history + rerun endpoint** - `156d2a8` (feat)
2. **Task 2: Router tests for all 6 tools** - `830de8e` (test)

## Files Created/Modified

- `app/routers/tools.py` - Extended tools_index with pagination/filter; added POST /{slug}/rerun/{job_id} endpoint
- `app/templates/tools/index.html` - Unified job history table with pagination, filter dropdown, hx-delete/hx-confirm, rerun button
- `tests/test_tools_router.py` - Extended from 12 to 41 tests covering all 6 tool slugs

## Decisions Made

- In-memory merge across 6 model queries chosen over raw SQL UNION for simplicity; at 20 jobs/page per user the scale is fine
- HTMX rerun uses HX-Redirect header to redirect after POST without page reload; standard browser falls through to 303

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 25 complete: all 6 tools (commercialization, meta-parser, relevant-url, brief, paa, wordstat-batch) implemented with unified job management
- Tools section ready for production deployment

---
*Phase: 25-serp-aggregation-tools*
*Completed: 2026-04-10*
