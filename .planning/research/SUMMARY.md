# Project Research Summary

**Project:** SEO Management Platform — v3.0 Client & Proposal Milestone
**Domain:** SEO Agency Internal Platform — Client CRM, Audit Intake, Proposal Templates, Document Generator
**Researched:** 2026-04-09
**Confidence:** HIGH

## Executive Summary

This milestone adds the sales and client management layer to an existing 117K LOC FastAPI + Celery + PostgreSQL platform. The platform already handles site monitoring, position tracking, content optimization, and PDF report generation — v3.0 turns it into a tool that can also sell SEO work: managing client companies, onboarding new sites through structured intake forms, and generating commercial proposals (КП) as branded PDFs. The core finding across all four research areas is that no new libraries are needed — every v3.0 capability maps directly to existing stack components, and every new architectural pattern has an established precedent in the current codebase.

The recommended approach is an additive, three-phase build driven by FK dependency order: Client CRM first (anchors all other entities), Site Audit Intake second (can run in parallel with CRM), Proposals and Document Generator third (requires client_id FK from Phase 1). The Document Generator is explicitly not a new subsystem — it is a generalisation of the existing ClientReport / subprocess_pdf.py / Celery lifecycle pattern. The total schema surface is six new tables and four additive changes to existing files.

The highest-risk area is the semantic boundary between Client (a business entity, new table) and User (role=client, existing table). If this distinction is not enforced from the first migration, queries that span client data and user permissions become tangled and future CRM features require expensive refactors. The second critical risk is RBAC scope for CRM endpoints — managers need full CRM access, client-role users need row-level isolation to their own record only. Both risks must be resolved in Phase 1 planning before any code is written.

---

## Key Findings

### Recommended Stack

The existing stack fully covers all v3.0 requirements. No new packages should be added. The key mappings: Jinja2 SandboxedEnvironment handles proposal template rendering from DB-stored templates (security-critical — user-authored templates must not use the main Jinja2Templates singleton); WeasyPrint via subprocess_pdf.py handles all PDF generation (memory leak mitigation, Decision D-12); HTMX section-by-section submission handles multi-step intake forms; SQLAlchemy JSONB columns handle flexible contact metadata on the clients table; Celery default queue handles async PDF generation with the existing pending -> generating -> ready | failed lifecycle.

**Core technologies (v3.0 relevant):**
- **Jinja2 3.1 SandboxedEnvironment**: render DB-stored proposal templates — prevents config.SECRET_KEY injection from user-authored templates; ships with Jinja2, no install needed
- **WeasyPrint 62 via subprocess_pdf.py**: all PDF generation — subprocess isolation prevents memory leaks; call render_pdf_in_subprocess(), never weasyprint.HTML().write_pdf() directly
- **SQLAlchemy 2.0 JSONB columns**: clients.contacts flexible metadata, proposals.resolved_vars snapshot — use JSONB not JSON for GIN indexability
- **Celery 5.4 default queue**: async PDF generation — clone client_report_tasks.py pattern exactly; no new queue needed
- **HTMX 2.0 hx-swap="outerHTML"**: section-by-section intake form saves — pattern already used in pipeline approval flow
- **python-multipart 0.0.9**: all form bodies — already the platform pattern, no change needed
- **Alembic 1.13**: three sequential migrations (0043 clients, 0044 intake, 0045 proposals) — always run alembic check before --autogenerate

### Expected Features

The v3.0 milestone delivers the "sales layer" on top of existing SEO monitoring. Feature research confirms all P1 (launch) features are achievable with existing infrastructure.

**Must have (table stakes / v3.0 MVP):**
- Client cards (name, company, INN/KPP, contacts, manager assignment) — Russian agency context requires INN/KPP for invoicing
- Sites attached to clients via nullable FK — one client owns 1-N sites
- Interaction log (text notes + date + author) — minimum CRM capability
- Site audit intake form (fixed schema, save draft, completion status, pre-populated from existing platform data)
- Proposal template CRUD (admin manages Jinja2-HTML templates with variable placeholders)
- Core variable resolver (client name, site URL, position metrics, audit error count)
- Async PDF generation from template + site data (Celery task, stored bytes, downloadable)
- Document list per client with download links

