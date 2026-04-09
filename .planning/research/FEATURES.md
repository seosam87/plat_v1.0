# Feature Research — v3.0 Client & Proposal

**Domain:** SEO Agency Internal Platform — Client CRM, Audit Intake, Proposal Templates, Document Generator
**Researched:** 2026-04-09
**Confidence:** HIGH (domain knowledge) / MEDIUM (competitor UI patterns — no live WebSearch available)

---

## Context: What Exists vs What's New

The platform already has: sites, site_groups, users (3 roles), projects linked to sites, client_user_id on Project, PDF generation via WeasyPrint (subprocess), ClientReport model (PDF bytes in DB), Kanban, content plan, PDF briefs, scheduled delivery.

v3.0 adds the **sales and client management layer** — the bridge between "we monitor SEO" and "we sell SEO work and document it." The four feature groups are:

1. **Client CRM** — company/contact cards, interaction history, sites attached to clients
2. **Site Audit Intake** — structured questionnaire/checklist for onboarding new sites
3. **Proposal Templates** — variable-driven КП (commercial proposal) templates
4. **Document Generator** — render any template + live platform data → PDF

---

## Feature Group 1: Client CRM

### What SEO Agencies Expect (Industry Norms)

SEO agencies managing 20–100 sites need client records separate from User accounts. The existing `users` table has a `client` role, but a client organisation may have multiple contacts, multiple sites, and a history of communications — none of which fits the User model. Tools like SE Ranking, Agency Analytics, and Semrush Agency Hub all distinguish between "client as user" and "client as account."

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Client card (company name, legal name, INN/KPP, phone, email, notes) | Every agency CRM has this; Russian market requires INN/KPP for invoicing | LOW | New `clients` table; separate from `users` |
| Attach sites to client | A client owns 1–N sites; managers need to see all sites for one client | LOW | FK from `sites` to `clients`; sites already exist |
| Attach user accounts to client | Client portal users belong to a client org | LOW | `client_user_id` on Project is a start; need `clients` → `users` mapping |
| Interaction log (notes + date + author) | Agencies log calls, emails, decisions per client | MEDIUM | Simple `client_interactions` table: text, timestamp, user_id |
| Client list page with search/filter | Without this the CRM is unusable at 20+ clients | LOW | Jinja2 table + HTMX filter |
| Client detail page | Summary of all attached sites, open tasks, recent interactions | MEDIUM | Aggregation query across sites, tasks, interactions |
| Assign manager to client | Each client has a primary responsible manager | LOW | FK `clients.manager_id` → `users` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Client health score | Aggregate site health widget data (from Phase 18) into a client-level score | MEDIUM | Requires joining site health checklist states across all client sites |
| "Sites needing attention" widget on client card | Surfaces sites where crawl failed, positions dropped, or audit errors spiked | MEDIUM | SQL aggregation across `crawl_pages`, `positions`, `platform_issues` |
| Interaction log linked to generated documents | "Sent proposal on 2026-04-01" as a linked entry | LOW | Add `document_id` FK to `client_interactions` |
| Client-scoped report delivery settings | Override global Telegram/SMTP delivery settings per client | HIGH | Separate delivery config per client; complex but valuable for white-label agencies |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full CRM pipeline (deal stages, sales funnel, probability) | Looks useful on paper | Scope creep; this platform is SEO monitoring, not Salesforce. A 5-stage sales pipeline requires 2–3 weeks of UI alone and won't be used | Keep interaction log as simple notes; integration with external CRM is a future bridge |
| Email composer inside the platform | "Send proposal from here" is appealing | Adds SMTP auth, threading, reply tracking complexity that derails the milestone | Generate the PDF; the team sends it from their own email client |
| Contact deduplication / merge | Real CRM problem | Not relevant at 20–100 clients scale | Just add a "duplicate?" warning if email matches |
| Client portal login scoped to CRM data | Client users see "their" CRM card | Client role already exists and is scoped by site access; extending RBAC to CRM entities is a high-complexity second-order change | Defer; in v3.0 CRM is admin/manager-only |

---

## Feature Group 2: Site Audit Intake

### What SEO Agencies Expect

