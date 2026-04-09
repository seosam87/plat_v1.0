---
phase: 20-client-crm
plan: 02
subsystem: router-ui
tags: [fastapi, htmx, jinja2, crm, crud]

requires:
  - 20-01 (Client models and service layer)
provides:
  - CRM router with 6 endpoints (list, new modal, edit modal, create, update, delete)
  - Client list page with search, manager filter, date range filter, pagination
  - Create/edit client modal with 8 form fields
  - CRM sidebar navigation entry with user-group icon
affects: [20-03, 20-04]

tech-stack:
  added: []
  patterns:
    - "HTMX partial swap pattern for table filtering (_client_rows.html partial)"
    - "Modal form pattern: hx-post/hx-put with HX-Trigger response headers for toast + close + refresh"

key-files:
  created:
    - app/routers/crm.py
    - app/templates/crm/index.html
    - app/templates/crm/_modal_client.html
    - app/templates/crm/_client_rows.html
  modified:
    - app/main.py
    - app/navigation.py
    - app/templates/components/sidebar.html
    - app/template_engine.py

key-decisions:
  - "Separate _client_rows.html partial for HTMX table body swap instead of block_name approach"
  - "Delete endpoint returns refreshed table body directly instead of HX-Trigger only"
  - "log_action called with detail dict (matching actual API) not string"

patterns-established:
  - "CRM HTMX partial pattern: partial=true query param triggers _rows.html response"
  - "CRM modal pattern: GET fragment -> #modal-container, form submit hx-swap=none with HX-Trigger headers"

requirements-completed: [CRM-01, CRM-02, CRM-06]

duration: 3min
completed: 2026-04-09
---

# Plan 20-02: CRM Router & Client List UI Summary

**CRM router with 6 endpoints, client list page with HTMX search/filter/date-range/pagination, and create/edit modal with all 8 form fields.**

## What Was Built

1. **CRM Router** (`app/routers/crm.py`): 6 HTTP endpoints for client CRUD:
   - GET /ui/crm/clients -- paginated list with search, manager filter, date range filter (D-14)
   - GET /ui/crm/clients/new -- create modal fragment
   - GET /ui/crm/clients/{id}/edit -- edit modal fragment
   - POST /ui/crm/clients -- create client with audit logging
   - PUT /ui/crm/clients/{id} -- update client with audit logging
   - DELETE /ui/crm/clients/{id} -- soft delete with audit logging

2. **Client List Page** (`app/templates/crm/index.html`): Full-featured list page with:
   - Search input (keyup 300ms delay HTMX trigger)
   - Manager dropdown filter
   - Date created range filter (created_from/created_to) per D-14
   - All filters cross-include each other via hx-include for combined filtering
   - Pagination with Prev/Next buttons
   - Empty state using empty_state macro
   - Modal container div for HTMX fragment injection

3. **Table Rows Partial** (`app/templates/crm/_client_rows.html`): Swappable table body rows for HTMX partial updates on search/filter/paginate.

4. **Create/Edit Modal** (`app/templates/crm/_modal_client.html`): Modal overlay with form containing: company_name (required), legal_name, inn, kpp, phone, email, manager_id dropdown, notes textarea. ESC key handler, backdrop click close.

5. **Navigation**: CRM section added to sidebar between keyword-suggest and settings with user-group icon SVG. Help module mapping added for /ui/crm prefix.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Added _client_rows.html partial template**
- **Found during:** Task 2
- **Issue:** Plan specified table body within index.html but HTMX partial swap needs a separate template file
- **Fix:** Created _client_rows.html as a reusable partial included by both index.html and returned directly for partial requests
- **Files created:** app/templates/crm/_client_rows.html

**2. [Rule 1 - Bug] Corrected log_action parameter name**
- **Found during:** Task 1
- **Issue:** Plan used `details=f"Created client..."` but actual API signature uses `detail` (dict type)
- **Fix:** Used `detail={"company_name": client.company_name}` matching actual audit_service.log_action signature
- **Files modified:** app/routers/crm.py

**3. [Rule 1 - Bug] Corrected import path for get_db**
- **Found during:** Task 1
- **Issue:** Plan suggested `from app.database import get_db` but actual import path is `from app.dependencies import get_db`
- **Fix:** Used correct import path matching existing routers
- **Files modified:** app/routers/crm.py

## Known Stubs

None -- all data flows are wired to the service layer from Plan 20-01.

## Self-Check: PASSED

- [x] app/routers/crm.py exists
- [x] app/templates/crm/index.html exists
- [x] app/templates/crm/_modal_client.html exists
- [x] app/templates/crm/_client_rows.html exists
- [x] Commit b87b347 (Task 1) exists
- [x] Commit b854861 (Task 2) exists