**Should have (differentiators, v3.x after validation):**
- Intake to proposal pre-fill (intake answers auto-populate proposal variables)
- Platform data variables (live position/traffic queries at render time)
- Send generated document via Telegram / SMTP
- Client health score (aggregate site health widget data)
- Variable overrides at generation time (per-generation override dict)

**Defer to v4+:**
- Client portal (CRM data visible to client-role users)
- E-signature integration
- LLM-assisted proposal copy (opt-in)
- Multi-language template variants
- Public intake form (client-filled, requires auth-free route)

### Architecture Approach

All v3.0 features integrate additively into the existing FastAPI app — no new services, no microservices, no new queues. Three new router/service/model families (clients, intake, proposals) follow the identical async service layer pattern used across 50+ existing services. The Document Generator reuses subprocess_pdf.py and client_report_tasks.py unchanged. The only existing files modified are app/main.py (three include_router() calls), app/navigation.py (new "Клиенты" section), app/celery_app.py (register proposal_tasks), and app/models/site.py (add nullable client_id column). All changes to existing files are append-only.

**Major components (new):**
1. **Client CRM** (app/models/client.py, routers/clients.py, services/client_service.py) — Client + ClientInteraction models; clients and client_interactions tables; migration 0043 also adds sites.client_id nullable FK
2. **Site Audit Intake** (app/models/intake.py, routers/intake.py, services/intake_service.py) — IntakeForm + IntakeResponse models; key-value row storage (not JSONB blob); migration 0044
3. **Proposal Templates + Document Generator** (app/models/proposal.py, routers/proposals.py, services/proposal_service.py, services/proposal_variable_service.py, tasks/proposal_tasks.py) — ProposalTemplate + Proposal models; Celery PDF generation cloned from client_report_tasks.py; migration 0045

**Patterns to replicate exactly:**
- Router -> service -> AsyncSession (no DB logic in routers)
- Celery task: asyncio.run(_run()) wrapper around async code
- PDF: render_pdf_in_subprocess() only — never direct WeasyPrint
- HTMX status polling: hx-trigger="every 3s" until status="ready" or "failed"
- Toast notifications: all POST handlers return HX-Trigger: {"showToast": {...}} header

### Critical Pitfalls

1. **Client/User entity conflation** — Client (company, CRM) and User (role=client, auth) are different concepts sharing one word. Resolve this in Phase 1 schema design before any migration: Client is a new table; users gains a nullable client_id FK; existing Project.client_user_id is left untouched. Never modify the UserRole enum value "client" — it is stored in the DB.

2. **WeasyPrint direct import in document service** — copying the wrong pattern creates an OOM-killing memory leak. The existing subprocess_pdf.py is the only sanctioned PDF API. Add a "WARNING: Never call weasyprint.HTML().write_pdf() directly" docstring to subprocess_pdf.py as the first task in Phase 3, before any document service code is written.

3. **Proposal template Undefined errors on incomplete site data** — Jinja2's default Undefined raises on missing variables; production sites often lack Metrika, positions, or GSC data. Use a ProposalContext Pydantic model with safe defaults ("" or 0) for all variables, and configure the proposal jinja2.Environment with undefined=ChainableUndefined (separate from the UI environment which uses strict undefined for security).

4. **RBAC collision for CRM endpoints** — require_admin locks out managers; require_any_authenticated allows client-role users to see all client data (IDOR). Use require_manager_or_above for all CRM writes; add row-level ownership check in service layer for client-role reads: if user.role == UserRole.client: assert record.client_id == user.client_id.

5. **Alembic migration drift** — 44 existing migrations; alembic revision --autogenerate silently includes stale diffs from unrelated model edits. Run alembic check before every --autogenerate. Review the full generated migration file. Verify alembic heads returns exactly 1 head as acceptance criterion for each phase.

