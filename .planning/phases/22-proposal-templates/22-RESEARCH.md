# Phase 22: Proposal Templates - Research

**Researched:** 2026-04-09
**Domain:** Jinja2 template management, CodeMirror 6, HTMX-driven preview with iframe isolation, FastAPI CRUD, SQLAlchemy async
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Template Editor**
- D-01: CodeMirror with HTML/Jinja2 syntax highlighting, line numbers, auto-close tags
- D-02: Side-by-side layout — CodeMirror left, preview right; "Preview" button refreshes right panel
- D-03: Create/edit on a dedicated full page `/ui/templates/{id}/edit` (not a modal)

**Template Metadata**
- D-04: Metadata: name, template_type (enum: proposal, audit_report, brief), description
- D-05: Template type is a fixed enum, not free text

**Variable System**
- D-06: Variable panel right of preview — grouped list of ~15 variables with descriptions; click inserts `{{ variable }}` at CodeMirror cursor
- D-07: Unresolved variables shown with yellow background: `<span class="unresolved-var">{{ var_name }}</span>`
- D-08: Variables grouped: Client (name, legal_name, inn, email, phone, manager), Site (url, domain, top_positions_count, audit_errors_count, last_crawl_date), Analytics (gsc_connected, metrika_id)

**Template List**
- D-09: Card grid — name, type badge, description, date, action buttons
- D-10: "Create Template" button leads to create page

**Access Control**
- D-11: Admin-only for create/edit/clone/delete; all authenticated users can view/preview

**Clone Workflow**
- D-12: Clone creates copy named "{original_name} (копия)" and redirects to clone's edit page

**Preview**
- D-13: Two dropdowns above preview: Client → Site (HTMX dependent select)
- D-14: Preview renders in iframe — HTMX POST sends body + client_id + site_id, Jinja2 renders, HTML returned to iframe for style isolation
- D-15: Preview renders in < 5 seconds

**Sandboxing**
- SandboxedEnvironment for Jinja2 rendering (STATE.md key decision)

### Claude's Discretion
- CodeMirror version (5 vs 6) — UI-SPEC chose CodeMirror 6 via esm.sh CDN
- CDN vs bundle for CodeMirror
- Exact JSON structure for template storage
- Pagination of template list (if needed at low count)
- Soft delete vs hard delete for templates

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TPL-01 | Admin can create, edit, and delete proposal templates with Jinja2 variable syntax | Model + router CRUD pattern established; `require_admin` dependency confirmed in `app/auth/dependencies.py` |
| TPL-02 | System resolves a fixed set of ~15 template variables from DB (client name, site URL, positions, audit errors, etc.) | Variable resolver pattern confirmed: query Client, Site, OAuthToken, CrawlJob, error_impact_scores tables; pass plain dict to SandboxedEnvironment |
| TPL-03 | User can preview a rendered template with real site/client data before generating PDF | iframe + JS `srcdoc` pattern confirmed; SandboxedEnvironment with custom Undefined class proven in testing; < 5s achievable with direct DB queries (no Celery) |
| TPL-04 | User can clone an existing template | Clone = copy row + redirect; HX-Redirect header pattern confirmed from CRM router |
</phase_requirements>

---

## Summary

Phase 22 introduces proposal template management — a CRUD interface for admin-authored Jinja2-HTML templates with a variable panel and live preview. All foundational patterns are already established in the codebase from Phase 20 (CRM CRUD) and Phase 21 (HTMX form saves). This phase introduces two new technical elements with no prior codebase precedent: CodeMirror 6 (editor component) and Jinja2 SandboxedEnvironment (user template rendering). Both are well-understood library features that require careful integration decisions.

The security model for SandboxedEnvironment requires explicit attention: the sandbox does NOT block attribute access on objects explicitly passed into the template context. The correct security approach — confirmed by live testing — is to resolve all variables server-side into a **plain dict** (no SQLAlchemy model objects, no config objects) before passing to SandboxedEnvironment. This confines the blast radius of any template injection to the pre-extracted flat dict.

