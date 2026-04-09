# Phase 20: Client CRM - Research

**Researched:** 2026-04-09
**Domain:** CRM data layer (SQLAlchemy 2.0), FastAPI + HTMX UI patterns, server-side pagination, inline editing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Client Card Layout**
- D-01: Client detail page uses tabbed layout — header with company info, then tabs: Sites, Contacts, Interactions, Info
- D-02: Header shows ALL key info: company name + legal name, manager badge, site count + open tasks counter, INN/KPP + contact info
- D-03: Create/edit client via modal dialog — consistent with existing site create pattern
- D-04: No search within client detail page (within tabs) — unnecessary at 20–100 clients scale

**Sidebar Navigation**
- D-05: New CRM section in sidebar (not just a single link) — prepares for Phases 21–23 sub-items (Clients, Intake, Templates, Documents)

**Contacts**
- D-06: Contact fields: name, phone, email, role, Telegram username, notes — extended set beyond CRM-04 minimum
- D-07: Inline editing for contacts on the Contacts tab — click row → fields become editable via HTMX swap

**Interaction Log**
- D-08: Simple text notes — text + date + author, no interaction types/categories
- D-09: Inline form above the log (like GitHub comments) — textarea + button, HTMX adds entry without reload
- D-10: User can edit/delete own entries, admin can edit/delete all
- D-11: Sort: newest first (descending by date)

**Client List**
- D-12: Table view with columns: name, manager, site count, last interaction date
- D-13: Server-side pagination (HTMX), consistent with existing list patterns
- D-14: Filters: manager dropdown, HTMX live-search (by name/INN/email), date created
- D-15: Default sort: alphabetical by company name (A→Z)

**Site ↔ Client Linking**
- D-16: Attach via dropdown with search on Sites tab — shows only unattached sites, HTMX search by URL
- D-17: Sites already attached to another client are hidden from dropdown — must detach first
- D-18: Client badge on site page — small "Клиент: ACME Corp" badge with link to client detail
- D-19: Bidirectional linking — can attach/detach from both client card (Sites tab) and site page (client dropdown)

### Claude's Discretion
- Client deletion strategy (soft delete vs hard delete) — Claude decides based on existing patterns
- Exact pagination page size (20–50 range)
- HTMX partial templates structure

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CRM-01 | User can create and edit client card (company name, legal name, INN/KPP, phone, email, notes) | Client model + modal create/edit pattern (D-03); existing SiteCreate/SiteUpdate Pydantic schema pattern |
| CRM-02 | User can assign a manager to a client | manager_id FK → users table, require_manager_or_above guard; manager dropdown populated from users with role=manager or admin |
| CRM-03 | User can attach/detach sites to a client organization | client_id nullable FK on sites table (SET NULL on detach); HTMX dropdown with search (D-16, D-17, D-19) |
| CRM-04 | User can add contacts to a client (multiple contacts per org with name, phone, email, role) | ClientContact child table; inline edit via HTMX row swap (D-06, D-07) |
| CRM-05 | User can log interactions per client (notes + date + author) | ClientInteraction table; inline form + HTMX append (D-08, D-09, D-10, D-11) |
| CRM-06 | User can view client list with search and filter | Server-side pagination; HTMX live-search; manager filter dropdown (D-12–D-15) |
| CRM-07 | User can view client detail page with attached sites, open tasks, and recent interactions | Tabbed detail page (D-01, D-02); open tasks = SeoTask.status != resolved join via sites.client_id |
</phase_requirements>

---

## Summary

Phase 20 introduces the `Client` entity as the anchor for all v3.0 downstream features. Three new tables are needed: `clients`, `client_contacts`, and `client_interactions`. One existing table (`sites`) gains a nullable `client_id` FK. The implementation follows patterns already present across ~35 completed phases: SQLAlchemy 2.0 `mapped_column`, FastAPI `APIRouter`, async service layer, Jinja2 + HTMX templates.

The HTMX interaction model is the primary new pattern: inline contact editing (row swap) and inline interaction log submission (outerHTML append) both require dedicated partial endpoint responses returning raw HTML fragments, not JSON. This is well-established in the existing codebase (see `sites.py` HTMX badge responses, `monitoring/index.html` partial swaps).

