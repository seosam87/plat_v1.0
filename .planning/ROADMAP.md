# Roadmap: SEO Management Platform

## Milestones

- **v1.0 MVP** — 16 phases (shipped 2026-04-06) — [details](milestones/v1.0-ROADMAP.md)
- **v2.0 SEO Insights & AI** — 7 phases (shipped 2026-04-08) — [details](milestones/v2.0-ROADMAP.md)
- **v2.1 Onboarding & Project Health** — Phases 18–19 + 19.1–19.2 (planned)
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

### v2.1 Onboarding & Project Health

**Milestone Goal:** Сделать платформу самодокументируемой для возвращающегося пользователя — каждая страница объясняет, почему нет данных и как получить результат; Site Overview показывает 7-шаговый чек-лист настройки проекта с прогрессом и следующим действием.

- [x] **Phase 18: Project Health Widget** — 7-шаговый setup чек-лист на Overview, status signals в site_service, ссылки на следующий шаг (completed 2026-04-08)
- [ ] **Phase 19: Empty States Everywhere** — reusable Jinja2-макрос + contextual empty states на всех основных страницах (core workflow, analytics, content, tools)
- [x] **Phase 19.1: UI Scenario Runner (Playwright)** — YAML-based scenario runner (pytest plugin), full docker-compose stack in CI, reuses Phase 15.1 seed fixtures, P0 covers suggest→results + form submit; YAML schema reserves 999.2 tour step types (promoted from backlog 2026-04-08) (completed 2026-04-08)
- [ ] **Phase 19.2: Interactive Tour Player** — frontend overlay (`app/static/js/tour.js`) consuming the same `scenarios/*.yaml` files from Phase 19.1 to auto-generate user onboarding tours; admin-only "Show tour" button per page (promoted from backlog 2026-04-08)

## Phase Details

### v3.0 Client & Proposal

**Milestone Goal:** Превратить платформу из инструмента мониторинга в инструмент продаж — карточки клиентов, аудит-анкеты, шаблоны КП и генератор документов. SEO-специалист получает полный цикл от первого контакта до отправки КП без выхода из системы.

- [ ] **Phase 20: Client CRM** — карточка клиента, история взаимодействий, статусы лид/активный/завершён
- [ ] **Phase 21: Site Audit Intake** — аудит-анкета сайта, импорт данных из XLSX/CSV (Топвизор, PageSpeed, Вебмастер), парсинг SEO-полей через краулер
- [ ] **Phase 22: Proposal Templates & Tariffs** — тарифная сетка, библиотека блоков КП, адаптация под клиента
- [x] **Phase 23: Document Generator** — генерация DOCX/PDF с версионированием, экспорт КП (completed 2026-04-09)

### Phase 18: Project Health Widget
**Goal**: A user returning to any site after weeks of inactivity immediately sees a 7-step setup checklist on the Site Overview page showing what's done, what's next, and a one-click link to the next required action — derived from existing DB state with zero new queries or Celery tasks
**Depends on**: Phase 17
**Requirements**: PHW-01, PHW-02, PHW-03, PHW-04, PHW-05, PHW-06
**Success Criteria** (what must be TRUE):
  1. The Site Overview page contains a Project Health widget showing the 7 setup steps as a vertical checklist; each step shows: completion status icon (✓ done / → current / ○ pending), step title, internal link to the relevant page, and a one-line description
  2. The widget derives status from DB state checks inside the existing `site_service.get_site_detail` call — no additional Celery tasks, no additional round-trips; reuses counts already loaded for the page (keywords, competitors, crawl_jobs, position_runs, scheduled_tasks)
  3. The widget highlights exactly one step as "current" — the first incomplete step in sequence; below the checklist a single line reads "Следующий шаг: [step name] →" linking directly to the target page
  4. If all 7 steps are complete the widget shows a success state ("Проект полностью настроен") with a link to the Overview dashboard
  5. The 7 checklist steps and their completion signals:
     1. Site created — always ✓ (site record exists)
     2. WordPress access configured — `site.wp_password` is set and `site.wp_url` is non-empty
     3. Keywords added — `keywords.count(site_id) > 0`
     4. Competitors added — `competitors.count(site_id) > 0`
     5. First crawl run — `crawl_jobs.count(site_id) > 0`
     6. First position check run — `position_check_runs.count(site_id) > 0`
     7. Schedule configured — at least one active `scheduled_task` for this site
  6. Step 7b "Analytics connected" (optional, shown as secondary) — Metrika token or GSC token configured; does NOT block the "fully set up" state
  7. Widget route covered by Phase 15.1 smoke crawler (Site Overview page already in fixture — no new smoke infra needed)
