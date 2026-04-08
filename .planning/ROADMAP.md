# Roadmap: SEO Management Platform

## Milestones

- **v1.0 MVP** — 16 phases (shipped 2026-04-06) — [details](milestones/v1.0-ROADMAP.md)
- **v2.0 SEO Insights & AI** — Phases 12–17 (in progress)
- **v3.0 Client & Proposal** — Phases 18–21 (planned)
- **v3.1 SEO Tools** — Phases 22–23 (planned)

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

### v2.0 SEO Insights & AI

**Milestone Goal:** Превратить собранные данные в actionable insights — Quick Wins, мёртвый контент, приоритизация ошибок, точки роста, AI-готовность, клиентские отчёты, keyword suggest и LLM-briefs.

- [x] **Phase 12: Analytical Foundations** - URL normalization + keyword_latest_positions table + Quick Wins + Dead Content surfaces (completed 2026-04-06)
- [x] **Phase 13: Impact Scoring & Growth Opportunities** - Error prioritization by traffic + unified growth opportunity dashboard (completed 2026-04-06)
- [x] **Phase 14: Client Instructions PDF** - Non-technical PDF report for site owners built on subprocess-isolated WeasyPrint (completed 2026-04-06)
- [x] **Phase 15: Keyword Suggest** - Yandex/Google autocomplete with Redis caching and rate-limited Celery tasks (completed 2026-04-07)
- [ ] **Phase 16: AI/GEO Readiness & LLM Briefs** - GEO checklist + opt-in Anthropic-powered brief enhancement
- [ ] **Phase 17: In-app Notifications** - Bell icon + notification feed for async task completions via HTMX polling

## Phase Details

### Phase 12: Analytical Foundations
**Goal**: Users can see which pages are Quick Wins (positions 4–20 with unfixed issues) and which are Dead Content (zero traffic + falling positions), backed by normalized URL JOINs and a fast position lookup table
**Depends on**: Nothing (first v2.0 phase — builds foundation)
**Requirements**: INFRA-V2-01, INFRA-V2-02, QW-01, QW-02, QW-03, DEAD-01, DEAD-02
**Success Criteria** (what must be TRUE):
  1. User can open the Quick Wins page for a site and see pages ranked by opportunity score (positions 4–20, sorted by (21-position) x weekly traffic), with each page showing its unfixed SEO issues
  2. User can select Quick Win pages and dispatch a batch-fix to the existing content pipeline without leaving the page
  3. User can open the Dead Content page and see pages with zero Metrika visits in 30 days or position drop > 10, each with a merge/redirect/rewrite/delete recommendation
  4. `normalize_url()` utility exists and is applied at write time so JOINs between pages, metrika, and positions return correct results for all URL variants (trailing slash, http/https, UTM)
  5. `keyword_latest_positions` flat table exists and is updated after each position check run, replacing DISTINCT ON partition scans in all analytical queries
**Plans:** 3/3 plans complete
Plans:
- [x] 12-01-PLAN.md — Infrastructure: normalize_url() + keyword_latest_positions table + migration + tests
- [x] 12-02-PLAN.md — Quick Wins page: service + router + template + batch fix + navigation
- [x] 12-03-PLAN.md — Dead Content page: service + router + template + task creation + navigation

### Phase 13: Impact Scoring & Growth Opportunities
**Goal**: Users can see all audit errors ranked by traffic impact and drill into a unified Growth Opportunities dashboard aggregating gap keywords, lost positions, and cannibalization
**Depends on**: Phase 12
**Requirements**: IMP-01, IMP-02, GRO-01, GRO-02
**Success Criteria** (what must be TRUE):
  1. Every audit error (404, noindex, missing schema) has an impact_score visible in the UI, computed as severity_weight × monthly Metrika traffic for the affected page
  2. User can sort the Kanban board by impact_score so highest-traffic errors appear first
  3. User can view the Growth Opportunities dashboard showing gap keyword count and potential traffic, lost positions, active cannibalization clusters, and visibility trend in one place
  4. User can click any card on the Growth Opportunities dashboard and navigate directly to the relevant detail view (gap analysis, positions, clusters)
  5. Impact scores are pre-computed by a Celery task and written to `error_impact_scores` table — the dashboard page loads in under 3 seconds without live aggregation
