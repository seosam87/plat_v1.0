# Roadmap: v4.0 UI Overhaul — Information Architecture

## Overview

This milestone restructures the platform's UI from a top-nav layout into a vertical sidebar with 6 SEO-process sections (Обзор, Сайты, Позиции и ключи, Аналитика, Контент, Настройки). No new backend features — pure information architecture, layout migration, and visual consistency. Every existing page is relocated into the new navigation structure and all HTMX interactions are validated post-migration.

## Phases

- [ ] **Phase v4-01: Navigation Foundation** - New base.html with sidebar, site selector, breadcrumb, active states
- [ ] **Phase v4-02: Секция «Обзор»** - Aggregated dashboard as landing page with positions, tasks, and alerts
- [ ] **Phase v4-03: Секция «Сайты»** - Migrate site management pages, remove site detail page
- [ ] **Phase v4-04: Секция «Позиции и ключи»** - Migrate keyword, position, cluster, and file upload pages
- [ ] **Phase v4-05: Секция «Аналитика»** - Migrate analytics workspace, gap, architecture, Metrika, traffic, competitors
- [ ] **Phase v4-06: Секция «Контент»** - Migrate content audit, WP pipeline, publisher, projects, kanban, monitoring
- [ ] **Phase v4-07: Секция «Настройки»** - Migrate admin pages with role guard
- [ ] **Phase v4-08: UI Smoke Test Agent** - Automated route crawler that finds 4xx/5xx errors across all pages
- [ ] **Phase v4-09: Visual Polish & Migration Completion** - Dark mode, URL redirects, HTMX validation pass

## Phase Details

### Phase v4-01: Navigation Foundation
**Goal**: Users see a new vertical sidebar layout that replaces the top nav and all pages inherit it without functional regression
**Depends on**: Nothing (first phase of milestone)
**Requirements**: NAV-01, NAV-02, NAV-03, NAV-04, NAV-05, NAV-06, VIS-01, VIS-03
**Success Criteria** (what must be TRUE):
  1. User sees a vertical sidebar with 6 named sections (Обзор, Сайты, Позиции и ключи, Аналитика, Контент, Настройки), each with an icon and collapsible sub-items
  2. User selects a site in the sticky site selector at the top of the sidebar and the selection persists when switching between sections
  3. The current sidebar section and sub-item are visually highlighted (active state) on every page
  4. User sees a breadcrumb trail (Section > Site > Page) on every page
  5. All existing pages load without errors and display the new sidebar layout
**Plans**: 1 plan
Plans:
- [ ] v4-01-01-PLAN.md — Sidebar layout, site selector, breadcrumbs, navigation config, active states
**UI hint**: yes

### Phase v4-02: Секция «Обзор»
**Goal**: Users land on an aggregated dashboard after login that shows cross-site position summary and today's tasks
**Depends on**: Phase v4-01
**Requirements**: OVR-01, OVR-02, OVR-03
**Success Criteria** (what must be TRUE):
  1. After login, the user lands on Обзор — not a redirect or splash screen
  2. User sees aggregated position summary across all sites (TOP-3/10/100 counts, weekly trend up/down)
  3. User sees overdue and in-progress tasks for today from the Kanban board
  4. The Обзор page loads in under 3 seconds
**Plans**: 2 plans
Plans:
- [ ] v4-02-01-PLAN.md — overview_service: cross-site position aggregation + today's tasks + Redis cache + unit tests
- [ ] v4-02-02-PLAN.md — dashboard/index.html rewrite: position summary cards, trend row, tasks widget (Tailwind)
**UI hint**: yes

### Phase v4-03: Секция «Сайты»
**Goal**: All site management functionality is accessible through sidebar sub-items and the site detail page no longer exists as a standalone page
**Depends on**: Phase v4-01
**Requirements**: SITE-V4-01, SITE-V4-02, SITE-V4-03
**Success Criteria** (what must be TRUE):
  1. User can add, remove, and verify sites via sidebar sub-items in the «Сайты» section
  2. User can view crawl history and crawl schedule for the selected site within the Сайты section
  3. Navigating to the old site detail URL either redirects or is absent — the sidebar and section pages cover all its prior functions
**Plans**: 2 plans
Plans:
- [ ] v4-03-01-PLAN.md — Nav update, site list Tailwind redesign with metrics, schedule page, detail removal
- [ ] v4-03-02-PLAN.md — Crawl history + change feed Tailwind migration, start crawl button
**UI hint**: yes

### Phase v4-04: Секция «Позиции и ключи»
**Goal**: All keyword, position, cluster, cannibalization, and import pages are reachable through sidebar sub-items and respond to site selector changes
**Depends on**: Phase v4-01
**Requirements**: KW-V4-01, KW-V4-02, KW-V4-03
**Success Criteria** (what must be TRUE):
  1. User can reach keywords, positions, clusters, cannibalization, intent, and bulk operations via sidebar sub-items under «Позиции и ключи»
  2. When the user changes the selected site in the sticky site selector, content in this section reloads for the new site without a full page navigation
  3. User can upload Topvisor, Key Collector, and SF files from within this section
**Plans**: 3 plans
Plans:
- [ ] v4-04-01-PLAN.md — Keywords + Positions Tailwind migration (table, forms, HTMX edits, distribution bar, Chart.js modals, async polling)
- [ ] v4-04-02-PLAN.md — Clusters + Cannibalization Tailwind migration (cards, intent dropdown, resolution forms, status history)
- [ ] v4-04-03-PLAN.md — Intent + Bulk operations Tailwind migration (async detection, proposals, filters, import/export)
**UI hint**: yes