---

## Implications for Roadmap

The FK dependency chain is the primary constraint on phase order: clients table must exist before proposals or documents can reference client_id. Audit intake has no FK dependency on clients (site-scoped) and can be built in parallel, but practical development on a solo stack favors sequential delivery.

### Phase 1: Client CRM Foundation

**Rationale:** All other v3.0 features require a clients table. The Client vs User semantic boundary must be established as a schema decision before any subsequent migration. RBAC patterns for CRM scope must be defined here and reused in Phases 2-3. Navigation restructuring for all v3.0 features belongs here to avoid four separate sidebar commits.

**Delivers:** clients table + client_interactions table + sites.client_id FK (migration 0043); client list page, client detail page, site-to-client attachment UI, interaction log; navigation "Клиенты" section with icon for all v3.0 children

**Addresses:** Client card CRUD (P1), sites attached to clients (P1), interaction log (P1)

**Avoids:** Client/User entity conflation (Pitfall 1), RBAC collision (Pitfall 4), audit_log semantic pollution (Pitfall 8), sidebar overflow (Pitfall 9)

**Must resolve in planning:** ADR covering Client vs User boundary; explicit RBAC rules per endpoint; SET NULL cascade on sites.client_id; sidebar icon for new "Клиенты" section added to sidebar.html

### Phase 2: Site Audit Intake

**Rationale:** Intake is site-scoped (no client_id FK dependency), making it buildable immediately after Phase 1. Intake data drives proposal pre-fill in Phase 3 — the intake_responses table's question_key schema must be designed with Phase 3's variable resolver in mind to enable intake -> proposal pre-fill without a schema rewrite.

**Delivers:** intake_forms + intake_responses tables (migration 0044); HTMX multi-section intake form per site; auto-population of known platform data (WP connected, GSC linked, crawl status); completion status flag; section-by-section save with HTMX outerHTML swap

**Addresses:** Site audit intake form (P1), pre-populated checklist items (P1), save draft and resume (P1), intake completeness score (P2)

**Avoids:** JSONB blob anti-pattern (Pitfall 5) — use typed key-value rows with UNIQUE(form_id, question_key); audit_log semantic pollution (Pitfall 8)

**Must resolve in planning:** question_key naming schema that aligns with Phase 3 variable resolver; JSONB vs typed rows decision (typed rows recommended); GIN index if JSONB is chosen

### Phase 3: Proposal Templates + Document Generator

**Rationale:** Requires clients table from Phase 1 (for proposals.client_id FK). Reuses the complete ClientReport infrastructure — the Document Generator is a generalisation of existing patterns, not a new subsystem. Variable resolver scope must be fixed upfront: static variables in v3.0, live complex aggregation queries deferred to v3.x.

**Delivers:** proposal_templates + proposals tables (migration 0045); admin template CRUD with Jinja2-HTML body and variable syntax; ProposalVariableResolver service (reads report_service, site_service, client_service); Celery async PDF generation task (cloned from client_report_tasks.py); HTMX status polling UI; document download endpoint; document list per client

**Addresses:** Proposal template CRUD (P1), core variable resolver (P1), PDF generation from template (P1), document storage + download (P1), document list per client (P1)

**Avoids:** Direct WeasyPrint import (Pitfall 3), Jinja2 Undefined errors on missing data (Pitfall 6), PDF blob table bloat (Pitfall 7 — add retention Celery Beat task on day 1)

**Must resolve in planning:** Variable resolver scope (static list in v3.0 — confirm with product owner); ProposalContext Pydantic model with safe defaults before first template; SandboxedEnvironment for DB templates; storage strategy for PDF blobs (DB with 3-version retention cap recommended at this scale); resolved_vars JSONB snapshot on every generation (audit trail)

### Phase Ordering Rationale