**Plans**: 3 plans
Plans:
- [x] 13-01-PLAN.md — Impact scoring backend: model + migration + service + Celery task + tests
- [x] 13-02-PLAN.md — Growth Opportunities dashboard: service + router + templates + tabs
- [x] 13-03-PLAN.md — Kanban impact sort + slide-over drill-down panels

### Phase 14: Client Instructions PDF
**Goal**: Users can generate a PDF report for site owners that explains each problem and its fix steps in plain Russian, using subprocess-isolated WeasyPrint to prevent OOM kills
**Depends on**: Phase 12
**Requirements**: CPDF-01, CPDF-02, CPDF-03
**Success Criteria** (what must be TRUE):
  1. User can click "Generate client PDF" for any site and receive a downloadable PDF within 60 seconds via Celery task
  2. The generated PDF combines Quick Wins, audit errors, and fix recommendations in a non-technical format (problem → solution → steps in WP admin)
  3. Each error type in the report uses a Russian-language instruction template explaining the fix steps; at least the standard error types (404, noindex, missing TOC, missing schema) are covered
  4. PDF generation runs in a subprocess per report so a WeasyPrint memory leak cannot kill the shared Celery worker
**Plans**: 3 plans
Plans:
- [x] 14-01-PLAN.md — Backend: ClientReport model + migration + subprocess PDF renderer + service + template
- [x] 14-02-PLAN.md — Frontend: Celery task + router + UI templates + sidebar navigation
- [x] 14-03-PLAN.md — Tests: service-layer + subprocess PDF renderer tests
**UI hint**: yes

### Phase 15: Keyword Suggest
**Goal**: Users can retrieve 200+ keyword suggestions by seed keyword from Yandex (primary) and Google (secondary) with results cached in Redis so repeat queries need no external calls
**Depends on**: Phase 12
**Requirements**: SUG-01, SUG-02, SUG-03, SUG-04
**Success Criteria** (what must be TRUE):
  1. User can enter a seed keyword and receive 200+ Yandex Suggest results via alphabetic expansion without triggering an IP ban (routed via XMLProxy or DataForSEO)
  2. User can toggle Google Suggest as an additional source and see combined deduplicated results
  3. User with a configured Yandex Direct OAuth token can see Wordstat frequency data alongside each suggestion (opt-in; UI shows the field only when the token is set)
  4. A repeated suggest request for the same seed returns instantly from Redis cache (TTL 24h) with no external API call
  5. The suggest endpoint is rate-limited (10 requests/minute); all external API calls run inside Celery tasks with retry=3, not inline in the request handler
**Plans**: 3 plans
Plans:
- [x] 15-01-PLAN.md — Backend: SuggestJob model + migration + suggest service + Celery task + Redis cache + tests
- [x] 15-02-PLAN.md — UI: router + templates + HTMX polling + CSV export + sidebar navigation + router tests
- [x] 15-03-PLAN.md — Wordstat integration + position engine fix + tests
**UI hint**: yes

### Phase 15.1: UI Smoke Crawler (INSERTED)

**Goal:** Any new UI page or HTMX partial gets automatic render verification before merge — eliminate Jinja key/attr collisions, undefined variables, missing context, and broken includes via a deterministic seed-driven pytest smoke crawler that auto-discovers GET routes from `app.routes` and asserts status + body markers + structural HTML, gated in CI.
**Requirements**: TBD (no roadmap requirement IDs — must_haves derived from CONTEXT success criteria)
**Depends on:** Phase 15
**Plans:** 5/5 plans complete

Plans:
- [x] 15.1-01-PLAN.md — Smoke seed fixture: deterministic ORM-based session-scoped seed (Site, User, Keywords, Positions, GapKeywords, SuggestJob, CrawlJob, AuditCheckDefinition, AuditResult, ClientReport, ServiceCredential)
- [x] 15.1-02-PLAN.md — Helper module: route discovery from app.routes, PARAM_MAP / SMOKE_SKIP, body marker scan, structural HTML check (with full unit tests)
- [x] 15.1-03-PLAN.md — Pytest smoke module: parametrized over discovered routes + smoke_client fixture overriding get_current_user/require_admin + data.items regression test
- [x] 15.1-04-PLAN.md — Evolve standalone tests/smoke_test.py into thin CLI wrapper reusing helpers (D-08)
- [x] 15.1-05-PLAN.md — CI gate: GitHub Actions workflow with Postgres service + tests/README.md "Adding a new route" docs

