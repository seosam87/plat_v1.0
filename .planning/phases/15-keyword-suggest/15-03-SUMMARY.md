---
phase: 15-keyword-suggest
plan: 03
subsystem: keyword-suggest
tags: [wordstat, celery, credentials, position-check, yandex]
requires:
  - SuggestJob model and suggest cache key (Plan 15-01)
  - ServiceCredential Fernet encryption infrastructure
provides:
  - Yandex Wordstat frequency lookup service
  - fetch_wordstat_frequency Celery task
  - Encrypted yandex_direct OAuth token storage
  - Correct NULL-engine default (yandex) for position checks
affects:
  - app/tasks/position_tasks.py (engine default fallback)
tech-stack:
  added: [httpx sync client for Wordstat API]
  patterns: [per-phrase POST loop, 429 early-exit, respx mocking]
key-files:
  created:
    - app/services/wordstat_service.py
    - tests/test_wordstat_service.py
    - tests/test_position_engine_fix.py
  modified:
    - app/services/service_credential_service.py
    - app/tasks/suggest_tasks.py
    - app/tasks/position_tasks.py
decisions:
  - Wordstat iterates phrases one-by-one (safer rate handling over batch)
  - 429 returns partial results instead of raising
  - NULL keyword.engine defaults to yandex (user memory: NULL = Yandex)
metrics:
  duration_minutes: 5
  tasks: 2
  files: 6
  completed: 2026-04-07
---

# Phase 15 Plan 03: Wordstat + Position Engine Fix Summary

Wordstat API frequency lookup with encrypted OAuth token plus position-check NULL-engine default fix (google -> yandex).

## Tasks

### Task 1: Wordstat service + credential + Celery task
Commit: 8026772

- `app/services/wordstat_service.py`: `fetch_wordstat_frequency_sync` using httpx sync client, Bearer auth, per-phrase POST, 429 early return, per-phrase error tolerance.
- `ENCRYPTED_FIELDS["yandex_direct"] = ["token"]`.
- `fetch_wordstat_frequency` Celery task (bind, retry=3, default queue) loads job, reads token, fetches frequency, updates suggestions cache in-place.
- 7 tests via respx cover success, bearer header, 429 partial, mid-batch HTTPError, topRequests fallback, empty input, encrypted fields registry.

### Task 2: Position engine default fix
Commit: 50a0319

- Replaced both `if kw.engine else "google"` defaults in `_check_via_dataforseo` and `_check_via_serp_parser` with `"yandex"`.
- 7 regression tests in `tests/test_position_engine_fix.py`.

## Verification

- `pytest tests/test_wordstat_service.py`: 7 passed
- `pytest tests/test_position_engine_fix.py`: 7 passed
- `grep -c 'else "yandex"' app/tasks/position_tasks.py`: 2

## Deviations from Plan

None — plan executed as written. Proxy management todo review (Task 2 secondary note) was informational only; no infra changes needed.

## Self-Check: PASSED

- app/services/wordstat_service.py exists
- app/tasks/suggest_tasks.py has fetch_wordstat_frequency
- app/services/service_credential_service.py has yandex_direct
- Commits 8026772, 50a0319 present on master
