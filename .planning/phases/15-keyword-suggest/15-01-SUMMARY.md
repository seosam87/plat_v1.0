---
phase: 15-keyword-suggest
plan: "01"
subsystem: keyword-suggest
tags: [celery, redis, suggest, yandex, google, proxy, tdd]
dependency_graph:
  requires: []
  provides: [SuggestJob model, suggest_service, fetch_suggest_keywords Celery task]
  affects: [app/celery_app.py, alembic migrations]
tech_stack:
  added: [redis sync client (sync_redis), respx mock in tests]
  patterns: [TDD red-green, sync Celery task, Redis cache with TTL, alphabetic expansion, proxy rotation]
key_files:
  created:
    - app/models/suggest_job.py
    - app/services/suggest_service.py
    - app/tasks/suggest_tasks.py
    - alembic/versions/0040_add_suggest_jobs.py
    - tests/test_suggest_service.py
    - tests/test_suggest_tasks.py
  modified:
    - app/models/__init__.py
    - app/celery_app.py
decisions:
  - "Sync HTTP (httpx.Client) for Celery tasks — matches existing pattern in codebase (D-03)"
  - "import redis as sync_redis to disambiguate from async redis.asyncio in other modules"
  - "Proxy exhaustion = proxy_idx >= len(proxies)*3 (3 full rotations) before declaring ban"
metrics:
  duration_minutes: 9
  completed_date: "2026-04-06"
  tasks_completed: 2
  files_changed: 8
requirements: [SUG-01, SUG-02, SUG-04]
---

# Phase 15 Plan 01: SuggestJob Model, Migration, suggest_service, and Celery Task Summary

**One-liner:** SuggestJob ORM model + Alembic migration + sync Yandex/Google Suggest HTTP service + А-Я alphabetic expansion Celery task with Redis cache (24h TTL) and proxy rotation ban handling.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | SuggestJob model + migration + suggest_service | 080b28f | app/models/suggest_job.py, app/models/__init__.py, alembic/versions/0040_add_suggest_jobs.py, app/services/suggest_service.py, tests/test_suggest_service.py |
| 2 | Celery suggest task with alphabetic expansion, cache, proxy rotation | 2de65c0 | app/tasks/suggest_tasks.py, tests/test_suggest_tasks.py, app/celery_app.py |

## What Was Built

### SuggestJob model (`app/models/suggest_job.py`)
SQLAlchemy 2.0 Mapped model following the ClientReport pattern:
- Status lifecycle: `pending` → `running` → `complete | partial | failed`
- `cache_hit` and `cache_key` fields track Redis cache usage
- `site_id` (optional FK) and `user_id` (optional FK) for context
- Index `ix_sj_user_created` on `(user_id, created_at)` for listing queries

### Alembic migration (`alembic/versions/0040_add_suggest_jobs.py`)
Creates `suggest_jobs` table with all columns + index. Revision `0040`, down_revision `0039`.

### suggest_service (`app/services/suggest_service.py`)
All functions are sync for use inside Celery tasks:
- `fetch_yandex_suggest_sync(query, proxy_url, timeout)` — handles both array and dict JSON formats; returns `[]` on any error
- `fetch_google_suggest_sync(query, timeout)` — no proxy, direct server call; returns `[]` on any error
- `suggest_cache_key(seed, include_google)` — normalizes to `suggest:{y|yg}:{lowercased_seed}`
- `deduplicate_suggestions(yandex, google)` — merges with source tags, deduplicates by normalized form, filters empty strings
- `get_active_proxy_urls_sync()` — queries DB for active proxies for Celery use
- Constants: `RU_ALPHABET` (33 chars), `SUGGEST_CACHE_TTL = 86400`, `YANDEX_SUGGEST_URL`, `GOOGLE_SUGGEST_URL`

### Celery task (`app/tasks/suggest_tasks.py`)
`fetch_suggest_keywords(job_id)` with `soft_time_limit=300`:
1. Loads job, sets `status="running"`
2. Checks Redis cache — cache hit returns immediately without external calls
3. А-Я expansion for Yandex (proxy rotation, 200-500ms pause per letter, 30s pause on ban)
4. А-Я expansion for Google if `include_google=True` (no proxy)
5. Deduplicates and writes to Redis with `ex=SUGGEST_CACHE_TTL`
6. Updates job status: `complete | partial | failed`

## Test Results

- `tests/test_suggest_service.py`: **18 tests passed** (fetch functions, cache key, deduplication)
- `tests/test_suggest_tasks.py`: **11 tests passed** (cache hit, alphabet iteration, dedup, proxy exhaustion, failure)
- Total: **29 tests**

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functions are fully implemented. Data flows from Redis/DB to task result.

## Self-Check: PASSED

- `app/models/suggest_job.py` — FOUND (080b28f)
- `app/services/suggest_service.py` — FOUND (080b28f)
- `app/tasks/suggest_tasks.py` — FOUND (2de65c0)
- `alembic/versions/0040_add_suggest_jobs.py` — FOUND (080b28f)
- `tests/test_suggest_service.py` — 18 passed
- `tests/test_suggest_tasks.py` — 11 passed
