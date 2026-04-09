# Architecture Research

**Domain:** Client CRM, Audit Intake, Proposal Templates, Document Generator — v3.0 milestone
**Researched:** 2026-04-09
**Confidence:** HIGH — based on direct codebase inspection, migration 0042, and established patterns

---

## Existing Architecture (as of v2.1)

### System Overview

```
Browser (HTMX + Jinja2)
        │  partial HTML responses / full page loads
        ▼
FastAPI (app/main.py)
  ├── 35+ routers in app/routers/
  ├── Jinja2Templates (shared via app/template_engine.py)
  ├── JWT + cookie auth middleware
  └── slowapi rate limiter
        │
        ├── AsyncSession (SQLAlchemy 2.0 / asyncpg)
        │       └── PostgreSQL 16 (42 Alembic migrations, head: 0042)
        │
        ├── Celery workers (3 queues: default, crawl, wp)
        │       └── Redis 7 broker + redbeat scheduler
        │
        └── WeasyPrint PDF (subprocess-isolated via subprocess_pdf.py)
```

### Central Entity: Site

Every feature in the platform is scoped to a `Site`. The `sites` table is the root anchor — keywords, crawl snapshots, audit results, positions, client reports all carry a `site_id` FK. The new v3.0 features must slot into this existing topology.

### Key Existing Components Relevant to v3.0

| Component | Location | Relevance to v3.0 |
|-----------|----------|-------------------|
| `Site` model | `app/models/site.py` | CRM clients own >= 1 site; proposals reference site data |
| `SiteGroup` model | `app/models/site_group.py` | Closest existing concept to a "client" — groups of sites |
| `Project` model | `app/models/project.py` | Has `client_user_id -> users.id`; partial client relationship |
| `User` model | `app/models/user.py` | 3 roles: admin, manager, client |
| `ClientReport` model | `app/models/client_report.py` | PDF generation lifecycle pattern (pending->generating->ready|failed) |
| `client_report_service.py` | `app/services/` | Jinja2+WeasyPrint subprocess pattern — reuse exactly |
| `subprocess_pdf.py` | `app/services/` | Shared PDF renderer — reuse unchanged |
| `client_report_tasks.py` | `app/tasks/` | Celery async PDF task pattern — clone for document generator |
| `navigation.py` | `app/navigation.py` | NAV_SECTIONS dict — add "Клиенты" section here |
| `base.html` | `app/templates/` | All UI pages extend this; new pages extend it too |
| Alembic migrations | `alembic/versions/` | Next migration will be ~0043 |

---

## New Feature Integration Map

### Feature 1: Client CRM

**What it is:** Client cards with contact info, linked sites, interaction history.

**Integration approach:**

A new `Client` model is the correct abstraction. `SiteGroup` is close but lacks contact fields and is already used for access control. Do not repurpose it.

```
clients (new table)
  id (UUID PK)
  name (str)
  company (str, nullable)
  email (str, nullable)
  phone (str, nullable)
  notes (text, nullable)
  created_at / updated_at

sites (existing table — ADD column)
  client_id (UUID FK -> clients.id, SET NULL, nullable)

client_interactions (new table)
  id (UUID PK)
  client_id (FK -> clients.id CASCADE)
  user_id (FK -> users.id SET NULL)   -- who logged it
  kind (enum: call, email, meeting, note)
  summary (text)
  occurred_at (timestamptz)
```

**Why not extend `SiteGroup`:** SiteGroup is an access-control primitive (`user_site_groups` join table drives RBAC). Adding CRM fields to it conflates two concerns and would require auditing all places that use site groups for permission checks.

**Why `client_id` on `sites` rather than a join table:** One site belongs to at most one client in this context (agency managing client sites). A nullable FK on `sites` is simpler and queryable without a join.

**New files (additions only):**
- `app/models/client.py` — `Client` + `ClientInteraction` models
- `app/routers/clients.py` — CRUD + interaction log routes (`/ui/clients/...`)
- `app/services/client_service.py` — async service layer
- `app/templates/clients/` — list, detail, edit, interactions partial
- Alembic migration ~0043: `clients`, `client_interactions`, `ALTER TABLE sites ADD COLUMN client_id`

