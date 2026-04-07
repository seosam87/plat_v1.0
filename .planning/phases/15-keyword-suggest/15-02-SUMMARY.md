---
phase: 15-keyword-suggest
plan: "02"
subsystem: keyword-suggest
tags: [fastapi, htmx, jinja2, slowapi, ui, router]
dependency_graph:
  requires: [SuggestJob model, fetch_suggest_keywords task, suggest_cache_key]
  provides: [keyword_suggest router, keyword_suggest templates, Keyword Suggest nav entry]
  affects: [app/main.py, app/navigation.py, app/templates/components/sidebar.html]
tech_stack:
  added: [app/rate_limit.py shared Limiter]
  patterns: [HTMX polling with hx-trigger=load delay, UTF-8 BOM CSV StreamingResponse, lazy import for cross-plan Celery task]
key_files:
  created:
    - app/routers/keyword_suggest.py
    - app/templates/keyword_suggest/index.html
    - app/templates/keyword_suggest/partials/suggest_status.html
    - app/templates/keyword_suggest/partials/suggest_results.html
    - app/rate_limit.py
    - tests/test_keyword_suggest_router.py
  modified:
    - app/main.py
    - app/navigation.py
    - app/templates/components/sidebar.html
decisions:
  - "Extracted slowapi Limiter to app/rate_limit.py to avoid circular import with app.main when decorating router endpoints with @limiter.limit"
  - "Used light-bulb sidebar icon instead of magnifying-glass to avoid conflict with existing Аналитика section"
  - "Lazy import of fetch_wordstat_frequency inside endpoint body — Plan 03 creates the task; avoids ImportError if Plan 02 executes first in Wave 2"
  - "Wordstat completion detected by presence of 'frequency' key on first cached suggestion (no separate status flag needed)"
metrics:
  duration_minutes: 12
  completed_date: "2026-04-07"
  tasks_completed: 2
  files_changed: 9
requirements: [SUG-01, SUG-02, SUG-03, SUG-04]
---

# Phase 15 Plan 02: Keyword Suggest UI (Router + Templates + Navigation) Summary

