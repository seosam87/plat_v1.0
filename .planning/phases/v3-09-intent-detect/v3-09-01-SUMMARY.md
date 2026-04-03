---
phase: v3-09
plan: "01"
subsystem: intent-detection
tags: [intent, serp, celery, playwright, proxy]
depends_on:
  requires: [proxy_serp_service, serp_analysis_service, cluster model]
  provides: [intent_service, intent router, batch intent detection UI]
  affects: [clusters page, keyword cluster intent field]
tech-stack:
  added: []
  patterns: [pure-function SERP analysis, Celery batch task with asyncio loop, HTMX-free JS fetch UI]
key-files:
  created:
    - app/routers/intent.py
    - app/templates/intent/index.html
  modified:
    - app/main.py
    - app/templates/clusters/index.html
decisions:
  - intent router uses /intent/{site_id} prefix consistent with gap/architecture pattern
  - bulk-confirm skips mixed intent proposals (only commercial/informational are auto-confirmed)
  - proposals loaded from SERP cache (use_cache=True) for UI display; async Celery task handles fresh parsing
  - confidence color: green >=80%, yellow 60-80%, red <60%
metrics:
  duration: "3 min"
  completed: "2026-04-03"
  tasks_completed: 5
  files_changed: 4
---

# Phase v3-09 Plan 01: Intent Auto-Detect — full phase Summary

Proxy-enabled SERP parser, intent detection service, batch Celery task, and semi-auto review UI — all implemented in a single plan. Intent is inferred from SERP TOP-10 commercial/informational site ratio, with confidence scoring and per-keyword confirm/skip workflow.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 01 | Proxy/anticaptcha config + proxy_serp_service.py | pre-existing (aebd70a era) | app/config.py, app/services/proxy_serp_service.py |
| 02 | intent_service.py | pre-existing (aebd70a era) | app/services/intent_service.py |
| 03 | Celery batch intent task | pre-existing (aebd70a era) | app/tasks/intent_tasks.py, app/celery_app.py |
| 04 | Intent router + UI page | aab0567 | app/routers/intent.py, app/templates/intent/index.html, app/main.py, app/templates/clusters/index.html |
| 05 | Unit tests (6 tests, all pass) | pre-existing (aebd70a era) | tests/test_intent_service.py |

## Decisions Made

- Intent router uses `/intent/{site_id}` prefix, consistent with gap/architecture/bulk pattern
- `bulk_confirm_intents` skips mixed proposals — only non-ambiguous intents are auto-applied
- UI loads proposals via `/intent/{site_id}/proposals` (cache-first) after triggering the Celery task
- Celery batch task uses `asyncio.new_event_loop()` pattern consistent with other tasks in the project
- Detection thresholds: commercial >= 7 → commercial, informational >= 7 → informational, else mixed

## Deviations from Plan

### Pre-implemented Tasks

**Tasks 01, 02, 03, 05 were already implemented** (in the `aebd70a` commit era) before this plan execution began. The plan executor verified their correctness against acceptance criteria and only implemented the missing Task 04 (router + UI).

- All acceptance criteria verified passing with env-var injection
- 6 unit tests pass: `python -m pytest tests/test_intent_service.py -x -q` → 6 passed in 0.02s

## Known Stubs

None. All intent detection logic is wired to real SERP parsing (with cache fallback). The UI proposals table loads live data via fetch.

## Self-Check: PASSED

- app/routers/intent.py: FOUND
- app/templates/intent/index.html: FOUND
- Commit aab0567: FOUND (git log confirms)
- Template contains "Определение интента": FOUND
- 6 tests pass: CONFIRMED