**Existing files modified:**
- `app/navigation.py` — add "Клиенты" section to `NAV_SECTIONS`
- `app/main.py` — `include_router(clients_router)`
- `app/models/site.py` — add `client_id` mapped column (nullable)

---

### Feature 2: Site Audit Intake

**What it is:** Structured intake forms for new sites — pre-audit questionnaires and checklists.

**Integration approach:**

This is distinct from the existing `AuditResult` / `AuditCheckDefinition` models (those record crawl-based automated checks). Intake is a human-filled form answered before crawling begins.

```
intake_forms (new table)
  id (UUID PK)
  site_id (FK -> sites.id CASCADE)
  created_by (FK -> users.id SET NULL)
  status (enum: draft, submitted, reviewed)
  submitted_at (timestamptz, nullable)
  reviewed_at / reviewed_by (nullable)

intake_responses (new table)
  id (UUID PK)
  form_id (FK -> intake_forms.id CASCADE)
  section (str -- e.g. "technical", "content", "goals")
  question_key (str -- slug identifier)
  answer (text)
  created_at
  UNIQUE (form_id, question_key)
```

Storing responses as key-value rows (not a JSON blob) allows querying specific responses and evolving question sets without schema changes. A `JSONB` column is viable if question sets are stable and you never need to filter by individual answer — key-value rows are safer here.

**New files:**
- `app/models/intake.py` — `IntakeForm`, `IntakeResponse` models
- `app/routers/intake.py` — routes under `/ui/sites/{site_id}/intake`
- `app/services/intake_service.py` — form CRUD, answer upsert
- `app/templates/intake/` — form, review, status pages
- Alembic migration ~0044: `intake_forms`, `intake_responses`

**Existing files modified:**
- `app/navigation.py` — add intake link under "Сайты" section children
- `app/main.py` — `include_router(intake_router)`

**Integration with Project Health Widget:** The intake form status can be surfaced in the Phase 18 checklist. Add an `intake_submitted` check step — query `intake_forms` for the site, show green if any record has `status = "submitted"`.

---

### Feature 3: Proposal Templates

**What it is:** Commercial proposal (KP) templates with variables populated from platform data.

**Integration approach:**

Templates are text/HTML documents with named variable placeholders (e.g. `{{site_name}}`, `{{keyword_count}}`, `{{top10_positions}}`). Variables are resolved at generation time by querying existing platform data.

```
proposal_templates (new table)
  id (UUID PK)
  name (str)
  description (str, nullable)
  body_html (text -- Jinja2 template syntax)
  is_default (bool)
  created_by (FK -> users.id SET NULL)
  created_at / updated_at

proposals (new table)
  id (UUID PK)
  template_id (FK -> proposal_templates.id SET NULL)
  client_id (FK -> clients.id SET NULL)   -- links to CRM
  site_id (FK -> sites.id SET NULL)       -- links to platform data
  title (str)
  resolved_vars (JSONB -- snapshot of variable values at generation time)
  body_html_rendered (text -- final rendered HTML, stored for re-download)
  pdf_data (LargeBinary, nullable)
  status (enum: draft, generating, ready, failed)
  celery_task_id (str, nullable)
  created_at / updated_at
```

**Variable resolution** is handled by a `ProposalVariableResolver` service that accepts `(site_id, db)` and returns a dict. It pulls from existing services:

```python
# app/services/proposal_variable_service.py
async def resolve_variables(db: AsyncSession, site_id: UUID) -> dict:
    from app.services.report_service import site_overview      # positions
    from app.services.quick_wins_service import get_quick_wins # QW count
    from app.services.site_service import get_site             # site name/url
    # ...
    return {"site_name": ..., "keyword_count": ..., "top10_count": ..., ...}
```

Template rendering: load `body_html` from the template row, create a `jinja2.Environment`, render with resolved vars dict. Do NOT use `FileSystemLoader` here — the template source is in the database. Use `jinja2.Template(body_html).render(**vars)` or `env.from_string(body_html).render(**vars)`.