### Phase v4-05: Секция «Аналитика»
**Goal**: Analytics Workspace, Gap analysis, Architecture, Metrika, traffic analysis, and competitors pages are all accessible under the Аналитика sidebar section
**Depends on**: Phase v4-01
**Requirements**: AN-V4-01, AN-V4-02
**Success Criteria** (what must be TRUE):
  1. User can reach Analytics Workspace, Gap-анализ, Архитектура, Metrika, and Анализ трафика via sidebar sub-items under «Аналитика»
  2. User can reach Конкуренты as a sub-item under «Аналитика»
**Plans**: 3 plans
Plans:
- [ ] v4-05-01-PLAN.md — Competitors + Gap analysis Tailwind migration (tables, modals, proposals, groups)
- [ ] v4-05-02-PLAN.md — Analytics Workspace + Architecture Tailwind migration (wizard steps, D3.js tree)
- [ ] v4-05-03-PLAN.md — Metrika + widget + Traffic Analysis Tailwind migration (Chart.js, HTMX events, bots, injections)
**UI hint**: yes

### Phase v4-06: Секция «Контент»
**Goal**: All content-related pages — audit, pipeline, publisher, projects, kanban, content plan, and change monitoring — are reachable through the Контент sidebar section
**Depends on**: Phase v4-01
**Requirements**: CNT-V4-01, CNT-V4-02, CNT-V4-03
**Success Criteria** (what must be TRUE):
  1. User can reach Content Audit, WP Pipeline, and DOCX Publisher via sidebar sub-items under «Контент»
  2. User can reach Проекты, Kanban, and Контент-план via sidebar sub-items under «Контент»
  3. User can reach Мониторинг изменений as a sub-item under «Контент»
**Plans**: 3 plans
Plans:
- [ ] v4-06-01-PLAN.md — Projects + Kanban + Content Plan Tailwind migration (form toggle, HTMX status transitions, create-draft)
- [ ] v4-06-02-PLAN.md — Pipeline Jobs + DOCX Publisher Tailwind migration (diff modal, tabs, bulk actions, upload form)
- [ ] v4-06-03-PLAN.md — Change Monitoring + Content Audit Tailwind migration (alert rules, digest, schema modal, filters)
**UI hint**: yes

### Phase v4-07: Секция «Настройки»
**Goal**: All admin configuration pages are reachable through the Настройки sidebar section and the section is invisible to non-admin users
**Depends on**: Phase v4-01
**Requirements**: CFG-V4-01, CFG-V4-02
**Success Criteria** (what must be TRUE):
  1. Admin user can reach user management, groups, data sources, proxy settings, parameters, and audit log via sidebar sub-items under «Настройки»
  2. Non-admin users (manager, client roles) do not see the «Настройки» section in the sidebar
**Plans**: TBD
**UI hint**: yes

### Phase v4-08: UI Smoke Test Agent
**Goal**: Automated test script that authenticates, discovers all UI routes from navigation config and main.py, visits every page with a real site_id, and reports 4xx/5xx errors with URL and status code. Runnable as `python -m tests.smoke_test` or via Celery task.
**Depends on**: Phase v4-01
**Requirements**: SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04
**Success Criteria** (what must be TRUE):
  1. Running `python -m tests.smoke_test` authenticates as admin and visits every registered UI route
  2. For site-scoped routes, the script substitutes a real site_id from the database
  3. The report lists every URL with HTTP status code; 4xx and 5xx are flagged as errors
  4. The script exits with code 1 if any errors found, code 0 if all pages return 200/3xx
  5. Can be triggered as a Celery task that sends results to Telegram
**Plans**: 2 plans
Plans:
- [ ] v4-08-01-PLAN.md — Smoke test runner: route discovery, auth, site_id substitution, colored report, exit codes
- [ ] v4-08-02-PLAN.md — Celery task wrapper with Telegram summary reporting

### Phase v4-09: Visual Polish & Migration Completion
**Goal**: Dark mode is available site-wide, all 50+ pages have been confirmed in their new sections, existing URL patterns are preserved or redirected, and HTMX interactions are validated
**Depends on**: Phase v4-02, Phase v4-03, Phase v4-04, Phase v4-05, Phase v4-06, Phase v4-07, Phase v4-08
**Requirements**: VIS-02, MIG-01, MIG-02, MIG-03
**Success Criteria** (what must be TRUE):
  1. User can toggle dark mode from the sidebar footer and the preference persists across page loads
  2. All 50+ existing pages render correctly in the new layout with no broken functionality
  3. All pre-existing URL patterns return correct content or respond with a 301 redirect to the new URL
  4. All HTMX partial-update interactions (inline edits, filters, table reloads) work correctly after migration to the new layout
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in order: v4-01 → (v4-02..v4-07 parallel) → v4-08 → v4-09

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| v4-01. Navigation Foundation | 1/1 | Complete | 2026-04-03 |
| v4-02. Секция «Обзор» | 2/2 | Complete | 2026-04-03 |
| v4-03. Секция «Сайты» | 2/2 | Complete | 2026-04-03 |
| v4-04. Секция «Позиции и ключи» | 3/3 | Complete | 2026-04-03 |
| v4-05. Секция «Аналитика» | 0/3 | **Next** | - |
| v4-06. Секция «Контент» | 0/3 | Not started | - |
| v4-07. Секция «Настройки» | 0/TBD | Not started | - |
| v4-08. UI Smoke Test Agent | 2/2 | Complete | 2026-04-03 |
| v4-09. Visual Polish & Migration | 0/TBD | Not started | - |
