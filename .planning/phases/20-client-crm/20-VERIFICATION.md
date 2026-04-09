---
phase: 20-client-crm
verified: 2026-04-09T14:00:00Z
status: human_needed
score: 5/5 must-haves verified
re_verification: true
gaps:
  - truth: "User can create and edit a client card with company name, legal name, INN/KPP, phone, email, and notes -- and assign a manager to that client"
    status: resolved
    reason: "Fixed in commit 23f646b — changed create_client(db, data) to create_client(db, **data) and update_client(db, client_id, data) to update_client(db, client_id, **data)"
human_verification:
  - test: "Open /ui/crm/clients, verify table loads under 3 seconds with 100+ clients"
    expected: "Paginated table renders within 3 seconds"
    why_human: "Performance threshold requires real data volume and browser measurement"
  - test: "Open a client detail page, switch between all 4 tabs"
    expected: "All tabs switch smoothly, data displays correctly"
    why_human: "Visual layout and tab switching behavior"
  - test: "On site detail page, verify client badge links back to correct client card"
    expected: "Badge shows company name in purple chip, clicking navigates to /ui/crm/clients/{id}"
    why_human: "Visual styling and navigation flow"
---

# Phase 20: Client CRM Verification Report

**Phase Goal:** Users can create and manage client organisations with contacts, assigned manager, linked sites, and a chronological interaction log -- establishing the client entity as the anchor for all v3.0 downstream features
**Verified:** 2026-04-09
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can create and edit a client card with company name, legal name, INN/KPP, phone, email, and notes -- and assign a manager | FAILED | Router passes dict as positional arg to keyword-only service functions (lines 159, 191). Will raise TypeError at runtime. Modal form, service layer, and all 8 fields are correctly implemented. |
| 2 | User can attach and detach existing sites to a client record; each site can belong to at most one client | VERIFIED | attach_site/detach_site in service layer with conflict detection; Sites tab in detail.html with HTMX search dropdown; site detail page with client assign dropdown; bidirectional endpoints wired |
| 3 | User can add multiple contacts to a client (name, phone, email, role) and log dated interaction notes attributed to the current user | VERIFIED | Contact CRUD endpoints (POST/GET/PUT/DELETE) with inline edit pattern; Interaction CRUD with ownership check (author_id or admin); author attribution via current_user.id; all wired through HTMX partials |
| 4 | User can view a paginated client list with search and filter; results load under 3 seconds for 100+ clients | VERIFIED (automated portion) | Pagination with page/page_size in service layer; search by company_name/INN/email ILIKE; manager_id filter; date range filter; HTMX partial swap pattern; 3-second threshold needs human verification |
| 5 | User can open a client detail page showing attached sites, open tasks across those sites, and most recent interaction notes in chronological order | VERIFIED | Detail endpoint fetches client, contacts, interactions (DESC by interaction_date), sites, open_task_count, manager; 4-tab layout with Sites (default), Contacts, Interactions, Info tabs |