**New files:**
- `app/models/proposal.py` — `ProposalTemplate`, `Proposal` models
- `app/routers/proposals.py` — routes under `/ui/proposals/`
- `app/services/proposal_service.py` — template CRUD, proposal CRUD
- `app/services/proposal_variable_service.py` — variable resolver (reads existing services)
- `app/tasks/proposal_tasks.py` — Celery task for PDF generation (clone of `client_report_tasks.py`)
- `app/templates/proposals/` — template editor, proposal list, generate, preview
- `app/templates/reports/proposal.html` — WeasyPrint PDF template
- `app/templates/reports/intake_summary.html` — WeasyPrint PDF template for intake
- Alembic migration ~0045: `proposal_templates`, `proposals`

**Existing files modified:**
- `app/celery_app.py` — add `"app.tasks.proposal_tasks"` to `include` list
- `app/navigation.py` — add "КП / Предложения" section
- `app/main.py` — `include_router(proposals_router)`

---

### Feature 4: Document Generator

**What it is:** Generates KP/audit PDFs from templates and aggregated platform data.

**Integration approach:**

This is not a new subsystem — it is the PDF rendering layer that serves Proposals and Audit Intake outputs. The pattern already exists in `client_report_service.py` + `subprocess_pdf.py`. No new infrastructure is needed.

**PDF generation flow (reusing existing pattern):**

```
POST /ui/proposals/{id}/generate
    │
    ▼
Router -> create/update Proposal record (status=pending)
    │
    ▼
Dispatch generate_proposal_pdf.delay(proposal_id)
    │
    ▼
Celery task (app/tasks/proposal_tasks.py)
    ├── resolve_variables(db, site_id)
    ├── render Jinja2 template (DB source): env.from_string(body_html).render(**vars)
    └── render_pdf_in_subprocess(html)   <- reuse subprocess_pdf.py unchanged
    │
    ▼
Proposal.status = "ready", Proposal.pdf_data = bytes, db.commit()
    │
    ▼
GET /ui/proposals/{id}/download
    -> Response(content=pdf_data, media_type="application/pdf")
```

**HTMX polling for status** (same pattern as `client_report_tasks`):
```html
<div hx-get="/ui/proposals/{{id}}/status"
     hx-trigger="every 3s"
     hx-target="this"
     hx-swap="outerHTML">
  Generating...
</div>
```

**No new Celery infrastructure needed.** The `default` queue handles PDF tasks. `generate_proposal_pdf` runs there alongside `generate_client_pdf`. Add `proposal_tasks` to `celery_app.conf.include` only.

---

## Data Flow: Proposal Generation End-to-End

```
User selects client + site + template
         |
         v
POST /ui/proposals/create
  -> create Proposal(status=draft)
  -> redirect to /ui/proposals/{id}/edit
         |
         v
User edits overrides, clicks "Generate PDF"
POST /ui/proposals/{id}/generate
  -> Proposal.status = "pending"
  -> generate_proposal_pdf.delay(proposal_id)
  -> return HTMX partial with polling spinner
         |  (Celery default queue)
         v
generate_proposal_pdf task:
  1. load Proposal + ProposalTemplate from DB
  2. resolve_variables(db, site_id) -> vars dict
  3. store vars snapshot in Proposal.resolved_vars (JSONB)
  4. env.from_string(template.body_html).render(**vars)
  5. render_pdf_in_subprocess(html) -> bytes
  6. Proposal.pdf_data = bytes, status = "ready", db.commit()
         |
         v
HTMX poll hits /ui/proposals/{id}/status
  -> returns "ready" partial with download link
         |
         v
GET /ui/proposals/{id}/download
  -> Response(content=pdf_data, media_type="application/pdf")
```

---

## Recommended Project Structure (new files only)

```
app/
├── models/
│   ├── client.py             # Client, ClientInteraction
│   ├── intake.py             # IntakeForm, IntakeResponse
│   └── proposal.py           # ProposalTemplate, Proposal
│
├── routers/
│   ├── clients.py            # /ui/clients/...
│   ├── intake.py             # /ui/sites/{site_id}/intake
│   └── proposals.py          # /ui/proposals/...
│
├── services/
│   ├── client_service.py
│   ├── intake_service.py
│   ├── proposal_service.py
│   └── proposal_variable_service.py
│
├── tasks/
│   └── proposal_tasks.py     # generate_proposal_pdf, generate_intake_pdf
│
├── templates/
│   ├── clients/
│   │   ├── list.html
│   │   ├── detail.html
│   │   ├── edit.html
│   │   └── partials/interactions.html
│   ├── intake/
│   │   ├── form.html
│   │   ├── review.html
│   │   └── status.html
│   ├── proposals/
│   │   ├── list.html
│   │   ├── detail.html
│   │   ├── template_editor.html
│   │   └── partials/status.html
│   └── reports/
│       ├── proposal.html          # WeasyPrint PDF template
│       └── intake_summary.html   # WeasyPrint PDF template
│
alembic/versions/
├── 0043_clients.py
├── 0044_intake_forms.py
└── 0045_proposals.py
```

