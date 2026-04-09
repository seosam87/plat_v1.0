# Pitfalls Research

**Domain:** SEO Management Platform v3.0 — Adding Client CRM, Site Audit Intake, Proposal Templates, and Document Generator to a 117K LOC FastAPI + Celery + PostgreSQL system with 44 applied Alembic migrations
**Researched:** 2026-04-09
**Confidence:** HIGH

This document focuses exclusively on pitfalls that arise from *adding* these four features to the *existing* v2.1 system. Generic web development mistakes are omitted. Every pitfall is grounded in the codebase's current state — the existing models, auth patterns, Alembic history, and the WeasyPrint subprocess infrastructure already in place.

---

## Critical Pitfalls

### Pitfall 1: Client Entity Conflicts With the Existing User+Site Relationship Model

**What goes wrong:**
The existing system already has a `client` user role in `UserRole` enum (`admin`, `manager`, `client`), a `client_user_id` FK on the `Project` model, and a `site_groups` table. A developer building a Client CRM entity creates a `clients` table with `name`, `contacts`, `linked_sites`, `interaction_history` — and immediately faces ambiguity: is a "client" in the CRM the same as a `client`-role `User`? Or a separate organizational entity that may or may not have a system login? If the answer is not resolved upfront, two competing representations of "client" exist in the DB, and every future query that spans both (e.g., "show this client's sites and their project history") requires joins across both systems.

**Why it happens:**
The CRM "client" is a business entity (a company, with contacts and contracts). The existing `User` with `role=client` is an authentication principal. They are different concepts, but sharing the word "client" causes developers to conflate them, especially when working solo without a reviewer to catch the semantic drift.

**How to avoid:**
- Define the CRM entity as `Client` (company-level) — separate from `User`. A `Client` may optionally have zero, one, or many `User` accounts linked (via a `client_id FK` on `users` or a join table).
- The existing `Project.client_user_id` points to a `User` — do not repurpose this FK to point at the new `Client` table. Keep backward compatibility by leaving `client_user_id` in place and adding a separate `client_id` FK pointing to `Client`.
- Add a `client_id` column to `sites` (nullable, `SET NULL` on delete) so sites can be associated with a CRM client without breaking the existing `site_groups` structure.
- Never rename the existing `client` `UserRole` value — it is stored in the DB enum and renaming requires an Alembic `op.execute("ALTER TYPE userrole RENAME VALUE ...")` which is PostgreSQL 10+ only and must be tested.

**Warning signs:**
- Service code that queries "all sites for a client" that must join `users`, `project_users`, `projects`, and `sites` — this means the CRM client concept was grafted onto the existing user model rather than being a first-class entity.
- A migration that modifies the `users` table to add CRM-style contact fields (phone, company, address) — signals that `User` and `Client` are being merged incorrectly.
- Template code where `client.username` and `client.contact_name` are used interchangeably for the same object.

**Phase to address:**
Phase 1 (Client CRM data model) — the `Client` entity and its relationship to `User` and `Site` must be the first schema decision. Write an ADR (architecture decision record) in the PLAN.md context before any migration is written.

---

### Pitfall 2: Alembic Migration Conflict With 44 Existing Migrations

**What goes wrong:**
The existing chain has 44 migrations with the most recent being `9c65e7d94183_add_report_schedules_table.py` (non-sequential naming). If a new migration is created with `alembic revision --autogenerate` and the developer has any pending local model changes that were not part of a previous migration, `autogenerate` silently includes those diffs in the new migration. This creates a migration that "secretly" alters existing tables as a side effect of the intended change. In production, `alembic upgrade head` applies the new migration and makes unintended schema changes.

**Why it happens:**
`autogenerate` diffs the ORM metadata against the DB state. Any model that has been edited (even whitespace changes that trigger re-detection of column types) will appear in the diff. The developer sees the `CREATE TABLE clients` statement, skims the migration, misses the spurious `ALTER COLUMN` for an unrelated table, and applies it.