**Score:** 4/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models/client.py` | Client, ClientContact, ClientInteraction models | VERIFIED | 3 models with correct columns, FKs, UUID PKs, soft delete on Client |
| `alembic/versions/0043_add_crm_tables.py` | Migration for CRM tables | VERIFIED | Creates 3 tables + sites.client_id FK, correct revision chain 0042->0043, proper downgrade |
| `app/services/client_service.py` | Async service layer | VERIFIED | 16 functions: full CRUD for clients/contacts/interactions, pagination, search, site linking, task count |
| `tests/services/test_client_service.py` | Service tests | VERIFIED | 20 test functions, 489 lines, covers CRUD, search, filters, site attach/detach, task count |
| `app/routers/crm.py` | CRM HTTP endpoints | VERIFIED (with bug) | 18 route decorators covering list, detail, modals, CRUD, contacts, interactions, site linking. Bug in create/update dict passing. |
| `app/templates/crm/index.html` | Client list page | VERIFIED | Search, manager filter, date range filter, HTMX partial swap, pagination, modal container |
| `app/templates/crm/_modal_client.html` | Create/edit modal | VERIFIED | 8 form fields, hx-post/hx-put conditional, ESC key handler, backdrop close |
| `app/templates/crm/detail.html` | Client detail page | VERIFIED | 4-tab layout (Sites, Contacts, Interactions, Info), header with company info and manager badge |
| `app/templates/crm/_contact_row.html` | Contact read row | VERIFIED | Inline display with hover-reveal edit/delete actions, hx-get for edit form |
| `app/templates/crm/_contact_edit.html` | Contact edit form row | VERIFIED | Inline edit with hx-put, hx-include for form data, cancel via hx-get |
| `app/templates/crm/_interaction_entry.html` | Interaction log entry | VERIFIED | Date, author, edited marker, inline JS toggle for edit, ownership-gated actions |
| `app/templates/crm/_sites_tab.html` | Sites tab partial | VERIFIED | Search input with HTMX dropdown, attached sites table, detach with confirm |
| `app/templates/crm/_site_search_results.html` | Site search dropdown | VERIFIED | Clickable results with hx-post to attach, empty state message |
| `app/models/site.py` | client_id FK column | VERIFIED | `client_id` with ForeignKey("clients.id", ondelete="SET NULL") |
| `app/models/__init__.py` | CRM model imports | VERIFIED | Imports Client, ClientContact, ClientInteraction |
| `app/templates/sites/detail.html` | Client badge on site page | VERIFIED | Client badge with link to /ui/crm/clients/{id}, assign dropdown with all clients |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| app/models/client.py | app.database.Base | `from app.database import Base` | WIRED | Line 11 |
| app/models/site.py | clients table | client_id FK | WIRED | ForeignKey("clients.id", ondelete="SET NULL") at line 39 |
| app/services/client_service.py | app/models/client.py | model imports | WIRED | Line 8: `from app.models.client import Client, ClientContact, ClientInteraction` |
| app/routers/crm.py | app/services/client_service.py | service calls | WIRED | `client_service.` used throughout for all CRUD operations |
| app/main.py | app/routers/crm.py | include_router | WIRED | Line 174: `app.include_router(crm_router)` |
| app/navigation.py | /ui/crm/clients | NAV_SECTIONS entry | WIRED | Line 103: crm-clients entry with label "Клиенты" |
| app/templates/crm/detail.html | /ui/crm/clients/{id}/contacts | hx-post | WIRED | Form at line 95 with hx-post to contacts endpoint |
| app/templates/crm/detail.html | /ui/crm/clients/{id}/interactions | hx-post | WIRED | Form at line 118 with hx-post to interactions endpoint |
| app/routers/crm.py | client_service contact/interaction CRUD | service calls | WIRED | create_contact, update_contact, create_interaction all called with keyword args |
| app/routers/sites.py via main.py | client_service attach/detach | POST /ui/sites/{id}/client | WIRED | Line 2262 in main.py, calls attach_site/detach_site |
| app/templates/sites/detail.html | /ui/crm/clients/{id} | client badge link | WIRED | Line 18: href to client detail page |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| crm/index.html | clients | client_service.list_clients() | DB query with select(Client) | FLOWING |
| crm/detail.html | contacts | select(ClientContact).where(client_id) | Direct DB query | FLOWING |
| crm/detail.html | interactions | client_service.list_interactions() | DB query with pagination | FLOWING |
| crm/detail.html | sites | select(Site).where(client_id) | Direct DB query | FLOWING |
| crm/detail.html | open_task_count | get_open_task_count_for_client() | DB join query SeoTask+Site | FLOWING |
| crm/_client_rows.html | client.site_count | Not computed | No such attribute on Client model | STATIC -- displays 0 via default filter |
| crm/_client_rows.html | client.last_interaction_date | Not computed | No such attribute on Client model | STATIC -- displays dash |

### Behavioral Spot-Checks

Step 7b: SKIPPED (no running server; application requires PostgreSQL and Redis to start)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CRM-01 | 20-01, 20-02 | Create and edit client card | BLOCKED | Service layer and UI correct, but router dict-passing bug prevents create/edit from working at runtime |
| CRM-02 | 20-01, 20-02 | Assign manager to client | BLOCKED | Same bug blocks this -- manager_id is part of the create/edit form data dict |
| CRM-03 | 20-04 | Attach/detach sites to client | SATISFIED | Bidirectional linking from both client detail and site detail pages |
| CRM-04 | 20-01, 20-03 | Add contacts to client | SATISFIED | Contact CRUD with inline edit, name/phone/email/role fields |
| CRM-05 | 20-01, 20-03 | Log interactions per client | SATISFIED | Interaction CRUD with author_id attribution, date, ownership check |
| CRM-06 | 20-01, 20-02 | Client list with search and filter | SATISFIED | Search by name/INN/email, manager filter, date range filter, pagination |
| CRM-07 | 20-03, 20-04 | Client detail page with sites, tasks, interactions | SATISFIED | 4-tab detail page with all sections populated from DB |

**Note:** CRM-07 is mapped to Phase 20 in REQUIREMENTS.md traceability table and is claimed by plans 20-03 and 20-04. It was not listed in the phase requirement IDs provided for verification, but it is covered.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| app/routers/crm.py | 159 | `create_client(db, data)` -- dict passed as positional arg to keyword-only function | BLOCKER | TypeError at runtime; client creation broken |
| app/routers/crm.py | 191 | `update_client(db, client_id, data)` -- same pattern | BLOCKER | TypeError at runtime; client update broken |
| app/templates/crm/_client_rows.html | 16 | `client.site_count` -- attribute does not exist on Client model | WARNING | Renders 0 for all clients; cosmetic inaccuracy |
| app/templates/crm/_client_rows.html | 18 | `client.last_interaction_date` -- attribute does not exist | WARNING | Renders dash for all clients; cosmetic inaccuracy |
| app/templates/crm/_sites_tab.html | 39 | Open tasks column shows "--" hardcoded | INFO | Cosmetic; acknowledged in SUMMARY as known stub |

### Human Verification Required

### 1. Performance Under Load

**Test:** Seed 100+ client records, open /ui/crm/clients, measure page load time
**Expected:** Page renders within 3 seconds
**Why human:** Requires real data volume and browser timing measurement

### 2. Tab Switching UX

**Test:** Open client detail page, click through Sites, Contacts, Interactions, Info tabs
**Expected:** All tabs switch instantly, correct content shows/hides
**Why human:** Visual layout and JavaScript behavior verification

### 3. Client Badge on Site Detail

**Test:** Attach a client to a site, open site detail page
**Expected:** Purple badge with company name links to /ui/crm/clients/{id}
**Why human:** Visual styling and navigation flow

### 4. HTMX Interaction Flows

**Test:** Create a contact via inline form, edit it inline, delete it; add an interaction, edit it, delete it
**Expected:** All HTMX swaps work correctly without full page reload
**Why human:** Dynamic DOM manipulation and HTMX swap behavior

### Gaps Summary

**One blocker bug prevents client creation and editing.** The CRM router (lines 159 and 191) passes the parsed form data dict as a positional argument to service functions that require keyword-only arguments. The fix is trivial -- change `create_client(db, data)` to `create_client(db, **data)` and `update_client(db, client_id, data)` to `update_client(db, client_id, **data)`.

All other truths are verified. The data layer (models, migration, service, tests) is solid. Templates are complete with proper HTMX wiring. Navigation is registered. Bidirectional site linking works from both client and site pages.

Two cosmetic issues in the client list rows partial reference nonexistent model attributes (`site_count`, `last_interaction_date`). These render fallback values (0 and dash) so the page loads but shows inaccurate data. These should be addressed but are not blockers.

---

_Verified: 2026-04-09_
_Verifier: Claude (gsd-verifier)_
