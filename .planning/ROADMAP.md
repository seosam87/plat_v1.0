# Roadmap: SEO Management Platform

## Milestones

- **v1.0 MVP** — 16 phases (shipped 2026-04-06) — [details](milestones/v1.0-ROADMAP.md)
- **v2.0 SEO Insights & AI** — 7 phases (shipped 2026-04-08) — [details](milestones/v2.0-ROADMAP.md)
- **v2.1 Onboarding & Project Health** — 4 phases (shipped 2026-04-09) — [details](milestones/v2.1-ROADMAP.md)
- **v3.0 Client & Proposal** — Phases 20–23 (planned)
- **v3.1 SEO Tools** — Phases 24–25 (planned)

## Phases

<details>
<summary>v1.0 MVP (16 phases) — SHIPPED 2026-04-06</summary>

- [x] Phase 1: Stack & Auth (4 plans)
- [x] Phase 2: Site Management (3 plans)
- [x] Phase 3: Crawler Core (4 plans)
- [x] Phase 4: Crawl Scheduling (3 plans)
- [x] Phase 4.1: Test Backfill — INSERTED
- [x] Phase 5: Keyword Import & File Parsers (5 plans)
- [x] Phase 6: Position Tracking (3 plans)
- [x] Phase 6.1: Proxy Management & XMLProxy — INSERTED (3 plans)
- [x] Phase 7: Semantics (3 plans)
- [x] Phase 8: WP Pipeline (4 plans)
- [x] Phase 9: Projects & Tasks (3 plans)
- [x] Phase 9.1: Fix Project UI Bugs — INSERTED (2 plans)
- [x] Phase 9.2: Fix Position Check Diagnostics — INSERTED (1 plan)
- [x] Phase 10: Reports & Ads (4 plans)
- [x] Phase 11: Hardening (4 plans)
- [x] Phase v4-09: Fix Runtime Route Gaps (1 plan)

v3.x analytics phases (Metrika, Content Audit, Change Monitoring, Analytics Workspace, Gap Analysis, Site Architecture, Bulk Operations, Cannibalization Resolution, Intent Detection, Traffic Analysis) and v4.x UI overhaul phases (Navigation, Overview, Sites, Positions/Keywords, Analytics, Content, Settings, Smoke Test) also completed within v1.0.

</details>

<details>
<summary>v2.0 SEO Insights & AI (7 phases) — SHIPPED 2026-04-08</summary>

- [x] Phase 12: Analytical Foundations (3 plans)
- [x] Phase 13: Impact Scoring & Growth Opportunities (3 plans)
- [x] Phase 14: Client Instructions PDF (3 plans)
- [x] Phase 15: Keyword Suggest (3 plans)
- [x] Phase 15.1: UI Smoke Crawler — INSERTED (5 plans)
- [x] Phase 16: AI/GEO Readiness & LLM Briefs (4 plans)
- [x] Phase 17: In-app Notifications (3 plans)

Full details: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

<details>
<summary>v2.1 Onboarding & Project Health (4 phases) — SHIPPED 2026-04-09</summary>

- [x] Phase 18: Project Health Widget (1 plan) — completed 2026-04-08
- [x] Phase 19: Empty States Everywhere (3 plans) — completed 2026-04-09
- [x] Phase 19.1: UI Scenario Runner — Playwright (5 plans) — completed 2026-04-08
- [x] Phase 19.2: Interactive Tour Player (4 plans) — completed 2026-04-09

Full details: [milestones/v2.1-ROADMAP.md](milestones/v2.1-ROADMAP.md)

</details>

### v3.0 Client & Proposal (In Progress)

**Milestone Goal:** Превратить платформу из инструмента мониторинга в инструмент продаж — карточки клиентов, аудит-анкеты, шаблоны КП и генератор документов. SEO-специалист получает полный цикл от первого контакта до отправки КП без выхода из системы.

- [x] **Phase 20: Client CRM** — client cards with contacts, manager assignment, site links, interaction log (completed 2026-04-09)
- [x] **Phase 21: Site Audit Intake** — structured intake form per site with auto-population from platform data (completed 2026-04-09)
- [ ] **Phase 22: Proposal Templates** — admin-managed Jinja2 proposal templates with variable resolution and preview
- [ ] **Phase 23: Document Generator** — async PDF generation from templates, document storage, download, and delivery

### v3.1 SEO Tools (Planned)

**Milestone Goal:** Добавить в платформу раздел «Инструменты» — автономные SERP-инструменты без привязки к сайту клиента.

- [ ] **Phase 24: Tools Infrastructure & Fast Tools** — новый раздел сайдбара, базовая Job-архитектура, три инструмента
- [ ] **Phase 25: SERP Aggregation Tools** — три инструмента, требующие SERP-краулинга

## Phase Details