When onboarding a new site, agencies run through a structured checklist: access verification, existing analytics setup, competitive context, client goals, technical baseline. This is typically a Google Form or Notion template filled out by the manager. Platforms like SE Ranking have "Site Audit" as a technical crawler report, but intake questionnaires are usually handled externally. An internal intake form tied to the site record is a genuine workflow improvement.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Intake form per site | Structured capture of: site access, goals, competitors, GSC status, Metrika status, existing SEO setup | MEDIUM | `site_intake` table with JSONB answers + structured fields |
| Checklist of verification steps | Manager works through: WP credentials verified, GSC connected, Metrika connected, sitemap found, crawl completed | LOW | Reuse the empty_state / health widget pattern from Phase 18/19 |
| Pre-populated fields from existing platform data | If WP is already connected and GSC is linked, those checklist items auto-check | LOW | Join against `sites`, `oauth_tokens`, `service_credentials` |
| "Intake complete" status on site | Other features (briefs, proposals) can gate on intake completion | LOW | Boolean flag + completion timestamp on `sites` or `site_intake` |
| Save draft and resume | Long checklist; manager may not fill it in one session | LOW | JSONB partial state; standard form save pattern |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-generate baseline crawl on intake completion | "Complete intake → trigger first crawl" one-click | LOW | Celery task trigger; crawl infrastructure already exists |
| Intake → proposal pre-fill | Answers from intake (competitors, goals, current traffic) pre-populate proposal template variables | MEDIUM | Requires intake data model to align with proposal variable schema |
| Intake completeness score | Show % of fields filled; surfaces when a site was hastily onboarded | LOW | Count non-null fields / total fields |
| Section-by-section HTMX save | Each section saves independently; no full-page reload | LOW | Pattern already used in existing forms |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Public intake form (client fills it) | "Client submits their own info" | Requires auth-free form route with CSRF, email delivery, and spam protection — 3 separate concerns | Manager fills it in based on a discovery call; the platform is internal |
| Dynamic form builder (custom fields) | Feels flexible | The SEO intake domain is fixed enough that a well-designed fixed schema covers 95% of cases; a form builder is a product in itself | Ship a well-structured fixed form with a "notes" overflow field |
| Version history of intake answers | "Track how requirements changed" | Audit log already captures changes; full version history requires event-sourcing complexity | Rely on audit_log for change tracking |

---

## Feature Group 3: Proposal Templates

### What SEO Agencies Expect

A "commercial proposal" (КП, коммерческое предложение) in Russian SEO agency context is a 5–15 page PDF that includes: agency branding, client-specific stats from the audit, scope of work (list of services), pricing table, timeline, and contact details. Currently this is done in Google Docs or Notion with manual copy-paste of platform data. The workflow pain is exactly this copy-paste step.

Tools like SE Ranking and Semrush have "reports" but not proposal templates. Proposify and PandaDoc are dedicated proposal tools (overkill for an internal platform). The gap is clear: a template system that knows about the platform's data.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Template library (admin manages, managers use) | Multiple proposal types: initial audit КП, monthly retainer КП, one-time project КП | MEDIUM | `proposal_templates` table with Jinja2 template body as TEXT; admin CRUD |
| Variable system (merge fields) | `{{client_name}}`, `{{site_url}}`, `{{top_position}}`, `{{audit_errors_count}}` | MEDIUM | Define variable schema; resolver pulls from DB at render time |
| Preview mode (render with sample data) | Manager needs to see what the template looks like before sending | MEDIUM | Render with dummy data or real site data; WeasyPrint already works |
| Template versioning (active / draft) | Avoid breaking live proposals when editing templates | LOW | `is_active` boolean + `version` integer on template |
| Rich text editing for template body | Marketing copy needs formatting: bold, lists, headings | HIGH | Inline rich text editor (Quill.js or similar) OR Jinja2 HTML with a textarea fallback |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Platform data variables (live from DB) | `{{positions_improved_count}}`, `{{crawl_errors}}`, `{{metrika_sessions_30d}}` — real numbers from the site at proposal generation time | HIGH | Variable resolver service that maps template vars to SQL queries |
| Intake-driven variables | `{{client_goal}}`, `{{main_competitors}}` sourced from site_intake answers | MEDIUM | Intake answers → variable resolver; requires Feature Group 2 first |
| Service rate card integration | Pricing table variables pull from a configurable rate card (hourly rates, service bundles) | MEDIUM | `rate_cards` table; admin manages; `{{price_monthly_seo}}` resolves to rate |
| Template cloning | "Duplicate and modify" is faster than starting from scratch | LOW | Standard copy row operation |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| E-signature integration (DocuSign, etc.) | "Send and sign in one step" | OAuth flows, legal compliance, webhook handling — entire separate product area | Generate PDF; team sends via email for signing separately |
| Real-time collaborative editing | "Multiple managers work on the same proposal" | Conflict resolution, WebSocket state — SPA-territory complexity | One editor at a time; last-write-wins is fine at this team size |
| LLM-generated proposal copy | "AI writes the pitch text" | LLM output is non-deterministic; proposal text is legally significant; the platform already gates LLM features as opt-in | Keep copy as human-written template text; LLM opt-in can be added in v3.x |
| Multi-language template variants | Russian + English version of same template | Doubles template management overhead | Ship Russian-first; add language field later if needed |

---

## Feature Group 4: Document Generator

### What SEO Agencies Expect

