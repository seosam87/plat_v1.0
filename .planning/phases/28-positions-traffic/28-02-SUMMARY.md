---
phase: 28-positions-traffic
plan: "02"
subsystem: mobile-traffic
tags: [mobile, traffic, metrika, htmx, jinja2]
dependency_graph:
  requires: [28-01]
  provides: [mobile-traffic-page, traffic-comparison-service]
  affects: [app/routers/mobile.py]
tech_stack:
  added: []
  patterns: [cache-then-fetch, htmx-partial-swap, period-preset-pills, tappable-rows]
key_files:
  created:
    - app/services/mobile_traffic_service.py
    - app/templates/mobile/traffic.html
    - app/templates/mobile/partials/traffic_content.html
    - app/templates/mobile/partials/traffic_summary.html
    - app/templates/mobile/partials/traffic_page_row.html
  modified:
    - app/routers/mobile.py
decisions:
  - "Used page_url key (not url) from compute_period_delta — matches actual metrika_service output"
  - "Created traffic_content.html partial for HTMX innerHTML swap instead of inline conditional in traffic.html"
  - "Used active_tab='more' since bottom nav has no traffic tab — closest overflow tab"
metrics:
  duration: 2
  completed_date: "2026-04-10"
  tasks_completed: 2
  files_changed: 6
---

# Phase 28 Plan 02: Mobile Traffic Page Summary

Mobile traffic comparison page: Metrika per-page delta between two periods with period preset pills, summary card, and tappable page rows for task creation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Traffic comparison service layer | 6ac1cd5 | app/services/mobile_traffic_service.py |
| 2 | Router endpoints + templates for /m/traffic | 11740af | app/routers/mobile.py, 4 templates |

## What Was Built

**Service layer (`mobile_traffic_service.py`):**
- `_period_dates(preset)` — sync helper returning ((a_start, a_end), (b_start, b_end)) for 3 presets
- `get_traffic_comparison()` — async orchestrator with DB cache-then-Metrika-API fetch, drops-first sort, 50-page limit
- `PERIOD_PRESETS` — dict of preset keys to Russian labels for templates

**Router (`/m/traffic`):**
- `GET /m/traffic` — full page + HTMX partial refresh (returns `traffic_content.html` on HX-Request)
- `GET /m/traffic/{site_id}/task-form` — inline task form fragment with parameterized `post_url`
- `POST /m/traffic/{site_id}/tasks` — create manual SEO task, returns 201

**Templates:**
- `traffic.html` — page with site selector, period pill group (3 presets), `#traffic-content` div, `#task-form-slot`
- `traffic_content.html` — HTMX swap target: no_metrika warning / error state / summary+list / empty state
- `traffic_summary.html` — total_a vs total_b with delta_pct in red/green
- `traffic_page_row.html` — min-h-[44px] tappable row loading task form on tap, visits_delta badge

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used `page_url` key instead of `url` in templates**
- **Found during:** Task 2
- **Issue:** Plan showed `page.url` in template code but `compute_period_delta` actually returns `page_url` key (confirmed in metrika_service.py lines 399, 407)
- **Fix:** Used `page.page_url` in traffic_page_row.html
- **Files modified:** app/templates/mobile/partials/traffic_page_row.html

**2. [Rule 2 - Missing functionality] Added `traffic_content.html` partial**
- **Found during:** Task 2
- **Issue:** HTMX target `#traffic-content` needed a reusable partial for both full-page include and HTMX partial swap responses
- **Fix:** Created `traffic_content.html` as a separate partial; included in `traffic.html` and returned directly on HX-Request
- **Files modified:** app/templates/mobile/partials/traffic_content.html (new)

**3. [Rule 2 - Missing functionality] Added `logger` import to mobile.py**
- **Found during:** Task 2
- **Issue:** New traffic endpoint uses `logger.error()` but loguru logger was not imported in mobile.py
- **Fix:** Added `from loguru import logger` import
- **Files modified:** app/routers/mobile.py

## Known Stubs

None — all data flows are wired to real services (metrika_service.py, DB cache).

## Self-Check: PASSED

Files exist:
- app/services/mobile_traffic_service.py: FOUND
- app/templates/mobile/traffic.html: FOUND
- app/templates/mobile/partials/traffic_content.html: FOUND
- app/templates/mobile/partials/traffic_summary.html: FOUND
- app/templates/mobile/partials/traffic_page_row.html: FOUND
- app/routers/mobile.py: FOUND (modified)

Commits exist:
- 6ac1cd5: feat(28-02): add mobile traffic comparison service
- 11740af: feat(28-02): add /m/traffic router endpoints and templates