### Phase 16: AI/GEO Readiness & LLM Briefs
**Goal**: Every page has a GEO readiness score visible in the audit table, and users with a configured Claude API key can generate an AI-enhanced brief that extends the existing template brief
**Depends on**: Phase 12, Phase 13
**Requirements**: GEO-01, GEO-02, GEO-03, LLM-01, LLM-02, LLM-03, LLM-04
**Success Criteria** (what must be TRUE):
  1. Every crawled page shows a GEO score 0–100 in the audit table computed from rule-based DOM checks (FAQPage schema, Article/Author schema, BreadcrumbList, answer-first structure, update date)
  2. User can filter the audit table by GEO score range and by individual geo_* check type
  3. GEO checks appear in the existing audit_check_definitions system as `geo_*` codes — no new audit infrastructure is required
  4. User sees an "Generate AI brief" button on the brief page only when a Claude API key is configured; clicking it enhances the existing template brief with LLM output
  5. If the Claude API is unavailable or the key is missing, the template brief is always returned unchanged — the LLM enhancement never blocks brief delivery
  6. LLM token usage is capped (input ~2000, output ~800) and a circuit breaker disables LLM calls after 3 consecutive failures
**Plans**: 4 plans
Plans:
- [x] 16-01-PLAN.md — GEO check runners + migration (geo_score, llm tables, anthropic_api_key column) + tests
- [x] 16-02-PLAN.md — Audit table UI: geo_score column + score-range and check-code filters
- [x] 16-03-PLAN.md — LLM backend: SDK install, per-user encrypted key, circuit breaker, prompt builder, Celery task
- [x] 16-04-PLAN.md — LLM UI: profile key management + Usage tab, brief detail Generate AI brief button, HTMX polling, Accept/Regenerate (human-verify deferred → Phase 999.6)
**UI hint**: yes

### Phase 17: In-app Notifications
**Goal**: Users see a notification bell in the sidebar with a live unread count and a feed of task completion events so they know when crawls, position checks, and PDF generation finish without checking Telegram
**Depends on**: Phase 12
**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03
**Success Criteria** (what must be TRUE):
  1. A bell icon in the sidebar shows a badge count of unread notifications that updates every 30 seconds via HTMX polling without a full page reload
  2. The notification feed lists recent events — crawl completed, position check completed, PDF generated, monitoring alert triggered — with timestamp and site name
  3. Notifications continue to be sent to Telegram as before; in-app notifications are additive, not a replacement
  4. Read notifications can be dismissed; dismissed notifications are hard-deleted (not soft-deleted) and a nightly Celery Beat task cleans up notifications older than 30 days
**Plans**: 3 plans
- [ ] 17-01-PLAN.md — Notification model, migration, notify() helper, nightly cleanup task
- [ ] 17-02-PLAN.md — Router + bell/dropdown/full-page templates + sidebar wiring + smoke routes
- [ ] 17-03-PLAN.md — Wire notify() into 7 Celery tasks + monitoring alert dispatcher
**UI hint**: yes

### v3.0 Client & Proposal

**Milestone Goal:** Превратить платформу из инструмента мониторинга в инструмент продаж — карточки клиентов, аудит-анкеты, шаблоны КП и генератор документов. SEO-специалист получает полный цикл от первого контакта до отправки КП без выхода из системы.

- [ ] **Phase 18: Client CRM** — карточка клиента, история взаимодействий, статусы лид/активный/завершён
- [ ] **Phase 19: Site Audit Intake** — аудит-анкета сайта, импорт данных из XLSX/CSV (Топвизор, PageSpeed, Вебмастер), парсинг SEO-полей через краулер
- [ ] **Phase 20: Proposal Templates & Tariffs** — тарифная сетка, библиотека блоков КП, адаптация под клиента
- [ ] **Phase 21: Document Generator** — генерация DOCX/PDF с версионированием, экспорт КП

