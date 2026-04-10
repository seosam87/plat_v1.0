---
phase: 25-serp-aggregation-tools
plan: "01"
subsystem: tools-backend
tags: [celery, playwright, models, migration, aggregation]
dependency_graph:
  requires: []
  provides:
    - brief_job_model
    - paa_job_model
    - wordstat_batch_job_model
    - brief_top10_service
    - brief_celery_chain
  affects:
    - app/routers/tools.py
    - app/celery_app.py
tech_stack:
  added: []
  patterns:
    - 4-step Celery chain with .si() immutable signatures
    - intermediate_data JSONB column for inter-step state
    - lightweight Playwright crawler (context-per-URL, no snapshot diffs)
key_files:
  created:
    - app/models/brief_job.py
    - app/models/paa_job.py
    - app/models/wordstat_batch_job.py
    - alembic/versions/0050_add_brief_paa_wordstat_batch_tables.py
    - app/services/brief_top10_service.py
    - app/tasks/brief_tasks.py
  modified:
    - app/routers/tools.py
    - app/celery_app.py
    - tests/test_brief_service.py
decisions:
  - intermediate_data JSONB on BriefJob for inter-step chain communication (avoids Redis or extra table)
  - crawl_top10_page returns None on all errors per D-06 (no re-raise, no retry)
  - serp_snippets collected in step1 and passed to aggregate for highlights
  - .si() not .s() in chain dispatch to prevent return-value injection between steps
  - Brief XLSX export uses multi-section workbook (not flat table like other tools)
metrics:
  duration_minutes: 7
  completed_date: "2026-04-10"
  tasks_completed: 2
  files_changed: 9
---

# Phase 25 Plan 01: All Phase 25 Models + Brief Pipeline Summary

Phase 25-01 establishes all DB models for the SERP aggregation tools (Brief, PAA, Wordstat), the single Alembic migration (0050), and the complete Brief backend pipeline: lightweight TOP-10 Playwright crawler + aggregation service + 4-step Celery chain + router integration.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | All Phase 25 models + single Alembic migration | ee10113 | app/models/brief_job.py, app/models/paa_job.py, app/models/wordstat_batch_job.py, alembic/versions/0050_add_brief_paa_wordstat_batch_tables.py |
| 2 | Brief TOP-10 service + 4-step Celery chain + tests | 70db2ce | app/services/brief_top10_service.py, app/tasks/brief_tasks.py, tests/test_brief_service.py, app/routers/tools.py, app/celery_app.py |

## What Was Built

### Models (Task 1)

**BriefJob** (`brief_jobs`): UUID PK, status, input_phrases JSONB, phrase_count, input_region (default 213), result_count, progress_pct, error_message, celery_task_id, `intermediate_data` JSONB (for chain state), created_at, completed_at, user_id FK.

**BriefResult** (`brief_results`): Aggregated one-row-per-job result with title_suggestions, h2_cloud, highlights, thematic_words, avg_text_length, avg_h2_count, commercialization_pct, pages_crawled, pages_attempted.

**PAAJob / PAAResult** (`paa_jobs` / `paa_results`): Same structure as CommerceCheckJob. PAAResult flat table with phrase, question, source_block (per D-09).

**WordstatBatchJob / WordstatBatchResult / WordstatMonthlyData**: WordstatBatchJob adds progress_pct. Monthly data normalized to separate table per D-13.

**Migration 0050**: Single file creates all 6 tables with indexes in one upgrade().

### Service (Task 2)

**crawl_top10_page(url)**: Uses process-level Playwright browser (`get_browser()`), creates BrowserContext + Page per URL, extracts h2s/visible_text/title, closes context in finally block. Returns None on HTTP 4xx/5xx, timeout, or any exception (D-06: skip silently).

**aggregate_brief_data(crawled_pages, phrases, serp_snippets)**: H2 cloud (Counter, sorted desc), thematic words (regex tokenizer, ~30 Russian/English stopwords filtered, top 100), title suggestions (deduplicated), highlights (from SERP snippets, deduplicated), avg_text_length, avg_h2_count, commercialization_pct (pages with цена/купить/etc.).

### Celery Chain (Task 2)

4 tasks in `brief_tasks.py`:
- `run_brief_step1_serp` (soft_time_limit=300): XMLProxy SERP fetch, collect TOP-10 URLs per phrase, store in `intermediate_data`
- `run_brief_step2_crawl` (soft_time_limit=900): Playwright crawl of all URLs, 0.5s politeness delay, progress tracking
- `run_brief_step3_aggregate` (soft_time_limit=120): Aggregate crawled data, create BriefResult row
- `run_brief_step4_finalize` (soft_time_limit=30): Set status=complete, clear intermediate_data

Dispatch in tools.py uses `celery_chain(...).delay()` with `.si()` immutable signatures.

### Router Integration (Task 2)

`tools.py` updated:
- `"brief"` added to TOOL_REGISTRY (limit=50 phrases)
- `_get_tool_models("brief")` returns BriefJob, BriefResult
- `_get_tool_task("brief")` returns None (signals chain dispatch)
- `tool_submit` branch dispatches 4-step chain with `.si()`
- `tool_export` branch for brief: XLSX-only with multi-section workbook (stats, H2 cloud, thematic words, titles, highlights); CSV path returns 400
- `tools_index` includes BriefJob in job count query

## Deviations from Plan

### Auto-fixed Issues

None significant.

**1. [Rule 2 - Enhancement] Added `serp_snippets` parameter to `aggregate_brief_data`**
- **Found during:** Task 2 implementation
- **Issue:** Plan described collecting SERP snippets in step1 for highlights but `aggregate_brief_data` signature only took `crawled_pages` and `phrases`
- **Fix:** Added optional `serp_snippets: list[str] | None = None` parameter; stored snippets in `intermediate_data` in step1 and passed to aggregate in step3
- **Files modified:** app/services/brief_top10_service.py, app/tasks/brief_tasks.py

**2. [Rule 1 - Cleanup] Existing `tests/test_brief_service.py` preserved**
- **Found during:** Task 2 test creation
- **Issue:** File already existed with 8 tests for the old `brief_service.py` (content brief generation); plan expected new file
- **Fix:** Appended Phase 25 tests to existing file (12 new tests, 20 total), preserving all existing tests

## Known Stubs

None. All Phase 25 tables are created and the full Brief backend pipeline is wired. PAA and Wordstat models are DB-only stubs (no tasks yet — that's Plan 03 and 04 scope).

## Verification

```
python -c "from app.models.brief_job import BriefJob, BriefResult; from app.models.paa_job import PAAJob, PAAResult; from app.models.wordstat_batch_job import WordstatBatchJob, WordstatBatchResult, WordstatMonthlyData; print('OK')"
# → OK

python -m pytest tests/test_brief_service.py -x
# → 20 passed

grep "brief" app/routers/tools.py | wc -l
# → 9 occurrences
```

## Self-Check: PASSED
