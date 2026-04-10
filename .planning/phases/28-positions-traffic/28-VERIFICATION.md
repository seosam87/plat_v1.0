---
phase: 28-positions-traffic
verified: 2026-04-10T22:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 28: Positions + Traffic Verification Report

**Phase Goal:** Пользователь может запустить проверку позиций и сравнить трафик по двум периодам с телефона и создать задачи на просевшие данные
**Verified:** 2026-04-10T22:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | User opens /m/positions and sees keyword cards with position, delta, engine, date | VERIFIED | `positions.html` + `position_card.html` render data from `get_mobile_positions()` real DB query |
| 2  | User taps 'Запустить проверку' and Celery task starts, progress polls every 3s | VERIFIED | `POST /m/positions/check` calls `check_positions.delay()`, `position_progress.html` has `hx-trigger="every 3s"` |
| 3  | After check completes, user sees 'Показать результаты' button (not auto-refresh) | VERIFIED | Done-state in `position_progress.html` has no `hx-trigger`, shows "Показать результаты" button |
| 4  | User switches to 'Просевшие' tab and sees only keywords with negative delta | VERIFIED | `dropped_only=True` maps to `WHERE delta < 0` in service; tab wired via `hx-get="/m/positions"` with `tab=dropped` |
| 5  | User taps 'Создать задачу' on a dropped keyword and task is saved | VERIFIED | `GET /m/positions/{site_id}/task-form` loads form; `POST /m/positions/{site_id}/tasks` creates `SeoTask(manual)` |
| 6  | User opens /m/traffic and sees traffic comparison for selected site and period preset | VERIFIED | `GET /m/traffic` calls `get_traffic_comparison()` which fetches/caches Metrika data |
| 7  | User switches between three period presets and data updates via HTMX | VERIFIED | Period pill buttons use `hx-get="/m/traffic"`, `_period_dates()` verified for all 3 presets |
| 8  | User sees summary card with total traffic period A vs B and delta percentage | VERIFIED | `traffic_summary.html` renders `total_a`, `total_b`, `delta_pct` with red/green coloring |
| 9  | User sees per-page list sorted by biggest drops first | VERIFIED | `comparison.sort(key=lambda r: r["visits_delta"])` in service, ascending order = drops first |
| 10 | User taps a dropped page row and creates a task via task_form.html | VERIFIED | `traffic_page_row.html` row-level `hx-get` loads task form; `POST /m/traffic/{site_id}/tasks` creates task |
| 11 | Site without metrika_token shows 'Метрика не подключена' warning | VERIFIED | Router checks `not site.metrika_token or not site.metrika_counter_id`, `traffic_content.html` renders yellow warning card |

**Score:** 11/11 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/mobile_positions_service.py` | Async position queries for mobile | VERIFIED | 85 lines; real SQLAlchemy JOIN query; `abs(delta) DESC NULLSLAST` ordering |
| `app/templates/mobile/positions.html` | Positions page template | VERIFIED | 4225 bytes; `active_tab = 'positions'`; filter bar, tabs, CTA, progress slot |
| `app/templates/mobile/partials/position_card.html` | Single keyword card partial | VERIFIED | Contains `kw.delta`, green/red delta chips, "Создать задачу" conditional button |
| `app/templates/mobile/partials/position_progress.html` | HTMX-polled progress block | VERIFIED | 3 states: running (hx-trigger every 3s + progress bar), done ("Показать результаты"), error |
| `app/services/mobile_traffic_service.py` | Traffic comparison orchestration | VERIFIED | 132 lines; `_period_dates()`, `get_traffic_comparison()`, `PERIOD_PRESETS`; cache-then-fetch pattern |
| `app/templates/mobile/traffic.html` | Traffic page template | VERIFIED | Site selector, period pill group, `#traffic-content`, `#task-form-slot` |
| `app/templates/mobile/partials/traffic_summary.html` | Summary card partial | VERIFIED | `delta_pct` with conditional red/green coloring, `визитов` label |
| `app/templates/mobile/partials/traffic_page_row.html` | Per-page row partial | VERIFIED | `visits_delta` badge, tappable `hx-get` loading task form, `min-h-[44px]` |
| `app/templates/mobile/partials/traffic_content.html` | HTMX swap target | VERIFIED | Added as deviation from plan; handles no_metrika / error / data / empty states |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `positions.html` | `app/routers/mobile.py` | `hx-get="/m/positions"`, `hx-post="/m/positions/check"` | WIRED | 5 occurrences of hx-get/hx-post on positions routes |
| `app/routers/mobile.py` | `mobile_positions_service.py` | `await get_mobile_positions()` | WIRED | Import at line 301, call at line 317 |
| `app/routers/mobile.py` | `app/tasks/position_tasks.py` | `check_positions.delay(str(site_id))` | WIRED | Line 400 |
| `traffic.html` | `app/routers/mobile.py` | `hx-get="/m/traffic"` | WIRED | Lines 13, 31 |
| `app/routers/mobile.py` | `mobile_traffic_service.py` | `await get_traffic_comparison()` | WIRED | Import at line 531, call at line 550 |
| `mobile_traffic_service.py` | `app/services/metrika_service.py` | `compute_period_delta(rows_a, rows_b)` | WIRED | Import at line 15, call at line 116 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `positions.html` / `position_card.html` | `positions` list | `get_mobile_positions()` → `SELECT … JOIN keyword_latest_positions, keywords WHERE site_id=…` | Yes — real DB query via `AsyncSession` | FLOWING |
| `position_progress.html` | `checked`, `total`, `status` | `celery_app.AsyncResult(task_id)` + `result.info` from `update_state(PROGRESS)` | Yes — live Celery state via Redis | FLOWING |
| `traffic_summary.html` | `comparison.total_a`, `total_b`, `delta_pct` | `get_traffic_comparison()` → `get_page_traffic()` (DB cache) or `fetch_page_traffic()` (Metrika API) | Yes — real DB or API data; no hardcoded fallback | FLOWING |
| `traffic_page_row.html` | `page.visits_delta`, `page.page_url` | `compute_period_delta(rows_a, rows_b)` from metrika_service | Yes — real delta computation | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Service imports cleanly | `python -c "from app.services.mobile_positions_service import get_mobile_positions"` | OK | PASS |
| Traffic service imports cleanly | `python -c "from app.services.mobile_traffic_service import get_traffic_comparison, PERIOD_PRESETS, _period_dates"` | OK | PASS |
| Period dates logic — all 3 presets | `_period_dates()` for each preset — non-overlapping, a < b | All 3 presets produce non-overlapping date ranges | PASS |
| All 8 new routes registered | Router introspection | GET/POST /positions, /positions/check, /positions/check/status, /positions/{id}/task-form, /positions/{id}/tasks, /traffic, /traffic/{id}/task-form, /traffic/{id}/tasks | PASS |
| Celery PROGRESS emission | `grep "update_state.*PROGRESS" app/tasks/position_tasks.py` | 2 matches (per-keyword + batch final) | PASS |
| Redis task_id storage | `grep "setex.*position_check" app/routers/mobile.py` | Line 405: `r.setex(f"position_check:{site_id}", 600, task.id)` | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| POS-01 | 28-01 | Пользователь может запустить проверку позиций для сайта с телефона | SATISFIED | `POST /m/positions/check` triggers `check_positions.delay()`; Redis stores task_id; progress page polls status |
| POS-02 | 28-01 | Пользователь видит результаты проверки: позиции, тренды, изменения за период | SATISFIED | `position_card.html` shows `position`, `delta` chip (green/red/new), `engine`, `checked_at`; period filter on service query |
| POS-03 | 28-01 | Пользователь может создать задачу на просевшие позиции прямо из результатов | SATISFIED | Dropped tab shows "Создать задачу" per card; `POST /m/positions/{site_id}/tasks` creates `SeoTask(manual)` |
| TRF-01 | 28-02 | Пользователь может сравнить трафик по сайту за два периода с телефона | SATISFIED | `GET /m/traffic` with 3 period presets; `get_traffic_comparison()` fetches/computes period A vs B |
| TRF-02 | 28-02 | Пользователь видит какие страницы просели/выросли и может создать ТЗ на просевшую | SATISFIED | `traffic_page_row.html` shows `visits_delta` badge; tappable row loads task form; `POST /m/traffic/{site_id}/tasks` creates task |

