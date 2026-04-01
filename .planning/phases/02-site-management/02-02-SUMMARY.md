---
phase: 02-site-management
plan: "02"
subsystem: ui
tags: [jinja2, htmx, httpx, wp-rest-api, fastapi, respx]

requires:
  - phase: 02-01
    provides: Site model, site_service.get_decrypted_password, site_service.set_connection_status, site_service.get_sites, require_admin

provides:
  - wp_service.verify_connection — async httpx WP REST verification with Basic Auth
  - POST /sites/{id}/verify — returns HTML status badge fragment (HTMX target)
  - GET /ui/sites — Jinja2 HTML page listing all sites with status badges and verify buttons
  - base.html Jinja2 base template with HTMX 2.0 CDN

affects:
  - 02-03 (enable/disable toggle visible in same UI)
  - All future UI phases (base.html is the layout foundation)

tech-stack:
  added: [jinja2>=3.1 (was missing from requirements.txt)]
  patterns:
    - HTMX verify pattern — button sends hx-post, server returns HTML fragment swapped into #status-{id}
    - wp_service decrypts password at call time via get_decrypted_password; never logs plain text
    - /ui/* routes return HTMLResponse via Jinja2Templates; API routes remain JSON

key-files:
  created:
    - app/services/wp_service.py
    - app/templates/base.html
    - app/templates/sites/index.html
    - tests/test_wp_service.py
  modified:
    - app/routers/sites.py (verify_site endpoint + _status_badge helper)
    - app/main.py (Jinja2Templates, get_db import, /ui/sites route)
    - requirements.txt (jinja2 added)

key-decisions:
  - "verify endpoint returns HTML fragment (not JSON) for HTMX inline swap — keeps verify interactive without full page reload"
  - "status badge CSS class is badge-{connection_status} — template drives styling, not inline style attr"
  - "Jinja2Templates directory set to app/templates (relative to workdir /app) — consistent with uvicorn cwd"

requirements-completed: [SITE-01, SITE-04]

duration: 3min
completed: 2026-04-01
---

# Phase 02 Plan 02: WP REST Verification + Jinja2/HTMX UI Summary

**WP Application Password verification via httpx Basic Auth and HTMX-powered site management page with live status updates**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-01T06:54:41Z
- **Completed:** 2026-04-01T06:58:30Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- `wp_service.verify_connection()` hits `/wp-json/wp/v2/users/me` with Basic Auth; handles 200/non-200/network errors; password never logged
- `POST /sites/{id}/verify` stores updated connection_status and returns HTML badge fragment for HTMX swap
- Jinja2 base template with HTMX 2.0 CDN, nav, CSS for badges and buttons
- Sites management page with per-row Verify button (HTMX hx-post, inline status update)
- 30 total tests passing (3 wp_service + 4 sites CRUD + 3 crypto + prior phase tests)

## Task Commits

1. **Test: wp_service failing tests** - `842ac5a` (test — TDD RED)
2. **Task 1: wp_service + verify endpoint** - `96ef586` (feat — TDD GREEN)
3. **Task 2: templates + UI route** - `0c921ee` (feat)

## Files Created/Modified

- `app/services/wp_service.py` — verify_connection with httpx + Basic Auth
- `app/routers/sites.py` — _status_badge helper + POST /{site_id}/verify endpoint
- `app/templates/base.html` — HTMX 2.0, nav, CSS, Jinja2 block layout
- `app/templates/sites/index.html` — sites table with status badges and HTMX verify buttons
- `app/main.py` — Jinja2Templates setup + GET /ui/sites
- `requirements.txt` — jinja2>=3.1 added
- `tests/test_wp_service.py` — 3 tests with respx mocking

## Decisions Made

- Verify endpoint returns HTML fragment (not JSON) for seamless HTMX swap without page reload
- `badge-{connection_status}` CSS pattern lets CSS handle colour — cleaner than inline styles in fragment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] jinja2 not in requirements.txt**
- **Found during:** Task 2 (templates + UI route)
- **Issue:** `AssertionError: jinja2 must be installed to use Jinja2Templates` when importing app.main
- **Fix:** Added `jinja2>=3.1,<4.0` to requirements.txt; pip-installed in running container
- **Files modified:** requirements.txt
- **Verification:** 30 tests pass after install
- **Committed in:** 0c921ee (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact:** Necessary dependency addition; no scope change.

## Issues Encountered

None — all tests passed after the jinja2 install.

## Next Phase Readiness

- 02-03 can add enable/disable toggle to the existing sites table in `sites/index.html`
- `wp_service` is available for import by the Celery task guard in 02-03
- All 30 tests green; base UI foundation established

---
*Phase: 02-site-management*
*Completed: 2026-04-01*