**Plans**: 1 plan
Plans:
- [x] 18-01-PLAN.md — DB status checks in `site_service.get_site_detail` + widget Jinja template + Overview page integration + unit tests for each status signal + widget placement (right sidebar or full-width card — decided during implementation based on current Overview layout)
**UI hint**: yes

### Phase 19: Empty States Everywhere
**Goal**: Every main platform page shows a contextual empty state explaining why there is no data and how to use the feature — so a user returning after weeks of inactivity can self-orient without documentation
**Depends on**: Phase 18
**Requirements**: EMP-01, EMP-02, EMP-03, EMP-04, EMP-05, EMP-06, EMP-07
**Success Criteria** (what must be TRUE):
  1. Every page listed in the page inventory (below) renders a reusable empty state component instead of a bare "No data" message when its primary data source is empty
  2. Each empty state contains three elements: (a) one-sentence reason why there is no data yet, (b) collapsible "Как использовать" section (HTML `<details>` / `<summary>` — works without JavaScript, HTMX-compatible) with prerequisites + step-by-step instructions + expected result format, (c) primary CTA button or link to the action that produces data
  3. The "Как использовать" content is written in Russian matching existing UI language and describes: what settings/credentials must be configured first, the sequence of actions, and what the result looks like when data is present
  4. Empty state implemented as a reusable Jinja2 macro in `app/templates/macros/empty_state.html` accepting: `reason` (str), `how_to_use` (HTML block via caller), `cta_label` (str), `cta_url` (str), `docs_url` (str, optional — parameter reserved for future help docs, not wired up yet); pages pass their specific content via Jinja2 `{% call %}` blocks so no logic lives in the macro
  5. All new empty state routes are registered in Phase 15.1 smoke crawler parametrization — no new smoke test infrastructure, just fixture additions
  6. Page inventory covered:
     - **Core workflow** — Crawls `/sites/{id}/crawls/`, Crawl schedule `/sites/{id}/crawls/schedule/`, Positions `/sites/{id}/positions/`, Keywords `/sites/{id}/keywords/`, Competitors `/sites/{id}/competitors/`
     - **Analytics & Content** — Traffic, Quick Wins, Dead Content, Gap Analysis, Cannibalization, Content Pipeline, Client Reports, Keyword Suggest
     - **Tools section** — every tool from Phase 24–25 (Commercialization Check, Meta Parser, Relevant URL Finder, Copywriting Brief, PAA Parser, Batch Wordstat) gets an empty state with input format hint + expected result description
**Plans**: 3 plans
Plans:
- [ ] 19-01-PLAN.md — Empty state macro + core workflow pages: Crawls, Crawl Schedule, Positions, Keywords, Competitors (reason + how-to + CTA for each)
- [ ] 19-02-PLAN.md — Empty state Analytics/Content pages: Traffic, Quick Wins, Dead Content, Gap Analysis, Cannibalization, Content Pipeline, Client Reports, Keyword Suggest
- [ ] 19-03-PLAN.md — Empty state Tools section (Phase 24–25 tool pages) + smoke crawler registration for all new empty state routes + router tests
**UI hint**: yes

