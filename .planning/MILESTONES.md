# Milestones

## v2.1 Onboarding & Project Health (Shipped: 2026-04-09)

**Phases completed:** 39 phases, 113 plans, 205 tasks

**Key accomplishments:**

- Full Docker Compose stack (FastAPI 0.115 + PostgreSQL 16 + Redis 7 + Celery 5.4 + redbeat) with async SQLAlchemy session pattern, 3-queue task topology, and per-test DB rollback fixtures
- Fernet-encrypted Site model with admin CRUD endpoints — WP Application Passwords never persist in plain text
- WP Application Password verification via httpx Basic Auth and HTMX-powered site management page with live status updates
- Proxy model + ServiceCredential model + Alembic migration 0033 + XMLProxy XML client + SOCKS5 health checker + per-field Fernet credential store, all backed by 14 passing unit tests
- 1. [Rule 2 - Missing] proxy_row.html created in Task 1
- One-liner:
- Pipeline page now shows job count feedback after "Run Batch" click and guides users through prerequisites in an empty state with icon and ordered steps
- One-liner:
- WeasyPrint PDF generation for brief/detailed project reports with Jinja2 A4 templates, download endpoints, and report UI page
- ReportSchedule model + morning digest Telegram service + SMTP wrapper + Celery Beat tasks for daily/weekly delivery with admin config UI at /ui/admin/report-schedule
- Fixed PDF 500 AttributeError (site.domain->site.name), dashboard status badges enum-to-string, ads 404 redirect, report schedule Tailwind polish, SVG icon sizing
- normalize_url() stdlib utility + keyword_latest_positions flat cache table replacing DISTINCT ON partition scans at 100K keywords
- Service
- ErrorImpactScore pre-computation backend: SQLAlchemy model, Alembic migration 0038, service with pure compute functions + pg_insert upsert, and Celery task joining audit_results + metrika_traffic_pages via normalize_url to produce severity_weight x monthly_traffic scores, triggered automatically after each audit
- Growth Opportunities dashboard with four HTMX tabs aggregating gap keywords, lost positions, cannibalization groups, and Metrika visibility trend from existing data
- One-liner:
- ClientReport model + subprocess-isolated WeasyPrint renderer + data aggregation service with 7 Russian instruction templates and A4 Jinja2 PDF template
- Celery generation task (90s soft limit), 7-endpoint FastAPI router, HTMX-driven templates, and sidebar entry connecting client PDF feature end-to-end
- tests/test_client_report_service.py
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- 9 rule-based GEO readiness checks (BeautifulSoup + regex, 0-100 score) wired into existing audit pipeline via GEO_CHECK_RUNNERS; migration 0041 adds pages.geo_score, llm_brief_jobs, llm_usage, and seeds 9 weighted rows into audit_check_definitions.
- geo_score column with color badges (green/yellow/red/gray) added to audit table; three filter controls (score min/max range + check code select) wired from server-side GET form through router Query params to DB-level WHERE clauses.
- Anthropic Claude Haiku 4.5 integration: per-user Fernet-encrypted key storage, structured JSON prompt builder with 5 context types, per-user Redis circuit breaker (3 failures/15 min), and Celery task with transient/permanent error split.
- Status:
- SQLAlchemy Notification model (D-03 fields + 3 indexes), Alembic migration 0042, notify() helper (D-01 signature), nightly cleanup Celery task wired into Beat at 03:00
- Bell badge in sidebar (HTMX 30s poll) + dropdown (last 10, auto-mark-read) + /notifications full page (kind/site/read-state filters, pagination 50, bulk mark-all)
- notify() import + D-02 guard pattern wired into 6 Celery task files and monitoring dispatcher; LLM brief is the only task with live user_id scope, firing real llm_brief.ready / llm_brief.failed notifications; all other tasks scaffold the guard ready for future user_id plumbing
- One-liner:
- Stub /ui/tools/ page with 6 empty-state sections for upcoming Phase 24-25 tools (Commercialization, Meta Parser, Relevant URL Finder, Copywriting Brief, PAA Parser, Batch Wordstat) and full template parse verification across all 17 Phase 19 templates
- One-liner:
- Pydantic v2 discriminated-union Scenario schema, pytest_collect_file YAML collector, and async executor skeleton with reserved-type skip-with-warning — full browser-free foundation for the scenario runner.
- Session-scoped Playwright fixtures, role/text/label/testid/css locator auto-detect, full P0 step dispatch (open/click/fill/wait_for/expect_text/expect_status), same-loop failure-artifact capture, and an idempotent live-stack seed module — the scenario runner is now functionally complete end-to-end.
- A docker-compose.ci.yml overlay adds a Playwright `tester` service plus the Celery worker healthcheck that RESEARCH.md flagged as a hidden blocker for the suggest scenario, and a single `scripts/run-scenarios-ci.sh` entrypoint brings up the stack, seeds the DB, and runs the scenario suite with one command — the CI plumbing is now complete and ready to consume the P0 YAMLs that plan 05 will ship.
- 1. [Rule 1 - Bug] Collector did not wire `scenario_page` fixture
- One-liner:
- Shepherd.js IIFE tour player (tour.js) with op handlers, sessionStorage resume, and admin-gated CDN include in base.html
- 1. [Verifier note] Dropped duplicate `noqa` re-import line in test additions
- Three Metrika data tables and two Site model columns established via SQLAlchemy 2.0 models and Alembic migration 0020, providing the full data layer for Yandex Metrika integration
- Yandex Metrika API client with organic-filtered daily and per-page traffic fetch, PostgreSQL upsert snapshots, period delta computation, and Celery on-demand task with exponential retry
- FastAPI router delivering 8 Metrika endpoints (dashboard page, fetch trigger, daily/page/compare JSON, events CRUD, settings) with Celery dispatch, Fernet token encryption, and HTMX partial responses
- HTMX lazy-load Metrika traffic widget with 4 KPIs and 30-day sparkline injected into site detail page; /ui/metrika routes and Трафик quick action button added
- One-liner:
- ContentType enum on Page, cta_template_html on Site, and three new audit tables (audit_check_definitions, audit_results, schema_templates) with Alembic migration 0021 seeding 7 default checks and 5 schema templates
- Regex-based HTML detection engine (author block, related posts, CTA) + content_type classifier + check engine with applies_to filtering, backed by PostgreSQL ON CONFLICT upsert persistence and 28 unit tests.
- Schema template service with {{placeholder}} rendering, content-type-to-schema-type mapping, and async CRUD for site-specific JSON-LD template overrides with system default fallback
- FastAPI audit router (13 endpoints), Celery batch audit task, and full-featured Jinja2+HTMX audit UI with per-page check status, content_type editor, CTA textarea, and schema template manager
- TOC/CTA/schema/internal-links fix generators with HTML integrity verification, pipeline job creation, and three REST endpoints wired to existing approve/push flow
- SQLAlchemy models for change monitoring with ChangeType/AlertSeverity enums, alert rules/history/digest tables, and Alembic migration 0022 seeding 9 default rules
- Change detection service with 9 SEO alert types, rule-based severity matching, immediate Telegram dispatch for error-level changes, and crawl pipeline hook
- Weekly digest service with per-site redbeat scheduling, cron computation helper, and send_weekly_digest Celery task wired into beat_init restore
- Monitoring router with 8 endpoints, Jinja2 template with alert rules table, weekly digest schedule form, and alert history feed — wires change monitoring data to the UI
- SQLAlchemy models for AnalysisSession, SessionSerpResult, CompetitorPageData, ContentBrief plus Alembic migration 0023 with sessionstatus enum and 4 tables
- Advanced keyword filter engine with 8 filter axes, full session CRUD, CSV export, and filter-options helper — all in app/services/analytics_service.py
- SERP analysis service with domain classification (aggregator/informational/commercial), competitor detection via frequency analysis, and three Celery tasks (check_group_positions, parse_group_serp, crawl_competitor_pages) for the analytics workspace workflow
- Template-based ТЗ generator producing SEO fields, keyword list, heading structure from competitor analysis and session keywords — with text and CSV export.
- FastAPI analytics router with 20 endpoints covering the full SEO workspace workflow: keyword filtering, session CRUD, Celery-triggered position checks/SERP parse/competitor crawl, side-by-side comparison, brief generation/export, and CSV export.
- 6-step analytics wizard UI: keyword filter → session creation → position check → SERP analysis → competitor comparison → content brief, all via JS fetch() and div panel toggling
- HTML analytics workspace page route with filter_options/sessions/briefs prefetch and 6 pure-function integration tests covering the SERP-to-brief pipeline
- Three SQLAlchemy 2.0 models for content gap analysis — GapKeyword, GapGroup, GapProposal with ProposalStatus enum — plus Alembic migration 0024 and 4 unit tests
- Gap analysis service with frequency × position scoring, SERP/file detection, group CRUD, proposal workflow, and multi-format parser (keys.so, Topvisor, generic CSV/XLSX)
- Gap analysis FastAPI router (14 endpoints), Jinja2 UI page with keyword table/groups/proposals/file upload, and site detail button — all wired together at /gap/{site_id}
- ArchitectureRole enum (8 values), Page.source/architecture_role fields, SitemapEntry + PageLink models, and Alembic migration 0025 for site architecture feature
- Architecture service implementing SF import, sitemap fetch/compare, D3-compatible URL tree, heuristic role detection (8 roles), and inlinks diff — with 10 passing unit tests for all pure functions
- FastAPI architecture router with 10 endpoints + D3.js collapsible URL tree + sitemap/role/inlinks Jinja2 UI, integrated into site detail page
- One-liner:
- FastAPI bulk router (7 endpoints) and Jinja2 UI with select-all keyword table, batch group/cluster/URL actions, CSV/XLSX export, and file import with duplicate-mode selector
- Cannibalization resolution proposals with 4 action types (merge/canonical/redirect/split), Russian action plan generation, SeoTask creation, and HTMX-powered UI with status tracking
- Tasks 01, 02, 03, 05 were already implemented
- SQLAlchemy models (TrafficAnalysisSession, TrafficVisit, BotPattern), Alembic migration 0027 with seeded bot patterns, pure-function bot detection and anomaly detection service, Apache/Nginx log parser, 10 unit tests all passing
- One-liner:
- Status:
- Cross-site position aggregation (TOP-3/10/100 + weekly trend) and today's tasks service with Redis 300s cache, wired into ui_dashboard via asyncio.gather
- Tailwind dashboard with TOP-3/10/100 position summary cards, weekly trend row, and today's tasks widget (priority/overdue/status badges) replacing all inline styles
- One-liner:
- Task 1 — keywords/index.html:
- One-liner:
- Zero inline style= attributes across intent detection and bulk keyword operations pages — classList toggling for all JS-driven show/hide and state color changes
- Both analytics templates (competitors 130L, gap 227L) fully migrated to Tailwind CSS — zero inline style= attributes, classList modal toggling, badge pattern for proposal statuses
- analytics/index.html
- Metrika page, dashboard widget, and Traffic Analysis page fully migrated to Tailwind CSS — all 69 + 23 + 127 inline style= attributes replaced; Chart.js graphs, HTMX event CRUD, bot detection, anomaly alerts, and period comparison all preserved.
- Three project-domain templates (index, kanban, plan) migrated to pure Tailwind with zero inline style= attributes, 5-column kanban grid, and all HTMX interactions preserved
- One-liner:
- monitoring/index.html (162 lines) and audit/index.html (300 lines) migrated to pure Tailwind with zero style= attributes — all JS interactions, severity badges, check icons, and schema modal preserved
- Settings section split into 7 per-child admin_only children with proxy+parameters routes and manager role access
- Tailwind migration of users.html, groups.html, and new proxy.html from settings.html split — 5 template files, zero style= attributes, classList modals
- Four settings templates migrated to Tailwind CSS: new parameters.html extracted from settings.html, plus issues, audit, and datasources pages — all zero style= attributes except one permitted progress bar width
- Async smoke test script that auto-discovers all UI routes from NAV_SECTIONS + main.py, authenticates via cookie JWT, substitutes real site UUIDs, and reports colored pass/fail table with exit code 1 on any 4xx/5xx
- One-liner:
- Fix crawl schedule 405 (hx-put to hx-post) and back-to-site navigation 405 (14 templates redirected to /ui/sites) plus orphaned settings.html deletion