### Phase 18: Client CRM
**Goal**: Users can create and manage client records with domain, niche, tariff, status, and interaction history — so every proposal and audit is linked to a client and searchable across the platform
**Depends on**: Phase 17
**Requirements**: CRM-01, CRM-02, CRM-03, CRM-04
**Success Criteria** (what must be TRUE):
  1. User can create a client record with: domain, company name, niche, contact name, contact channel (phone/telegram/email), assigned tariff, status (lead / active / paused / closed), start date, notes
  2. User can view a client's timeline — chronological list of proposals sent, audits created, tasks created, and manual notes — on a single page
  3. User can filter the client list by status, niche, and tariff; the list loads in under 2 seconds for 100+ clients
  4. Every existing Site record can be linked to a Client record via a foreign key — migration preserves all existing sites with client_id = NULL (nullable, not required)
  5. Audit log captures all client record changes (field, old value, new value, user, timestamp) using the existing audit log infrastructure
**Plans**: 3 plans
Plans:
- [ ] 18-01-PLAN.md — Backend: Client model + migration + ClientSite link + service + CRUD router + tests
- [ ] 18-02-PLAN.md — Frontend: client list + detail page + timeline + HTMX inline edit + sidebar navigation
- [ ] 18-03-PLAN.md — Link existing Sites to Clients: UI picker + migration + audit log integration + tests
**UI hint**: yes

### Phase 19: Site Audit Intake
**Goal**: Users can run a structured audit intake for any client site — filling a checklist, importing position/error data from XLSX/CSV exports (Topvisor, PageSpeed, Webmaster), and triggering SEO-field extraction via the existing crawler — producing a saved audit snapshot that feeds the proposal
**Depends on**: Phase 18
**Requirements**: AUD-01, AUD-02, AUD-03, AUD-04, AUD-05
**Success Criteria** (what must be TRUE):
  1. User can open "New Audit" for a client and fill a structured intake checklist covering: technical block (HTTPS, robots.txt, sitemap, CMS, SEO plugin, page speed score), local SEO block (Yandex.Business status, NAP consistency, geo services), positions block (top competitors, tracking status), content block (intent issues flagged, key sections)
  2. User can upload a Topvisor XLSX export (multi-domain position comparison format) and have the system parse it into a positions comparison table: keyword / client position / competitor positions — stored against the audit record
  3. User can upload a PageSpeed or Webmaster CSV/XLSX export and have key metrics (LCP, TBT, CLS, score, error counts) extracted and stored against the audit record with column mapping UI for non-standard exports
  4. User can trigger SEO-field extraction for up to 20 URLs from the client's site using the existing Playwright crawler — the system fetches each URL and stores: title, H1, meta description, H2 list, presence of price/CTA in body text, detected intent type (informational / commercial heuristic)
  5. An audit snapshot is saved with a timestamp and version number; user can create multiple audit versions for the same client and compare them side by side
**Plans**: 4 plans
Plans:
- [ ] 19-01-PLAN.md — Backend: SiteAudit model + AuditSnapshot + migration + service + tests
- [ ] 19-02-PLAN.md — Intake checklist UI: structured form + HTMX save + checklist renderer + router
- [ ] 19-03-PLAN.md — XLSX/CSV import: Topvisor parser + PageSpeed/Webmaster parser + column mapping UI + Celery task + tests
- [ ] 19-04-PLAN.md — SEO-field crawler: URL list input + Playwright extraction + intent heuristic + results table + tests
**UI hint**: yes

### Phase 20: Proposal Templates & Tariffs
**Goal**: Users can define tariffs with structured work compositions, build proposals from a block library, and adapt any block to client-specific data — so a proposal for a new client in a known niche takes minutes, not hours
**Depends on**: Phase 19
**Requirements**: PROP-01, PROP-02, PROP-03, PROP-04
**Success Criteria** (what must be TRUE):
  1. User can create and edit tariffs in the system UI: name, monthly price, pages per month by type (event / route / blog), included work directions (list of named items), excluded items — stored in DB and reusable across proposals
  2. User can open a proposal builder for a client, select a tariff, and have tariff content auto-populated into the proposal sections (work composition, volume, pricing)
  3. User can insert pre-written blocks from a block library into any proposal section — blocks are tagged by type (technical, local SEO, content, schema, audit finding) and searchable; each block contains a title and body text with {{placeholders}} for client-specific values
  4. Placeholders in blocks are resolved automatically from the linked client record and audit snapshot (e.g. {{domain}}, {{lcp_score}}, {{top_competitor}}, {{pages_in_index}}); unresolved placeholders are highlighted in the UI for manual fill
  5. User can save a proposal as a named version (e.g. "v1 — initial", "v2 — after call") and restore any previous version; version list is visible on the proposal detail page