---

## Modified Existing Files

| File | Change | Risk |
|------|--------|------|
| `app/main.py` | Add 3 `include_router()` calls | Low — mechanical addition |
| `app/navigation.py` | Add "Клиенты" and "КП" to NAV_SECTIONS | Low — append-only |
| `app/celery_app.py` | Add `app.tasks.proposal_tasks` to include list | Low — append-only |
| `app/models/site.py` | Add nullable `client_id` mapped column | Low — requires 0043 migration |

No existing service, task, or template file requires modification. All changes to existing files are additive.

---

## Architectural Patterns to Follow

### Pattern 1: Async Service Layer

All DB work lives in `app/services/`, not in routers. Routers call service functions with an `AsyncSession` dependency. This is the established pattern across all 50+ existing services.

```python
# app/routers/clients.py
@router.get("/ui/clients/", response_class=HTMLResponse)
async def clients_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager),
) -> HTMLResponse:
    clients = await client_service.list_clients(db)
    return templates.TemplateResponse("clients/list.html", {...})
```

### Pattern 2: Celery PDF Task (existing pattern — replicate exactly)

The `client_report_tasks.py` is the canonical PDF generation flow:
1. Router creates DB record with `status="pending"` and dispatches task
2. Task runs `asyncio.run(_run())` (sync Celery wrapper around async code)
3. Task writes result to DB record (`status="ready"` or `"failed"`)
4. HTMX polls a status endpoint every 3s until ready

Do NOT attempt synchronous WeasyPrint in the router — the memory leak is real and documented as D-12. The subprocess isolation pattern must be used for all PDF generation.

### Pattern 3: Jinja2 Template-in-DB Rendering

For proposal templates stored in the database, do not use `FileSystemLoader`. Use `jinja2.Environment` with `autoescape=True` and silent undefined:

```python
from jinja2 import Environment, Undefined

env = Environment(undefined=Undefined, autoescape=True)
tmpl = env.from_string(template.body_html)
rendered = tmpl.render(**resolved_vars)
```

Set `undefined=Undefined` (not `StrictUndefined`) so missing variable placeholders render as empty string rather than raising at generation time.

### Pattern 4: HTMX Status Polling

Status polling for async PDF tasks follows the established pattern from client_reports. A partial template fragment is returned with `hx-trigger="every 3s"` until the status reaches `"ready"` or `"failed"`, at which point the partial renders without the polling trigger.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Extending SiteGroup for CRM

**What people do:** Add `email`, `phone`, `company` columns to `site_groups` to avoid a new table.

**Why it's wrong:** `SiteGroup` is an RBAC primitive — `user_site_groups` join table controls which users see which sites. Adding CRM fields conflates access control with business data and requires auditing all RBAC checks.

**Do this instead:** Create a new `clients` table. Add nullable `client_id` FK to `sites`. Leave `SiteGroup` unchanged.

### Anti-Pattern 2: Synchronous WeasyPrint in Router

**What people do:** Call `weasyprint.HTML(string=html).write_pdf()` inline in a FastAPI endpoint.

**Why it's wrong:** WeasyPrint leaks memory per render. Decision D-12 (Phase 14) documents this with upstream GitHub issue references. In a long-running FastAPI process this causes unbounded memory growth.

**Do this instead:** Always use `render_pdf_in_subprocess()` from `app/services/subprocess_pdf.py`, called via `await loop.run_in_executor(None, render_pdf_in_subprocess, html)` inside a Celery task.

### Anti-Pattern 3: JSONB Blob for Intake Responses

**What people do:** Store all intake form answers as a single `JSONB` column on the form record.

