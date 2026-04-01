---
phase: v3-01
plan: "03"
subsystem: api
tags: [fastapi, metrika, router, htmx, celery, pydantic]

# Dependency graph
requires:
  - phase: v3-01-01
    provides: MetrikaTrafficDaily, MetrikaTrafficPage, MetrikaEvent models and migrations
  - phase: v3-01-02
    provides: metrika_service functions, fetch_metrika_data Celery task, crypto_service

provides:
  - FastAPI router for all 8 Metrika endpoints under /metrika prefix
  - GET /metrika/{site_id} — HTML dashboard page
  - POST /metrika/{site_id}/fetch — Celery task dispatch
  - GET /metrika/{site_id}/daily — daily traffic JSON
  - GET /metrika/{site_id}/pages — per-page traffic JSON
  - GET /metrika/{site_id}/compare — period delta with is_new/is_lost
  - POST /metrika/{site_id}/events — HTMX partial response
  - DELETE /metrika/{site_id}/events/{event_id} — HTMX swap
  - PUT /metrika/{site_id}/settings — token encryption + save
  - Pydantic schemas: MetrikaSettingsUpdate, MetrikaFetchRequest
  - Router registered in main.py with /ui/metrika help module mapping

affects: [v3-01-04, v3-01-05, templates, frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HTMX partial response from POST endpoint returning HTMLResponse"
    - "Form body parsed via request.form() for HTMX form posts"
    - "Celery task dispatch with .delay() returning task.id for polling"
    - "Fernet encryption applied at router boundary before saving token"

key-files:
  created:
    - app/routers/metrika.py
  modified:
    - app/main.py

key-decisions:
  - "Events endpoint reads form body via request.form() rather than Pydantic JSON schema (HTMX sends multipart/form-data)"
  - "Token is encrypted with crypto_service.encrypt() at router boundary, not in service layer"
  - "Default fetch range: 90 days back to yesterday; dashboard display defaults to last 30 days"

patterns-established:
  - "HTMX form endpoints: use request.form() + return HTMLResponse with rendered partial"
  - "Site lookup helper _get_site_or_404() extracted to avoid repetition across endpoints"

requirements-completed: []

# Metrics
duration: 8min
completed: 2026-04-01
---

# Phase v3-01 Plan 03: Metrika Router and main.py Registration Summary

**FastAPI router delivering 8 Metrika endpoints (dashboard page, fetch trigger, daily/page/compare JSON, events CRUD, settings) with Celery dispatch, Fernet token encryption, and HTMX partial responses**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-01T21:10:00Z
- **Completed:** 2026-04-01T21:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `app/routers/metrika.py` with all 8 endpoints covering the full Metrika API surface
- Registered metrika router in `app/main.py` alongside existing routers
- Added `/ui/metrika` → `"metrika"` to `_HELP_MODULE_MAP` for context-aware help injection
- All endpoints gated behind `require_admin` dependency
- Settings endpoint encrypts OAuth token via Fernet before persisting to Site model

## Task Commits

Each task was committed atomically:

1. **Task 01: Create metrika router with all endpoints** - `c7dadbb` (feat)
2. **Task 02: Register metrika router in main.py** - `8a3fb11` (feat)

## Files Created/Modified
- `app/routers/metrika.py` — New router: 8 endpoints, 2 Pydantic schemas, _get_site_or_404 helper
- `app/main.py` — Added metrika_router import, include_router call, help module map entry

## Decisions Made
- Events `POST` endpoint reads form data via `request.form()` rather than a JSON Pydantic schema. HTMX sends `multipart/form-data` from HTML forms, so JSON body parsing would fail.
- Fernet encryption is applied at the router boundary in the settings endpoint rather than in the service layer, keeping the service layer pure and crypto-agnostic.
- Default date range for fetch trigger is 90 days ago to yesterday; the dashboard page loads last 30 days by default for performance.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required for this plan.

## Next Phase Readiness
- Full API surface established; templates (Plan 04) and widgets (Plan 05) can now consume these endpoints
- `/metrika/{site_id}` HTML endpoint requires `metrika/index.html` and `metrika/_events_list.html` templates to be created in Plan 04
- All JSON endpoints are ready for HTMX `hx-get` wiring

---
*Phase: v3-01*
*Completed: 2026-04-01*