**Plans**: 4 plans
Plans:
- [ ] 20-01-PLAN.md — Backend: Tariff model + ProposalTemplate + ProposalBlock library + migration + service + tests
- [ ] 20-02-PLAN.md — Tariff editor UI: CRUD + composition builder + price input + HTMX preview
- [ ] 20-03-PLAN.md — Proposal builder UI: block library sidebar + drag-in blocks + placeholder resolver + section editor
- [ ] 20-04-PLAN.md — Proposal versioning: snapshot save + version list + restore + diff view + tests
**UI hint**: yes

### Phase 21: Document Generator
**Goal**: Users can export any saved proposal as a DOCX or PDF document — with the platform's visual style applied, tables and lists rendered correctly, and each export saved as a file artifact linked to the proposal version
**Depends on**: Phase 20
**Requirements**: DOC-01, DOC-02, DOC-03
**Success Criteria** (what must be TRUE):
  1. User can click "Export DOCX" on any proposal version and receive a downloadable .docx file within 30 seconds via Celery task — generated by python-docx with styles matching the platform's document conventions (headings, tables, bullet lists, color scheme)
  2. User can click "Export PDF" on any proposal version and receive a downloadable .pdf file — generated by the existing subprocess-isolated WeasyPrint infrastructure (same pattern as Phase 14) to prevent OOM kills
  3. The generated document includes all proposal sections in order: intro, audit findings (from audit snapshot), strategy, local SEO block, tariff cards, work stages table, forecast, next steps — sections present in the proposal are included; empty sections are omitted automatically
  4. Position comparison data from the audit snapshot (keyword / client / competitor columns) is rendered as a formatted table in the audit section of the document, with color coding applied where the export format supports it
  5. Each export is saved as a ProposalExport record (file path, format, timestamp, generated_by user) linked to the proposal version — user can download any previous export from the proposal history page
**Plans**: 3 plans
Plans:
- [ ] 21-01-PLAN.md — Backend: python-docx renderer + ProposalExport model + migration + Celery task + tests
- [ ] 21-02-PLAN.md — PDF renderer: WeasyPrint subprocess adapter + HTML proposal template + CSS styles
- [ ] 21-03-PLAN.md — Export UI: export buttons + status polling (HTMX) + download links + export history tab + tests
**UI hint**: yes

### v3.1 SEO Tools

**Milestone Goal:** Добавить в платформу раздел «Инструменты» — автономные SERP-инструменты без привязки к сайту клиента, работающие по модели Job: пользователь запускает задачу, Celery выполняет, результат доступен для просмотра и CSV/XLSX экспорта. Архитектура по образцу Phase 15 (SuggestJob), каждый инструмент — своя модель.

- [ ] **Phase 22: Tools Infrastructure & Fast Tools** — новый раздел сайдбара, базовая Job-архитектура, три инструмента на существующих компонентах (коммерциализация, парсер мета-тегов, релевантный URL)
- [ ] **Phase 23: SERP Aggregation Tools** — три инструмента, требующие SERP-краулинга (ТЗ на основе ТОП, PAA, пакетная частотность Wordstat)