The navigation system (`app/navigation.py` + `app/template_engine.py`) requires a specific extension: add a `crm` section to `NAV_SECTIONS` in `navigation.py` with a `clients` child. The sidebar icon system in `sidebar.html` only renders SVG for known icon names — a new icon name for CRM must be added to the `{% if section.icon == ... %}` chain.

**Primary recommendation:** Follow the exact model/router/service/template quad used in `notifications` (Phase 17) and `projects` — it's the most recently completed pattern and the closest structural match (child records, access control, HTMX partials).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.x (≥2.0.30) | ORM — Client, ClientContact, ClientInteraction models | Project constraint; async mapped_column pattern used throughout |
| FastAPI | 0.115.x | Router — /crm/clients endpoints + HTMX partials | Project constraint |
| Pydantic v2 | 2.7+ | ClientCreate, ClientUpdate, ContactCreate schemas | Project constraint; `model_config = {"from_attributes": True}` |
| Jinja2 | 3.1.x | client list, detail, partial templates | Project constraint |
| HTMX | 2.0.x | Live search, inline edit, pagination, log append | Project constraint; loaded from CDN in base.html |
| Alembic | 1.13.x | Migration 0043: clients + contacts + interactions + sites FK | Project constraint |
| asyncpg | 0.29.x | Async PG driver (transitive) | Project constraint |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| loguru | 0.7.x | Logging in service layer | All service actions; already configured |
| python-jose | 3.3.x | JWT decode for auth guards | `require_manager_or_above` dependency |
| slowapi | 0.1.9 | Rate limiting | Already installed; attach to any public-facing endpoints |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| HTMX inline edit (row swap) | Alpine.js reactive form | Alpine adds a new JS dependency; HTMX is already loaded and used throughout |
| Soft delete (is_deleted flag) | Hard delete | See Architecture Patterns — soft delete recommended; consistent with `is_active` pattern on Site |
| Single migration 0043 | Split into 0043 + 0044 | CRM tables are cohesive; one migration is cleaner here. Phase 21 intake gets 0044. |

---

## Architecture Patterns

### Recommended Project Structure
```
app/
├── models/
│   └── client.py            # Client, ClientContact, ClientInteraction models
├── routers/
│   └── crm.py               # APIRouter prefix="/crm", all CRM endpoints
├── services/
│   └── client_service.py    # Async service layer — CRUD + pagination + linking
├── templates/
│   └── crm/
│       ├── index.html        # Client list (table + filters + HTMX pagination)
│       ├── detail.html       # Client detail (tabbed: Sites, Contacts, Interactions, Info)
│       ├── _modal_create.html   # Create/edit client modal fragment
│       ├── _contact_row.html    # Single contact row (read mode)
│       ├── _contact_edit.html   # Single contact row (edit mode — HTMX swap target)
│       ├── _interaction_entry.html  # Single interaction log entry
│       ├── _sites_tab.html      # Sites tab partial
│       └── _site_search_results.html  # HTMX dropdown results for site attach
alembic/
└── versions/
    └── 0043_add_crm_tables.py
```

### Pattern 1: SQLAlchemy Model — Client (established project pattern)
**What:** Three new models in `app/models/client.py` following the exact `mapped_column` / UUID PK / `Base` pattern.
**When to use:** Always; do not deviate from project model conventions.

```python
# Source: existing app/models/site.py + app/models/user.py patterns
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ClientContact(Base):
    __tablename__ = "client_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class ClientInteraction(Base):
    __tablename__ = "client_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    interaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

### Pattern 2: HTMX Partial Response (established project pattern)
**What:** Router endpoints return `HTMLResponse` fragments for HTMX swap targets. This is how the existing codebase handles inline updates without full-page reload.
**When to use:** Contact inline edit, interaction log append, site attach/detach, live search, pagination.

```python
# Source: existing app/routers/sites.py @router.patch("/{site_id}/status")
# and app/routers/sites.py @router.post("/{site_id}/verify")
from fastapi.responses import HTMLResponse
from app.template_engine import templates