"Generate PDF" is a two-step operation: (1) select a template, (2) bind it to a client + site + optional date range, then render to PDF. The platform already does this for `client_reports` and `briefs`. The v3.0 document generator extends this to proposals and audit intake outputs.

The key expectation: a generated document is stored, downloadable later, and optionally deliverable via Telegram/SMTP.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Generate PDF from proposal template + site data | Core value proposition of the milestone | MEDIUM | Reuse WeasyPrint subprocess pattern; new `generated_documents` table |
| Document list per client / per site | Manager needs to find previously generated proposals | LOW | Table with filter by client, site, document type, date |
| Download link (served from app, not stored on disk) | DB-stored PDF bytes pattern already established in `client_reports` | LOW | Existing `/client_reports/{id}/download` pattern to clone |
| Async generation (Celery task) | Complex proposals may take 3–5 seconds to render; UI must not block | LOW | Pattern already established in `client_reports` (pending → ready) |
| Document status (pending / ready / failed) | Users need feedback during generation | LOW | Reuse `ClientReport.status` lifecycle pattern |
| Document type enum (proposal / audit_report / brief) | Different templates for different document types | LOW | `DocumentType` enum on `generated_documents` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Send generated document via Telegram | "Generate and send to client" in one action | MEDIUM | Celery task; `telegram_service` already exists; need client-level bot token config |
| Send via SMTP | Same as above but email attachment | MEDIUM | `aiosmtplib` already in stack; need document attachment support |
| Document audit trail | Who generated what document, when, for which client | LOW | `audit_log` table already exists; add document generation events |
| Auto-generate proposal after intake completion | Workflow trigger: intake complete → auto-draft first proposal | MEDIUM | Celery task trigger; requires Feature Groups 2 + 3 first |
| Variable overrides at generation time | Manager can override `{{price_monthly_seo}}` at generate time without editing the template | MEDIUM | Override dict stored in `generated_documents.variable_overrides` JSONB |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| DOCX / Word export | Some clients want Word files | `python-docx` is out of scope per PROJECT.md; adds a maintenance dependency for a niche use case | PDF is universal; WeasyPrint output is clean and printable |
| Online proposal viewer (HTML, not PDF) | "Looks more modern" | Requires a public-facing auth-free URL, link expiry, analytics tracking — significant security surface | Download PDF; share file via any channel |
| Template-per-generated-document editing | "Edit this specific proposal before sending" | Turns the generator into a WYSIWYG editor; complex state management | Template has a rich text body; generate, download, edit in external tool if needed |
| Bulk generation (all clients at once) | "Send monthly reports to all clients" | The scheduler + report delivery system already handles periodic reports; proposals are intentional, one-at-a-time acts | Use existing scheduled delivery for periodic reports; proposals are manual |

---

## Feature Dependencies

```
Client CRM (clients table)
    └──required by──> Site Audit Intake (intake.client_id)
    └──required by──> Proposal Templates (proposal.client_id)
    └──required by──> Document Generator (document.client_id)

Site Audit Intake
    └──enhances──> Proposal Templates (intake answers → template variables)
    └──enhances──> Document Generator (intake completion → auto-draft trigger)

Proposal Templates
    └──required by──> Document Generator (template → rendered PDF)

Existing: WeasyPrint PDF infrastructure (client_reports pattern)
    └──reused by──> Document Generator

Existing: Celery async task pattern (client_reports generation)
    └──reused by──> Document Generator

Existing: sites, site_groups, users, projects, audit_log
    └──extended by──> all four feature groups

Existing: telegram_service, aiosmtplib
    └──extended by──> Document Generator delivery
```

### Dependency Notes

- **Client CRM must come first:** Site Audit Intake, Proposals, and Documents all need a `clients` table with IDs to link to.
- **Proposal Templates before Document Generator:** Can't generate a document without a template.
- **Site Audit Intake is independent of Proposals** (can be built in parallel), but intake → proposal pre-fill requires both to exist.
- **Document Generator reuses 80% of existing `client_reports` infrastructure.** The pattern (Celery task, PDF bytes in DB, status lifecycle, download endpoint) just needs to be generalised into a `generated_documents` table covering multiple document types.

---

## MVP Definition

### Launch With (v3.0)

The minimum that delivers the milestone goal ("turn the platform into a sales tool"):

- [ ] **Client cards** (name, contacts, INN/KPP, notes, manager assignment) — without this nothing else has an anchor
- [ ] **Sites attached to clients** — the core data relationship
- [ ] **Interaction log** (text notes + date) — bare minimum CRM capability
- [ ] **Site audit intake form** (fixed schema, save draft, completion status) — structured onboarding
- [ ] **Pre-populated checklist items** from existing platform data (WP connected, GSC linked, Metrika linked)
- [ ] **Proposal template CRUD** (admin manages templates with Jinja2-style variable syntax)
- [ ] **Core variable resolver** (client name, site URL, key position metrics, audit error count)
- [ ] **Generate PDF from template + site** (async Celery, stored as bytes, downloadable)
- [ ] **Document list per client** with download links