### Phase 22: Tools Infrastructure & Fast Tools
**Goal**: Users can access a new "Tools" sidebar section with three standalone SERP instruments — commercialization check, meta-tag parser, and relevant URL finder — each running as an async Celery job with typed result storage, downloadable CSV output, and no site binding required
**Depends on**: Phase 21
**Requirements**: TOOL-INFRA-01, TOOL-INFRA-02, COM-01, META-01, REL-01
**Success Criteria** (what must be TRUE):
  1. A "Tools" section appears in the sidebar navigation, accessible to admin and manager roles; the section lists all available tools with a status indicator (running / ready / failed) for the user's recent jobs across all tools
  2. Each tool follows the same UX pattern: input form → submit → HTMX polling on job status → results table rendered in-page → CSV/XLSX download button; no page reload required at any step
  3. User can submit a list of up to 200 keyword phrases to the Commercialization Check tool and receive for each phrase: commercialization % (0–100), intent classification (informational / mixed / commercial), geo-dependency flag, localization flag — powered by XMLProxy Yandex SERP analysis; results stored in CommerceCheckJob + CommerceCheckResult rows
  4. User can submit a list of up to 500 URLs to the Meta Tag Parser and receive for each URL: HTTP status code, title, H1, H2 list (up to 10), meta description, canonical — fetched via async httpx with 10s timeout and 5 concurrent workers; results stored in MetaParseJob + MetaParseResult rows
  5. User can submit a list of up to 100 keyword phrases to the Relevant URL Finder, select a domain to check, and receive for each phrase: which URL from that domain appears in Yandex TOP-10 (or "not found"), its position, and the top-3 competing domains — powered by XMLProxy; results stored in RelevantUrlJob + RelevantUrlResult rows
  6. All three tools are rate-limited (10 requests/minute per user), run exclusively inside Celery tasks (no inline HTTP in request handlers), have retry=3 on external calls, and are covered by service-layer tests with mocked external responses
**Plans**: 5 plans
Plans:
- [ ] 22-01-PLAN.md — Tools infrastructure: sidebar section + shared job-list page + HTMX polling pattern + CSV/XLSX export helper + navigation + smoke tests
- [ ] 22-02-PLAN.md — Commercialization Check: CommerceCheckJob + CommerceCheckResult models + migration + service + Celery task + XMLProxy integration + UI + tests
- [ ] 22-03-PLAN.md — Meta Tag Parser: MetaParseJob + MetaParseResult models + migration + async httpx fetcher service + Celery task + UI + tests
- [ ] 22-04-PLAN.md — Relevant URL Finder: RelevantUrlJob + RelevantUrlResult models + migration + service + Celery task + XMLProxy integration + UI + tests
- [ ] 22-05-PLAN.md — Integration: tools index page + recent jobs across all tools + role-based access + router tests
**UI hint**: yes

### Phase 23: SERP Aggregation Tools
**Goal**: Users can run three advanced tools requiring multi-step SERP aggregation and page crawling — a full copywriting brief generator (TOP-10 analysis + Playwright crawl of each result), a PAA parser, and a batch Wordstat frequency tool — each following the same Job architecture established in Phase 22
**Depends on**: Phase 22
**Requirements**: BRIEF-01, BRIEF-02, PAA-01, FREQ-01
**Success Criteria** (what must be TRUE):
  1. User can submit a group of keyword phrases (up to 30, intended for one landing page) to the Copywriting Brief tool and receive a structured brief containing: recommended title and H1 suggestions, list of H2 headings aggregated from TOP-10 pages, Yandex search highlights (подсветки) across TOP-10, thematic words frequency table, average text volume from TOP-10 pages, commercialization % for the group — all stored in BriefJob + BriefResult with section-level JSON structure
  2. The Copywriting Brief pipeline runs as a multi-step Celery chain: (1) XMLProxy fetches TOP-10 URLs for each phrase → (2) Playwright crawls each TOP-10 page extracting H2s, visible text, and highlights → (3) aggregation service merges results across phrases and computes frequency tables → (4) results written to DB and status set to ready; total runtime under 3 minutes for 10 phrases × 10 results
  3. User can submit a list of up to 50 keyword phrases to the PAA Parser and receive for each phrase: list of "People Also Ask" questions extracted from Yandex SERP, with nested follow-up questions where available — fetched via Playwright (JavaScript-rendered SERP), results stored in PAAJob + PAAResult rows; exported as flat CSV with phrase / question / level columns
  4. User can submit a list of up to 1000 keyword phrases to the Batch Wordstat tool (requires configured Yandex Direct OAuth token, same as Phase 15.3) and receive for each phrase: exact-match frequency "phrase", broad-match frequency [phrase], monthly dynamics chart data — stored in WordstatBatchJob + WordstatBatchResult rows; this extends the Phase 15.3 per-suggest Wordstat into a standalone parity tool matching KeyCollector's batch frequency workflow
  5. All three tools appear in the Tools sidebar section with the same job-list UX from Phase 22; the Batch Wordstat tool shows a warning if no Yandex Direct OAuth token is configured and links to the settings page; all tools have service-layer tests with mocked external calls