### Phase 19.1: UI Scenario Runner (Playwright)
**Goal**: YAML-based scenario runner using Playwright async, hosted as a pytest plugin. P0 ships 2 scenarios (suggest→results HTMX polling + site form submit) running against the full docker-compose stack in CI. YAML schema reserves 19.2 tour step types (`say`, `highlight`, `wait_for_click`) so the same files become tour sources later.
**Depends on**: Phase 15.1 (smoke seed fixture)
**Requirements**: SCN-01, SCN-02, SCN-03, SCN-04, SCN-05, SCN-06, SCN-07, SCN-08, SCN-09, SCN-10
**Context**: `19.1-CONTEXT.md` (8 decisions D-01..D-08 captured 2026-04-08) + `19.1-RESEARCH.md`
**Plans**: 5 plans
Plans:
- [x] 19.1-01-PLAN.md — Wave 0 foundations: refactor smoke_seed public seed_core/seed_extended, scaffold scenario_runner package + scenarios/ dir, add playwright + pyyaml to test deps, gitignore artifacts
- [x] 19.1-02-PLAN.md — Pydantic v2 Scenario/Step discriminated union schema (incl. reserved 19.2 types) + pytest_collect_file collector + executor skeleton with reserved-type skip-with-warning
- [x] 19.1-03-PLAN.md — Playwright runtime: session browser + storage_state auth fixtures, locator auto-detect, full P0 step dispatch, failure-artifact capture (screenshot + trace.zip), idempotent out-of-process live-stack seed
- [x] 19.1-04-PLAN.md — CI plumbing: docker-compose.ci.yml overlay with tester service (MS Playwright image) + worker healthcheck, single-command run-scenarios-ci.sh entrypoint
- [x] 19.1-05-PLAN.md — P0 scenarios (01-suggest-to-results.yaml + 02-site-form-submit.yaml) + scenarios/README.md documenting schema/reserved types/19.2 handoff; end-to-end CI green run

### Phase 19.2: Interactive Tour Player
**Goal**: Frontend overlay (`app/static/js/tour.js` — lightweight custom or Shepherd.js via CDN) that highlights elements with tooltip/next/prev controls. Consumes the same `scenarios/*.yaml` files from Phase 19.1 to auto-generate user onboarding tours. Admin-only "Show tour" button on each page. Step types: `highlight` + `say` + `wait_for_click`. One source of truth for tests and tours.
**Depends on**: Phase 19.1
**Requirements**: TBD (define before /gsd:plan-phase)
**Plans**: TBD

**Dependency Graph (v2.1):**
```
Phase 18 (Project Health Widget)
    └── Phase 19 (Empty States Everywhere)
            └── Phase 19.1 (UI Scenario Runner)
                    └── Phase 19.2 (Interactive Tour Player)
```

**Notes:**
- Phase 18 is intentionally small (1 plan, pure read-path derivation) — it unblocks "where do I go next?" UX without requiring new models or migrations
- Phase 19-01 and 19-02 can run in parallel as Wave 2 after 19-01's macro is committed (shared macro only; disjoint page sets)
- Phase 19-03 depends on Phase 24–25 tool pages existing; if those aren't built yet, skip the Tools half of 19-03 and run it again after Phase 25 lands
- `<details>`/`<summary>` needs no custom JS and is HTMX-compatible — no sidebar wiring required
- `docs_url` macro parameter stays unused in Phase 19; wired up later when help.arsenkin.ru-style docs surface
- Step 7b "Analytics connected" in Phase 18 widget is deliberately non-blocking — separate visual style (link, no ✓/→/○), so users still see "Проект полностью настроен" after step 7 without confusion

### Phase 20: Client CRM
**Goal**: Users can create and manage client records with domain, niche, tariff, status, and interaction history — so every proposal and audit is linked to a client and searchable across the platform
**Depends on**: Phase 19
**Requirements**: CRM-01, CRM-02, CRM-03, CRM-04
**Success Criteria** (what must be TRUE):
  1. User can create a client record with: domain, company name, niche, contact name, contact channel (phone/telegram/email), assigned tariff, status (lead / active / paused / closed), start date, notes
  2. User can view a client's timeline — chronological list of proposals sent, audits created, tasks created, and manual notes — on a single page
  3. User can filter the client list by status, niche, and tariff; the list loads in under 2 seconds for 100+ clients
  4. Every existing Site record can be linked to a Client record via a foreign key — migration preserves all existing sites with client_id = NULL (nullable, not required)
  5. Audit log captures all client record changes (field, old value, new value, user, timestamp) using the existing audit log infrastructure
