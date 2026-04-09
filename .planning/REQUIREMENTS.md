# Requirements: SEO Management Platform

**Defined:** 2026-04-09
**Core Value:** A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.

## v3.0 Requirements

Requirements for v3.0 Client & Proposal milestone. Each maps to roadmap phases.

### Client CRM

- [ ] **CRM-01**: User can create and edit client card (company name, legal name, INN/KPP, phone, email, notes)
- [ ] **CRM-02**: User can assign a manager to a client
- [ ] **CRM-03**: User can attach/detach sites to a client organization
- [ ] **CRM-04**: User can add contacts to a client (multiple contacts per org with name, phone, email, role)
- [ ] **CRM-05**: User can log interactions per client (notes + date + author)
- [ ] **CRM-06**: User can view client list with search and filter
- [ ] **CRM-07**: User can view client detail page with attached sites, open tasks, and recent interactions

### Site Audit Intake

- [x] **INTAKE-01**: User can fill a structured intake form per site (access, goals, competitors, GSC/Metrika status, SEO setup)
- [x] **INTAKE-02**: User can see a verification checklist (WP verified, GSC connected, Metrika linked, sitemap found, crawl done)
- [x] **INTAKE-03**: Checklist items auto-populate from existing platform data
- [x] **INTAKE-04**: User can save intake form as draft and resume later (section-by-section HTMX save)
- [x] **INTAKE-05**: Site shows "intake complete" status after form is finished

### Proposal Templates

- [x] **TPL-01**: Admin can create, edit, and delete proposal templates with Jinja2 variable syntax
- [x] **TPL-02**: System resolves a fixed set of ~15 template variables from DB (client name, site URL, positions, audit errors, etc.)
- [ ] **TPL-03**: User can preview a rendered template with real site/client data before generating PDF
- [ ] **TPL-04**: User can clone an existing template

### Document Generator

- [ ] **DOC-01**: User can generate PDF from a proposal template + client + site data (async Celery task)
- [ ] **DOC-02**: User can view list of generated documents per client with filters by type and date
- [ ] **DOC-03**: User can download generated PDF documents
- [ ] **DOC-04**: System supports document types (proposal, audit_report, brief)
- [ ] **DOC-05**: User can send generated document via Telegram or SMTP

## Future Requirements

Deferred to v3.x or later. Tracked but not in current roadmap.

### CRM Enhancements

- **CRM-08**: Client health score aggregated from site health widget data
- **CRM-09**: "Sites needing attention" widget on client card
- **CRM-10**: Interaction log linked to generated documents

### Intake Enhancements

- **INTAKE-06**: Auto-generate baseline crawl on intake completion
- **INTAKE-07**: Intake answers pre-populate proposal template variables

### Template Enhancements

- **TPL-05**: Platform data variables with live DB queries (positions_improved_count, crawl_errors, metrika_sessions_30d)
- **TPL-06**: Service rate card integration (pricing variables from configurable rate card)
- **TPL-07**: Rich text editor for template body (Quill.js or similar)
- **TPL-08**: Template versioning (active / draft status)

### Document Enhancements

- **DOC-06**: Variable overrides at generation time
- **DOC-07**: Auto-generate proposal after intake completion
- **DOC-08**: Document audit trail via audit_log

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Full CRM pipeline (deal stages, sales funnel) | Scope creep; platform is SEO monitoring, not Salesforce |
| Email composer inside platform | SMTP auth, threading, reply tracking — derails milestone |
| Contact deduplication / merge | Not relevant at 20-100 clients scale |
| Client portal for CRM data | High RBAC complexity; defer to v4+ |
| Public intake form (client-filled) | Auth-free route, CSRF, spam protection — 3 separate concerns |
| Dynamic form builder (custom intake fields) | Fixed schema covers 95% of cases; form builder is a product in itself |
| E-signature integration (DocuSign) | OAuth, legal compliance, webhooks — separate product area |
| Real-time collaborative template editing | Conflict resolution, WebSocket — SPA territory |
| LLM-generated proposal copy | Non-deterministic output; proposal text is legally significant |
| Multi-language template variants | Doubles template management; ship Russian-first |
| DOCX / Word export | python-docx out of scope per PROJECT.md |
| Online proposal viewer (HTML) | Public auth-free URL, link expiry — significant security surface |
| Bulk proposal generation | Proposals are intentional one-at-a-time; scheduled delivery covers periodic reports |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CRM-01 | Phase 20 | Pending |
| CRM-02 | Phase 20 | Pending |
| CRM-03 | Phase 20 | Pending |
| CRM-04 | Phase 20 | Pending |
| CRM-05 | Phase 20 | Pending |
| CRM-06 | Phase 20 | Pending |
| CRM-07 | Phase 20 | Pending |
| INTAKE-01 | Phase 21 | Complete |
| INTAKE-02 | Phase 21 | Complete |
| INTAKE-03 | Phase 21 | Complete |
| INTAKE-04 | Phase 21 | Complete |
| INTAKE-05 | Phase 21 | Complete |
| TPL-01 | Phase 22 | Complete |
| TPL-02 | Phase 22 | Complete |
| TPL-03 | Phase 22 | Pending |
| TPL-04 | Phase 22 | Pending |
| DOC-01 | Phase 23 | Pending |
| DOC-02 | Phase 23 | Pending |
| DOC-03 | Phase 23 | Pending |
| DOC-04 | Phase 23 | Pending |
| DOC-05 | Phase 23 | Pending |

**Coverage:**
- v3.0 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after roadmap creation*