**Plans**: 5 plans
Plans:
- [ ] 23-01-PLAN.md — Copywriting Brief backend: BriefJob + BriefResult models + migration + XMLProxy TOP-10 fetcher + Playwright page crawler + aggregation service + Celery chain + tests
- [ ] 23-02-PLAN.md — Copywriting Brief UI: input form (phrase group + region + PS selector) + Celery chain status polling + brief renderer (sections: title/H1, H2 cloud, highlights, thematic words, volume) + XLSX export
- [ ] 23-03-PLAN.md — PAA Parser: PAAJob + PAAResult models + migration + Playwright SERP scenario + nested question extractor + Celery task + UI + CSV export + tests
- [ ] 23-04-PLAN.md — Batch Wordstat: WordstatBatchJob + WordstatBatchResult models + migration + Wordstat API service (extends Phase 15.3) + Celery task + UI + XLSX export + OAuth token check + tests
- [ ] 23-05-PLAN.md — Tools section completion: unified job history page across all 6 tools + pagination + job deletion + re-run button + router tests
**UI hint**: yes

**Dependency Graph (v3.1):**
```
Phase 22 (Tools Infrastructure & Fast Tools)
    └── Phase 23 (SERP Aggregation Tools)
```

**Wave structure:**
- Phase 22: Wave 1 → 22-01 (infra); Wave 2 → 22-02 + 22-03 + 22-04 (parallel); Wave 3 → 22-05
- Phase 23: Wave 1 → 23-01 + 23-03 + 23-04 (parallel backends); Wave 2 → 23-02 (Brief UI, depends on 23-01) + 23-05 (completion)

**Notes:**
- Copywriting Brief (23-01/02) is the heaviest plan — Playwright crawling N×10 pages per job; enforce per-job concurrency limit (max 3 parallel Playwright workers) to avoid VPS memory pressure
- Batch Wordstat (23-04) reuses Yandex Direct OAuth infrastructure from Phase 15.3 — low effort relative to other Phase 23 plans
- All six tool models follow the same pattern: `Job (input, status, user_id, created_at, completed_at)` + `Result (job_id FK, per-row data)`; no shared base model (variant B per architecture decision)
- XMLProxy is already rate-limited via the existing proxy management module — tool jobs must respect the same queue
- Phase 22 smoke tests must cover the HTMX polling pattern — add tool job routes to the Phase 15.1 smoke crawler parametrization

**Dependency Graph (v3.0):**
```
Phase 18 (Client CRM)
    └── Phase 19 (Site Audit Intake)
            └── Phase 20 (Proposal Templates & Tariffs)
                    └── Phase 21 (Document Generator)
```

**Notes:**
- Phases 18–21 form a single milestone (v3.0) and should be planned as a wave sequence
- Phase 19-03 (XLSX/CSV import) can run in parallel with 19-02 (checklist UI) as Wave 2
- Phase 19-04 (SEO-field crawler) reuses existing Playwright infrastructure — lower effort than a new crawler build
- Phase 21-01 (DOCX) and 21-02 (PDF) can run in parallel as Wave 2 within Phase 21
- Block library in Phase 20 can be seeded with content from the primeboat.ru proposal session as real-world examples

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 12. Analytical Foundations | v2.0 | 3/3 | Complete    | 2026-04-06 |
| 13. Impact Scoring & Growth Opportunities | v2.0 | 3/3 | Complete    | 2026-04-06 |
| 14. Client Instructions PDF | v2.0 | 3/3 | Complete    | 2026-04-06 |
| 15. Keyword Suggest | v2.0 | 3/3 | Complete   | 2026-04-07 |
| 15.1. UI Smoke Crawler | v2.0 | 5/5 | Complete   | 2026-04-07 |
| 16. AI/GEO Readiness & LLM Briefs | v2.0 | 4/4 | Complete (LLM e2e deferred) | 2026-04-08 |
| 17. In-app Notifications | v2.0 | 0/TBD | Not started | - |
| 18. Client CRM | v3.0 | 0/3 | Not started | - |
| 19. Site Audit Intake | v3.0 | 0/4 | Not started | - |
| 20. Proposal Templates & Tariffs | v3.0 | 0/4 | Not started | - |
| 21. Document Generator | v3.0 | 0/3 | Not started | - |
| 22. Tools Infrastructure & Fast Tools | v3.1 | 0/5 | Not started | - |
| 23. SERP Aggregation Tools | v3.1 | 0/5 | Not started | - |