### Add After Validation (v3.x)

Features to add once the core flow works:

- [ ] **Intake → proposal pre-fill** — once intake data model is stable
- [ ] **Platform data variables** (live position/traffic queries at render time) — once variable resolver pattern is established
- [ ] **Send document via Telegram / SMTP** — once document model is stable
- [ ] **Client health score** — aggregation query across site health widget data
- [ ] **Rate card integration** — pricing variables in templates
- [ ] **Variable overrides at generation time** — power user need

### Defer to v4+

- Client portal (CRM data visible to client role users)
- E-signature integration
- LLM-assisted proposal copy (opt-in, same pattern as LLM briefs)
- Multi-language template variants
- Public intake form (client-filled)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Client card CRUD | HIGH | LOW | P1 |
| Site → client relationship | HIGH | LOW | P1 |
| Interaction log | MEDIUM | LOW | P1 |
| Site audit intake form | HIGH | MEDIUM | P1 |
| Auto-populate intake from platform data | HIGH | LOW | P1 |
| Proposal template CRUD (admin) | HIGH | MEDIUM | P1 |
| Core variable resolver | HIGH | MEDIUM | P1 |
| PDF generation from template | HIGH | LOW (reuse existing) | P1 |
| Document storage + download | HIGH | LOW (reuse existing) | P1 |
| Document list per client | HIGH | LOW | P1 |
| Platform data variables (live queries) | HIGH | HIGH | P2 |
| Intake → proposal pre-fill | MEDIUM | MEDIUM | P2 |
| Rich text template editor | MEDIUM | HIGH | P2 |
| Send via Telegram / SMTP | MEDIUM | MEDIUM | P2 |
| Client health score widget | MEDIUM | MEDIUM | P2 |
| Variable overrides at generation time | LOW | MEDIUM | P3 |
| Rate card integration | MEDIUM | MEDIUM | P3 |
| Template versioning | LOW | LOW | P3 |
| Auto-generate proposal on intake completion | LOW | MEDIUM | P3 |

---

## Implementation Notes: Reuse vs New Build

### Reuse Directly (No Changes Needed)
- `WeasyPrint` subprocess isolation pattern — copy from `brief_service.py`
- Celery task lifecycle (pending → generating → ready | failed) — copy from `client_reports` model
- PDF download endpoint pattern — copy from `client_reports` router
- `audit_log` for document generation events — existing table
- `telegram_service.py` — already sends text/files
- `crypto_service.py` — Fernet encryption for any sensitive intake fields

### Extend (Minor Additions)
- `sites` table — add `client_id` FK, `intake_completed_at`
- `users` table — no change needed; `client` role already exists
- `projects` table — add `client_id` FK (currently only `client_user_id`)

### New Tables Required
- `clients` — company card, manager FK, created_at
- `client_contacts` — multiple contacts per client (name, phone, email, role)
- `client_interactions` — interaction log (client_id, user_id, text, timestamp, optional document_id)
- `site_intake` — JSONB answers + structured fields + completion status per site
- `proposal_templates` — template body (HTML/Jinja2 text), name, variable_schema JSON, is_active
- `generated_documents` — generalised document table (type enum, template_id, client_id, site_id, variable_overrides JSONB, pdf_data, status, celery_task_id)

---

## Complexity Summary

| Feature Group | Overall Complexity | Key Risk |
|---------------|-------------------|----------|
| Client CRM | LOW-MEDIUM | Schema design (clients vs users distinction) |
| Site Audit Intake | MEDIUM | Variable schema alignment with proposals |
| Proposal Templates | MEDIUM-HIGH | Rich text editor choice; variable resolver scope |
| Document Generator | LOW-MEDIUM | Generalising existing client_reports pattern |

The highest-risk decision is the **variable resolver for proposal templates**: scope it to static variables (client name, site URL, a handful of DB queries) in v3.0 and expand to live complex queries in v3.x. Trying to make it fully dynamic in one milestone risks over-engineering the schema.

---

## Sources

- PROJECT.md — existing platform capabilities and v3.0 milestone goal
- Existing codebase: `app/models/client_report.py`, `app/models/site.py`, `app/models/project.py`, `app/models/user.py` — established patterns
- Domain knowledge: SE Ranking, Agency Analytics, Semrush Agency Hub, Proposify — SEO agency CRM conventions (training knowledge, no live verification)
- Russian SEO agency context: КП structure, INN/KPP requirements — established practice (HIGH confidence)

---
*Feature research for: v3.0 Client & Proposal milestone*
*Researched: 2026-04-09*