**Plans**: 3 plans
Plans:
- [ ] 20-01-PLAN.md — Backend: Client model + migration + ClientSite link + service + CRUD router + tests
- [ ] 20-02-PLAN.md — Frontend: client list + detail page + timeline + HTMX inline edit + sidebar navigation
- [ ] 20-03-PLAN.md — Link existing Sites to Clients: UI picker + migration + audit log integration + tests
**UI hint**: yes

### Phase 21: Site Audit Intake
**Goal**: Users can run a structured audit intake for any client site — filling a checklist, importing position/error data from XLSX/CSV exports (Topvisor, PageSpeed, Webmaster), and triggering SEO-field extraction via the existing crawler — producing a saved audit snapshot that feeds the proposal
**Depends on**: Phase 20
**Requirements**: AUD-01, AUD-02, AUD-03, AUD-04, AUD-05
**Success Criteria** (what must be TRUE):
  1. User can open "New Audit" for a client and fill a structured intake checklist covering: technical block (HTTPS, robots.txt, sitemap, CMS, SEO plugin, page speed score), local SEO block (Yandex.Business status, NAP consistency, geo services), positions block (top competitors, tracking status), content block (intent issues flagged, key sections)
  2. User can upload a Topvisor XLSX export (multi-domain position comparison format) and have the system parse it into a positions comparison table: keyword / client position / competitor positions — stored against the audit record
  3. User can upload a PageSpeed or Webmaster CSV/XLSX export and have key metrics (LCP, TBT, CLS, score, error counts) extracted and stored against the audit record with column mapping UI for non-standard exports
  4. User can trigger SEO-field extraction for up to 20 URLs from the client's site using the existing Playwright crawler — the system fetches each URL and stores: title, H1, meta description, H2 list, presence of price/CTA in body text, detected intent type (informational / commercial heuristic)
  5. An audit snapshot is saved with a timestamp and version number; user can create multiple audit versions for the same client and compare them side by side
**Plans**: 4 plans
Plans:
- [ ] 21-01-PLAN.md — Backend: SiteAudit model + AuditSnapshot + migration + service + tests
- [ ] 21-02-PLAN.md — Intake checklist UI: structured form + HTMX save + checklist renderer + router
- [ ] 21-03-PLAN.md — XLSX/CSV import: Topvisor parser + PageSpeed/Webmaster parser + column mapping UI + Celery task + tests
- [ ] 21-04-PLAN.md — SEO-field crawler: URL list input + Playwright extraction + intent heuristic + results table + tests
**UI hint**: yes

### Phase 22: Proposal Templates & Tariffs
**Goal**: Users can define tariffs with structured work compositions, build proposals from a block library, and adapt any block to client-specific data — so a proposal for a new client in a known niche takes minutes, not hours
**Depends on**: Phase 21
**Requirements**: PROP-01, PROP-02, PROP-03, PROP-04
**Success Criteria** (what must be TRUE):
  1. User can create and edit tariffs in the system UI: name, monthly price, pages per month by type (event / route / blog), included work directions (list of named items), excluded items — stored in DB and reusable across proposals
  2. User can open a proposal builder for a client, select a tariff, and have tariff content auto-populated into the proposal sections (work composition, volume, pricing)
  3. User can insert pre-written blocks from a block library into any proposal section — blocks are tagged by type (technical, local SEO, content, schema, audit finding) and searchable; each block contains a title and body text with {{placeholders}} for client-specific values
  4. Placeholders in blocks are resolved automatically from the linked client record and audit snapshot (e.g. {{domain}}, {{lcp_score}}, {{top_competitor}}, {{pages_in_index}}); unresolved placeholders are highlighted in the UI for manual fill
  5. User can save a proposal as a named version (e.g. "v1 — initial", "v2 — after call") and restore any previous version; version list is visible on the proposal detail page