**Why it's wrong:** Querying specific answers (e.g., "show all sites with goal=SEO"), adding new questions, or versioning question sets requires app-level parsing or awkward JSONB operators. Also harder to index specific fields.

**Do this instead:** `intake_responses` table with `(form_id, section, question_key, answer)` rows. Add `UNIQUE (form_id, question_key)` for upsert on re-submission.

### Anti-Pattern 4: Missing `resolved_vars` Snapshot on Proposals

**What people do:** Skip storing the variable snapshot and re-resolve variables from live DB data when re-downloading a proposal.

**Why it's wrong:** Platform data changes over time. A proposal generated in March should show March's position counts when re-downloaded in June, not June's counts. The snapshot is the audit trail.

**Do this instead:** Always serialize the resolved vars dict to `Proposal.resolved_vars` (JSONB) before rendering. Store `body_html_rendered` (the final HTML after variable substitution) too, so re-download skips template re-rendering.

---

## Build Order and Dependencies

The features have internal FK dependencies that dictate build sequence:

```
Phase A: Client CRM
  clients, client_interactions tables
  sites.client_id column (migration 0043)
        |
        | (client_id FK required by proposals)
        v
Phase B: Site Audit Intake        (parallel with A — no FK dependency)
  intake_forms, intake_responses tables (migration 0044)
        |
        v
Phase C: Proposal Templates + Document Generator
  proposal_templates, proposals tables (migration 0045)
  proposals.client_id FK -> clients (requires Phase A)
  proposal_tasks.py + variable resolver (requires Phase B intake data optional)
```

| Phase | Features | Migrations | Blocks |
|-------|----------|------------|--------|
| A | Client CRM | 0043 | Nothing — first to build |
| B | Audit Intake | 0044 | Nothing — parallel with A |
| C | Proposals + Document Generator | 0045 | Requires Phase A (client_id FK) |

---

## Integration Points Summary

| New Feature | Reads From (existing) | Writes To (existing) | New Tables |
|-------------|----------------------|---------------------|------------|
| Client CRM | `sites`, `users` | `sites.client_id` | `clients`, `client_interactions` |
| Audit Intake | `sites`, `users` | — | `intake_forms`, `intake_responses` |
| Proposal Templates | `sites`, `clients` (new), `users` | — | `proposal_templates`, `proposals` |
| Document Generator | `proposal_templates`, `proposals`, existing data services | `proposals.pdf_data`, `proposals.status` | — (reuses subprocess_pdf.py) |

The document generator's variable resolver calls into existing services:
- `report_service.site_overview()` — position stats (top10/top30 counts)
- `quick_wins_service.get_quick_wins()` — QW count
- `site_service.get_site()` — site name/URL
- `client_service.get_client()` — client name/contact for cover page

---

## Scaling Considerations

At the current deployment scale (20–100 sites, small internal team) no architectural changes are needed beyond the additive changes listed above.

| Concern | Current approach | Notes |
|---------|-----------------|-------|
| PDF generation | Celery default queue, subprocess isolated | soft_time_limit=90 matches existing client_report task |
| Proposal template storage | `body_html TEXT` in DB | Fine for < 1000 templates |
| Intake form responses | Key-value rows | Fast for < 10K responses |
| Client count | Simple CRUD table | Trivial at 20–100 clients |

---

## Sources

- Direct codebase inspection: `app/models/`, `app/services/`, `app/tasks/`, `app/routers/`
- `app/services/subprocess_pdf.py` — WeasyPrint subprocess isolation pattern (D-12)
- `app/tasks/client_report_tasks.py` — canonical Celery PDF task pattern
- `app/models/client_report.py` — PDF lifecycle model pattern (pending/ready/failed)
- `app/navigation.py` — sidebar NAV_SECTIONS structure
- `app/models/site_group.py` — RBAC primitive (confirmed: not suitable for CRM extension)
- `app/models/project.py` — existing `client_user_id` FK (partial client concept)
- `alembic/versions/` — migration 0042 is current head
- `app/celery_app.py` — queue routing and task registration patterns
- `.planning/PROJECT.md` — v3.0 milestone feature list

---
*Architecture research for: SEO Management Platform v3.0 Client & Proposal milestone*
*Researched: 2026-04-09*