### Phase 20: Client CRM
**Goal**: Users can create and manage client organisations with contacts, assigned manager, linked sites, and a chronological interaction log — establishing the client entity as the anchor for all v3.0 downstream features
**Depends on**: Phase 19
**Requirements**: CRM-01, CRM-02, CRM-03, CRM-04, CRM-05, CRM-06, CRM-07
**Success Criteria** (what must be TRUE):
  1. User can create and edit a client card with company name, legal name, INN/KPP, phone, email, and notes — and assign a manager to that client
  2. User can attach and detach existing sites to a client record; each site can belong to at most one client
  3. User can add multiple contacts to a client (name, phone, email, role) and log dated interaction notes attributed to the current user
  4. User can view a paginated client list with search and filter; results load under 3 seconds for 100+ clients
  5. User can open a client detail page showing attached sites, open tasks across those sites, and the most recent interaction notes in chronological order
**Plans**: 4 plans
Plans:
- [x] 20-01-PLAN.md — CRM models, migration, service layer, tests
- [x] 20-02-PLAN.md — Router, navigation, client list page, create/edit modal
- [x] 20-03-PLAN.md — Client detail page, contacts tab, interactions tab
- [x] 20-04-PLAN.md — Sites tab, site linking, client badge on site pages
**UI hint**: yes

### Phase 21: Site Audit Intake
**Goal**: Users can fill a structured site intake form that auto-populates known platform data, save progress section by section, and mark a site as intake-complete — giving the team a single structured record of site access, goals, and configuration at onboarding time
**Depends on**: Phase 20
**Requirements**: INTAKE-01, INTAKE-02, INTAKE-03, INTAKE-04, INTAKE-05
**Success Criteria** (what must be TRUE):
  1. User can open an intake form for any site and fill structured fields covering access credentials, site goals, competitors, GSC/Metrika status, and SEO plugin setup
  2. User can see a verification checklist (WP connected, GSC linked, Metrika linked, sitemap found, crawl done) where each item shows the real-time status pulled from platform data
  3. User can save the form section by section without losing prior answers (HTMX partial save); returning to the form resumes from saved state
  4. After completing all required sections, user can mark the intake as complete; the site then shows an "intake complete" badge visible from the site list
**Plans**: 3 plans
Plans:
- [x] 21-01-PLAN.md — SiteIntake model, migration, service layer, tests
- [x] 21-02-PLAN.md — Intake router, form page with 5-tab layout, HTMX section saves
- [x] 21-03-PLAN.md — Intake badge integration in site list and detail pages
**UI hint**: yes

### Phase 22: Proposal Templates
**Goal**: Admins can create and manage Jinja2-HTML proposal templates with a fixed set of platform-resolved variables; any user can preview a rendered template against real client and site data and clone templates for new variations
**Depends on**: Phase 20
**Requirements**: TPL-01, TPL-02, TPL-03, TPL-04
**Success Criteria** (what must be TRUE):
  1. Admin can create, edit, and delete proposal templates; template body uses Jinja2 variable syntax and is stored in the database; admin can clone any existing template
  2. System resolves a documented set of ~15 variables from DB at render time (client name, site URL, top positions count, audit error count, and similar platform metrics) without manual data entry
  3. User can open a preview of any template rendered with real data from a selected client and site — unresolved variables are visibly highlighted; preview renders in under 5 seconds
**Plans**: TBD
**UI hint**: yes

### Phase 23: Document Generator
**Goal**: Users can generate a PDF document from any proposal template combined with client and site data, view the list of all generated documents per client, download any document, and send it via Telegram or SMTP
**Depends on**: Phase 22
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOC-05
**Success Criteria** (what must be TRUE):
  1. User can trigger PDF generation from a template + client + site selection; the job runs as a Celery task and the UI polls status until ready or failed
  2. User can download the generated PDF file; the download link is available immediately when the job reaches ready status
  3. User can view a filtered list of all generated documents for a client, filterable by document type and date range
  4. System distinguishes between document types (proposal, audit_report, brief) and stores the type on each generated document record
  5. User can send any generated document via Telegram or SMTP from the document list view
**Plans**: TBD
**UI hint**: yes

