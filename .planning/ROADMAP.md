# Roadmap: SEO Management Platform

## Milestones

- **v1.0 MVP** — 16 phases (shipped 2026-04-06) — [details](milestones/v1.0-ROADMAP.md)
- **v2.0 SEO Insights & AI** — Phases 12–17 (in progress)

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
- [ ] **Phase 13: Impact Scoring & Growth Opportunities** - Error prioritization by traffic + unified growth opportunity dashboard
- [ ] **Phase 14: Client Instructions PDF** - Non-technical PDF report for site owners built on subprocess-isolated WeasyPrint
- [ ] **Phase 15: Keyword Suggest** - Yandex/Google autocomplete with Redis caching and rate-limited Celery tasks
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
**Plans**: TBD

### Phase 14: Client Instructions PDF
**Goal**: Users can generate a PDF report for site owners that explains each problem and its fix steps in plain Russian, using subprocess-isolated WeasyPrint to prevent OOM kills
**Depends on**: Phase 12
**Requirements**: CPDF-01, CPDF-02, CPDF-03
**Success Criteria** (what must be TRUE):
  1. User can click "Generate client PDF" for any site and receive a downloadable PDF within 60 seconds via Celery task
  2. The generated PDF combines Quick Wins, audit errors, and fix recommendations in a non-technical format (problem → solution → steps in WP admin)
  3. Each error type in the report uses a Russian-language instruction template explaining the fix steps; at least the standard error types (404, noindex, missing TOC, missing schema) are covered
  4. PDF generation runs in a subprocess per report so a WeasyPrint memory leak cannot kill the shared Celery worker
**Plans**: TBD
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
**Plans**: TBD

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
**Plans**: TBD
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
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 12. Analytical Foundations | v2.0 | 3/3 | Complete    | 2026-04-06 |
| 13. Impact Scoring & Growth Opportunities | v2.0 | 0/TBD | Not started | - |
| 14. Client Instructions PDF | v2.0 | 0/TBD | Not started | - |
| 15. Keyword Suggest | v2.0 | 0/TBD | Not started | - |
| 16. AI/GEO Readiness & LLM Briefs | v2.0 | 0/TBD | Not started | - |
| 17. In-app Notifications | v2.0 | 0/TBD | Not started | - |