**Plans**: 4 plans
Plans:
- [ ] 22-01-PLAN.md — Backend: Tariff model + ProposalTemplate + ProposalBlock library + migration + service + tests
- [ ] 22-02-PLAN.md — Tariff editor UI: CRUD + composition builder + price input + HTMX preview
- [ ] 22-03-PLAN.md — Proposal builder UI: block library sidebar + drag-in blocks + placeholder resolver + section editor
- [ ] 22-04-PLAN.md — Proposal versioning: snapshot save + version list + restore + diff view + tests

**UI hint**: yes

### Phase 23: Document Generator
**Goal**: Users can export any saved proposal as a DOCX or PDF document — with the platform's visual style applied, tables and lists rendered correctly, and each export saved as a file artifact linked to the proposal version
**Depends on**: Phase 22
**Requirements**: DOC-01, DOC-02, DOC-03
**Success Criteria** (what must be TRUE):
  1. User can click "Export DOCX" on any proposal version and receive a downloadable .docx file within 30 seconds via Celery task — generated by python-docx with styles matching the platform's document conventions (headings, tables, bullet lists, color scheme)
  2. User can click "Export PDF" on any proposal version and receive a downloadable .pdf file — generated by the existing subprocess-isolated WeasyPrint infrastructure (same pattern as Phase 14) to prevent OOM kills
  3. The generated document includes all proposal sections in order: intro, audit findings (from audit snapshot), strategy, local SEO block, tariff cards, work stages table, forecast, next steps — sections present in the proposal are included; empty sections are omitted automatically
  4. Position comparison data from the audit snapshot (keyword / client / competitor columns) is rendered as a formatted table in the audit section of the document, with color coding applied where the export format supports it
  5. Each export is saved as a ProposalExport record (file path, format, timestamp, generated_by user) linked to the proposal version — user can download any previous export from the proposal history page
**Plans**: 3 plans
Plans:
- [x] 23-01-PLAN.md — Backend: python-docx renderer + ProposalExport model + migration + Celery task + tests
- [x] 23-02-PLAN.md — PDF renderer: WeasyPrint subprocess adapter + HTML proposal template + CSS styles
- [ ] 23-03-PLAN.md — Export UI: export buttons + status polling (HTMX) + download links + export history tab + tests
**UI hint**: yes

### v3.1 SEO Tools

**Milestone Goal:** Добавить в платформу раздел «Инструменты» — автономные SERP-инструменты без привязки к сайту клиента, работающие по модели Job: пользователь запускает задачу, Celery выполняет, результат доступен для просмотра и CSV/XLSX экспорта. Архитектура по образцу Phase 15 (SuggestJob), каждый инструмент — своя модель.

- [ ] **Phase 24: Tools Infrastructure & Fast Tools** — новый раздел сайдбара, базовая Job-архитектура, три инструмента на существующих компонентах (коммерциализация, парсер мета-тегов, релевантный URL)
- [ ] **Phase 25: SERP Aggregation Tools** — три инструмента, требующие SERP-краулинга (ТЗ на основе ТОП, PAA, пакетная частотность Wordstat)

### Phase 24: Tools Infrastructure & Fast Tools
**Goal**: Users can access a new "Tools" sidebar section with three standalone SERP instruments — commercialization check, meta-tag parser, and relevant URL finder — each running as an async Celery job with typed result storage, downloadable CSV output, and no site binding required
**Depends on**: Phase 23
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
- [ ] 24-01-PLAN.md — Tools infrastructure: sidebar section + shared job-list page + HTMX polling pattern + CSV/XLSX export helper + navigation + smoke tests
- [ ] 24-02-PLAN.md — Commercialization Check: CommerceCheckJob + CommerceCheckResult models + migration + service + Celery task + XMLProxy integration + UI + tests
- [ ] 24-03-PLAN.md — Meta Tag Parser: MetaParseJob + MetaParseResult models + migration + async httpx fetcher service + Celery task + UI + tests
- [ ] 24-04-PLAN.md — Relevant URL Finder: RelevantUrlJob + RelevantUrlResult models + migration + service + Celery task + XMLProxy integration + UI + tests
- [ ] 24-05-PLAN.md — Integration: tools index page + recent jobs across all tools + role-based access + router tests
**UI hint**: yes

