---
phase: v3-01
plan: "04"
subsystem: ui
tags: [htmx, chart.js, jinja2, sparkline, metrika, widget]

requires:
  - phase: v3-01-01
    provides: MetrikaTrafficDaily model and DB schema
  - phase: v3-01-02
    provides: metrika_service.get_daily_traffic, get_page_traffic, get_events
  - phase: v3-01-03
    provides: metrika router with 8 endpoints and metrika/index.html template

provides:
  - HTMX lazy-load widget partial (metrika/_widget.html) for site overview
  - GET /metrika/{site_id}/widget endpoint returning traffic summary
  - GET /ui/metrika and GET /ui/metrika/{site_id} UI routes in main.py
  - "Трафик" quick action button in site detail page
  - Metrika widget injected into site overview card grid

affects: [v3-01-05, any phase touching site detail page or main.py UI routes]

tech-stack:
  added: []
  patterns:
    - "HTMX lazy load pattern: hx-get + hx-trigger=load for async widget injection"
    - "UI routes in main.py (not in routers) to avoid prefix collision"
    - "Widget partial returns empty HTMLResponse when Metrika not configured (no empty card)"

key-files:
  created:
    - app/templates/metrika/_widget.html
    - .planning/phases/v3-01-yandex-metrika/v3-01-04-SUMMARY.md
  modified:
    - app/routers/metrika.py
    - app/templates/sites/detail.html
    - app/main.py

key-decisions:
  - "UI routes /ui/metrika placed in main.py not metrika router — router prefix=/metrika would cause /metrika/ui/metrika path collision"
  - "Widget endpoint returns empty string (HTMLResponse) when site has no metrika_counter_id — keeps site detail page clean"
  - "Sparkline uses Chart.js 4.4.0 CDN already loaded by the page; no additional CDN registration needed"

patterns-established:
  - "HTMX widget lazy load: hx-get={endpoint} hx-trigger=load hx-swap=innerHTML"

requirements-completed: []

duration: 12min
completed: 2026-04-01
---

# Phase v3-01 Plan 04: Site Overview traffic widget and site detail integration Summary

**HTMX lazy-load Metrika traffic widget with 4 KPIs and 30-day sparkline injected into site detail page; /ui/metrika routes and Трафик quick action button added**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-01T21:13:29Z
- **Completed:** 2026-04-01T21:25:00Z
- **Tasks:** 4
- **Files modified:** 4 (3 modified + 1 created)

## Accomplishments

- Widget partial `metrika/_widget.html` with 4 KPI mini-metrics, 30-day sparkline (Chart.js, 80px, no axes/points, indigo line + 8% opacity fill), Russian copy per UI-SPEC
- Widget endpoint `GET /metrika/{site_id}/widget` returns empty for unconfigured sites, no-data state for configured-but-unfetched, full widget with sparkline for sites with data
- Site detail page integrates widget via HTMX lazy load and adds "Трафик" quick action button in sky blue (#0ea5e9)
- `/ui/metrika` and `/ui/metrika/{site_id}` routes added to `main.py` (correct pattern — avoids router prefix collision)

## Task Commits

1. **Task 01: Add widget endpoint to metrika router** - `31d7471` (feat)
2. **Task 02: Create widget partial template** - `fdb99cf` (feat)
3. **Task 03: Integrate widget and quick action into site detail page** - `d5c1596` (feat)
4. **Task 04: Add metrika UI route** - `61ceef6` (feat)

## Files Created/Modified

- `app/templates/metrika/_widget.html` — HTMX partial: KPI metrics row + Chart.js sparkline + no-data fallback state
- `app/routers/metrika.py` — Added `GET /{site_id}/widget` endpoint; import of site_service
- `app/templates/sites/detail.html` — HTMX widget lazy-load div after stats row; Трафик quick action button
- `app/main.py` — `GET /ui/metrika` and `GET /ui/metrika/{site_id}` UI routes

## Decisions Made

- `/ui/metrika` routes placed in `main.py` (not in `app/routers/metrika.py`) because the metrika router has `prefix="/metrika"`, which would make `@router.get("/ui/metrika")` resolve to `/metrika/ui/metrika` — a path collision. Following the existing pattern used by `/ui/positions` and `/ui/keywords`.
- Widget returns `HTMLResponse("")` (empty string) when site has no `metrika_counter_id` — the wrapping div in the site detail page collapses naturally, no empty card shown.
- UI-SPEC specifies fill as `rgba(79,70,229,0.08)` (8% opacity) for the sparkline; the main traffic chart uses `rgba(79,70,229,0.1)` (10%) — followed spec exactly for each context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed incorrectly placed /ui/metrika routes from metrika router**
- **Found during:** Task 04 verification
- **Issue:** Task 01 added `/ui/metrika` routes to the metrika router (prefix=/metrika), which would resolve to `/metrika/ui/metrika` — not the intended `/ui/metrika` path
- **Fix:** Removed those routes from the router; added correct `/ui/metrika` and `/ui/metrika/{site_id}` routes in `main.py` following the positions/keywords pattern
- **Files modified:** app/routers/metrika.py, app/main.py
- **Committed in:** 61ceef6 (Task 04 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking path conflict)
**Impact on plan:** Essential correction. Without this fix, `/ui/metrika` links in the site detail page would 404.

## Issues Encountered

None beyond the router prefix issue documented above.

## Known Stubs

None. The widget correctly handles all three states:
- No counter configured → empty HTMLResponse (invisible in page)
- Configured but no data → "Данные не загружены" state with settings link
- Has data → full widget with KPI metrics and sparkline

## Next Phase Readiness

- Site overview integration is complete; users can see traffic KPIs at a glance on any site detail page
- The `/ui/metrika/{site_id}` route renders `metrika/index.html` which was built in Plan 03
- Plan 05 (if any) can extend the traffic page or add additional Metrika features

---
*Phase: v3-01-yandex-metrika*
*Completed: 2026-04-01*