---

## Anti-Patterns Found

No anti-patterns detected in any of the 10 phase files. No TODO/FIXME/PLACEHOLDER comments, no empty return stubs, no hardcoded empty data passed to rendering paths.

---

## Human Verification Required

### 1. Position check full flow (phone UX)

**Test:** Open `/m/positions` on a mobile browser, select a site, tap "Запустить проверку", observe the progress bar and polling behavior, wait for completion, tap "Показать результаты"
**Expected:** Progress bar increments as Celery processes keywords; after completion the polling stops and results list refreshes
**Why human:** Requires a running app with Celery workers, Redis, and seeded keyword data; real-time polling behavior cannot be verified statically

### 2. Traffic comparison with live Metrika data

**Test:** Open `/m/traffic` on a site with `metrika_token` configured, switch between all 3 period presets
**Expected:** Each preset triggers HTMX swap of `#traffic-content`, shows correct period dates in summary card, page list sorted by drops
**Why human:** Requires a configured Metrika counter and live API token

### 3. No-Metrika warning display

**Test:** Open `/m/traffic` on a site with no Metrika token configured
**Expected:** Yellow "Метрика не подключена" card renders, no JS errors, no spinner
**Why human:** Requires a site record without `metrika_token` in DB

### 4. Task creation end-to-end

**Test:** On `/m/positions` (Просевшие tab), tap "Создать задачу" on a keyword, fill in the form, submit
**Expected:** Task form appears inline, form submits to `/m/positions/{site_id}/tasks`, task appears in the task list
**Why human:** Requires running app, DB with dropped keywords, and task list visibility to confirm persistence

---

## Deviations from Plan (Non-blocking)

| Deviation | Plan | Actual | Impact |
|-----------|------|--------|--------|
| `traffic_content.html` partial added | Not in 28-02-PLAN artifacts list | Created as new file for HTMX `innerHTML` swap of `#traffic-content` | Positive — cleaner template separation; backward-compatible |
| `active_tab='more'` for traffic page | Plan said "check base_mobile.html nav" | Used `more` (closest overflow tab in bottom nav) | No impact — bottom nav doesn't have a traffic tab |
| `page_url` key in templates | Plan showed `page.url` | Used `page.page_url` matching actual `compute_period_delta` output | Correct fix — would have caused `AttributeError` at render time |

---

## Summary

Phase 28 goal is fully achieved. All 11 observable truths are verified with substantive implementations and wired data flows. Both service files contain real async queries/API calls — no stubs. All 5 requirement IDs (POS-01 through POS-03, TRF-01 through TRF-02) are satisfied with clear implementation evidence. The 3 deviations from plan are all positive or correct fixes. Four human verification items remain for end-to-end behavioral confirmation in a running environment with real data.

---

_Verified: 2026-04-10T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