### Phase 25: SERP Aggregation Tools
**Goal**: Users can run three advanced tools requiring multi-step SERP aggregation and page crawling — a full copywriting brief generator (TOP-10 analysis + Playwright crawl of each result), a PAA parser, and a batch Wordstat frequency tool — each following the same Job architecture established in Phase 24
**Depends on**: Phase 24
**Requirements**: BRIEF-01, BRIEF-02, PAA-01, FREQ-01
**Success Criteria** (what must be TRUE):
  1. User can submit a group of keyword phrases (up to 30, intended for one landing page) to the Copywriting Brief tool and receive a structured brief containing: recommended title and H1 suggestions, list of H2 headings aggregated from TOP-10 pages, Yandex search highlights (подсветки) across TOP-10, thematic words frequency table, average text volume from TOP-10 pages, commercialization % for the group — all stored in BriefJob + BriefResult with section-level JSON structure
  2. The Copywriting Brief pipeline runs as a multi-step Celery chain: (1) XMLProxy fetches TOP-10 URLs for each phrase → (2) Playwright crawls each TOP-10 page extracting H2s, visible text, and highlights → (3) aggregation service merges results across phrases and computes frequency tables → (4) results written to DB and status set to ready; total runtime under 3 minutes for 10 phrases × 10 results
  3. User can submit a list of up to 50 keyword phrases to the PAA Parser and receive for each phrase: list of "People Also Ask" questions extracted from Yandex SERP, with nested follow-up questions where available — fetched via Playwright (JavaScript-rendered SERP), results stored in PAAJob + PAAResult rows; exported as flat CSV with phrase / question / level columns
  4. User can submit a list of up to 1000 keyword phrases to the Batch Wordstat tool (requires configured Yandex Direct OAuth token, same as Phase 15.3) and receive for each phrase: exact-match frequency "phrase", broad-match frequency [phrase], monthly dynamics chart data — stored in WordstatBatchJob + WordstatBatchResult rows; this extends the Phase 15.3 per-suggest Wordstat into a standalone parity tool matching KeyCollector's batch frequency workflow
  5. All three tools appear in the Tools sidebar section with the same job-list UX from Phase 22; the Batch Wordstat tool shows a warning if no Yandex Direct OAuth token is configured and links to the settings page; all tools have service-layer tests with mocked external calls
**Plans**: 5 plans
Plans:
- [ ] 25-01-PLAN.md — Copywriting Brief backend: BriefJob + BriefResult models + migration + XMLProxy TOP-10 fetcher + Playwright page crawler + aggregation service + Celery chain + tests
- [ ] 25-02-PLAN.md — Copywriting Brief UI: input form (phrase group + region + PS selector) + Celery chain status polling + brief renderer (sections: title/H1, H2 cloud, highlights, thematic words, volume) + XLSX export
- [ ] 25-03-PLAN.md — PAA Parser: PAAJob + PAAResult models + migration + Playwright SERP scenario + nested question extractor + Celery task + UI + CSV export + tests
- [ ] 25-04-PLAN.md — Batch Wordstat: WordstatBatchJob + WordstatBatchResult models + migration + Wordstat API service (extends Phase 15.3) + Celery task + UI + XLSX export + OAuth token check + tests
- [ ] 25-05-PLAN.md — Tools section completion: unified job history page across all 6 tools + pagination + job deletion + re-run button + router tests
**UI hint**: yes

**Dependency Graph (v3.1):**
```
Phase 24 (Tools Infrastructure & Fast Tools)
    └── Phase 25 (SERP Aggregation Tools)
```

**Wave structure:**
- Phase 24: Wave 1 → 24-01 (infra); Wave 2 → 24-02 + 24-03 + 24-04 (parallel); Wave 3 → 24-05
- Phase 25: Wave 1 → 25-01 + 25-03 + 25-04 (parallel backends); Wave 2 → 25-02 (Brief UI, depends on 25-01) + 25-05 (completion)

