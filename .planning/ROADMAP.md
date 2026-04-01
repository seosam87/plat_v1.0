# Roadmap: SEO Management Platform

## Overview

Starting from a blank VPS, we build in strict dependency order: database and auth patterns first (everything else depends on them), then site management, then the Playwright crawler (which establishes the worker pattern reused by SERP parsing), then keyword import and position tracking (with `keyword_positions` monthly partitioning created before the first write — this is non-negotiable), then semantic clustering, the WordPress content pipeline (the platform's structural differentiator), project/task management, reporting, and finally client access hardening. Each phase delivers a coherent, usable capability; later phases consume data produced by earlier ones and add no value without them.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Stack & Auth** — Developer can start the full Docker stack and log in with role-based access
- [x] **Phase 2: Site Management** — Admin can add, verify, and manage WordPress sites with encrypted credentials
- [x] **Phase 3: Crawler Core** — User can crawl a site, view per-page SEO data, and browse a snapshot diff feed (completed 2026-04-01)
- [x] **Phase 4: Crawl Scheduling** — User can configure crawl schedules from the UI without restarting the app, and auto-tasks appear for 404s (completed 2026-04-01)
- [x] **Phase 4.1: Test Backfill** — INSERTED — unit tests for phases 1–4 service logic, crawl helpers, WP service, router gaps (completed 2026-04-01)
- [x] **Phase 5: Keyword Import & File Parsers** — Keywords from Topvisor/KC/manual, SF import, GSC/DataForSEO/Yandex Webmaster APIs (completed 2026-04-01)
- [ ] **Phase 6: Position Tracking** — User can see position history, delta indicators, 90-day charts, and receive Telegram alerts on drops
- [ ] **Phase 7: Semantics** — User can cluster keywords, map them to pages, and see cannibalization flags
- [ ] **Phase 8: WP Pipeline** — User can run the content enrichment pipeline with mandatory diff preview before any change goes live
- [ ] **Phase 9: Projects & Tasks** — User can manage work on a Kanban board, plan content, and generate page briefs
- [ ] **Phase 10: Reports & Ads** — User can view the dashboard, export reports, schedule delivery, and upload ad traffic data
- [ ] **Phase 11: Hardening** — Platform is rate-limited, fully RBAC-audited, observable, and deployable from README in <30 min

## Phase Details

### Phase 1: Stack & Auth
**Goal**: Working Docker Compose stack with JWT authentication (3 roles), correct Celery queue topology, Redis configuration, async session patterns, and audit logging — the foundation every subsequent phase builds on.
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-05, INFRA-06, INFRA-07, AUTH-01, AUTH-02, AUTH-05, SEC-01, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. `docker-compose up --build` starts cleanly from a fresh clone with no manual steps
  2. A user can log in with email/password and receive a JWT; token is rejected after 24h
  3. Admin, manager, and client roles exist and can be assigned; admin can create/deactivate accounts
  4. All user actions (login, create, update, delete) appear in the `audit_log` table with user and timestamp
  5. Three Celery queues (`crawl`, `wp`, `default`) are visible and routing is verified in logs
**Plans**: 4 plans

Plans:
- [x] 01-01: Docker Compose stack — FastAPI + PostgreSQL 16 + Redis 7 + Celery 5.4 + Beat; env vars; lifespan pattern; async session with try/finally; Redis appendonly + maxmemory-policy; Celery result_expires=3600; three queues wired
- [ ] 01-02: Alembic setup + users table migration; bcrypt password hashing; JWT issue/verify (24h expiry); login endpoint; current-user dependency
- [ ] 01-03: Role model (admin / manager / client); admin user-management endpoints (create, edit, deactivate); role guard at route + service layer
- [ ] 01-04: Audit log model + middleware; structured JSON logging with loguru (DEBUG/INFO/ERROR, 10 MB rotation, 30-day retention); Alembic migration baseline

### Phase 2: Site Management
**Goal**: Admin can add WordPress sites with Fernet-encrypted Application Passwords, verify the WP REST API connection, and see connection status for all sites. Associated jobs stop cleanly when a site is disabled.
**Depends on**: Phase 1
**Requirements**: SITE-01, SITE-02, SITE-03, SITE-04, SEC-02
**Success Criteria** (what must be TRUE):
  1. Admin can add a site (name, URL, Application Password) and immediately see a "connected" or "failed" status
  2. The stored Application Password is Fernet-encrypted at rest and never appears in API responses or logs
  3. Admin can disable a site; any running jobs for that site fail gracefully without affecting other sites
  4. A site management page lists all sites with their current connection status
**Plans**: 3 plans

Plans:
- [x] 02-01: Site model + Alembic migration; Fernet encryption service for WP credentials (encrypt on write, decrypt at call time only); site CRUD endpoints
- [x] 02-02: WP REST API connection verification (ping `/wp/v2/users/me` with Application Password); connection status stored on site model; site management UI page (Jinja2 + HTMX)
- [x] 02-03: Site disable/enable logic; Celery task guard (skip tasks for disabled sites without crash); basic WP post/page CRUD via WP REST API

### Phase 3: Crawler Core
**Goal**: System can crawl a WordPress site using Playwright, capture per-page SEO signals, save snapshots with JSON diffs vs. the previous crawl, and let users browse a filterable change feed.
**Depends on**: Phase 2
**Requirements**: CRAWL-01, CRAWL-02, CRAWL-03, CRAWL-04, CRAWL-05, CRAWL-08, CRAWL-09, INFRA-09
**Success Criteria** (what must be TRUE):
  1. Triggering a crawl collects URL, title, H1, meta description, HTTP status, depth, and internal link count for every discovered page
  2. Each page is classified as category / article / landing / product; TOC, schema.org, noindex presence is detected
  3. After the second crawl, a diff is available showing which SEO fields changed and what content changed (first 500 chars)
  4. Change feed UI filters correctly by: SEO fields changed / content changed / new pages / status changes
  5. Playwright workers use `--max-tasks-per-child=50` and a `BrowserContext` closed in `finally`; no orphaned Chromium processes after task completion
**Plans**: 4 plans

Plans:
- [ ] 03-01: Playwright worker setup — `worker_process_init` signal for module-level Browser; one BrowserContext per task closed in finally; `WORKER_MAX_TASKS_PER_CHILD=50`; `crawl` queue concurrency=2; `soft_time_limit`; `CRAWLER_DELAY_MS` env var
- [ ] 03-02: Sitemap.xml parser to seed URL discovery; recursive link-following crawler; page data model + Alembic migration (URL, title, H1, meta, status, depth, link count, page type, TOC/schema/noindex flags)
- [ ] 03-03: Page snapshot model + diff computation (SEO fields + first 500 chars of content stored as JSON in `page_snapshots`); max-pages limit enforced
- [ ] 03-04: Change feed UI — filterable by change type (SEO / content / new / status); HTMX-powered filter controls; page detail view with before/after diff display

### Phase 4: Crawl Scheduling
**Goal**: User can configure crawl schedules (daily / weekly / manual) from the UI without restarting any container, and the schedule survives Redis flushes and Docker restarts. System auto-creates project tasks for 404s and lost-indexation pages.
**Depends on**: Phase 3
**Requirements**: CRAWL-06, CRAWL-07, INFRA-08
**Success Criteria** (what must be TRUE):
  1. User can change a site's crawl schedule (daily / weekly / manual) in the UI and the new schedule takes effect without restarting workers or Beat
  2. After a Redis `FLUSHALL`, the crawl schedule is restored from PostgreSQL without manual intervention
  3. A crawl that finds a 404 page auto-creates a task in the project (if one exists for that site) with the URL and issue type in the task context
  4. A page that had indexation on the previous crawl and is now noindex auto-creates a "lost indexation" task
**Plans**: 3 plans

Plans:
- [x] 04-01: redbeat 2.2 integration — PostgreSQL-backed schedule storage; Beat startup loads schedules from DB; redbeat configured in Celery Beat service
- [x] 04-02: Crawl schedule UI — per-site schedule selector (daily / weekly / manual); HTMX form updates redbeat entry without restart; schedule stored in DB as source of truth
- [x] 04-03: Auto-task creation from crawl results — 404 detection → task; lost-indexation detection (noindex flip vs. previous snapshot) → task; task model + Alembic migration; task linked to site and page URL

### Phase 5: Keyword Import & File Parsers
**Goal**: User can import keywords from Topvisor/Key Collector/manual entry, import technical audit from Screaming Frog, and pull positions from GSC, Yandex Webmaster, and DataForSEO. All file imports track history and support real column formats from these tools.
**Depends on**: Phase 4
**Requirements**: RANK-01, RANK-02, RANK-03, RANK-04, RANK-05, RANK-06, RANK-12, RANK-13
**Success Criteria** (what must be TRUE):
  1. User can import keywords from a Key Collector XLSX/CSV (with keyword groups, positions, URLs) — groups preserved
  2. User can import keywords from a Topvisor XLSX/CSV (keywords, frequency, position history by date columns)
  3. User can import Screaming Frog XLSX/CSV as a technical audit (URL, status, title, H1, word count, inlinks) — saved as Page records
  4. All imports tracked in file_uploads table with status; upload history visible in UI
  5. User can manually add individual keywords with frequency, region, and engine fields
  6. GSC OAuth 2.0 flow completes; platform fetches positions, clicks, CTR, and impressions
  7. DataForSEO credentials accepted; position queries return results
  8. Yandex Webmaster API token accepted; platform fetches position data
  9. Playwright SERP parser with UA rotation, <50 req/day guard
**Plans**: 5 plans

Plans:
- [x] 05-01: Keyword + KeywordGroup + FileUpload models, Alembic migration; keyword fields: phrase, frequency, region, engine, group_id, site_id; file_uploads: site_id, file_type, original_name, status, row_count, uploaded_at; manual keyword entry form + API
- [x] 05-02: File parsers — Topvisor (xlsx/csv: keywords, frequency, position history by date columns), Key Collector (xlsx/csv: keywords, parent group, positions, URLs), Screaming Frog (xlsx/csv: URL, status, title, H1, word count, inlinks → Page records); column auto-detection; upload UI with file type selector; upload history page; unit tests for each parser
- [x] 05-03: GSC integration — OAuth 2.0 flow with authlib; Search Analytics fetch (positions, clicks, CTR, impressions); token refresh; GSC credentials stored encrypted; pagination with `startRow` for large sites
- [x] 05-04: DataForSEO integration — SERP endpoint as primary; Keywords Data endpoint for volume/difficulty estimates; batch scheduling; retry=3; DataForSEO set as primary SERP source with Playwright as fallback
- [x] 05-05: Yandex Webmaster API integration (token-based, not scraping); Playwright SERP parser with User-Agent rotation, configurable delays, low-volume guard (<50 req/day without proxy); Celery Beat position check schedule (daily / weekly / manual)

### Phase 6: Position Tracking
**Goal**: User can see current positions with delta indicators and colour coding, drill into a 90-day history chart per keyword, filter by engine/region/cluster/top-N, and receive Telegram alerts when a keyword drops.

> **CRITICAL — `keyword_positions` partitioning:** The `keyword_positions` table MUST be created with monthly range partitioning on `checked_at` in this phase's first Alembic migration — before any position data is written. This cannot be added retroactively to a populated table without a full rebuild. At 50 sites × 500 keywords × 2 engines × 365 days = 18M rows/year, a non-partitioned table will cause full table scans and chart timeouts. This is a hard constraint, not an option.

**Depends on**: Phase 5
**Requirements**: RANK-07, RANK-08, RANK-09, RANK-10, RANK-11
**Success Criteria** (what must be TRUE):
  1. `keyword_positions` table exists with monthly range partitioning on `checked_at` (verified via `\d+ keyword_positions` in psql) before any position row is inserted
  2. Positions table shows keyword, current position, delta vs. previous check (arrow + colour), URL, engine, geo, device for every tracked keyword
  3. Clicking a keyword opens a 90-day Chart.js history chart rendered from partitioned data
  4. Filter controls (top-3 / top-10 / top-100 / engine / region / cluster) correctly narrow the positions table
  5. A Telegram alert is sent when a keyword drops by the configured threshold (e.g. −5 positions)
**Plans**: 3 plans

Plans:
- [ ] 06-01: `keyword_positions` Alembic migration — monthly range-partitioned table on `checked_at`; partition management; indexes on (keyword_id, engine, checked_at); this migration runs before any position write
- [ ] 06-02: Position writer service — stores DataForSEO/GSC/Yandex results into `keyword_positions`; delta computation vs. previous check; Celery Beat schedule for automated checks
- [ ] 06-03: Position table UI — keyword + position + delta arrow + colour indicator + URL + engine/geo/device columns; filter controls (top-N / engine / region / cluster); 90-day Chart.js chart per keyword; Telegram alert task (configurable drop threshold, retry=3)

### Phase 7: Semantics
**Goal**: User can cluster keywords manually or via SERP intersection, map clusters to target pages, see cannibalization warnings, export the full keyword list, and have the system auto-create tasks for keywords with no mapped page.
**Depends on**: Phase 6
**Requirements**: SEM-01, SEM-02, SEM-03, SEM-04, SEM-05, SEM-06, PROJ-03 (partial — missing-page and cannibalization auto-tasks)
**Success Criteria** (what must be TRUE):
  1. User can drag keywords into named clusters and save the grouping
  2. Auto-cluster runs SERP intersection (keywords sharing ≥N top-10 results) and proposes clusters the user can accept or edit
  3. User can map a keyword or cluster to a target page URL; mapping is stored and visible in the positions table
  4. System flags cannibalization when two or more mapped pages both rank in top-100 for the same keyword
  5. Keywords with no mapped page trigger a "missing page" task auto-creation in the linked project
  6. User can export the full keyword list with cluster labels and page mappings as CSV
**Plans**: 3 plans

Plans:
- [ ] 07-01: Cluster model + Alembic migration; manual cluster UI with drag-and-drop (HTMX + Sortable.js); keyword-to-cluster assignment; cluster CRUD endpoints
- [ ] 07-02: SERP-intersection auto-clustering (keywords sharing ≥N results in top-10); keyword → page URL mapping model; cannibalization detection query (2+ pages ranked top-100 for same keyword); cannibalization flag in positions table UI
- [ ] 07-03: Missing-page detector (keyword with no mapped page) → auto-create task in project; keyword list CSV export (keyword, cluster, mapped URL, volume, engine); SEM-06 + SEM-05 complete

### Phase 8: WP Pipeline
**Goal**: User can run the content enrichment pipeline (TOC generation, schema.org injection, internal linking) against any page, review a mandatory diff before anything is pushed to WordPress, and roll back to previous content from job history.
**Depends on**: Phase 7
**Requirements**: WPC-01, WPC-02, WPC-03, WPC-04, WPC-05, WPC-06, WPC-07, WPC-08, WPC-09
**Success Criteria** (what must be TRUE):
  1. User can fetch the WP page list filtered by status, type, TOC present, and schema.org present
  2. Pages missing TOC or schema.org Article markup are flagged in the UI
  3. Triggering pipeline on a page runs download → TOC generation → schema.org injection → internal link insertion → Yoast/RankMath meta update — all in Celery without blocking the UI
  4. Diff view (changed blocks only, before/after) is shown and must be explicitly approved before content is pushed to WP
  5. User can view job history for any page and roll back to a previous version
  6. Batch processing for all pages in a category runs in background; user can monitor progress
**Plans**: 4 plans

Plans:
- [ ] 08-01: WP page list fetch (WP REST API, filters: status/type/TOC/schema); `wp_content_jobs` model + Alembic migration (status, diff_json, processed_at, rollback payload); Yoast vs RankMath plugin detection per site (`seo_plugin` field on site model)
- [ ] 08-02: Celery `wp` queue pipeline task — download full HTML via Playwright; H2–H3 structure detection; TOC HTML block generation; JSON-LD schema.org Article injection (headline, datePublished, author); WP rate-limit handling (exponential backoff on 429/403)
- [ ] 08-03: Internal linking — find relevant pages from DB by keyword overlap; insert link block into content; Yoast/RankMath post_meta write via WP REST API; diff_json computation (before/after changed blocks)
- [ ] 08-04: Diff preview UI (mandatory approval gate before push); batch processing by category (HTMX progress bar); job history UI with rollback action; one-click new WP post creation from platform

### Phase 9: Projects & Tasks
**Goal**: User can create SEO projects, manage tasks on a Kanban board, build a content plan, create WP draft posts in one click, and generate downloadable page briefs from keyword clusters.
**Depends on**: Phase 8
**Requirements**: PROJ-01, PROJ-02, PROJ-03, PROJ-04, PROJ-05, PROJ-06, PROJ-07, PROJ-08
**Success Criteria** (what must be TRUE):
  1. User can create a project linked to a site and a client; project has name, description, and status
  2. Kanban board shows tasks in To Do / In Progress / Done columns with drag-and-drop status changes
  3. Tasks for missing pages, cannibalized pages, and pages without schema.org are auto-created with issue context (keyword, URL, type)
  4. Content plan rows link keyword → proposed title → status → planned date → WP post; user can create a WP draft from a row in one click
  5. Page brief generated from a cluster includes H1–H3 structure, target keywords, and volume estimates; downloadable as HTML and PDF
**Plans**: 3 plans

Plans:
- [ ] 09-01: Project model + Alembic migration (site, client link, name, description, status); task model (title, description, status, assignee, due date, issue context); project and task CRUD endpoints; project dashboard page
- [ ] 09-02: Kanban board UI — To Do / In Progress / Done columns; HTMX drag-and-drop status updates; auto-task creation wiring for missing pages + cannibalization + no-schema triggers; manual task create/edit/assign/due-date
- [ ] 09-03: Content plan model (keyword → title → status → date → WP post link); content plan UI; one-click WP draft creation from content plan row; template-based page brief generator (H1–H3 + keywords + volume); WeasyPrint PDF export; brief linked to task or content plan row

### Phase 10: Reports & Ads
**Goal**: User can view a live dashboard aggregating all projects, export project reports as PDF and Excel, schedule automatic delivery via Telegram or email, and upload/compare ad traffic data.
**Depends on**: Phase 9
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, ADS-01, ADS-02, ADS-03
**Success Criteria** (what must be TRUE):
  1. Dashboard loads in <3s with 50 active projects, showing top positions, tasks in progress, and recent site changes
  2. Manager can generate a project report (position trends + task progress + site changes) downloadable as PDF and Excel
  3. Report delivery can be scheduled via Celery Beat to Telegram and/or SMTP; morning digest is configurable
  4. User can upload ad traffic CSV (source, date, sessions, conversions, cost) and immediately see the data in charts
  5. Period comparison (before / after) shows a table with % and absolute delta for sessions, conversions, CR%, cost-per-conversion
**Plans**: 4 plans

Plans:
- [ ] 10-01: Dashboard aggregation queries — Redis-cached (5-min TTL); CTEs/window functions for cross-project aggregation (avoid N+1 over sites); top positions, tasks in progress, recent changes widgets; EXPLAIN ANALYZE verification at 50 sites × 500 keywords
- [ ] 10-02: Project report generation — WeasyPrint PDF (position trends, task progress, site changes); openpyxl Excel export; report download endpoints
- [ ] 10-03: Scheduled report delivery — Celery Beat tasks for Telegram (Bot API) and SMTP; morning digest Telegram message; configurable schedule per project; retry=3 on delivery failures
- [ ] 10-04: Ad traffic module — CSV upload (source, date, sessions, conversions, cost); ad_traffic model + Alembic migration; period comparison table (% + absolute delta); weekly/monthly trend chart per source (Chart.js)

### Phase 11: Hardening
**Goal**: Platform enforces rate limits on all endpoints, RBAC is audited at service layer, client invite links work, task queue is observable, health check covers all components, and the system is deployable from scratch in <30 minutes following the README.
**Depends on**: Phase 10
**Requirements**: INFRA-02, INFRA-03, INFRA-04, INFRA-10, AUTH-03, AUTH-04, SEC-05
**Success Criteria** (what must be TRUE):
  1. `GET /health` returns 200 with DB, Redis, and Celery status; returns 503 if any component is down
  2. Manager accessing another manager's project receives 403 (not 404 or 200); client accessing any project they are not assigned to receives 403
  3. Admin can generate an invite link; following it creates a client account bound to the specified project
  4. Repeated rapid requests to any API endpoint trigger rate limiting (429 response)
  5. Celery task queue status is visible in Flower or an equivalent UI
  6. A developer following only the README can have the full stack running locally in <30 minutes
**Plans**: 4 plans

Plans:
- [ ] 11-01: RBAC service-layer audit — review all service functions for role checks; add manager→own-projects guard and client→assigned-projects guard at service layer (not just routes); integration tests for 403 paths
- [ ] 11-02: Client invite link system — generate signed URL (JWT or UUID token); registration endpoint that accepts token and auto-binds new client account to project; token expiry
- [ ] 11-03: slowapi rate limiting on all API endpoints; `GET /health` endpoint (DB ping + Redis ping + Celery inspect ping + Beat schedule count assert); Celery Flower configured with basic auth in docker-compose; HTTPS via Nginx reverse proxy in docker-compose
- [ ] 11-04: OpenAPI docs verified at `/docs`; README: prerequisites + clone + env setup + `docker-compose up --build` + first login; deploy walkthrough tested end-to-end; version pins locked in requirements.txt

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Stack & Auth | 0/4 | Not started | - |
| 2. Site Management | 0/3 | Not started | - |
| 3. Crawler Core | 0/4 | Complete    | 2026-04-01 |
| 4. Crawl Scheduling | 0/3 | Not started | - |
| 5. Keyword Import | 0/4 | Not started | - |
| 6. Position Tracking | 0/3 | Not started | - |
| 7. Semantics | 0/3 | Not started | - |
| 8. WP Pipeline | 0/4 | Not started | - |
| 9. Projects & Tasks | 0/3 | Not started | - |
| 10. Reports & Ads | 0/4 | Not started | - |
| 11. Hardening | 0/4 | Not started | - |
