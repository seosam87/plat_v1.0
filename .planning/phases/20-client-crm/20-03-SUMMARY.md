---
phase: 20-client-crm
plan: 03
subsystem: router-ui
tags: [fastapi, htmx, jinja2, crm, detail-page, contacts, interactions]

requires:
  - 20-01 (CRM models and service layer)
  - 20-02 (CRM router with client list)
provides:
  - Client detail page with tabbed layout (Sites, Contacts, Interactions, Info)
  - Contact CRUD endpoints with inline edit HTMX pattern
  - Interaction CRUD endpoints with ownership check
  - 4 Jinja2 templates (detail page + 3 partials)
affects: [20-04]

tech-stack:
  added: []
  patterns:
    - "HTMX inline row edit pattern: hx-get edit form -> hx-put save -> hx-get cancel (contact table)"
    - "HTMX prepend pattern: hx-post with hx-swap=afterbegin for newest-first interaction timeline"
    - "JS tab switching via classList + style.display toggle (no HTMX for tabs)"
    - "Interaction ownership check: author_id match or admin role for edit/delete"

key-files:
  created:
    - app/templates/crm/detail.html
    - app/templates/crm/_contact_row.html
    - app/templates/crm/_contact_edit.html
    - app/templates/crm/_interaction_entry.html
  modified:
    - app/routers/crm.py

key-decisions:
  - "authors_map dict passed to detail template for interaction author lookup -- avoids N+1 queries"
  - "Inline JS toggle for interaction edit instead of additional HTMX endpoint -- simpler for single-field edit"
  - "Empty state for contacts uses inline message + hidden table that shows on first add via JS"

patterns-established:
  - "CRM detail tab pattern: JS switchTab() with data-tab attributes and crm-tab-panel class"
  - "Hover-reveal actions: opacity:0 -> opacity:1 on parent :hover via CSS"

requirements-completed: [CRM-04, CRM-05, CRM-07]

duration: 3min
completed: 2026-04-09
---

# Plan 20-03: Client Detail Page with Contacts & Interactions Summary

**Client detail page with 4-tab layout, HTMX inline contact editing (row swap), interaction timeline with compose form and ownership-gated edit/delete.**

## What Was Built

1. **Router Endpoints** (`app/routers/crm.py`): 9 new endpoints added to existing CRM router:
   - GET /clients/{client_id} -- detail page assembling client, contacts, interactions, sites, counts, manager
   - POST/GET(edit)/GET(read)/PUT/DELETE for contacts under /clients/{id}/contacts/
   - POST/PUT/DELETE for interactions under /clients/{id}/interactions/
   - All contact mutations require manager_or_above auth
   - Interaction update/delete enforce ownership check (author_id match or admin role per D-10)

2. **Detail Page** (`app/templates/crm/detail.html`):
   - Header card: company name (text-xl 600), legal name, INN/KPP, phone/email, manager badge (#eef2ff), site count and task count chips
   - 4 tabs with JS switching: Sites (default active), Contacts, Interactions, Info
   - Sites tab: table of linked sites or empty state
   - Contacts tab: table with inline edit + add-contact compact form (2-col grid)
   - Interactions tab: compose textarea at top (afterbegin prepend), timeline below
   - Info tab: notes display, created/updated timestamps

3. **Contact Partials**:
   - `_contact_row.html`: read-mode table row with hover-reveal edit/delete actions
   - `_contact_edit.html`: inline form row replacing read row via outerHTML swap

4. **Interaction Partial** (`_interaction_entry.html`):
   - Date + author + edited marker, note text, hover-reveal edit/delete
   - Inline JS toggle for edit mode (textarea replaces note text)
   - Conditional edit/delete based on author_id or admin role

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Added authors_map for interaction display**
- **Found during:** Task 1
- **Issue:** Plan's detail endpoint didn't specify how to pass author User objects to interaction partial template
- **Fix:** Added authors_map dict (author_id -> User) prefetched in detail endpoint, passed to template context
- **Files modified:** app/routers/crm.py

**2. [Rule 1 - Bug] Service layer call signatures use keyword-only args**
- **Found during:** Task 1
- **Issue:** Service functions like create_contact use keyword-only args (after `*`), not positional dict
- **Fix:** Called service functions with explicit keyword arguments matching their signatures
- **Files modified:** app/routers/crm.py

## Known Stubs

None -- all data flows are wired to the service layer from Plan 20-01. Sites tab shows real linked sites from DB.

## Self-Check: PASSED

- [x] app/templates/crm/detail.html exists with 4 tab panels
- [x] app/templates/crm/_contact_row.html exists with hx-get
- [x] app/templates/crm/_contact_edit.html exists with hx-put
- [x] app/templates/crm/_interaction_entry.html exists with interaction display
- [x] app/routers/crm.py has 15 total route decorators (6 original + 9 new)
- [x] Commit e914363 (Task 1) exists
- [x] Commit fe25143 (Task 2) exists