## Backlog

### Phase 999.1: UI Scenario Runner (Playwright) (BACKLOG)

**Goal:** YAML-based scenario runner using Playwright async. Format: steps with open/click/fill/wait_for/expect_text/expect_status. Runs in CI against full docker-compose stack. Reuses seed fixtures from Phase 15.1. Covers interactive flows: form submit, HTMX polling, slide-over detail panels, suggest→results flow, gap analysis, position checks. Scenarios stored in `scenarios/*.yaml` — same files later consumed by 999.2 tour player (one source of truth for tests and tours).
**Requirements:** TBD
**Plans:** 3/4 plans executed

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.3: Smart Route Discovery (response_class filter) (BACKLOG)

**Goal:** Extend `tests/_smoke_helpers.py::discover_routes` to auto-filter routes by `response_class=HTMLResponse` (or return-type annotation), skipping JSON/CSV endpoints automatically instead of requiring explicit `SMOKE_SKIP` entries. Eliminates the need for the 5 manual skips added during phase-15.1-deferred-routes debug session (`/metrika/{id}/pages`, `/metrika/{id}/compare`, `/analytics/sessions/{id}/export`, `/traffic-analysis/sessions/{id}`, `/traffic-analysis/sessions/{id}/anomalies`). Rationale: surfaced as tech debt in `.planning/phases/15.1-ui-smoke-crawler/deferred-items.md`.
**Requirements:** TBD
**Plans:** 1/1 plans complete

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.4: Tests Bind-Mount Fix (RESOLVED via quick fix 035793f)

**Goal:** Add `./tests:/app/tests` bind mount to api service so test edits don't require `docker cp`.
**Resolution:** Fixed inline via /gsd:quick on 2026-04-07 (commit 035793f). No phase needed.

### Phase 999.5: Repo ↔ Deployment Sync Strategy (BACKLOG)

**Goal:** Two independent deployment-drift incidents were caught in a single work session between `/projects/test/app/` (git repo) and `/opt/seo-platform/app/` (running deployment tree): (1) `opportunities_gaps.html` stale in `/opt/...` (Plan 15.1-03), (2) `opportunities_{cannibal,losses}.html` stale in `/opt/...` (debug phase-15.1-deferred-routes Group A). Root cause: no automated sync. Options to evaluate: rsync post-commit hook, symlink `/opt/seo-platform/app → /projects/test/app`, docker bind-mount restructure, or CI-driven rsync on merge to master. Decision deferred — needs discuss-phase to weigh against deployment model. Until fixed, the smoke gate running against `/opt/...` will keep catching drift as it happens, which is the safety net for this debt.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.6: LLM API Integration & Live Verification (BACKLOG)

**Goal:** Complete the human-verify checkpoint deferred from Phase 16-04. Requires a real Anthropic API key. Steps: (1) obtain Claude API key, (2) set via `/profile/` Save → Validate → green "Ключ работает", (3) open `/analytics/briefs/{id}/view` and confirm "Generate AI brief" button appears, (4) click → HTMX polling → preview with 3 collapsible sections (Расширенные разделы / FAQ блок / Title+Meta) → Accept merges, (5) verify Usage tab populates with cost, (6) remove key → button hidden and grey hint shown. Optionally: add integration test hitting Anthropic sandbox, and a smoke test for `/analytics/briefs/{id}/view` with a key-set fixture user.
**Depends on:** Phase 16 (code already in master)
**Requirements:** LLM-01, LLM-02 (live verification only — code coverage already complete)
**Plans:** TBD

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.2: Interactive Tour Player (BACKLOG)

**Goal:** Frontend overlay (`app/static/js/tour.js` — lightweight custom or Shepherd.js via CDN) that highlights elements with tooltip/next/prev controls. Consumes the same `scenarios/*.yaml` files from Phase 999.1 to auto-generate user onboarding tours for new interfaces. Admin-only "Show tour" button on each page. Step types: highlight + say + wait_for_click. One source of truth: CI tests and user tours share scenario files.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