**Notes:**
- Copywriting Brief (25-01/02) is the heaviest plan — Playwright crawling N×10 pages per job; enforce per-job concurrency limit (max 3 parallel Playwright workers) to avoid VPS memory pressure
- Batch Wordstat (25-04) reuses Yandex Direct OAuth infrastructure from Phase 15.3 — low effort relative to other Phase 25 plans
- All six tool models follow the same pattern: `Job (input, status, user_id, created_at, completed_at)` + `Result (job_id FK, per-row data)`; no shared base model (variant B per architecture decision)
- XMLProxy is already rate-limited via the existing proxy management module — tool jobs must respect the same queue
- Phase 24 smoke tests must cover the HTMX polling pattern — add tool job routes to the Phase 15.1 smoke crawler parametrization

**Dependency Graph (v3.0):**
```
Phase 20 (Client CRM)
    └── Phase 21 (Site Audit Intake)
            └── Phase 22 (Proposal Templates & Tariffs)
                    └── Phase 23 (Document Generator)
```

**Notes:**
- Phases 20–23 form a single milestone (v3.0) and should be planned as a wave sequence
- Phase 21-03 (XLSX/CSV import) can run in parallel with 21-02 (checklist UI) as Wave 2
- Phase 21-04 (SEO-field crawler) reuses existing Playwright infrastructure — lower effort than a new crawler build
- Phase 23-01 (DOCX) and 23-02 (PDF) can run in parallel as Wave 2 within Phase 23
- Block library in Phase 22 can be seeded with content from the primeboat.ru proposal session as real-world examples

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 12. Analytical Foundations | v2.0 | 3/3 | Complete    | 2026-04-06 |
| 13. Impact Scoring & Growth Opportunities | v2.0 | 3/3 | Complete    | 2026-04-06 |
| 14. Client Instructions PDF | v2.0 | 3/3 | Complete    | 2026-04-06 |
| 15. Keyword Suggest | v2.0 | 3/3 | Complete   | 2026-04-07 |
| 15.1. UI Smoke Crawler | v2.0 | 5/5 | Complete   | 2026-04-07 |
| 16. AI/GEO Readiness & LLM Briefs | v2.0 | 4/4 | Complete (LLM e2e deferred) | 2026-04-08 |
| 17. In-app Notifications | v2.0 | 3/3 | Complete   | 2026-04-08 |
| 18. Project Health Widget | v2.1 | 1/1 | Complete    | 2026-04-08 |
| 19. Empty States Everywhere | v2.1 | 0/3 | Not started | - |
| 20. Client CRM | v3.0 | 0/3 | Not started | - |
| 21. Site Audit Intake | v3.0 | 0/4 | Not started | - |
| 22. Proposal Templates & Tariffs | v3.0 | 0/4 | Not started | - |
| 23. Document Generator | v3.0 | 2/3 | Complete    | 2026-04-09 |
| 24. Tools Infrastructure & Fast Tools | v3.1 | 0/5 | Not started | - |
| 25. SERP Aggregation Tools | v3.1 | 0/5 | Not started | - |

## Backlog

### Phase 999.3: Smart Route Discovery (response_class filter) (BACKLOG)

**Goal:** Extend `tests/_smoke_helpers.py::discover_routes` to auto-filter routes by `response_class=HTMLResponse` (or return-type annotation), skipping JSON/CSV endpoints automatically instead of requiring explicit `SMOKE_SKIP` entries. Eliminates the need for the 5 manual skips added during phase-15.1-deferred-routes debug session (`/metrika/{id}/pages`, `/metrika/{id}/compare`, `/analytics/sessions/{id}/export`, `/traffic-analysis/sessions/{id}`, `/traffic-analysis/sessions/{id}/anomalies`). Rationale: surfaced as tech debt in `.planning/phases/15.1-ui-smoke-crawler/deferred-items.md`.
**Requirements:** TBD
**Plans:** 2 plans

Plans:
- [x] 999.3-01-PLAN.md — Three-tier response_class filter + 5 SMOKE_SKIP removals + unit tests + README
- [ ] 999.3-02-PLAN.md — Fix 2 missing stub routes in test fixture (/profile/, /notifications)

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