- FK dependency drives the order: clients before proposals (hard FK dependency); intake before proposals optional but aligns question_key schema with variable resolver
- RBAC patterns established in Phase 1 are reused in Phases 2-3 — consistent require_manager_or_above + row-level client ownership check across all three feature families
- Navigation restructuring in Phase 1 avoids four separate sidebar commits — "Клиенты" section with all four feature children is designed once, icon added to sidebar.html once
- Variable resolver scope decision in Phase 3 planning prevents over-engineering — static variables only in v3.0; deferred live queries keep the migration surface manageable

### Research Flags

All three phases have standard patterns well-documented in the codebase. No phase requires /gsd:research-phase.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Client CRM):** CRUD patterns and RBAC patterns are established. Use /gsd:discuss-phase for Client vs User schema ADR.
- **Phase 2 (Audit Intake):** HTMX multi-section forms and key-value row storage are documented patterns already in the codebase. Use /gsd:discuss-phase for question_key schema alignment with Phase 3.
- **Phase 3 (Proposals + Doc Generator):** Jinja2 sandbox and Celery PDF cloning are fully documented. Use /gsd:discuss-phase to confirm variable resolver scope boundary before planning.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on direct codebase inspection of requirements.txt and all service files; no new libraries required means no compatibility unknowns |
| Features | HIGH (domain) / MEDIUM (competitor UI) | Russian SEO agency KP structure and INN/KPP requirements are well-established; competitor platform features are training-data knowledge without live verification |
| Architecture | HIGH | Based on direct inspection of 35+ routers, 50+ services, Alembic migration history (0042 head), and existing model relationships; all integration points verified against actual code |
| Pitfalls | HIGH | Derived from existing codebase decisions (D-12 WeasyPrint subprocess, RBAC in dependencies.py, migration naming in alembic/versions/) — not generic warnings |

**Overall confidence:** HIGH

### Gaps to Address

- **Variable resolver scope boundary:** Research recommends static variables for v3.0 and deferred live queries for v3.x, but the exact variable list should be confirmed with the product owner during Phase 3 planning. This boundary affects the ProposalContext Pydantic model design.
- **PDF retention strategy:** Research recommends DB storage with 3-version cap and 90-day retention for this scale. If proposal generation volume is expected to exceed 20 sites x 10 versions/year, filesystem storage with path reference in DB should be adopted instead. Confirm expected volume before migration 0045.
- **Rich text editor for proposal templates:** Research explicitly deferred this in favor of a textarea with documented Jinja2 placeholder syntax. If managers require WYSIWYG editing, this becomes a P2 task requiring a JS library decision outside v3.0 scope.
- **Client health score aggregation:** Deferred to v3.x pending stable site health widget data from Phase 18. No schema changes needed now.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection (2026-04-09): app/models/, app/services/, app/tasks/, app/routers/, app/navigation.py, alembic/versions/, requirements.txt
- app/services/subprocess_pdf.py — WeasyPrint subprocess isolation pattern (D-12, Phase 14)
- app/tasks/client_report_tasks.py — canonical Celery PDF task pattern
- app/models/client_report.py — PDF lifecycle model (pending/generating/ready/failed)
- app/models/site_group.py — RBAC primitive (confirmed: not suitable for CRM extension)
- app/auth/dependencies.py — require_role() factory and existing role guards
- alembic/versions/ — migration 0042 is current head; naming conventions verified
- Jinja2 3.1 SandboxedEnvironment documentation — ships with Jinja2 >=2.0
- PostgreSQL 16 JSONB GIN index documentation

### Secondary (MEDIUM confidence)

- SE Ranking, Agency Analytics, Semrush Agency Hub — SEO agency CRM feature conventions (training knowledge, no live verification)
- Russian SEO agency KP structure and INN/KPP invoicing requirements — established practice
- WeasyPrint GitHub issues #2130 and #1977 — memory leak basis for D-12 decision (referenced in project history, not re-verified)

---
*Research completed: 2026-04-09*
*Ready for roadmap: yes*