**One-liner:** FastAPI router with search/status/CSV/Wordstat endpoints, HTMX-polled Jinja2 templates with client-side filter/sort/copy, sidebar nav entry, 10/minute slowapi rate limit on search.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Router + templates + sidebar nav + main.py registration | ef5a575 | app/routers/keyword_suggest.py, app/templates/keyword_suggest/{index,partials/*}.html, app/rate_limit.py, app/main.py, app/navigation.py, app/templates/components/sidebar.html |
| 2 | Router integration tests | 1271fff | tests/test_keyword_suggest_router.py |

## What Was Built

### Router (`app/routers/keyword_suggest.py`)
Six endpoints under prefix `/ui/keyword-suggest`:
1. `GET /` — main page, loads sites list and wordstat-token flag.
2. `POST /search` — creates SuggestJob row, checks Redis cache (instant-complete on hit), else dispatches `fetch_suggest_keywords.delay(...)`. Rate-limited `@limiter.limit("10/minute")`.
3. `GET /status/{job_id}` — HTMX polling endpoint; returns pending/complete/partial/failed partial; loads results from Redis via `cache_key` when done.
4. `GET /export?job_id=...` — UTF-8 BOM CSV `StreamingResponse`; headers `Подсказка,Источник,Частотность`; filename `suggest_{slug}_{YYYY-MM-DD}.csv`.
5. `POST /{job_id}/wordstat` — validates job status and yandex_direct token, lazy-imports `fetch_wordstat_frequency` (Plan 03) and dispatches it. Returns inline HTMX polling partial.
6. `GET /{job_id}/wordstat-status` — polling endpoint; detects completion by presence of `"frequency"` key on first cached suggestion; returns success or spinner partial.

### Templates
- **`index.html`** — seed input (required, maxlength 100), Google checkbox, site dropdown, "Найти подсказки" indigo CTA, HTMX indicator, optional Wordstat banner (dismissable), rate-limit notice. Targets `#suggest-status`.
- **`partials/suggest_status.html`** — four states: pending/running (blue + spinner + `hx-trigger="load delay:3s"`), complete (green, "Из кэша" when cache_hit), partial (amber with proxy warning), failed (red). Includes `suggest_results.html` when data present.
- **`partials/suggest_results.html`** — filter row (text + source select), sortable table with source badges (Я red / G blue), hidden frequency column, per-row copy button, export row ("Копировать всё", "Скачать CSV"), Wordstat dispatch button when token present. Inline JS for filter, sort (asc/desc toggle), per-row and bulk clipboard copy with toast.

### Navigation + sidebar
- New `keyword-suggest` section in `NAV_SECTIONS` between client-reports and settings, icon `light-bulb`, child "Поиск подсказок" → `/ui/keyword-suggest/`.
- Added `light-bulb` Heroicon SVG path to `sidebar.html` icon dispatch block.

### Rate limiter extraction (`app/rate_limit.py`)
Module-level `limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])`. `app.main` now imports it from here, so routers can `from app.rate_limit import limiter` and apply `@limiter.limit("10/minute")` without circular imports.

### Router tests (`tests/test_keyword_suggest_router.py`)
12 tests overriding `get_current_user` and mocking `_read_cache` / Celery `.delay()`:
- `test_index_page_loads`, `test_empty_seed_rejected`
- `test_search_dispatches_task`, `test_search_rate_limit` (sends 12 rapid POSTs, asserts 429 present)
- `test_status_polling_pending`, `test_status_complete_returns_results`
- `test_csv_export` (asserts BOM, headers, Яндекс/Google translated sources)
- `test_wordstat_dispatch`, `test_wordstat_dispatch_no_token`, `test_wordstat_dispatch_job_not_ready`
- `test_wordstat_status_polling`, `test_wordstat_status_complete`

## Deviations from Plan

**[Rule 3 — Blocking issue] Extracted limiter to `app/rate_limit.py`**
The plan allowed this as an option. Direct `from app.main import limiter` causes circular import because `app.main` imports the router before the limiter is fully bound in the routed module's scope. Created `app/rate_limit.py` and refactored `app.main` to import from it.

**[Rule 2 — Missing critical functionality] Used `light-bulb` sidebar icon**
The plan itself noted the magnifying-glass icon is already used by Аналитика. Swapped to `light-bulb` (Heroicons) and added its SVG path to `sidebar.html` icon dispatch.

## Verification

- `python -c "from app.routers.keyword_suggest import router; print(len(router.routes))"` → `6` (OK)
- `python -c "from app.main import app; print(len(app.routes))"` → `336` (OK, registered)
- `grep "keyword-suggest" app/navigation.py` → present
- `grep "keyword_suggest_router" app/main.py` → present
- `grep "wordstat" app/routers/keyword_suggest.py` → 17+ hits (both endpoints + token checks)
- Router tests: not executed in planning environment (no postgres/redis); same limitation affects pre-existing `tests/test_router_gaps.py`. Tests will run inside the Docker test stack as normal.

## Known Stubs

None. The Wordstat task's lazy import is not a stub — it is a deliberate cross-plan integration pattern documented in the plan; Plan 03 will provide `fetch_wordstat_frequency`.

## Self-Check: PASSED

- app/routers/keyword_suggest.py — FOUND
- app/templates/keyword_suggest/index.html — FOUND
- app/templates/keyword_suggest/partials/suggest_status.html — FOUND
- app/templates/keyword_suggest/partials/suggest_results.html — FOUND
- app/rate_limit.py — FOUND
- tests/test_keyword_suggest_router.py — FOUND
- Commit ef5a575 — FOUND
- Commit 1271fff — FOUND
