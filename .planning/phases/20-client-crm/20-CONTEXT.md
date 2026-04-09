# Phase 20: Client CRM - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can create and manage client organisations with contacts, assigned manager, linked sites, and a chronological interaction log. The client entity becomes the anchor for all v3.0 downstream features (intake, proposals, documents).

</domain>

<decisions>
## Implementation Decisions

### Client Card Layout
- **D-01:** Client detail page uses **tabbed layout** — header with company info, then tabs: Sites, Contacts, Interactions, Info
- **D-02:** Header shows ALL key info: company name + legal name, manager badge, site count + open tasks counter, INN/KPP + contact info
- **D-03:** Create/edit client via **modal dialog** — consistent with existing site create pattern
- **D-04:** No search within client detail page (within tabs) — unnecessary at 20–100 clients scale

### Sidebar Navigation
- **D-05:** New **CRM section** in sidebar (not just a single link) — prepares for Phases 21–23 sub-items (Clients, Intake, Templates, Documents)

### Contacts
- **D-06:** Contact fields: name, phone, email, role, Telegram username, notes — extended set beyond CRM-04 minimum
- **D-07:** **Inline editing** for contacts on the Contacts tab — click row → fields become editable via HTMX swap

### Interaction Log
- **D-08:** Simple text notes — text + date + author, no interaction types/categories
- **D-09:** **Inline form above the log** (like GitHub comments) — textarea + button, HTMX adds entry without reload
- **D-10:** User can edit/delete own entries, admin can edit/delete all
- **D-11:** Sort: newest first (descending by date)

### Client List
- **D-12:** **Table view** with columns: name, manager, site count, last interaction date
- **D-13:** **Server-side pagination** (HTMX), consistent with existing list patterns
- **D-14:** Filters: manager dropdown, HTMX live-search (by name/INN/email), date created
- **D-15:** Default sort: alphabetical by company name (A→Z)

### Site ↔ Client Linking
- **D-16:** Attach via **dropdown with search** on Sites tab — shows only unattached sites, HTMX search by URL
- **D-17:** Sites already attached to another client are **hidden** from dropdown — must detach first
- **D-18:** **Client badge on site page** — small "Клиент: ACME Corp" badge with link to client detail
- **D-19:** **Bidirectional linking** — can attach/detach from both client card (Sites tab) and site page (client dropdown)

### Claude's Discretion
- Client deletion strategy (soft delete vs hard delete) — Claude decides based on existing patterns
- Exact pagination page size (20–50 range)
- HTMX partial templates structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — CRM-01 through CRM-07 acceptance criteria
- `.planning/ROADMAP.md` §Phase 20 — success criteria, dependencies, UI hint

### Existing Patterns
- `app/models/site.py` — Site model (needs client_id FK), UUID pattern, ConnectionStatus enum
- `app/models/project.py` — Project model with M2M association table pattern (project_users)
- `app/models/user.py` — User model with UserRole enum (admin/manager/client)
- `app/routers/sites.py` — Router + Pydantic schema pattern (SiteCreate, SiteUpdate)
- `app/templates/components/sidebar.html` — Sidebar structure for adding CRM section
- `app/templates/macros/empty_state.html` — Reusable empty state macro

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `empty_state` Jinja2 macro — for empty client list, empty contacts tab, empty interaction log
- Sidebar component (`components/sidebar.html`) — add new CRM section
- Breadcrumb component (`components/breadcrumb.html`) — for client detail page hierarchy

### Established Patterns
- **Model**: SQLAlchemy 2.0 mapped_column, UUID PK, Base class from `app.database`
- **Router**: FastAPI APIRouter with prefix, Pydantic BaseModel for create/update schemas
- **Service**: Async service layer in `app/services/` with `AsyncSession` dependency
- **Templates**: Jinja2 with HTMX attributes, partials for swap targets
- **Auth**: `require_admin` dependency for protected routes, `User` from `app.auth.dependencies`

### Integration Points
- `Site` model — add `client_id` FK column (nullable, SET NULL on delete)
- Site detail template — add client badge with link
- Site edit form — add client dropdown for linking
- Sidebar template — add CRM section between existing sections
- Alembic migration — new tables (clients, client_contacts, client_interactions) + site.client_id FK

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 20-client-crm*
*Context gathered: 2026-04-09*
