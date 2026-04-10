---
phase: 25-serp-aggregation-tools
plan: "04"
subsystem: tools
tags: [wordstat, yandex, batch, frequency, celery, htmx, openpyxl, oauth]

requires:
  - phase: 25-01
    provides: WordstatBatchJob, WordstatBatchResult, WordstatMonthlyData models + migration 0050

provides:
  - Batch Wordstat service (separate from wordstat_service.py per D-11): exact+broad API calls with proper quoting, monthly dynamics
  - Celery task run_wordstat_batch with progress_pct updates every 50 phrases
  - Router integration: TOOL_REGISTRY wordstat-batch, multi-sheet XLSX export, OAuth token check
  - UI: landing page with OAuth warning banner, results table with Динамика column, progress bar partial

affects:
  - tools-infrastructure
  - 25-05 (next tool in phase)
  - PAA tool (added to TOOL_REGISTRY by parallel agent)

tech-stack:
  added: []
  patterns:
    - "Separate batch service pattern (D-11): batch_wordstat_service.py is independent from wordstat_service.py"
    - "Progress tracking pattern: Celery task updates job.progress_pct = int(processed/total*100) every 50 phrases"
    - "OAuth warning pattern: router checks token before rendering landing, passes oauth_warning bool to template"
    - "Multi-sheet XLSX export: Sheet1=frequencies, Sheet2=monthly dynamics with result_id join"

key-files:
  created:
    - app/services/batch_wordstat_service.py
    - app/tasks/wordstat_batch_tasks.py
    - tests/test_batch_wordstat_service.py
    - app/templates/tools/wordstat-batch/index.html
    - app/templates/tools/wordstat-batch/results.html
    - app/templates/tools/wordstat-batch/partials/job_status.html
  modified:
    - app/routers/tools.py
    - app/celery_app.py
    - app/templates/tools/tool_landing.html
    - app/templates/tools/tool_results.html
    - app/templates/tools/partials/job_status.html

key-decisions:
  - "Exact match uses f'\"phrase\"' quoting (Pitfall 4) — verified by test_exact_vs_broad_different_quotes"
  - "Monthly dynamics parsed from broad match response (monthlyData/dynamics/searchedWith keys)"
  - "OAuth token check runs in thread executor via asyncio.run_in_executor to avoid blocking event loop"
  - "Wordstat-batch export is XLSX-only (export_only_xlsx=True) — CSV not practical for multi-sheet monthly data"
  - "Progress bar polling at 5s interval (vs 10s for other tools) since Wordstat can take minutes for 1000 phrases"

patterns-established:
  - "OAuth-gated tool pattern: TOOL_REGISTRY entry has needs_oauth field; router checks and passes oauth_warning to template"
  - "Multi-sheet XLSX export: slug-specific branch before generic XLSX handler in tool_export"

requirements-completed:
  - FREQ-01

duration: 8min
completed: "2026-04-10"
---

# Phase 25 Plan 04: Batch Wordstat Tool Summary

**Batch Wordstat frequency checker: separate service with exact/broad quoting, Celery progress tracking, OAuth warning banner, monthly dynamics in normalized table, multi-sheet XLSX export**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-10T13:10:54Z
- **Completed:** 2026-04-10T13:18:00Z
- **Tasks:** 2
- **Files modified:** 10 (6 created, 4 modified)

## Accomplishments

- `batch_wordstat_service.py` makes two separate API calls per phrase (exact=quoted, broad=unquoted) per Pitfall 4; monthly dynamics extracted from broad response
- `run_wordstat_batch` Celery task updates `progress_pct` every 50 phrases; stores `WordstatMonthlyData` rows per result; handles missing OAuth token with "failed" status
- Full router integration: TOOL_REGISTRY with limit=1000, `needs_oauth`, `export_only_xlsx`; multi-sheet XLSX (Sheet1=Частотность, Sheet2=Динамика); OAuth check via thread executor
- Templates: wordstat-batch landing with OAuth amber banner, results table with Динамика column (last 3 months), slug-specific job_status partial with progress bar + `progress_pct` display
- 11 tests passing: quoting logic, error handling (continues on per-phrase failure), monthly parsing, OAuth token check

## Task Commits

1. **Task 1: Batch Wordstat service + Celery task + tests** — `3ef6242` (feat)
2. **Task 2: Router integration + UI templates** — `aed682e` (feat)

## Files Created/Modified

- `app/services/batch_wordstat_service.py` — New: exact+broad API calls, monthly dynamics extraction, OAuth token check
- `app/tasks/wordstat_batch_tasks.py` — New: Celery task with progress tracking, WordstatMonthlyData creation
- `tests/test_batch_wordstat_service.py` — New: 11 tests (quoting, error handling, monthly, OAuth)
- `app/routers/tools.py` — wordstat-batch in TOOL_REGISTRY, _get_tool_models/_task/_EXPORT_HEADERS, multi-sheet XLSX, OAuth check, monthly data loading for results page
- `app/celery_app.py` — wordstat_batch_tasks added to include list
- `app/templates/tools/wordstat-batch/index.html` — New: landing with OAuth warning banner
- `app/templates/tools/wordstat-batch/results.html` — New: results table with Динамика column
- `app/templates/tools/wordstat-batch/partials/job_status.html` — New: progress_pct + progress bar
- `app/templates/tools/tool_landing.html` — Added oauth_warning conditional block
- `app/templates/tools/tool_results.html` — Added wordstat-batch branch with Динамика column
- `app/templates/tools/partials/job_status.html` — Added progress_pct + progress bar for wordstat-batch slug

## Decisions Made

- Used `asyncio.run_in_executor` for OAuth check in the async `tool_landing` handler — avoids blocking the event loop with sync DB call
- Wordstat-batch polling interval set to 5s (vs 10s for other tools) — batch of 1000 phrases can take several minutes, faster feedback is useful
- Monthly dynamics parsed from broad response only (not exact) — avoids 4 API calls per phrase; broad response naturally has time-dimension data

## Deviations from Plan

None — plan executed exactly as written. The plan's `_check_oauth_token_sync` pattern was implemented as a module-level helper function in the router.

## Issues Encountered

- `check_wordstat_oauth_token` test needed to patch `app.services.service_credential_service.get_credential_sync` (the source module), not the importing module, since the function uses a local import inside the body. Fixed with `patch.object(scs_module, ...)`.

## Next Phase Readiness

- Batch Wordstat tool complete and integrated; all routes registered
- Yandex Direct OAuth token configuration in `/ui/settings` needed for live use
- Plan 05 (next tool in phase) can proceed

---
*Phase: 25-serp-aggregation-tools*
*Completed: 2026-04-10*
