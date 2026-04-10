---
phase: 28-positions-traffic
plan: "01"
subsystem: mobile-positions
tags: [mobile, positions, htmx, celery, jinja2]
dependency_graph:
  requires:
    - app/models/keyword_latest_position.py
    - app/models/keyword.py
    - app/tasks/position_tasks.py
    - app/templates/mobile/partials/task_form.html
    - app/services/mobile_digest_service.py
  provides:
    - app/services/mobile_positions_service.py
    - app/routers/mobile.py (positions endpoints)
    - app/templates/mobile/positions.html
    - app/templates/mobile/partials/position_card.html
    - app/templates/mobile/partials/position_progress.html
  affects:
    - app/routers/mobile.py
    - app/tasks/position_tasks.py
    - app/templates/mobile/partials/task_form.html
tech_stack:
  added: []
  patterns:
    - async SQLAlchemy JOIN query (keyword_latest_positions + keywords)
    - HTMX polling every 3s with outerHTML swap for progress tracking
    - Celery update_state(PROGRESS) for granular task progress
    - Redis setex for task_id TTL storage (10 min)
    - Parameterized Jinja2 partial (task_form post_url with default filter)
key_files:
  created:
    - app/services/mobile_positions_service.py
    - app/templates/mobile/positions.html
    - app/templates/mobile/partials/position_card.html
    - app/templates/mobile/partials/position_progress.html
  modified:
    - app/routers/mobile.py
    - app/tasks/position_tasks.py
    - app/templates/mobile/partials/task_form.html
decisions:
  - "Use Redis setex(600) for position_check:{site_id} task_id rather than DB record — ephemeral, TTL-managed, no schema change needed"
  - "Jinja2 Environment + FileSystemLoader for HTMX partial rendering of positions list (avoids TemplateResponse overhead for innerHTML swap)"
  - "Self-contained _render_positions_list() helper in router for HX-Request partial responses"
metrics:
  duration: 12
  completed_date: "2026-04-10"
  tasks_completed: 2
  files_changed: 7
---

# Phase 28 Plan 01: Mobile Positions Page Summary

**One-liner:** Mobile /m/positions page with async position service, HTMX polling progress, keyword cards with delta chips, dropped-only tab, and task creation from dropped keywords.

## What Was Built

### Task 1: Service layer + Celery progress + task_form refactor
**Commit:** `50f0bd8`

- Created `app/services/mobile_positions_service.py` with `get_mobile_positions()` — async SQLAlchemy query on `keyword_latest_positions` JOIN `keywords`, supporting `period_days`, `dropped_only`, and `limit` filters, ordered by `abs(delta) DESC NULLSLAST`.
- Added `self_task.update_state(state='PROGRESS', meta={'checked': i+1, 'total': len(keywords)})` per-keyword in `_check_via_xmlproxy` loop. Added `self_task` parameter to `_check_via_dataforseo` with final PROGRESS emit after batch.
- Refactored `task_form.html` `hx-post` to use `{{ post_url | default('/m/health/' ~ site_id ~ '/tasks') }}` — backward-compatible default preserves existing health page usage.

### Task 2: Router endpoints + templates for /m/positions
**Commit:** `935b7c5`

Added 5 endpoints to `app/routers/mobile.py`:
- `GET /m/positions` — full page + HTMX partial for `#positions-list` refresh
- `POST /m/positions/check` — triggers `check_positions.delay()`, stores `task_id` in Redis, returns progress partial
- `GET /m/positions/check/status` — polls Celery `AsyncResult`, returns running/done/error state
- `GET /m/positions/{site_id}/task-form` — returns `task_form.html` with `post_url=/m/positions/{site_id}/tasks`
- `POST /m/positions/{site_id}/tasks` — creates `SeoTask(manual)` from positions page

Created 3 templates:
- `positions.html` — extends `base_mobile.html`, `active_tab='positions'`, site+period filter dropdowns, all/dropped tabs, "Запустить проверку" CTA, `#check-progress-slot`, `#positions-list`, `#task-form-slot`
- `position_card.html` — keyword row with phrase, position badge (gray), delta chip (green/red/new), engine, date, conditional "Создать задачу" button (dropped tab only)
- `position_progress.html` — 3 states: running (HTMX polling every 3s + progress bar), done (no polling + "Показать результаты" button), error (retry button)

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Redis setex(600) for task_id storage | Ephemeral data — 10-min TTL sufficient; no DB schema change needed |
| _render_positions_list() helper for HX-Request | Jinja2 Environment FileSystemLoader renders partial HTML without full TemplateResponse overhead; keeps partial swaps clean |
| self_task parameter added to _check_via_dataforseo | Consistent with _check_via_xmlproxy pattern; needed for PROGRESS emit; minimal API surface change |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all data flows are wired. The positions list renders real data from `keyword_latest_positions`. Empty states are clearly labeled (no fake data).

## Self-Check: PASSED