### Phase 24: Tools Infrastructure & Fast Tools
**Goal**: Users can access a new "Tools" sidebar section with three standalone SERP instruments — commercialization check, meta-tag parser, and relevant URL finder — each running as an async Celery job with typed result storage, downloadable CSV output, and no site binding required
**Depends on**: Phase 23
**Requirements**: TOOL-INFRA-01, TOOL-INFRA-02, COM-01, META-01, REL-01
**Success Criteria** (what must be TRUE):
  1. A "Tools" section appears in the sidebar navigation, accessible to admin and manager roles; the section lists all available tools with a status indicator (running / ready / failed) for the user's recent jobs across all tools
  2. Each tool follows the same UX pattern: input form → submit → HTMX polling on job status → results table rendered in-page → CSV/XLSX download button; no page reload required at any step
  3. User can submit a list of up to 200 keyword phrases to the Commercialization Check tool and receive for each phrase: commercialization %, intent classification, geo-dependency flag, localization flag
  4. User can submit a list of up to 500 URLs to the Meta Tag Parser and receive for each URL: HTTP status code, title, H1, H2 list, meta description, canonical
  5. User can submit up to 100 keyword phrases to the Relevant URL Finder and receive for each: which URL from the target domain appears in Yandex TOP-10 and its position
  6. All three tools are rate-limited, run exclusively inside Celery tasks, have retry=3 on external calls, and are covered by service-layer tests
**Plans**: TBD
**UI hint**: yes

### Phase 25: SERP Aggregation Tools
**Goal**: Users can run three advanced tools requiring multi-step SERP aggregation and page crawling — a full copywriting brief generator, a PAA parser, and a batch Wordstat frequency tool — each following the same Job architecture established in Phase 24
**Depends on**: Phase 24
**Requirements**: BRIEF-01, BRIEF-02, PAA-01, FREQ-01
**Success Criteria** (what must be TRUE):
  1. User can submit a group of keyword phrases to the Copywriting Brief tool and receive a structured brief with title/H1 suggestions, H2 headings aggregated from TOP-10, Yandex highlights, thematic word frequency table, and average text volume
  2. The Copywriting Brief pipeline runs as a Celery chain (fetch TOP-10 → crawl each page → aggregate) and completes under 3 minutes for 10 phrases
  3. User can submit keyword phrases to the PAA Parser and receive People Also Ask questions extracted from Yandex SERP, exported as flat CSV
  4. User can submit up to 1000 keyword phrases to the Batch Wordstat tool and receive exact-match and broad-match frequency for each phrase
  5. All three tools appear in the Tools section with the same job-list UX from Phase 24; all have service-layer tests with mocked external calls
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 12. Analytical Foundations | v2.0 | 3/3 | Complete | 2026-04-06 |
| 13. Impact Scoring & Growth Opportunities | v2.0 | 3/3 | Complete | 2026-04-06 |
| 14. Client Instructions PDF | v2.0 | 3/3 | Complete | 2026-04-06 |
| 15. Keyword Suggest | v2.0 | 3/3 | Complete | 2026-04-07 |
| 15.1. UI Smoke Crawler | v2.0 | 5/5 | Complete | 2026-04-07 |
| 16. AI/GEO Readiness & LLM Briefs | v2.0 | 4/4 | Complete (LLM e2e deferred) | 2026-04-08 |
| 17. In-app Notifications | v2.0 | 3/3 | Complete | 2026-04-08 |
| 18. Project Health Widget | v2.1 | 1/1 | Complete | 2026-04-08 |
| 19. Empty States Everywhere | v2.1 | 3/3 | Complete | 2026-04-09 |
| 19.1. UI Scenario Runner | v2.1 | 5/5 | Complete | 2026-04-08 |
| 19.2. Interactive Tour Player | v2.1 | 4/4 | Complete | 2026-04-09 |
| 20. Client CRM | v3.0 | 4/4 | Complete    | 2026-04-09 |
| 21. Site Audit Intake | v3.0 | 3/3 | Complete   | 2026-04-09 |
| 22. Proposal Templates | v3.0 | 0/? | Not started | - |
| 23. Document Generator | v3.0 | 0/? | Not started | - |
| 24. Tools Infrastructure & Fast Tools | v3.1 | 0/? | Not started | - |
| 25. SERP Aggregation Tools | v3.1 | 0/? | Not started | - |

## Backlog

### Phase 999.3: Smart Route Discovery (response_class filter) (BACKLOG)

**Goal:** Extend `tests/_smoke_helpers.py::discover_routes` to auto-filter routes by `response_class=HTMLResponse` (or return-type annotation), skipping JSON/CSV endpoints automatically instead of requiring explicit `SMOKE_SKIP` entries. Eliminates the need for the 5 manual skips added during phase-15.1-deferred-routes debug session.
**Requirements:** TBD
**Plans:** 3/3 plans complete

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.5: Repo ↔ Deployment Sync Strategy (BACKLOG)

**Goal:** Two independent deployment-drift incidents were caught in a single work session. Root cause: no automated sync. Options to evaluate: rsync post-commit hook, symlink, docker bind-mount restructure, or CI-driven rsync on merge to master.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.6: LLM API Integration & Live Verification (BACKLOG)

**Goal:** Complete the human-verify checkpoint deferred from Phase 16-04. Requires a real Anthropic API key.
**Depends on:** Phase 16 (code already in master)
**Requirements:** LLM-01, LLM-02 (live verification only — code coverage already complete)
**Plans:** TBD

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