@router.post("/{client_id}/contacts/{contact_id}/edit-mode")
async def contact_edit_mode(
    client_id: uuid.UUID,
    contact_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    contact = await client_service.get_contact(db, contact_id, client_id)
    if not contact:
        raise HTTPException(status_code=404)
    # Return edit-mode row fragment
    return templates.TemplateResponse(
        request, "crm/_contact_edit.html", {"contact": contact}
    )
```

### Pattern 3: Server-side Pagination (established project pattern)
**What:** HTMX `hx-get` with `?page=N` query param; endpoint returns partial HTML (table rows + pagination controls). Page size: **25** (within the 20–50 range from Claude's discretion; 25 balances density for 100-client scale).
**When to use:** Client list; consistent with existing notification list pagination.

```python
# Pagination query pattern (from existing service layer)
from sqlalchemy import select, func

async def list_clients(
    db: AsyncSession,
    search: str | None = None,
    manager_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Client], int]:
    q = select(Client).where(Client.is_deleted == False)
    if search:
        term = f"%{search.lower()}%"
        q = q.where(
            func.lower(Client.company_name).like(term) |
            func.lower(Client.inn).like(term) |
            func.lower(Client.email).like(term)
        )
    if manager_id:
        q = q.where(Client.manager_id == manager_id)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()
    q = q.order_by(Client.company_name.asc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total
```

### Pattern 4: Navigation Extension (CRM section)
**What:** Add CRM section to `NAV_SECTIONS` in `app/navigation.py` and add the new icon to `sidebar.html`.
**When to use:** Required once; sets up the navigation anchor for Phases 21–23.

```python
# app/navigation.py — add after the "client-reports" section
{
    "id": "crm",
    "label": "CRM",
    "icon": "user-group",    # new icon — must also add SVG to sidebar.html
    "url": None,
    "admin_only": False,
    "children": [
        {"id": "crm-clients", "label": "Клиенты", "url": "/ui/crm/clients"},
        # Phase 21–23 children added in those phases
    ],
},
```

```html
<!-- app/templates/components/sidebar.html — add to the icon if/elif chain -->
{% elif section.icon == 'user-group' %}
<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="sidebar-icon" style="width:1.25rem;height:1.25rem;flex-shrink:0;">
  <path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z" />
</svg>
```

### Pattern 5: Soft Delete (Claude's Discretion — recommended)
**What:** `is_deleted = True` flag on `Client`; all queries filter `WHERE is_deleted = FALSE`. Consistent with `Site.is_active` and the existing `is_active` pattern. Hard delete is avoided because downstream phases (21–23) reference `client_id`.
**Why not hard delete:** Once intake forms, proposals, and documents reference `client_id`, hard delete causes cascade orphan problems. Soft delete preserves referential integrity.

### Pattern 6: RBAC — `require_manager_or_above`
**What:** STATE.md explicitly calls this out: "require_admin locks out managers; require_any_authenticated causes IDOR on client data." Use `require_manager_or_above` for all CRM write endpoints. Row-level check: for client-role users (future), add explicit client_id ownership check, but that is deferred (not in Phase 20 scope).

```python
# Source: app/auth/dependencies.py — already defined
require_manager_or_above = require_role(UserRole.admin, UserRole.manager)

# Use for all CRM mutation endpoints:
current_user: User = Depends(require_manager_or_above)
```

### Anti-Patterns to Avoid
- **Returning JSON from HTMX partial endpoints:** Existing pattern returns `HTMLResponse` fragments from HTMX-triggered routes. Returning JSON breaks the swap target. Only use `response_model=` on JSON API endpoints (if any).
- **Adding `client_id` FK directly in the model file without migration:** Always generate via `alembic revision --autogenerate` and review before applying. The `site.py` change (adding `client_id`) must be part of migration 0043.
- **Importing `Jinja2Templates` directly in a new router:** All routers must import `templates` from `app.template_engine`, not create their own instance. The nav-aware wrapper only works when all responses go through the shared `_NavAwareTemplates`.
- **Creating a second CRM router file:** One `app/routers/crm.py` with prefix `/crm` covers all CRM endpoints. Splitting by sub-resource creates import chain complexity.
- **Using `require_admin` instead of `require_manager_or_above`:** Managers must be able to manage their own clients.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Server-side search with debounce | Custom JS debounce + fetch | HTMX `hx-trigger="keyup changed delay:300ms"` | HTMX 2.0 handles debounce natively; already in base.html |
| Pagination state | JS state management | Query params (`?page=N&search=X`) + HTMX `hx-push-url="true"` | Bookmarkable, back-button compatible, zero JS |
| Modal dialog | Custom dialog JS | CSS + `classList.toggle('hidden')` inline JS (matches existing project pattern — see projects/index.html `onclick="document.getElementById('new-project-form').classList.remove('hidden')"`) | Project uses vanilla inline JS, no dialog library |
| Live search filtering | Full re-render on every keystroke | HTMX `hx-trigger="keyup changed delay:300ms" hx-target="#client-table-body"` partial returning only `<tbody>` rows | Same pattern as notification kind filter |
| Audit logging | Custom log table | `app/services/audit_service.log_action()` | Already exists; all mutations should call it with `entity_type="client"` |

---

## Common Pitfalls

### Pitfall 1: Migration Order — `clients` must exist before `sites.client_id`
**What goes wrong:** Alembic `--autogenerate` may order table creation after FK addition if the FK is detected on `sites` first.
**Why it happens:** SQLAlchemy introspects model metadata; FK reference requires the target table to exist first.
**How to avoid:** In migration 0043, `op.create_table("clients", ...)` must appear before `op.add_column("sites", sa.Column("client_id", ...))`. Review generated migration before applying.
**Warning signs:** `alembic upgrade head` fails with `relation "clients" does not exist`.

### Pitfall 2: HTMX Inline Edit — Out-of-Band Updates
**What goes wrong:** After saving a contact edit, the row swaps back to read mode correctly but the contacts count in the header stays stale.
**Why it happens:** HTMX `hx-swap` only updates the declared `hx-target`; other parts of the DOM are not automatically refreshed.
**How to avoid:** Use `HX-Trigger` response header to fire a named event, or use HTMX out-of-band swap (`hx-swap-oob="true"`) on the header count element returned alongside the contact row fragment.

### Pitfall 3: `require_manager_or_above` + Client Row-Level Access
**What goes wrong:** Manager A can edit Manager B's clients.
**Why it happens:** `require_manager_or_above` only checks role, not ownership.
**How to avoid:** For Phase 20 (internal team tool, no client-role access), this is acceptable — STATE.md explicitly defers row-level checks to a future phase. Document this as a known limitation. Do not over-engineer RBAC for v3.0.

### Pitfall 4: Site Dropdown Search — Showing Already-Attached Sites
**What goes wrong:** The attach dropdown shows sites already linked to another client.
**Why it happens:** Query doesn't filter `WHERE client_id IS NULL`.
**How to avoid:** The site attach search endpoint must always filter: `WHERE sites.client_id IS NULL OR sites.client_id = :current_client_id`. This matches D-17.

### Pitfall 5: Circular Import on `client.py` Model
**What goes wrong:** `app/models/client.py` imports `User` for type annotation; `app/models/__init__.py` imports everything; circular import at startup.
**Why it happens:** SQLAlchemy FK strings avoid this for FK declarations, but type-annotated relationship `Mapped["User"]` can trigger it.
**How to avoid:** Use string FK references (`ForeignKey("users.id")`) and `TYPE_CHECKING` guard for relationship annotations. Do not add ORM `relationship()` declarations unless needed — the service layer uses explicit `select()` queries, not ORM lazy loading.

### Pitfall 6: Navigation `resolve_nav_context` Miss
**What goes wrong:** CRM pages show no active section in sidebar (no highlight).
**Why it happens:** `app/navigation.py` `_URL_TO_NAV` is built at module import time. The `/ui/crm/clients` URL must be in `NAV_SECTIONS` before the app starts.
**How to avoid:** Add the CRM section to `NAV_SECTIONS` in the same task that registers the router. Test by visiting `/ui/crm/clients` and confirming the "CRM" sidebar section highlights.

### Pitfall 7: `app/main.py` Import Registration
**What goes wrong:** New router is never registered; all `/crm/*` routes return 404.
**Why it happens:** FastAPI requires explicit `app.include_router(crm_router)` in `main.py`.
**How to avoid:** Add both the import and `app.include_router()` call in the same task that creates `app/routers/crm.py`.

---

## Code Examples

### Alembic Migration Pattern (migration 0043)
```python
# Source: alembic/versions/0042_notifications.py pattern
"""Add CRM tables and client_id FK to sites.

Revision ID: 0043
Revises: 0042
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0043"
down_revision = "0042"

def upgrade() -> None:
    # 1. Create clients table first (FK target)
    op.create_table(
        "clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("inn", sa.String(20), nullable=True),
        sa.Column("kpp", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("manager_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_clients_company_name", "clients", ["company_name"])
    op.create_index("ix_clients_manager_id", "clients", ["manager_id"])

    # 2. Create client_contacts
    op.create_table(
        "client_contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("telegram_username", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_client_contacts_client_id", "client_contacts", ["client_id"])

    # 3. Create client_interactions
    op.create_table(
        "client_interactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("interaction_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_client_interactions_client_id_date", "client_interactions", ["client_id", sa.text("interaction_date DESC")])

    # 4. Add client_id FK to sites (after clients table exists)
    op.add_column("sites", sa.Column("client_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_sites_client_id", "sites", "clients", ["client_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_sites_client_id", "sites", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_sites_client_id", table_name="sites")
    op.drop_constraint("fk_sites_client_id", "sites", type_="foreignkey")
    op.drop_column("sites", "client_id")
    op.drop_index("ix_client_interactions_client_id_date", table_name="client_interactions")
    op.drop_table("client_interactions")
    op.drop_index("ix_client_contacts_client_id", table_name="client_contacts")
    op.drop_table("client_contacts")
    op.drop_index("ix_clients_manager_id", table_name="clients")
    op.drop_index("ix_clients_company_name", table_name="clients")
    op.drop_table("clients")
```

### HTMX Live Search Pattern (from existing codebase)
```html
<!-- Client list search input — triggers partial table reload -->
<input
  type="text"
  name="search"
  placeholder="Поиск по имени, ИНН, email..."
  hx-get="/ui/crm/clients"
  hx-trigger="keyup changed delay:300ms"
  hx-target="#client-table-body"
  hx-include="[name='manager_id'],[name='page']"
  hx-vals='{"partial": "true"}'
  style="..."
>
```

### Open Tasks Count for Client Detail (CRM-07)
```python
# Source: adapted from app/services/project_service.py + app/models/task.py
from sqlalchemy import select, func
from app.models.task import SeoTask, TaskStatus
from app.models.site import Site

async def get_open_task_count_for_client(db: AsyncSession, client_id: uuid.UUID) -> int:
    """Count open SeoTasks across all sites linked to a client."""
    result = await db.execute(
        select(func.count(SeoTask.id))
        .join(Site, Site.id == SeoTask.site_id)
        .where(
            Site.client_id == client_id,
            SeoTask.status != TaskStatus.resolved,
        )
    )
    return result.scalar_one()
```

### Client Badge on Site Detail Page
```html
<!-- app/templates/sites/detail.html — add after the stats row -->
{% if client %}
<div style="margin-bottom:1rem;">
  <span style="font-size:0.85rem;color:#6b7280;">Клиент:</span>
  <a href="/ui/crm/clients/{{ client.id }}" style="display:inline-flex;align-items:center;gap:0.3rem;padding:0.2rem 0.6rem;background:#eef2ff;color:#4338ca;border-radius:4px;font-size:0.85rem;font-weight:500;text-decoration:none;">
    {{ client.company_name }}
  </a>
</div>
{% endif %}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate Jinja2Templates per router | Shared `app.template_engine.templates` | Phase 17 | All routers must use the shared instance |
| `on_event("startup")` | `@asynccontextmanager lifespan=` | Phase 1 | No deprecated patterns |
| `require_admin` everywhere | Role-specific guards (`require_manager_or_above`) | Phase 18 | CRM must use `require_manager_or_above` for writes |

**Deprecated/outdated:**
- `FastAPI on_event`: removed, use lifespan (already done in this codebase)
- `Pydantic v1 @validator`: replaced by `@field_validator` (already v2 throughout)

---

## Open Questions

1. **Interaction edit timestamp display**
   - What we know: D-10 says users can edit/delete own interactions; D-11 says newest first
   - What's unclear: Should edited interactions show "edited" marker (e.g., "(изм.)")?
   - Recommendation: Add `updated_at` to the model (already in schema above); show "(изм.)" if `updated_at > created_at + 1 minute`. Low implementation cost, useful for audit trail.

2. **Client badge on site list vs. site detail only**
   - What we know: D-18 specifies client badge on site page (detail)
   - What's unclear: D-18 says "site page" — does this mean only `sites/detail.html` or also `sites/index.html` table rows?
   - Recommendation: Detail page only per D-18 literal reading. The site list already has many columns; a client column would require schema join on every list load. Defer site list column to a future enhancement if requested.

3. **Manager dropdown population**
   - What we know: D-02 shows manager badge; CRM-02 requires manager assignment
   - What's unclear: Does the manager dropdown on the create/edit modal show only users with role=manager, or also admins?
   - Recommendation: Include both `UserRole.admin` and `UserRole.manager` — admins often also manage clients directly; consistent with how `require_manager_or_above` is defined.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 20 is pure code/model/template changes. No new external dependencies. All required tools (PostgreSQL, Alembic, FastAPI, HTMX) are already confirmed operational from prior phases.

---

## Project Constraints (from CLAUDE.md)

| Constraint | Applies to Phase 20 |
|------------|---------------------|
| Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic, asyncpg | All model/router/service code |
| PostgreSQL 16 only; all schema changes via Alembic migrations | Migration 0043 only — no direct schema edits |
| Passwords bcrypt, WP credentials Fernet-encrypted, JWT exp=24h | Not directly relevant; no new secrets in CRM |
| Celery retry=3 for external API calls | Not applicable — CRM has no external API calls |
| UI pages < 3s; long operations always async via Celery | Client list + detail are DB-only queries; no Celery tasks needed |
| pytest + httpx AsyncClient; service layer coverage > 60% by iteration 4 | New `client_service.py` must have test coverage |
| loguru, JSON format, DEBUG/INFO/ERROR levels, 10 MB rotation, 30-day retention | Service layer log calls via loguru |
| No substitutions to fixed tech stack | No Alpine.js, no new JS libraries |
| GSD workflow enforcement | All changes through GSD execute-phase |

---

## Sources

### Primary (HIGH confidence)
- `app/models/site.py` — UUID PK, mapped_column, nullable FK pattern (verified directly)
- `app/models/project.py` — M2M association table pattern (verified directly)
- `app/models/user.py` — UserRole enum, is_active pattern (verified directly)
- `app/auth/dependencies.py` — `require_manager_or_above` already defined (verified directly)
- `app/navigation.py` — NAV_SECTIONS structure, URL pattern resolution (verified directly)
- `app/template_engine.py` — `_NavAwareTemplates` wrapper, shared templates instance (verified directly)
- `alembic/versions/0042_notifications.py` — latest migration pattern (verified directly)
- `app/routers/sites.py` — HTMX HTMLResponse pattern, Pydantic schema pattern (verified directly)
- `app/services/project_service.py` — service layer CRUD pattern, access control (verified directly)
- `app/services/audit_service.py` — `log_action` signature (verified directly)
- `app/templates/components/sidebar.html` — icon chain pattern (verified directly)
- `.planning/STATE.md` — key decisions, RBAC guidance (verified directly)

### Secondary (MEDIUM confidence)
- `app/templates/sites/edit.html` — modal/form field pattern for CRM create modal
- `app/templates/projects/index.html` — hidden form toggle pattern for modals
- HTMX 2.0 documentation — `hx-trigger="keyup changed delay:300ms"` debounce syntax (HIGH — HTMX 2.0 confirmed in base.html CDN URL)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are project-locked; versions confirmed from existing code
- Architecture: HIGH — all patterns verified from existing codebase at runtime
- Pitfalls: HIGH — identified from direct inspection of navigation, migration, and template code
- HTMX patterns: HIGH — HTMX 2.0.3 confirmed in base.html; existing HTMX usage patterns verified

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable stack; no fast-moving dependencies)