CodeMirror 6 is an ES module library with no jQuery dependency. The project's CDN-first approach is carried through via `esm.sh`. The editor communicates with the surrounding Jinja2 page via a thin JS bridge: on form submit, `view.state.doc.toString()` is written to a hidden `<input name="body">`; variable panel clicks use `view.dispatch()` to insert at cursor. These are standard CodeMirror 6 patterns documented in the official API.

**Primary recommendation:** Build `app/services/template_variable_resolver.py` as a standalone async function that takes `db, client_id, site_id` and returns a safe flat dict; all render endpoints call only this function — never pass raw ORM objects to SandboxedEnvironment.

---

## Standard Stack

### Core (all already installed)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| Jinja2 | 3.1.6 | Template rendering + SandboxedEnvironment | Installed, verified |
| jinja2.sandbox.SandboxedEnvironment | 3.1.6 | User-authored template isolation | Verified in live test |
| FastAPI | 0.115.x | Router + HTML responses | Installed |
| SQLAlchemy async | 2.0.x | ORM queries for variable resolution | Installed |
| HTMX | 2.0.3 | Dependent select, preview POST, delete | In base.html |

### New CDN Libraries (no install required)

| Library | Version | Purpose | Load Via |
|---------|---------|---------|----------|
| `@codemirror/basic-setup` | 0.20 | Editor scaffold (line numbers, syntax, keymaps) | `https://esm.sh/@codemirror/basic-setup@0.20` |
| `@codemirror/lang-html` | 6.x | HTML language mode (covers Jinja2 `{{ }}` syntax) | `https://esm.sh/@codemirror/lang-html@6` |
| `@codemirror/view` | 6.x | EditorView API | bundled with basic-setup via esm.sh |
| `@codemirror/state` | 6.x | EditorState, transactions | bundled with basic-setup via esm.sh |

**No new pip packages required.** All Python dependencies are already installed.

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
app/
├── models/
│   └── proposal_template.py         # ProposalTemplate model
├── routers/
│   └── templates.py                 # /ui/templates router
├── services/
│   ├── template_service.py          # CRUD: list, get, create, update, delete, clone
│   └── template_variable_resolver.py # Variable resolution: DB queries → plain dict
├── templates/
│   └── proposal_templates/
│       ├── index.html               # Card grid list page
│       ├── edit.html                # Three-column editor/preview/variables page
│       └── _preview_frame.html      # (optional) server preview response fragment
alembic/versions/
└── 0045_add_proposal_templates.py   # Migration
```

### Pattern 1: ProposalTemplate Model

Follow the established SQLAlchemy 2.0 mapped_column pattern from `app/models/client.py` and `app/models/site_intake.py`.

```python
# Source: established project pattern (app/models/client.py)
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TemplateType(str, PyEnum):
    proposal = "proposal"
    audit_report = "audit_report"
    brief = "brief"


class ProposalTemplate(Base):
    __tablename__ = "proposal_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[TemplateType] = mapped_column(
        SAEnum(TemplateType), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
```

**Hard delete decision (Claude's Discretion):** Use hard delete (no `is_deleted` flag). Rationale: Phase 23 document generation references `template_id`; Phase 23 will add its own FK constraint. Deleting a template in Phase 22 is safe because no generated documents exist yet. Soft delete adds complexity without benefit at this stage.

### Pattern 2: Variable Resolver — Safe Dict Construction

**Critical security pattern.** SandboxedEnvironment does NOT block attribute access on objects passed explicitly into the context — it only blocks dunder attributes and unsafe traversal. Therefore: resolve all data server-side into a plain Python dict with no ORM objects.

```python
# Source: verified by live testing on this machine (2026-04-09)
# app/services/template_variable_resolver.py
from __future__ import annotations

import uuid
from jinja2 import Undefined
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.oauth_token import OAuthToken
from app.models.site import Site