---

## v1.0 MVP (Shipped: 2026-04-06)

**Timeline:** 2026-03-31 — 2026-04-06 (6 days)
**Scope:** 16 phases, 427 commits, 559 files, 35,402 LOC Python

**Key accomplishments:**

- Full Docker Compose stack (FastAPI 0.115 + PostgreSQL 16 + Redis 7 + Celery 5.4 + redbeat) with JWT auth, 3 roles, audit logging
- WordPress site management with Fernet-encrypted credentials, Playwright crawler with snapshot diffs and change feed
- Keyword import (Topvisor/KC/SF), position tracking with monthly-partitioned table, XMLProxy integration for Yandex SERP
- Semantic clustering (SERP intersection), cannibalization detection, keyword-to-page mapping with auto-task creation
- WP content pipeline: TOC generation, schema.org injection, internal linking, mandatory diff approval, rollback
- SEO projects with Kanban board, content plan, one-click WP draft, WeasyPrint PDF briefs
- Dashboard with cross-project aggregation, PDF/Excel reports, scheduled Telegram/SMTP delivery, ad traffic module
- Rate limiting, RBAC audit, client invite links, health endpoint, Flower, HTTPS via Nginx, full README
- Sidebar UI overhaul (v4.0): 6-section navigation, Tailwind CSS migration across 35+ templates, smoke test agent
- Yandex Metrika integration, content audit engine, change monitoring with weekly digests, analytics workspace, gap analysis, site architecture, traffic analysis

**Known gaps (deferred to v2.0):**

- VIS-02: Dark mode toggle not implemented
- MIG-01/02/03: Formal migration audit (page regrouping, 301 redirects, HTMX audit) not performed

**Archives:** [ROADMAP](milestones/v1.0-ROADMAP.md) | [REQUIREMENTS](milestones/v1.0-REQUIREMENTS.md) | [AUDIT](milestones/v1.0-MILESTONE-AUDIT.md)

---