**How to avoid:**
- Before any `alembic revision --autogenerate`, run `alembic check` to verify that the current DB state matches the ORM. If it reports differences, investigate them before generating the new migration.
- After generating each migration, read the entire file — not just the new table/column that was intended. Any `op.alter_column()` or `op.drop_*` for tables that are not part of the current feature is a red flag.
- Run `alembic upgrade --sql head` (dry run to stdout) and inspect the SQL before applying to production.
- Name migrations sequentially: `0043_add_clients_table.py`, `0044_add_audit_intake_table.py` etc. The existing `9c65e7d94183_` naming divergence was fine for one migration but mixing naming styles creates confusion in the sort order.

**Warning signs:**
- `alembic heads` returns more than 1 head (two developers working on migrations simultaneously, or a branch that was rebased improperly).
- A migration file's `upgrade()` function contains `op.alter_column()` for `sites`, `users`, or `projects` tables when the developer intended to only add a new table.
- `alembic history` shows a gap in the chain (a migration file that has `down_revision` pointing to a non-existent revision hash).

**Phase to address:**
Every phase — verify `alembic heads` returns exactly 1 head as a first step in each phase's execution. Include this check in the PLAN.md acceptance criteria.

---

### Pitfall 3: PDF Document Generation Ignores the Existing Subprocess Isolation Pattern

