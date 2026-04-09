---
phase: 20-client-crm
plan: 04
subsystem: router-ui
tags: [fastapi, htmx, jinja2, crm, site-linking, bidirectional]

requires:
  - 20-01 (CRM models, service layer with attach_site/detach_site/list_unattached_sites)
  - 20-02 (CRM router base)
  - 20-03 (Client detail page with tabs)
provides:
  - Bidirectional site-client linking from both client detail and site detail pages
  - Sites tab content on client detail page with HTMX search dropdown and attach/detach
  - Client badge and assign/unassign dropdown on site detail page
affects: []

tech-stack:
  added: []
  patterns:
    - "HTMX search dropdown: keyup delay:300ms triggers search, click attaches and refreshes parent"
    - "Bidirectional entity linking: same service functions called from two different page contexts"

key-files:
  created:
    - app/templates/crm/_sites_tab.html
    - app/templates/crm/_site_search_results.html
  modified:
    - app/routers/crm.py
    - app/templates/crm/detail.html
    - app/main.py
    - app/templates/sites/detail.html

key-decisions:
  - "Client assign endpoint placed in main.py (not sites.py) because site detail page is served from main.py"
  - "Site search dropdown positioned absolutely below search input for overlay effect"
  - "HX-Redirect used after client assignment to refresh full site detail page"

patterns-established:
  - "HTMX search-and-select dropdown: search input triggers partial, clicking result fires POST and refreshes container"
  - "Bidirectional linking UI: badge (read-only link) + dropdown (editable) shown together"

requirements-completed: [CRM-03, CRM-07]

duration: 4min
completed: 2026-04-09
---

# Plan 20-04: Bidirectional Site-Client Linking Summary

**HTMX search dropdown for attaching sites on client card, client badge + assign dropdown on site detail page, completing bidirectional D-19 linking.**

## What Was Built

1. **Site Linking Endpoints** (`app/routers/crm.py`): 3 new endpoints added:
   - GET /clients/{id}/sites/search -- returns unattached sites matching query as clickable dropdown
   - POST /clients/{id}/sites/{sid}/attach -- attaches site, returns refreshed Sites tab
   - DELETE /clients/{id}/sites/{sid} -- detaches site with confirmation, returns refreshed Sites tab
   - All endpoints use audit logging and require manager_or_above auth

2. **Sites Tab Partial** (`app/templates/crm/_sites_tab.html`):
   - Search input with hx-trigger="keyup changed delay:300ms" for real-time site search
   - Attached sites table with URL link, connection status badge, and detach button with hx-confirm
   - Empty state with guidance text when no sites attached

3. **Site Search Results** (`app/templates/crm/_site_search_results.html`):
   - Absolute-positioned dropdown below search input
   - Each result is clickable (hx-post to attach) with hover highlight
   - "Нет доступных сайтов" message when no matches

4. **Client Badge on Site Detail** (`app/templates/sites/detail.html`):
   - Client badge (#eef2ff background) linking to /ui/crm/clients/{id} when attached
   - "Без клиента" badge when no client
   - Client-select dropdown with all non-deleted clients + save button (D-19)

5. **Client Assignment Endpoint** (`app/main.py`):
   - POST /ui/sites/{id}/client handles both assign (valid UUID) and unassign ("none")
   - ValueError catch for already-attached sites with Russian error toast
   - HX-Redirect to refresh page after successful assignment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Client assign endpoint moved from sites.py to main.py**
- **Found during:** Task 2
- **Issue:** sites.py router has prefix="/sites" but site detail page is at /ui/sites/{id} served from main.py. Placing endpoint in sites.py would produce wrong URL path (/sites/ui/sites/{id}/client)
- **Fix:** Placed POST /ui/sites/{id}/client endpoint in main.py alongside the existing site detail endpoint, using _get_current_user_from_cookie pattern for auth
- **Files modified:** app/main.py

## Known Stubs

- Sites tab "Открытых задач" column shows "--" placeholder. The open task count per-site is not computed in the attach/detach endpoints. This is cosmetic only and can be wired in a future iteration when task counts are needed per-site on the CRM view.

## Self-Check: PASSED