class _HighlightUndefined(Undefined):
    """Replaces unresolved {{ var }} with a visible amber span in preview."""
    def __str__(self) -> str:
        return (
            f'<span class="unresolved-var" '
            f'style="background:#fef3c7;color:#92400e;padding:0 4px;'
            f'border-radius:2px;font-family:monospace;font-size:0.85em;">'
            f'{{{{ {self._undefined_name} }}}}</span>'
        )


async def resolve_template_variables(
    db: AsyncSession,
    client_id: uuid.UUID,
    site_id: uuid.UUID,
) -> dict:
    """
    Fetch all ~15 template variables from DB and return a SAFE PLAIN DICT.
    Never pass SQLAlchemy model objects into SandboxedEnvironment.
    """
    # Fetch Client
    client_row = (await db.execute(
        select(Client).where(Client.id == client_id, Client.is_deleted == False)
    )).scalar_one_or_none()

    # Fetch Site
    site_row = (await db.execute(
        select(Site).where(Site.id == site_id)
    )).scalar_one_or_none()

    # GSC connection
    gsc_count = (await db.execute(
        select(func.count()).select_from(OAuthToken).where(
            OAuthToken.site_id == site_id,
            OAuthToken.provider == "gsc",
        )
    )).scalar_one()

    # Last crawl date
    last_crawl = (await db.execute(text(
        "SELECT MAX(created_at) FROM crawl_jobs WHERE site_id = :sid AND status = 'done'"
    ), {"sid": site_id})).scalar_one_or_none()

    # Audit error count (from pre-computed error_impact_scores)
    audit_errors = (await db.execute(text(
        "SELECT COUNT(DISTINCT page_url) FROM error_impact_scores WHERE site_id = :sid"
    ), {"sid": site_id})).scalar_one()

    # Top-10 positions count (from keyword_latest_positions or keyword_positions)
    top10 = (await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (keyword_id, engine) position
            FROM keyword_positions
            WHERE site_id = :sid
            ORDER BY keyword_id, engine, checked_at DESC
        )
        SELECT COUNT(*) FILTER (WHERE position IS NOT NULL AND position <= 10)
        FROM latest
    """), {"sid": site_id})).scalar_one()

    # Manager name
    manager_name = None
    if client_row and client_row.manager_id:
        from app.models.user import User
        manager_row = (await db.execute(
            select(User).where(User.id == client_row.manager_id)
        )).scalar_one_or_none()
        manager_name = manager_row.username if manager_row else None

    # Build FLAT PLAIN DICT — no ORM objects
    from urllib.parse import urlparse
    site_url = site_row.url if site_row else ""
    domain = urlparse(site_url).netloc if site_url else ""

    return {
        "client": {
            "name": client_row.company_name if client_row else "",
            "legal_name": client_row.legal_name or "" if client_row else "",
            "inn": client_row.inn or "" if client_row else "",
            "email": client_row.email or "" if client_row else "",
            "phone": client_row.phone or "" if client_row else "",
            "manager": manager_name or "",
        },
        "site": {
            "url": site_url,
            "domain": domain,
            "top_positions_count": int(top10 or 0),
            "audit_errors_count": int(audit_errors or 0),
            "last_crawl_date": last_crawl.strftime("%d.%m.%Y") if last_crawl else "",
            "gsc_connected": bool(gsc_count),
            "metrika_id": site_row.metrika_counter_id or "" if site_row else "",
        },
    }


def render_template_preview(body: str, context: dict) -> str:
    """Render user-authored template body with highlighted unresolved vars."""
    env = SandboxedEnvironment(undefined=_HighlightUndefined)
    try:
        return env.from_string(body).render(context)
    except Exception as exc:
        # Return error message as safe HTML for preview display
        return f'<p style="color:#dc2626;font-family:monospace;">Ошибка рендеринга: {exc}</p>'
```

### Pattern 3: Router Structure

Follow `app/routers/crm.py` — same router style, HTMX partial responses with `HX-Trigger` toast headers, `require_admin` for write operations, `require_any_authenticated` for reads.

```python
# Source: app/routers/crm.py pattern
router = APIRouter(prefix="/ui/templates", tags=["templates"])

# List — all authenticated
@router.get("", response_class=HTMLResponse)
async def template_list(request, db, current_user=Depends(require_any_authenticated)):
    ...

# Create form page — admin only
@router.get("/new", response_class=HTMLResponse)
async def template_new_page(request, db, current_user=Depends(require_admin)):
    ...

# Edit/preview page — admin only
@router.get("/{template_id}/edit", response_class=HTMLResponse)
async def template_edit_page(request, template_id, db, current_user=Depends(require_admin)):
    ...

# Save (POST = create, PUT = update) — admin only
@router.post("", response_class=HTMLResponse)
async def template_create(request, ..., current_user=Depends(require_admin)):
    ...

@router.post("/{template_id}", response_class=HTMLResponse)  # or PUT
async def template_update(request, template_id, ..., current_user=Depends(require_admin)):
    ...

# Preview — all authenticated (reads only resolved vars)
@router.post("/{template_id}/preview", response_class=HTMLResponse)
async def template_preview(request, template_id, ..., current_user=Depends(require_any_authenticated)):
    ...

# Dependent select: sites by client
@router.get("/sites", response_class=HTMLResponse)
async def sites_for_client(client_id, db, current_user=Depends(require_any_authenticated)):
    ...

# Clone — admin only
@router.post("/{template_id}/clone", response_class=HTMLResponse)
async def template_clone(request, template_id, db, current_user=Depends(require_admin)):
    # Creates copy, sets HX-Redirect to /ui/templates/{clone_id}/edit
    ...

# Delete — admin only
@router.delete("/{template_id}", response_class=HTMLResponse)
async def template_delete(request, template_id, db, current_user=Depends(require_admin)):
    ...
```

### Pattern 4: Alembic Migration (0045)

Follows the established pattern from `0044_add_site_intakes_table.py`. Revision ID: `0045`, `down_revision = "0044"`. Must create `templatetype` PostgreSQL enum type.

### Pattern 5: CodeMirror 6 — JS Integration on Edit Page

The edit page `edit.html` extends `base.html` and loads CodeMirror 6 via ES module script tags. The editor mounts into a `div#codemirror-mount`.

```javascript
// Source: CodeMirror 6 official API (https://codemirror.net/docs/ref/)
// Load via type="module" — esm.sh bundles correctly
import { basicSetup } from 'https://esm.sh/@codemirror/basic-setup@0.20';
import { EditorView } from 'https://esm.sh/@codemirror/view@6';
import { html } from 'https://esm.sh/@codemirror/lang-html@6';

const view = new EditorView({
  doc: document.getElementById('template-body-initial').textContent,
  extensions: [basicSetup, html()],
  parent: document.getElementById('codemirror-mount'),
});

// Variable panel click → insert at cursor
function insertVariable(varName) {
  const pos = view.state.selection.main.head;
  view.dispatch({
    changes: { from: pos, insert: '{{ ' + varName + ' }}' },
    selection: { anchor: pos + varName.length + 6 },
  });
  view.focus();
}

// Before form submit: sync editor content to hidden input
document.getElementById('save-form').addEventListener('submit', () => {
  document.getElementById('body-hidden').value = view.state.doc.toString();
});
```

**esm.sh import note:** `@codemirror/basic-setup` re-exports `EditorView` and `EditorState` in newer versions. If import fails, import `EditorView` directly from `@codemirror/view@6`. The UI-SPEC (22-UI-SPEC.md) specifies `basic-setup@0.20` — use that pinned version.

### Pattern 6: iframe Preview via JS `srcdoc`

The preview panel uses a `<iframe id="preview-iframe">` that is updated by JS, not HTMX `hx-swap` (per D-14 — style isolation from platform CSS). HTMX triggers the fetch; JS handles the iframe update.

```javascript
// Triggered by "Обновить превью" button
document.getElementById('preview-btn').addEventListener('click', async () => {
  const body = view.state.doc.toString();
  const clientId = document.getElementById('client-select').value;
  const siteId = document.getElementById('site-select').value;
  if (!clientId || !siteId) return;

  const resp = await fetch('/ui/templates/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ body, client_id: clientId, site_id: siteId }),
  });
  const html = await resp.text();
  document.getElementById('preview-iframe').srcdoc = html;
});
```

**Note:** The preview endpoint for unsaved templates (new template page) should not require a `template_id` — accept `body` as a form field directly. For the edit page, it can accept either.

### Anti-Patterns to Avoid

- **Passing SQLAlchemy model instances to SandboxedEnvironment:** The sandbox blocks `__class__` and dunder traversal, but allows normal attribute access on any object in context. Always convert to plain dicts in `template_variable_resolver.py` before rendering.
- **Using `on_event("startup")` / `on_event("shutdown")`:** Deprecated. The project already uses `lifespan=` pattern in `app/main.py`.
- **Registering templates router with `include_router` but forgetting navigation entry:** Must add to both `app/main.py` and `app/navigation.py`.
- **HTMX `hx-swap` directly into iframe:** HTMX cannot set `srcdoc`. Use JS fetch + `iframe.srcdoc = response` for style isolation.
- **CodeMirror form body not synced on submit:** The editor's content is NOT in a `<textarea>` — must copy `view.state.doc.toString()` to a hidden `<input name="body">` before the form POST fires.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template variable isolation | Custom string replace / regex | `jinja2.sandbox.SandboxedEnvironment` | Handles loops, filters, conditionals; sandbox blocks dunder traversal |
| Unresolved var highlighting | Post-process HTML with regex | Custom `Undefined` subclass in SandboxedEnvironment | Applied at render time; no post-processing needed; handles nested vars |
| Code editor in browser | `<textarea>` | CodeMirror 6 via CDN | Syntax highlighting, cursor-position API for insert, undo/redo |
| Dependent select (Client→Site) | Custom JS | HTMX `hx-get` + `hx-trigger="change"` | Already used in CRM; exact same pattern |
| UUID primary keys | Auto-increment int | `uuid.uuid4` via `default=uuid.uuid4` | Established convention across all models in this project |

---

## Variable Resolution — Concrete Queries

The 15 variables map to these DB sources:

| Variable | Source Table | Query Method |
|----------|-------------|--------------|
| `client.name` | `clients.company_name` | `select(Client)` |
| `client.legal_name` | `clients.legal_name` | same row |
| `client.inn` | `clients.inn` | same row |
| `client.email` | `clients.email` | same row |
| `client.phone` | `clients.phone` | same row |
| `client.manager` | `users.username` via `clients.manager_id` | JOIN or second query |
| `site.url` | `sites.url` | `select(Site)` |
| `site.domain` | derived from `sites.url` | `urlparse(url).netloc` in Python |
| `site.top_positions_count` | `keyword_positions` | `COUNT(*) FILTER (WHERE position <= 10)` with `DISTINCT ON (keyword_id, engine)` subquery |
| `site.audit_errors_count` | `error_impact_scores` | `COUNT(DISTINCT page_url)` |
| `site.last_crawl_date` | `crawl_jobs` | `MAX(created_at) WHERE status='done'` |
| `site.gsc_connected` | `oauth_tokens` | `COUNT(*) WHERE provider='gsc'` |
| `site.metrika_id` | `sites.metrika_counter_id` | same Site row |

**Performance note:** All 7 queries are indexed and fast. `keyword_positions` is range-partitioned — queries are filtered by `site_id` which uses the FK index. Total expected resolution time < 200ms, well within the 5-second preview budget.

---

## Navigation and Router Registration

**Two files require updates** when adding the templates router:

1. `app/main.py` — add import and `app.include_router(templates_router)`
2. `app/navigation.py` — add child entry `{"id": "crm-templates", "label": "Шаблоны КП", "url": "/ui/templates"}` under the `"crm"` section (id: `"crm"`)
3. `app/template_engine.py` — add `"/ui/templates": "crm"` to `_HELP_MODULE_MAP`

---

## Common Pitfalls

### Pitfall 1: SandboxedEnvironment False Security Assumption
**What goes wrong:** Assuming SandboxedEnvironment prevents all injection, then passing `Site` or `Client` ORM model objects directly into the render context. A template author could access `{{ site.encrypted_app_password }}` or `{{ site.metrika_token }}` since those are normal attributes on the Site model.
**Why it happens:** SandboxedEnvironment only blocks dunder attributes (`__class__`, `__globals__` etc.) — not regular attribute access.
**How to avoid:** Build a flat plain dict in `template_variable_resolver.py` with ONLY the ~15 declared variables. Never pass ORM model objects to `SandboxedEnvironment.from_string().render()`.
**Warning signs:** If the render context dict contains anything other than plain Python types (str, int, bool, dict, list), stop and refactor.

### Pitfall 2: CodeMirror Body Not Submitted with Form
**What goes wrong:** The form POST sends an empty `body` field because CodeMirror's editor content lives in an internal editor state, not in a `<textarea>`.
**Why it happens:** CodeMirror 6 renders into a `contenteditable` div, not a form element.
**How to avoid:** On form `submit` event, run `document.getElementById('body-hidden').value = view.state.doc.toString()` before the submit fires. Use `addEventListener('submit', ...)` with the copy operation as the first step.
**Warning signs:** `body` field arrives as empty string on the server.

### Pitfall 3: Preview Endpoint Returns Platform Styles in iframe
**What goes wrong:** If the preview endpoint returns a full platform page (with base.html) instead of a bare HTML document, the platform's Tailwind/CDN CSS renders inside the iframe, mangling the user's template styles.
**Why it happens:** Reusing the standard `templates.TemplateResponse` with `base.html` inheritance.
**How to avoid:** The preview endpoint returns `HTMLResponse(content=rendered_html)` directly — a raw HTML string with no platform wrapper. The `rendered_html` is the user's template body after Jinja2 rendering. If the template author includes `<html><head><style>...</style></head><body>...</body></html>`, it renders cleanly. If not, the iframe shows bare HTML with browser defaults — acceptable.
**Warning signs:** Preview iframe shows the platform sidebar or Tailwind utility classes.

### Pitfall 4: Alembic Enum Type Conflict
**What goes wrong:** `alembic upgrade head` fails with `type "templatetype" already exists`.
**Why it happens:** PostgreSQL creates named enum types; if a prior failed migration left a partial state, re-running upgrade tries to create the type again.
**How to avoid:** Use `checkfirst=True` on `sa.Enum.create()` in the migration (same pattern as `0044_add_site_intakes_table.py` line: `intakestatus.create(op.get_bind(), checkfirst=True)`).
**Warning signs:** `ProgrammingError: type "templatetype" already exists` during migration.

### Pitfall 5: esm.sh CDN Module Loading Order
**What goes wrong:** `EditorView is not defined` or `basicSetup is not defined` JavaScript errors because ES module imports are async but the initialization code runs synchronously.
**Why it happens:** `<script type="module">` tags are deferred and async by default; if the init code is in a non-module script tag that runs first, imports haven't resolved yet.
**How to avoid:** Put ALL CodeMirror initialization code inside a single `<script type="module">` tag that performs the imports at the top. Do not mix module and non-module script tags for CodeMirror.
**Warning signs:** Console shows `ReferenceError: EditorView is not defined`.

### Pitfall 6: Clone Redirect Before Commit
**What goes wrong:** `HX-Redirect` fires before the new template row is committed to the DB. The edit page for the new clone 404s.
**Why it happens:** `db.flush()` assigns the ID but `db.commit()` finalizes the row. If `HX-Redirect` header is set after flush but before commit, the redirect fires while the transaction is still open.
**How to avoid:** Call `await db.commit()` before setting the `HX-Redirect` header. Same pattern required for all redirect-after-create flows.
**Warning signs:** Redirect lands on 404 for the new clone's edit page.

---

## Code Examples

### Alembic Migration Template (0045)

```python
# Source: 0044_add_site_intakes_table.py pattern
revision = "0045"
down_revision = "0044"

def upgrade() -> None:
    templatetype = sa.Enum("proposal", "audit_report", "brief", name="templatetype")
    templatetype.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "proposal_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("template_type", sa.Enum("proposal", "audit_report", "brief", name="templatetype"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_proposal_templates_type", "proposal_templates", ["template_type"])

def downgrade() -> None:
    op.drop_index("ix_proposal_templates_type", table_name="proposal_templates")
    op.drop_table("proposal_templates")
    sa.Enum(name="templatetype").drop(op.get_bind(), checkfirst=True)
```

### HX-Trigger Toast Pattern (from crm.py)

```python
# Source: app/routers/crm.py line 171
resp = templates.TemplateResponse(request, "proposal_templates/index.html", ctx)
resp.headers["HX-Trigger"] = '{"showToast": "Шаблон сохранён"}'
return resp
```

### HX-Redirect After Clone

```python
# Source: established pattern — commit before redirect
await db.commit()
from fastapi.responses import HTMLResponse as _HTML
resp = _HTML(content="", status_code=200)
resp.headers["HX-Redirect"] = f"/ui/templates/{clone.id}/edit"
return resp
```

### Dependent Select Handler (sites by client)

```python
# Source: app/routers/crm.py pattern — exact same shape
@router.get("/sites", response_class=HTMLResponse)
async def sites_for_client(
    client_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_authenticated),
) -> HTMLResponse:
    result = await db.execute(
        select(Site).where(Site.client_id == client_id, Site.is_active == True)
        .order_by(Site.name)
    )
    sites = list(result.scalars().all())
    # Return outerHTML for the select element
    return HTMLResponse(content=render_sites_select_html(sites))
```

---

## State of the Art

| Old Approach | Current Approach | Impact for Phase 22 |
|--------------|------------------|---------------------|
| CodeMirror 5 (jQuery-dependent) | CodeMirror 6 (ES modules, no jQuery) | Use CM6 — no jQuery in this project |
| `on_event("startup")` | `lifespan=` asynccontextmanager | Already handled in main.py — no action needed |
| Pydantic v1 `@validator` | Pydantic v2 `@field_validator` | Use v2 syntax if adding Pydantic schemas |
| `jinja2.Environment` for user templates | `jinja2.sandbox.SandboxedEnvironment` | Always use sandboxed for user-authored content |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Jinja2 SandboxedEnvironment | TPL-02, TPL-03 | Yes | 3.1.6 | — |
| PostgreSQL | All DB queries | Yes (via asyncpg) | 16.x | — |
| `error_impact_scores` table | `audit_errors_count` variable | Yes (migration 0038) | — | Return 0 if table empty |
| `keyword_positions` table | `top_positions_count` variable | Yes (partitioned, migration 0011) | — | Return 0 if no data |
| `crawl_jobs` table | `last_crawl_date` variable | Yes (existing) | — | Return empty string |
| `oauth_tokens` table | `gsc_connected` variable | Yes (existing) | — | Return False |
| esm.sh CDN (CodeMirror 6) | Editor on edit page | Network-dependent | 0.20/6.x | Graceful degradation to textarea (not recommended — plan for CDN availability) |

**Missing dependencies with no fallback:** None — all server-side dependencies are present.

**CDN note:** esm.sh is a reliable public CDN with SRI support. For production VPS deployment, consider downloading and serving CodeMirror 6 as a static file if the VPS is in a network-restricted environment. This is a deployment concern, not a development blocker.

---

## Project Constraints (from CLAUDE.md)

All directives below must be honored by the planner and executor:

| Directive | Applies To |
|-----------|-----------|
| Python 3.12, FastAPI 0.111+, SQLAlchemy 2.0 async, Alembic, asyncpg, Jinja2 + HTMX — fixed stack | All new files |
| PostgreSQL 16 only; all schema changes via Alembic migrations, no direct schema edits | `0045` migration required |
| Passwords bcrypt, WP credentials Fernet-encrypted, JWT exp=24h | Not directly affected; user auth reuses existing auth system |
| UI pages < 3s; long operations via Celery — UI never blocks | Preview is synchronous (direct DB query) — must complete < 3s; verified achievable |
| pytest + httpx AsyncClient; service layer coverage > 60% by iteration 4 | `template_service.py` and `template_variable_resolver.py` must have unit tests |
| loguru JSON format, DEBUG/INFO/ERROR levels, 10 MB rotation, 30-day retention | Use `logger.debug/info/error` in router and services |
| Do not use: `on_event`, Pydantic v1, `requests`, HTMX 1.x, psycopg2 | None of these are planned for this phase |
| WeasyPrint via subprocess only (STATE.md) | Not applicable — Phase 22 has no PDF generation; Phase 23 owns PDF |
| SandboxedEnvironment for user-authored Jinja2 (STATE.md) | Confirmed — see Pattern 2 above |

---

## Open Questions

1. **Preview endpoint URL: per-template vs generic**
   - What we know: UI-SPEC shows `POST /ui/templates/{id}/preview`; new-template page has no `{id}` yet
   - What's unclear: Should the preview endpoint require a saved template ID, or accept the body directly?
   - Recommendation: Use `POST /ui/templates/preview` (no `{id}`) accepting `body` + `client_id` + `site_id` form fields. For the edit page, the same endpoint works. Template does not need to be saved before it can be previewed.

2. **`top_positions_count` definition: top-10 vs top-3 vs configurable**
   - What we know: CONTEXT.md D-08 says `top_positions_count` without specifying threshold; other services use top-3, top-10, top-30 as separate buckets
   - What's unclear: Is this top-10 (standard SEO metric) or top-3?
   - Recommendation: Default to top-10 (most common SEO definition of "first page"). Use `top10` from the same subquery pattern already in `report_service.py`.

3. **`site.domain` derivation**
   - What we know: `Site.url` stores full URLs like `https://acme.com/`; `domain` is not a DB column
   - What's unclear: Should domain include `www.` or strip it?
   - Recommendation: Use `urlparse(url).netloc` which preserves `www.` as stored in the URL. This is consistent with what users entered when creating the site.

---

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection: `app/models/client.py`, `app/models/site.py`, `app/models/oauth_token.py`, `app/models/crawl.py`, `app/models/site_intake.py`, `app/models/impact_score.py`, `app/models/position.py`
- Codebase direct inspection: `app/routers/crm.py`, `app/routers/intake.py`, `app/auth/dependencies.py`, `app/template_engine.py`, `app/navigation.py`
- Codebase direct inspection: `app/services/client_report_service.py`, `app/services/report_service.py`
- Codebase direct inspection: `alembic/versions/0044_add_site_intakes_table.py` (migration pattern)
- Live Python testing on this machine: `jinja2.sandbox.SandboxedEnvironment` security model, `_HighlightUndefined` implementation
- `22-CONTEXT.md` — 15 locked decisions
- `22-UI-SPEC.md` — component inventory, interaction contracts, CodeMirror 6 CDN decision
- `REQUIREMENTS.md` — TPL-01 through TPL-04 acceptance criteria
- `CLAUDE.md` — technology constraints and security requirements

### Secondary (MEDIUM confidence)
- CodeMirror 6 official documentation patterns (https://codemirror.net/docs/ref/) — `EditorView`, `dispatch`, `selection.main.head` — consistent with training data through Aug 2025
- esm.sh CDN serving `@codemirror/basic-setup@0.20` and `@codemirror/lang-html@6` — consistent with UI-SPEC decision

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all Python dependencies verified installed; CodeMirror 6 via CDN matches UI-SPEC decision
- Architecture: HIGH — all patterns derived from existing codebase (crm.py, intake.py, client_service.py)
- Variable resolution: HIGH — live-tested queries against known schema; all source tables confirmed present
- Pitfalls: HIGH — SandboxedEnvironment security pitfall verified by live testing on this machine
- CodeMirror integration: MEDIUM — API confirmed via documentation; not previously used in this codebase

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable libraries; CodeMirror 6 API is stable)
