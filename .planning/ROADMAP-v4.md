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
- [ ] **Phase v4-08: Visual Polish & Migration Completion** - Dark mode, URL redirects, HTMX validation pass

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
**Plans**: TBD
**UI hint**: yes

### Phase v4-03: Секция «Сайты»
**Goal**: All site management functionality is accessible through sidebar sub-items and the site detail page no longer exists as a standalone page
**Depends on**: Phase v4-01
**Requirements**: SITE-V4-01, SITE-V4-02, SITE-V4-03
**Success Criteria** (what must be TRUE):
  1. User can add, remove, and verify sites via sidebar sub-items in the «Сайты» section
  2. User can view crawl history and crawl schedule for the selected site within the Сайты section
  3. Navigating to the old site detail URL either redirects or is absent — the sidebar and section pages cover all its prior functions
**Plans**: TBD
**UI hint**: yes

### Phase v4-04: Секция «Позиции и ключи»
**Goal**: All keyword, position, cluster, cannibalization, and import pages are reachable through sidebar sub-items and respond to site selector changes
**Depends on**: Phase v4-01
**Requirements**: KW-V4-01, KW-V4-02, KW-V4-03
**Success Criteria** (what must be TRUE):
  1. User can reach keywords, positions, clusters, cannibalization, intent, and bulk operations via sidebar sub-items under «Позиции и ключи»
  2. When the user changes the selected site in the sticky site selector, content in this section reloads for the new site without a full page navigation
  3. User can upload Topvisor, Key Collector, and SF files from within this section
**Plans**: TBD
**UI hint**: yes

### Phase v4-05: Секция «Аналитика»
**Goal**: Analytics Workspace, Gap analysis, Architecture, Metrika, traffic analysis, and competitors pages are all accessible under the Аналитика sidebar section
**Depends on**: Phase v4-01
**Requirements**: AN-V4-01, AN-V4-02
**Success Criteria** (what must be TRUE):
  1. User can reach Analytics Workspace, Gap-анализ, Архитектура, Metrika, and Анализ трафика via sidebar sub-items under «Аналитика»
  2. User can reach Конкуренты as a sub-item under «Аналитика»
**Plans**: TBD
**UI hint**: yes

### Phase v4-06: Секция «Контент»
**Goal**: All content-related pages — audit, pipeline, publisher, projects, kanban, content plan, and change monitoring — are reachable through the Контент sidebar section
**Depends on**: Phase v4-01
**Requirements**: CNT-V4-01, CNT-V4-02, CNT-V4-03
**Success Criteria** (what must be TRUE):
  1. User can reach Content Audit, WP Pipeline, and DOCX Publisher via sidebar sub-items under «Контент»
  2. User can reach Проекты, Kanban, and Контент-план via sidebar sub-items under «Контент»
  3. User can reach Мониторинг изменений as a sub-item under «Контент»
**Plans**: TBD
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

### Phase v4-08: Visual Polish & Migration Completion
**Goal**: Dark mode is available site-wide, all 50+ pages have been confirmed in their new sections, existing URL patterns are preserved or redirected, and HTMX interactions are validated
**Depends on**: Phase v4-02, Phase v4-03, Phase v4-04, Phase v4-05, Phase v4-06, Phase v4-07
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
Phases execute in order: v4-01 → v4-02 → v4-03 → v4-04 → v4-05 → v4-06 → v4-07 → v4-08

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| v4-01. Navigation Foundation | 0/1 | Planned | - |
| v4-02. Секция «Обзор» | 0/TBD | Not started | - |
| v4-03. Секция «Сайты» | 0/TBD | Not started | - |
| v4-04. Секция «Позиции и ключи» | 0/TBD | Not started | - |
| v4-05. Секция «Аналитика» | 0/TBD | Not started | - |
| v4-06. Секция «Контент» | 0/TBD | Not started | - |
| v4-07. Секция «Настройки» | 0/TBD | Not started | - |
| v4-08. Visual Polish & Migration | 0/TBD | Not started | - |