**What goes wrong:**
The existing `subprocess_pdf.py` implements subprocess-isolated WeasyPrint rendering to prevent memory leaks (documented in Phase 14 CONTEXT.md, referencing GitHub issues #2130 and #1977). A developer implementing the Document Generator (proposal PDFs) writes a new PDF service that calls `weasyprint.HTML(string=html).write_pdf()` directly in the Celery task, bypassing the subprocess isolation. The memory leak is invisible in development (10 test PDFs) but causes the Celery worker container to exhaust RAM in production (100+ proposals per week), triggering OOM kills mid-task.

**Why it happens:**
The `subprocess_pdf.py` module is not well-advertised as "the only way to call WeasyPrint." A developer implementing a new feature scans `services/` for a PDF example, finds `client_report_service.py`, sees it imports `render_pdf_in_subprocess` — but assumes that complexity was only needed for the specific case there, and uses the simpler direct API for the new feature.

**How to avoid:**
- Document `render_pdf_in_subprocess` as the mandatory PDF rendering API in a docstring at the top of `subprocess_pdf.py`. Add a comment: "# WARNING: Never call weasyprint.HTML().write_pdf() directly in a long-running process. Use this function instead."
- For the Document Generator, extend `subprocess_pdf.py` with a `render_template_pdf(template_name, context)` helper that handles Jinja2 template rendering + subprocess isolation in one call. This makes the correct pattern the easy pattern.
- Proposal PDFs and audit PDFs should use the same Celery task scaffolding as `ClientReport`: `status = pending -> generating -> ready | failed`, with `celery_task_id` stored, so the UI can poll for completion without blocking.

**Warning signs:**
- A new `*_pdf_service.py` that imports `weasyprint` directly rather than `from app.services.subprocess_pdf import render_pdf_in_subprocess`.
- `docker stats` shows the `celery-default` container memory growing monotonically during document generation and not returning to baseline after tasks complete.
- WeasyPrint-related calls appearing in the call stack of the main Celery worker (vs. a subprocess).

**Phase to address:**
Phase 3 (Document Generator / PDF) — the first task in that phase must be extending `subprocess_pdf.py` to support template-based rendering, before any document-generation service code is written.

---

### Pitfall 4: RBAC for CRM Features Collides With the Existing Admin-Only Site Model

**What goes wrong:**
The existing `sites.py` router applies `require_admin` to almost every site management endpoint. The new Client CRM introduces a use case where `manager`-role users need to view and edit client cards, attach sites to clients, and generate proposals — but they should not have the same admin site-management powers (creating sites, editing WP credentials, etc.). If the new CRM routes reuse `require_admin` (the easy, copy-paste choice), managers cannot use the CRM. If a developer uses `require_any_authenticated` to allow all roles including `client`, client-role users can see other clients' data — a data isolation violation.

**Why it happens:**
The existing `require_role` factory in `dependencies.py` provides `require_admin`, `require_manager_or_above`, and `require_any_authenticated` — but no `require_manager_or_above` + "only your own data" guard. The CRM needs a new access pattern: "manager can see all clients, client-role user can only see their own client record."

**How to avoid:**
- Use `require_manager_or_above` for all CRM write operations (create client, edit client, attach sites, generate proposals).
- For client-role read access (e.g., a client viewing their own proposal), add a row-level ownership check in the service layer: `if current_user.role == UserRole.client: assert record.client_id == current_user.client_id`.
- Never use `require_any_authenticated` on any CRM endpoint that returns data about multiple clients. The client role must be scoped to "their own" records only.
- Add a `client_id` FK on `users` (nullable) to formally link a `client`-role User to a `Client` CRM record. Without this FK, the ownership check requires a join through `sites` → `client_id`, which is fragile.

**Warning signs:**
- A CRM router where all endpoints use `require_admin` (managers cannot use the CRM at all).
- A CRM router where all endpoints use `require_any_authenticated` without a row-level check (any client-role user can read all client cards).
- The `Client` service layer contains no `assert` or `raise HTTPException(403)` path for role-based record ownership.

**Phase to address:**
Phase 1 (Client CRM) — RBAC must be specified in the PLAN.md before any route is written. The rule "client-role can read their own record only" must appear as an explicit acceptance criterion.

---

### Pitfall 5: Audit Intake Checklist Stored as JSON Becomes Unqueryable Over Time

**What goes wrong:**
A site audit intake form captures structured answers: technical checks (robots.txt, sitemap), content checks (word count thresholds, schema types found), business context (client goals, target audience). The tempting data model is `audit_intake` with a `responses_json JSONB` column that stores all answers as a freeform dict. This works for rendering the form on screen, but makes reporting impossible: "show me all sites where the client said their goal is 'brand awareness'" or "show me all intakes where robots.txt was missing" requires a PostgreSQL JSON path query (`WHERE responses_json->>'goal' = 'brand_awareness'`). JSON path queries cannot use standard B-tree indexes; the GIN index required for JSONB containment queries is easy to forget, and adding it later requires a full table scan rewrite.

**Why it happens:**
Intake forms feel dynamic and schema-less ("every client has different requirements"). JSONB feels like the right fit. The mistake is treating "flexible input" as equivalent to "unstructured storage." The intake categories (technical, content, business) are well-defined; only the answers vary.

**How to avoid:**
- Store the intake as a typed structure: a `section` column (`technical`, `content`, `business`) and a separate row per checklist item, with `check_key` (string identifier), `check_value` (string or boolean), and `passed` (boolean nullable). This makes queries trivial: `SELECT check_key FROM audit_intake_items WHERE site_id = ? AND passed = FALSE`.
- If full JSONB is used for flexibility, add a GIN index immediately: `CREATE INDEX ix_audit_intake_gin ON audit_intake USING GIN(responses_json)`. Do not defer this index.
- Add a `version` column to the intake table to track which checklist template was used, so that the schema of `responses_json` can evolve without breaking old records.
- Define a Pydantic schema for each section's responses, and serialize to/from JSONB using that schema. This prevents freeform key drift.

**Warning signs:**
- `audit_intake.responses_json` grows to contain keys that are not in the original checklist specification (freeform text added ad-hoc).
- A service function that does `intake.responses_json.get('goal')` instead of a typed attribute — no IDE completion, no type safety.
- `EXPLAIN ANALYZE` on a reporting query shows `Seq Scan on audit_intake` even though an index exists (wrong index type for the query pattern).

**Phase to address:**
Phase 2 (Site Audit Intake) — decide the data model before the migration. Typed rows with `check_key`/`check_value` are recommended. If JSONB is chosen, the GIN index must be in the same migration.

---

### Pitfall 6: Proposal Templates With Variable Substitution Break on Missing Platform Data

**What goes wrong:**
Proposal templates reference platform data variables: `{{ site.keyword_count }}`, `{{ site.avg_position }}`, `{{ top_opportunities | first }}`. These variables are resolved at proposal-generation time. If Metrika is not connected for a site, `site.avg_position` is None. If no position tracking exists, `top_opportunities` is an empty list. Jinja2's default behavior with undefined variables raises `UndefinedError`, which causes the entire proposal generation to fail with a 500 error rather than gracefully substituting a placeholder.

**Why it happens:**
Developers test with the "golden path" site that has all data connected. The template works. Production sites with incomplete data break on generation. The Jinja2 `Environment` by default uses `Undefined` which raises on access — the developer doesn't notice because their test site is complete.

**How to avoid:**
- Use Jinja2's `ChainableUndefined` or `Undefined(silent=True)` mode for proposal template rendering. This renders missing variables as empty strings rather than raising.
- Better: build a `ProposalContext` Pydantic model that represents all template variables with safe defaults. Populate it from platform data where available, defaulting to `"—"` or `0` for missing values. Pass the model to Jinja2 rather than raw ORM objects.
- For critical metrics (position, traffic), add an explicit "data not available" block: `{% if site.avg_position %}{{ site.avg_position | round(1) }}{% else %}Данные позиций не подключены{% endif %}`.
- Add a pre-generation validation step: before rendering, check which data sources are available for the site and warn the user about missing sections in a preview UI ("This proposal will not include position data — position tracking not configured for this site").

**Warning signs:**
- Proposal generation tasks fail with `jinja2.exceptions.UndefinedError` in Celery logs.
- Template development only tested against the developer's own fully-configured site.
- A proposal template that uses `{{ value }}` without any `| default('')` filter or `{% if value %}` guard.

**Phase to address:**
Phase 3 (Proposal Templates) — the `ProposalContext` Pydantic model with safe defaults must be built before the first template is written. The Jinja2 environment for proposals must be configured separately from the UI Jinja2 environment (which uses strict undefined for security reasons).

---

### Pitfall 7: Document Generation Stores PDF Blobs in PostgreSQL and Causes Table Bloat

**What goes wrong:**
The existing `client_reports.pdf_data` column uses `LargeBinary` to store PDF bytes directly in PostgreSQL. This was acceptable for a single `client_reports` table (infrequent generation, one PDF per site per run). For the Document Generator producing proposals on demand, the volume increases: 20 sites × 5 proposal versions × 200 KB per PDF = 20 MB in the first week, growing to hundreds of MB. PostgreSQL is not optimized for large binary blobs — every autovacuum on a table with large TOAST-stored values is expensive, and `pg_dump` for backups grows proportionally.

**Why it happens:**
The developer sees `LargeBinary` working in `ClientReport` and copies the pattern. The difference in generation frequency is not considered.

**How to avoid:**
- For documents generated on demand and potentially in multiple versions, store PDFs on disk (mounted Docker volume) or in object storage, and store only the file path in the DB column: `pdf_path VARCHAR(500)`. Retrieval is a file read, not a DB query.
- If remaining in PostgreSQL for simplicity (acceptable for this scale), add a hard retention policy: `DELETE FROM proposal_documents WHERE created_at < now() - interval '90 days'`. Also implement a "download and delete" pattern — after the user downloads, the binary can be removed from the DB (store `downloaded_at`, delete binary after download).
- Monitor table size monthly: `SELECT pg_size_pretty(pg_total_relation_size('proposal_documents'))`.
- Cap stored versions per proposal to 3 (keep latest 3 generations, delete older ones automatically).

**Warning signs:**
- `proposal_documents` table size growing > 500 MB.
- `pg_dump` duration increasing week-over-week.
- Autovacuum running frequently on `proposal_documents` table (`pg_stat_user_tables.last_autovacuum` multiple times per day).

**Phase to address:**
Phase 3 (Document Generator) — storage strategy must be decided upfront. For this project's scale (20–100 sites, proposals generated on-demand), filesystem storage with path reference in DB is recommended. The Docker Compose volume configuration for document storage must be in the same phase.

---

### Pitfall 8: Interaction History Timeline Becomes an Audit Log Duplicate

**What goes wrong:**
Client CRM interaction history ("called client 2026-04-09, discussed Q2 SEO plan") is tempting to store in the existing `audit_log` table (it's already there, already indexed). A developer adds entries for CRM interactions with `action="client.interaction"` and `entity_type="client"`. This works but the `audit_log` table is designed for system events (site.create, bulk.import) — it has no `interaction_type`, `notes`, or `follow_up_date` fields. Storing CRM interactions there requires overloading `detail_json` with CRM-specific fields. The audit log becomes a dual-purpose table that serves two semantically distinct functions, making both harder to query and maintain.

**Why it happens:**
The `audit_log` table is already available and "works." Adding to it is faster than creating a new table and writing a new service. The divergence only becomes apparent months later when querying "all interactions with ClientX" returns system events mixed with CRM notes.

**How to avoid:**
- Create a separate `client_interactions` table: `(id, client_id, user_id, interaction_type ENUM, notes TEXT, follow_up_date DATE, created_at)`. This is the correct domain model for CRM interaction history.
- The `audit_log` table may still receive a `client.interaction.created` event (one row: "a new interaction was logged") but the interaction content lives in `client_interactions`.
- Keep `audit_log` semantically pure: system-level events, not business notes.

**Warning signs:**
- `audit_log.detail_json` contains keys like `interaction_type`, `follow_up_date`, `notes` — CRM business data in a system event log.
- Queries for "all interactions with client X" require filtering `audit_log` by `entity_type='client'` rather than querying a dedicated CRM table.
- A `detail_json` value that is a freeform note written by a human rather than a machine-generated event description.

**Phase to address:**
Phase 1 (Client CRM) — `client_interactions` table in its own migration, separate from `audit_log`. The service must call `log_action()` for the system event AND insert into `client_interactions` for the CRM record.

---

### Pitfall 9: Sidebar Navigation Grows Unmanageably Without a Section Strategy

**What goes wrong:**
The sidebar has 6 sections with collapsible children, rendered from a `nav_sections` list injected by each router's `get_context()` function (or equivalent). Adding CRM, audit intake, proposal templates, and document generator as new top-level children without a plan fills the sidebar with 4–8 new items, pushing the existing content below the fold. On a laptop screen, the sidebar requires scrolling to reach frequently-used items like Positions and Keywords.

**Why it happens:**
Each new feature adds 1–2 sidebar entries. No single developer "owns" the global sidebar information architecture. Each phase adds its entries without auditing what is already there.

**How to avoid:**
- Before writing any router, decide which sidebar section the new features belong to. Recommendation: add a new section "Клиенты" (Clients) grouping CRM, audit intake, proposals, and documents under one collapsible section with 4 children.
- Audit the existing 6 sections for items that can be collapsed or deprioritized. If the sidebar has items that are rarely used (e.g., Competitors, Architecture — less than 5% of pageviews), consider hiding them behind an "advanced" toggle.
- The sidebar component reads from `nav_sections` — ensure any new section follows the exact same data structure (id, label, icon, children). Look at how the icon name maps to SVG in `sidebar.html` — a new section with an icon not in the existing `{% elif section.icon == '...' %}` chain will render no icon.
- Add the new icon branch to `sidebar.html` in the same commit that adds the new nav section.

**Warning signs:**
- `sidebar.html` has more than 10 top-level sections.
- A new sidebar item appears without an icon (blank space where icon should be) — the icon name was not added to the `{% elif %}` chain.
- Users report needing to scroll the sidebar to find Keywords or Positions after the new features were added.

**Phase to address:**
Phase 1 (Client CRM) — sidebar section design for all v3.0 features should be decided at the start of the first phase, not added feature-by-feature.

---

## Technical Debt Patterns

Shortcuts that seem reasonable for v3.0 but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Storing proposal/audit data in `detail_json` on `audit_log` | No new table needed | Unqueryable business data mixed with system events; two semantically different things in one table | Never |
| Calling `weasyprint.HTML().write_pdf()` directly in Celery task for proposals | Simpler code | Memory leak; OOM kills after 50+ PDFs; copied from wrong pattern | Never — always use `render_pdf_in_subprocess` |
| Using `require_any_authenticated` on CRM list endpoints | Easier to code | Client-role users can see all clients' data — data isolation violation | Never |
| Storing PDF blobs in `LargeBinary` for proposal documents | Consistent with existing `client_reports` pattern | DB bloat; slow backups; autovacuum overhead at scale | Acceptable for proposals with strict 3-version retention + auto-delete policy |
| JSONB for all audit intake responses without GIN index | Flexible schema, fast to build | Seq scans on reporting queries; unindexed containment checks | Acceptable only with GIN index in the same migration |
| Adding CRM navigation items to existing sections rather than a new "Clients" section | Avoids sidebar restructuring work | 8+ ungrouped items; sidebar requires scrolling | Never — new section needed |
| Sharing `client_user_id` on `Project` as the CRM client link | No new FK column | Conflates authentication principal (User) with business entity (Client); blocks future CRM features that don't involve system access | Never for new CRM work; leave existing FK untouched |
| Generating proposal PDFs synchronously in the request handler | Simpler endpoint code | Blocks HTTP worker for 5–30 seconds; violates < 3s page response constraint | Never — Celery task from the start |

---

## Integration Gotchas

Common mistakes when connecting the new v3.0 features to the existing system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Client CRM + existing `User` (role=client) | Treating a `User` record as the CRM `Client` record | `Client` is a company entity; `User` is an auth principal; link them via `users.client_id FK` but keep separate tables |
| Client CRM + `Site` | Adding a `client_id` column to `sites` and forgetting `SET NULL` on delete | Always use `ForeignKey("clients.id", ondelete="SET NULL")` — a deleted client should not cascade-delete all their sites |
| Proposal Templates + Jinja2 environment | Reusing the same `Jinja2Templates` instance used for UI rendering | Proposals need `Undefined(silent=True)`; the UI needs strict undefined for security. Use a separate `jinja2.Environment` for document rendering |
| Document Generator + WeasyPrint | Importing `weasyprint` directly in the new service | Always call `render_pdf_in_subprocess()` from `subprocess_pdf.py` |
| Audit Intake + existing `audit_service.py` | Naming the new intake model `Audit` (conflicts with existing `audit.py` / `audit_service.py`) | Name it `IntakeForm` or `AuditIntake` to avoid import collisions |
| Audit Intake + `audit_log` | Recording intake submission as a long-form `audit_log` entry | Log the event minimally in `audit_log` (action="intake.submitted"); full intake data goes in `audit_intake_items` |
| HTMX forms for CRM + existing toast pattern | Not returning `HX-Trigger: {"showToast": ...}` header from CRM endpoints | All form POST handlers in this codebase return HTMX response headers for toast notifications; follow the same pattern |
| Alembic + new tables | `alembic revision --autogenerate` picking up stale diffs from older model edits | Always run `alembic check` before generating a new revision; fix any pre-existing diffs first |

---

## Performance Traps

Patterns that work in development but fail at production data volumes.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching all sites for a client with eager-loaded keyword counts | Page load > 3s for a client with 20+ sites | Use a subquery or CTE to count keywords per site; do not load all keyword rows | At 5+ sites with 1000+ keywords each |
| Interaction history query without `LIMIT` | Client timeline page takes 10+ seconds for clients active for 2+ years | Always `ORDER BY created_at DESC LIMIT 50` with cursor pagination | After ~500 interaction records per client |
| WeasyPrint called inline in HTTP request for "preview" | HTTP timeout for large templates | Preview mode renders only page 1 of the document (add `?preview=1` param that truncates data) or returns HTML without PDF conversion | Immediately for proposals > 3 pages |
| Generating proposals for all sites in a batch without Celery `group` | Single task holds worker for 10+ minutes; other tasks queue | Use `celery.group()` — one task per document, results joined | At 10+ documents in one batch |
| Storing `client.notes` as unlimited `Text` with full-text search via `ILIKE '%query%'` | Notes search slows as CRM grows | Add PostgreSQL full-text search index (`tsvector`) if notes search is needed, or use `ILIKE` only with a `LIMIT 100` | After ~1000 client notes |

---

## Security Mistakes

Domain-specific security issues for v3.0 features.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Client-role user can access another client's CRM card via direct URL (IDOR) | Client A reads Client B's proposal, contacts, interaction history | Row-level ownership check in every CRM service function: `if user.role == client: assert record.client_id == user.client_id` |
| Proposal PDF accessible via a predictable or unauthenticated URL | Anyone with the link can download proposals (contain pricing, SEO strategy) | Serve PDFs via an authenticated endpoint: `GET /proposals/{id}/download` with `require_manager_or_above` check; never serve from static files |
| Audit intake form accepts arbitrary file uploads for "site screenshots" without validation | Remote code execution via malicious file, or disk exhaustion | If file upload is added to intake forms, reuse the existing `upload_service.py` with file type validation and size limits; store in a dedicated path |
| CRM contacts stored with phone/email as plaintext | PII in DB plaintext — GDPR concern for EU clients | Acceptable for an internal tool at this scale, but add a note in the model docstring: "PII stored plaintext — do not replicate to logs or external services" |
| Proposal template variables can be set by managers to inject HTML into generated PDFs | XSS in the PDF (low severity, but messy) | Auto-escape all template variables in the proposal Jinja2 environment: `autoescape=True` |

---

## UX Pitfalls

Common user experience mistakes for these specific features.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Audit intake form has 50+ fields with no section grouping | Users abandon the form halfway through | Group into 4–5 collapsible sections (Technical, Content, Business Goals, Competitors, Notes); show a completion progress indicator |
| Proposal generation has no "generating..." feedback | User clicks "Generate PDF" and sees nothing for 30 seconds | Return HTMX response immediately with a spinner + Celery task ID; poll status with `hx-get` every 3 seconds; show "Ready — Download" when complete |
| Proposal template editor has no preview | Template editor produces broken PDFs due to Jinja2 syntax errors | Add a "Preview HTML" button that renders the template with sample data in-browser (HTML only, no PDF) before committing |
| Client CRM shows all sites for a client without SEO health summary | Manager must navigate to each site individually to get context | Show inline health badges (position trend arrow, last crawl date, issue count) next to each site in the client card |
| Audit intake does not pre-fill known data from the platform | User manually types information the platform already has (sitemap URL, crawl issue count, top keywords) | Pre-populate intake form fields from existing site data wherever possible: `site.url`, `audit_results`, `keyword_count` |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Client CRM:** `Client` entity is distinct from `User` (role=client) — verify that creating a client does not touch the `users` table and that `users.client_id FK` is nullable.
- [ ] **Client CRM:** Row-level access for client-role users implemented — verify that a client-role user cannot fetch another client's card via direct API call (`GET /clients/{other_id}` returns 403, not 200).
- [ ] **Client CRM:** `clients.id` is referenced in `sites` with `SET NULL` cascade — verify by deleting a test client and confirming that associated sites still exist with `client_id = NULL`.
- [ ] **Audit Intake:** JSONB responses have a GIN index (if JSONB approach chosen) — verify with `\d audit_intake` in psql that the index appears.
- [ ] **Audit Intake:** Form pre-populates known site data — verify by opening intake for a fully-configured site and confirming that auto-populated fields appear.
- [ ] **Proposal Templates:** Jinja2 environment for templates uses `Undefined(silent=True)` — verify by rendering a proposal with a variable that has no data and confirming it outputs `""` not a 500 error.
- [ ] **Proposal Templates:** `ProposalContext` Pydantic model has safe defaults for all fields — verify by passing an empty `Site` object and confirming every template variable renders without error.
- [ ] **Document Generator:** Calls `render_pdf_in_subprocess()` — verify that no `import weasyprint` appears in the new document service file.
- [ ] **Document Generator:** PDF generation is Celery-async — verify that the generate endpoint returns immediately with a task ID, not after 30 seconds.
- [ ] **Document Generator:** Retention policy implemented — verify that old document blobs are deleted after 90 days (check Celery Beat schedule in Flower).
- [ ] **Sidebar:** New "Clients" section has a working icon — verify that the sidebar renders the icon correctly (no blank space) after adding the new nav section.
- [ ] **Alembic:** `alembic heads` returns exactly 1 head after all v3.0 migrations — verify in CI.
- [ ] **RBAC:** All CRM write endpoints use `require_manager_or_above` — verify with a test that sends a request authenticated as a `client`-role user and expects 403.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Client/User entity conflation discovered after migration | HIGH | Requires a new migration to create `Client` table, backfill from `users` where `role=client`, add FKs, update service layer; data is not lost but schema migration is complex |
| Alembic multiple heads | LOW | `alembic merge heads -m "0045_merge_v3_heads"`; review and apply; takes < 30 minutes |
| WeasyPrint OOM (wrong pattern used for document generation) | LOW-MEDIUM | Restart Celery worker container; refactor document service to use `render_pdf_in_subprocess`; redeploy; all in-flight documents must be regenerated |
| JSONB without GIN index (reporting queries are slow) | LOW | `CREATE INDEX CONCURRENTLY ix_audit_intake_gin ON audit_intake USING GIN(responses_json)` — runs online without locking the table |
| PDF blobs causing DB bloat | MEDIUM | One-time cleanup: export blobs to filesystem, update `pdf_path` column, `UPDATE` to set `pdf_data = NULL`, `VACUUM FULL`; takes 1–2 hours |
| Proposal template Undefined errors in production | LOW | Set `undefined=ChainableUndefined` in the Jinja2 environment and redeploy; 5-minute fix |
| Client-role IDOR vulnerability discovered | HIGH | Immediate hotfix: add ownership check to all CRM service functions; audit logs to determine if any data was accessed improperly; notify affected users |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Client/User entity conflation | Phase 1 (Client CRM) | `Client` table exists; `users` table unchanged except for nullable `client_id` FK |
| Alembic migration drift | Every phase | `alembic check` passes before each `revision --autogenerate`; `alembic heads` returns 1 |
| WeasyPrint direct import in document service | Phase 3 (Document Generator) | `grep -r "import weasyprint" app/services/` returns only `subprocess_pdf.py` |
| RBAC collision (manager vs admin vs client scope) | Phase 1 (Client CRM) | Test: client-role user cannot access other client's data |
| Audit intake unqueryable JSONB | Phase 2 (Audit Intake) | GIN index present OR typed rows used; reporting query uses index (EXPLAIN ANALYZE) |
| Proposal template Undefined errors | Phase 3 (Proposal Templates) | Template renders without error for a site with zero connected data sources |
| PDF blob table bloat | Phase 3 (Document Generator) | Retention Celery task appears in Flower schedule on day 1 |
| CRM interaction history in audit_log | Phase 1 (Client CRM) | `client_interactions` table exists; `audit_log` only contains event summary |
| Sidebar overflow | Phase 1 (Client CRM) | "Clients" section added with icon; sidebar items per section ≤ 6 |

---

## Sources

- WeasyPrint memory leak: project history Phase 14 CONTEXT.md (D-12), `subprocess_pdf.py` module docstring, WeasyPrint GitHub issues #2130 and #1977
- Existing auth model: `app/auth/dependencies.py` — `require_role()`, `require_admin`, `require_manager_or_above`, `require_any_authenticated`
- Existing RBAC pattern: `app/routers/sites.py` — `require_admin` applied to all site management endpoints
- Existing PDF pattern: `app/services/client_report_service.py` + `app/services/subprocess_pdf.py`
- Existing Alembic chain: 44 migrations, most recent `9c65e7d94183_add_report_schedules_table.py`
- Existing User model: `app/models/user.py` — `UserRole` enum with `admin`, `manager`, `client` values
- Existing Project model: `app/models/project.py` — `client_user_id` FK on `users.id`
- Existing Site model: `app/models/site.py` — no `client_id` column currently
- Existing sidebar: `app/templates/components/sidebar.html` — icon name mapped to SVG via `{% elif %}` chain; new icons require adding a new branch
- Jinja2 `Undefined` behavior: Jinja2 3.1 documentation — `Environment(undefined=Undefined)` raises on access; `ChainableUndefined` or `DebugUndefined` silently returns empty string
- PostgreSQL JSONB GIN indexing: PostgreSQL 16 documentation — `CREATE INDEX ... USING GIN(jsonb_col)` required for `@>` containment queries; B-tree index on JSONB does not help
- HTMX toast pattern: existing `base.html` — `htmx:responseError` event handler + `showToast()` JS function; all POST handlers should return `HX-Trigger: {"showToast": {...}}` header

---
*Pitfalls research for: SEO Management Platform v3.0 (Client CRM, Audit Intake, Proposal Templates, Document Generator)*
*Researched: 2026-04-09*
