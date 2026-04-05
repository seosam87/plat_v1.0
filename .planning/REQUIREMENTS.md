# Requirements: SEO Management Platform

**Defined:** 2026-03-31
**Core Value:** A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.

## v4.0 Requirements — UI Overhaul

### Layout & Navigation Shell

- [x] **NAV-01**: Пользователь видит вертикальный sidebar с 6 секциями (Обзор, Сайты, Позиции и ключи, Аналитика, Контент, Настройки), каждая с иконкой и раскрываемыми подпунктами
- [x] **NAV-02**: Пользователь может выбрать сайт в sticky site selector (верх sidebar), и выбор сохраняется при переключении между разделами
- [x] **NAV-03**: Sidebar сворачивается до иконок на экранах < 1024px и появляется как overlay на мобильных (< 768px) по hamburger-кнопке
- [x] **NAV-04**: Пользователь видит breadcrumb trail (Секция > Сайт > Страница) на каждой странице для ориентации
- [x] **NAV-05**: Текущая секция и подпункт sidebar визуально выделены (active state)
- [x] **NAV-06**: base.html заменён на новый layout с sidebar вместо top nav; все существующие страницы наследуют новый layout без потери функциональности

### Секция «Обзор»

- [x] **OVR-01**: Пользователь видит агрегированную сводку позиций по всем сайтам (TOP-3/10/100, тренд вверх/вниз за неделю) на главной странице
- [x] **OVR-02**: Пользователь видит задачи на сегодня (overdue + in progress) из Kanban на главной странице
- [x] **OVR-03**: Обзор загружается < 3с и является landing page после логина

### Секция «Сайты»

- [x] **SITE-V4-01**: Пользователь может управлять сайтами через подпункты sidebar секции «Сайты»
- [x] **SITE-V4-02**: Пользователь видит историю краулов и расписания для выбранного сайта в этой секции
- [x] **SITE-V4-03**: Страница site detail убрана — её функции распределены между sidebar и соответствующими секциями

### Секция «Позиции и ключи»

- [x] **KW-V4-01**: Ключевые слова, позиции, кластеры, каннибализация, интент и массовые операции доступны через подпункты sidebar
- [x] **KW-V4-02**: Все страницы секции используют sticky site selector — при смене сайта контент перезагружается без перехода
- [x] **KW-V4-03**: Загрузка файлов (Topvisor, KC, SF) доступна из этой секции

### Секция «Аналитика»

- [x] **AN-V4-01**: Analytics Workspace, Gap-анализ, Архитектура, Metrika и Анализ трафика доступны через подпункты sidebar
- [x] **AN-V4-02**: Конкуренты доступны как подпункт «Аналитики»

### Секция «Контент»

- [x] **CNT-V4-01**: Content Audit, WP Pipeline, DOCX Publisher доступны через подпункты sidebar
- [x] **CNT-V4-02**: Проекты, Kanban и Контент-план доступны как подпункты секции «Контент»
- [x] **CNT-V4-03**: Мониторинг изменений доступен как подпункт секции «Контент»

### Секция «Настройки»

- [x] **CFG-V4-01**: Управление пользователями, группами, источниками данных, прокси, параметрами и журналом аудита через подпункты sidebar
- [x] **CFG-V4-02**: Секция «Настройки» видна только пользователям с ролью admin

### Визуальная консистентность

- [x] **VIS-01**: Все site-scoped страницы используют единый layout: sidebar + breadcrumb + content area
- [ ] **VIS-02**: Dark mode через toggle в sidebar footer, Tailwind dark: классы на всех страницах
- [x] **VIS-03**: Единая цветовая палитра (indigo primary, emerald success, red danger)

### UI Smoke Test Agent

- [x] **SMOKE-01**: Скрипт `python -m tests.smoke_test` авторизуется как admin и обходит все зарегистрированные UI маршруты
- [x] **SMOKE-02**: Для site-scoped маршрутов скрипт подставляет реальный site_id из БД
- [x] **SMOKE-03**: Отчёт содержит URL + HTTP-код для каждой страницы; 4xx/5xx помечены как ошибки, exit code 1
- [x] **SMOKE-04**: Скрипт можно запустить как Celery-задачу с отправкой результатов в Telegram

### Миграция страниц

- [ ] **MIG-01**: Все 50+ существующих UI-страниц перегруппированы по новой IA без потери функциональности
- [ ] **MIG-02**: Все существующие URL-паттерны сохранены или имеют 301 редирект
- [ ] **MIG-03**: HTMX-взаимодействия работают корректно после миграции на новый layout

---

## v1 Requirements

### Authentication & Access Control

- [ ] **AUTH-01**: User can log in with email and password and stay logged in across sessions (JWT, 24h expiry)
- [ ] **AUTH-02**: Admin can create, edit, and deactivate user accounts with roles (admin / manager / client)
- [ ] **AUTH-03**: Manager sees only their own projects; client sees only their assigned projects (403 on others)
- [ ] **AUTH-04**: Admin can generate invite links that register a new client account bound to a specific project
- [ ] **AUTH-05**: All user actions are logged to audit_log (entity type, entity id, action, user, timestamp)

### Site Management

- [x] **SITE-01**: Admin can add a WordPress site (name, URL, WP Application Password) and verify the connection
- [ ] **SITE-02**: Admin can remove or disable a site; associated jobs stop without crashing other sites
- [x] **SITE-03**: WP Application Passwords are stored Fernet-encrypted; never logged or exposed in responses
- [x] **SITE-04**: User can view connection status for all sites on a management page

### Crawler

- [ ] **CRAWL-01**: System can crawl a WordPress site with Playwright, collecting: URL, title, H1, meta description, HTTP status, page depth, incoming internal link count
- [ ] **CRAWL-02**: Crawler detects page type (category / article / landing / product) from URL patterns and content
- [ ] **CRAWL-03**: Crawler detects presence of TOC, schema.org markup, noindex, and internal links per page
- [ ] **CRAWL-04**: Each crawl saves a snapshot; system computes a diff vs. previous crawl (SEO fields + first 500 chars of content) stored as JSON in page_snapshots
- [ ] **CRAWL-05**: User can view a change feed filtered by: SEO fields changed / content changed / new pages / status changes
- [ ] **CRAWL-06**: Crawl schedule (daily / weekly / manual) is configurable from UI without application restart (using redbeat + PostgreSQL-backed schedule storage)
- [ ] **CRAWL-07**: System auto-creates a project task when a crawl finds a 404 or a page that lost indexation
- [ ] **CRAWL-08**: Crawler uses configurable delay between requests (CRAWLER_DELAY_MS env var) and respects a max-pages limit
- [ ] **CRAWL-09**: Sitemap.xml is parsed first to seed URL discovery before recursive crawling

### Keyword & Position Tracking

- [ ] **RANK-01**: User can import keywords from CSV (Key Collector format) and XLSX (Topvisor format) without errors for batches up to 500 keywords
- [ ] **RANK-02**: User can manually add individual keywords with frequency, region, and engine fields
- [ ] **RANK-03**: System integrates with Google Search Console via OAuth 2.0 to fetch positions, clicks, CTR, and impressions
- [ ] **RANK-04**: System integrates with Yandex Webmaster (API token) and/or DataForSEO (login/password) for position data
- [ ] **RANK-05**: DataForSEO is used as the primary SERP data source; Playwright-based parsing is the fallback for cost saving at low volume (<50 queries/day without proxy)
- [ ] **RANK-06**: Playwright SERP parser rotates User-Agent strings and uses configurable delays to reduce ban risk
- [ ] **RANK-07**: Position history is stored in keyword_positions with monthly range partitioning on checked_at (must be set in Iteration 3 migration — not retrofittable)
- [ ] **RANK-08**: Position table UI shows keyword, current position, delta vs. previous check (arrow + colour), URL, engine, geo, device
- [ ] **RANK-09**: User can view a 90-day position history chart per keyword (Chart.js)
- [ ] **RANK-10**: User can filter positions by: top-3 / top-10 / top-100, engine, region, cluster
- [ ] **RANK-11**: System sends a Telegram alert when a keyword drops by a configurable threshold (e.g. −5 positions)
- [ ] **RANK-12**: Position checks run on a configurable Celery Beat schedule (daily / weekly / manual)
- [ ] **RANK-13**: Keyword volume data is sourced from DataForSEO Keywords Data endpoint (for brief generation estimates)

### Semantics & Clustering

- [ ] **SEM-01**: User can cluster keywords manually (drag-and-drop into named clusters)
- [ ] **SEM-02**: System can auto-cluster keywords by SERP intersection (keywords sharing ≥N results in top-10)
- [ ] **SEM-03**: User can map a keyword (or cluster) to a page URL
- [ ] **SEM-04**: System detects cannibalization: keywords mapped to 2+ pages both ranking in top-100
- [ ] **SEM-05**: User can export the full keyword list with clusters and page mappings to CSV
- [ ] **SEM-06**: System detects keywords with no mapped page and auto-creates a "missing page" task in the project

### WordPress Content Pipeline

- [ ] **WPC-01**: User can fetch the list of pages/posts for a site from WP REST API with filters: status, type, TOC present, schema.org present
- [ ] **WPC-02**: System identifies pages missing TOC and/or schema.org Article markup
- [ ] **WPC-03**: Celery processes each page: download full HTML via Playwright, detect H2–H3 structure, generate TOC as HTML block, inject JSON-LD schema.org Article (headline, datePublished, author)
- [ ] **WPC-04**: System finds relevant internal pages from DB by keyword overlap and inserts a link block into the page content
- [ ] **WPC-05**: System updates SEO title and meta description via Yoast/RankMath post_meta through WP REST API
- [ ] **WPC-06**: A diff view (before/after, changed blocks only) is shown and must be approved before content is pushed to WP
- [ ] **WPC-07**: User can trigger batch processing for all pages in a category; batches run without blocking the UI
- [ ] **WPC-08**: Every WP content job is stored in wp_content_jobs with status, diff_json, processed_at; user can view history and roll back to previous content
- [ ] **WPC-09**: User can create a new WP post from the platform (title, content, keywords, publish date)

### SEO Projects & Tasks

- [ ] **PROJ-01**: User can create a project linked to a site and a client; project has name, description, status
- [ ] **PROJ-02**: User can view and manage tasks on a Kanban board (To Do / In Progress / Done) with drag-and-drop status changes
- [ ] **PROJ-03**: System auto-creates tasks for: missing pages, cannibalized pages, pages without schema.org; tasks include context (keyword, URL, issue type)
- [ ] **PROJ-04**: User can manually create, edit, assign, and set due dates for tasks
- [ ] **PROJ-05**: Content plan rows link keyword → proposed title → status → planned date → WP post (once published)
- [ ] **PROJ-06**: User can create a WP draft post from a content plan row in one click
- [ ] **PROJ-07**: User can generate a page brief from a keyword cluster: H1–H3 structure, target keywords, volume estimate (template-based, no LLM)
- [ ] **PROJ-08**: Brief is downloadable as HTML and PDF (WeasyPrint); brief can be linked to a task or content plan row

### Dashboard & Reporting

- [x] **DASH-01**: Dashboard shows across all projects: top positions, tasks in progress, recent site changes; loads in <3s with 50 active projects
- [x] **DASH-02**: Manager/admin can generate a project report (position trends + task progress + site changes) as PDF and Excel
- [x] **DASH-03**: Reports can be scheduled for automatic delivery via Telegram and/or SMTP (Celery Beat)
- [x] **DASH-04**: Morning Telegram digest summarising project status is optionally configurable

### Advertising Traffic

- [x] **ADS-01**: User can upload ad traffic data as CSV (source, date, sessions, conversions, cost)
- [x] **ADS-02**: User can compare two periods (before / after): table with % and absolute delta for sessions, conversions, CR%, cost-per-conversion
- [x] **ADS-03**: User can view a weekly/monthly traffic trend chart per source

### Infrastructure & Operations

- [x] **INFRA-01**: `docker-compose up --build` starts the full stack (FastAPI + PostgreSQL + Redis + Celery Worker + Celery Beat) from scratch with no manual steps
- [ ] **INFRA-02**: `GET /health` returns 200 with status of DB, Redis, and Celery; returns 503 if any component is down
- [ ] **INFRA-03**: Rate limiting (slowapi) protects all API endpoints from overload
- [ ] **INFRA-04**: Celery Flower or equivalent UI shows task queue status
- [ ] **INFRA-05**: Logs use loguru in JSON format, DEBUG/INFO/ERROR levels, 10 MB rotation, 30-day retention
- [x] **INFRA-06**: All DB schema changes are managed through Alembic migrations; no direct schema edits in production
- [x] **INFRA-07**: Number of Celery workers is configurable in docker-compose without code changes
- [ ] **INFRA-08**: Celery Beat schedule is persisted in PostgreSQL via redbeat (not local file; survives Redis flush and Docker restart)
- [ ] **INFRA-09**: `WORKER_MAX_TASKS_PER_CHILD` is set to 50–100 for Playwright workers to prevent browser process memory leaks
- [ ] **INFRA-10**: README covers deployment from zero to running in <30 minutes

### Security

- [ ] **SEC-01**: Passwords are hashed with bcrypt; plaintext passwords never stored or logged
- [x] **SEC-02**: WP Application Passwords are Fernet-encrypted at rest; decrypted only at call time, never logged
- [ ] **SEC-03**: JWT tokens expire after 24h; refresh requires re-authentication
- [ ] **SEC-04**: Role checks are enforced at both route level and service layer (not route-only)
- [ ] **SEC-05**: HTTPS is enforced in production (Nginx/Caddy reverse proxy in docker-compose)

## v2 Requirements

### Extended Integrations

- **INT-01**: GSC URL Inspection API — detect pages de-indexed in GSC without a noindex tag
- **INT-02**: Direct integration with Google Ads API for ad traffic (currently CSV-only)
- **INT-03**: Direct integration with Yandex Direct API for ad traffic
- **INT-04**: Facebook Ads API integration for ad traffic

### Semantics

- **SEM-V2-01**: Keyword suggest via Google/Yandex (Playwright or API) to expand semantics
- **SEM-V2-02**: Yandex Wordstat frequency data via API or Key Collector import

### Content

- **CONT-V2-01**: LLM-assisted brief generation (optional feature flag; template-based is default)
- **CONT-V2-02**: Scheduled content plan reminders (email/Telegram when planned date approaches)

### Platform

- **PLAT-V2-01**: White-label branding (custom logo, colours per client view)
- **PLAT-V2-02**: Two-factor authentication (TOTP)
- **PLAT-V2-03**: In-app notification feed (in addition to Telegram/email)

## Out of Scope

| Feature | Reason |
|---------|--------|
| LLM content generation | Deterministic output preferred; adds API cost and non-determinism. Can be added as opt-in flag later without rearchitecting. |
| Real-time SERP polling | Operationally unsustainable; scheduled checks are the right model at this scale |
| Backlink crawling / index | Requires own crawler infrastructure; Ahrefs/Majestic do this better |
| SPA / React / Vue frontend | Jinja2 + HTMX eliminates build toolchain; no heavy SPA needed |
| Mobile app | Web-first; mobile browser works fine for read-only client views |
| Competitor keyword gap analysis | Requires own SERP index; anti-feature at this scope |
| Direct ad platform APIs (v1) | OAuth complexity; CSV upload covers 90% of use cases with zero maintenance |
| Multi-locale SERP expansion | Out of initial scope; can be added to DataForSEO calls later |
| Penalty detection | Too many false positives; out of scope |
| SQLite | Not async-native; PostgreSQL from day one |
| APScheduler | Celery + Redis is the correct scheduler for multi-worker setup |
| Selenium | Playwright is faster, async-native, better headless support |

## Traceability

### v4.0 Requirements

| Requirement | Phase | Status |
|-------------|-------|--------|
| NAV-01 | Phase v4-01: Navigation Foundation | Complete |
| NAV-02 | Phase v4-01: Navigation Foundation | Complete |
| NAV-03 | Phase v4-01: Navigation Foundation | Complete |
| NAV-04 | Phase v4-01: Navigation Foundation | Complete |
| NAV-05 | Phase v4-01: Navigation Foundation | Complete |
| NAV-06 | Phase v4-01: Navigation Foundation | Complete |
| OVR-01 | Phase v4-02: Секция «Обзор» | Complete |
| OVR-02 | Phase v4-02: Секция «Обзор» | Complete |
| OVR-03 | Phase v4-02: Секция «Обзор» | Complete |
| SITE-V4-01 | Phase v4-03: Секция «Сайты» | Complete |
| SITE-V4-02 | Phase v4-09: Fix Runtime Route Gaps | Complete |
| SITE-V4-03 | Phase v4-09: Fix Runtime Route Gaps | Complete |
| KW-V4-01 | Phase v4-04: Секция «Позиции и ключи» | Complete |
| KW-V4-02 | Phase v4-04: Секция «Позиции и ключи» | Complete |
| KW-V4-03 | Phase v4-04: Секция «Позиции и ключи» | Complete |
| AN-V4-01 | Phase v4-05: Секция «Аналитика» | Complete |
| AN-V4-02 | Phase v4-05: Секция «Аналитика» | Complete |
| CNT-V4-01 | Phase v4-06: Секция «Контент» | Complete |
| CNT-V4-02 | Phase v4-06: Секция «Контент» | Complete |
| CNT-V4-03 | Phase v4-06: Секция «Контент» | Complete |
| CFG-V4-01 | Phase v4-07: Секция «Настройки» | Complete |
| CFG-V4-02 | Phase v4-07: Секция «Настройки» | Complete |
| VIS-01 | Phase v4-01: Navigation Foundation | Complete |
| VIS-02 | Phase v4-08: Visual Polish & Migration | Pending |
| VIS-03 | Phase v4-01: Navigation Foundation | Complete |
| MIG-01 | Phase v4-08: Visual Polish & Migration | Pending |
| MIG-02 | Phase v4-08: Visual Polish & Migration | Pending |
| MIG-03 | Phase v4-08: Visual Polish & Migration | Pending |

**Coverage (v4.0):**
- v4.0 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓

### v1 Requirements

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1: Stack & Auth | Pending |
| AUTH-02 | Phase 1: Stack & Auth | Pending |
| AUTH-03 | Phase 11: Hardening | Pending |
| AUTH-04 | Phase 11: Hardening | Pending |
| AUTH-05 | Phase 1: Stack & Auth | Pending |
| SITE-01 | Phase 2: Site Management | Complete |
| SITE-02 | Phase 2: Site Management | Pending |
| SITE-03 | Phase 2: Site Management | Complete |
| SITE-04 | Phase 2: Site Management | Complete |
| CRAWL-01 | Phase 3: Crawler Core | Pending |
| CRAWL-02 | Phase 3: Crawler Core | Pending |
| CRAWL-03 | Phase 3: Crawler Core | Pending |
| CRAWL-04 | Phase 3: Crawler Core | Pending |
| CRAWL-05 | Phase 3: Crawler Core | Pending |
| CRAWL-06 | Phase 4: Crawl Scheduling | Pending |
| CRAWL-07 | Phase 4: Crawl Scheduling | Pending |
| CRAWL-08 | Phase 3: Crawler Core | Pending |
| CRAWL-09 | Phase 3: Crawler Core | Pending |
| RANK-01 | Phase 5: Keyword Import | Pending |
| RANK-02 | Phase 5: Keyword Import | Pending |
| RANK-03 | Phase 5: Keyword Import | Pending |
| RANK-04 | Phase 5: Keyword Import | Pending |
| RANK-05 | Phase 5: Keyword Import | Pending |
| RANK-06 | Phase 5: Keyword Import | Pending |
| RANK-07 | Phase 6: Position Tracking | Pending |
| RANK-08 | Phase 6: Position Tracking | Pending |
| RANK-09 | Phase 6: Position Tracking | Pending |
| RANK-10 | Phase 6: Position Tracking | Pending |
| RANK-11 | Phase 6: Position Tracking | Pending |
| RANK-12 | Phase 5: Keyword Import | Pending |
| RANK-13 | Phase 5: Keyword Import | Pending |
| SEM-01 | Phase 7: Semantics | Pending |
| SEM-02 | Phase 7: Semantics | Pending |
| SEM-03 | Phase 7: Semantics | Pending |
| SEM-04 | Phase 7: Semantics | Pending |
| SEM-05 | Phase 7: Semantics | Pending |
| SEM-06 | Phase 7: Semantics | Pending |
| WPC-01 | Phase 8: WP Pipeline | Pending |
| WPC-02 | Phase 8: WP Pipeline | Pending |
| WPC-03 | Phase 8: WP Pipeline | Pending |
| WPC-04 | Phase 8: WP Pipeline | Pending |
| WPC-05 | Phase 8: WP Pipeline | Pending |
| WPC-06 | Phase 8: WP Pipeline | Pending |
| WPC-07 | Phase 8: WP Pipeline | Pending |
| WPC-08 | Phase 8: WP Pipeline | Pending |
| WPC-09 | Phase 8: WP Pipeline | Pending |
| PROJ-01 | Phase 9: Projects & Tasks | Pending |
| PROJ-02 | Phase 9: Projects & Tasks | Pending |
| PROJ-03 | Phase 9: Projects & Tasks | Pending |
| PROJ-04 | Phase 9: Projects & Tasks | Pending |
| PROJ-05 | Phase 9: Projects & Tasks | Pending |
| PROJ-06 | Phase 9: Projects & Tasks | Pending |
| PROJ-07 | Phase 9: Projects & Tasks | Pending |
| PROJ-08 | Phase 9: Projects & Tasks | Pending |
| DASH-01 | Phase 10: Reports & Ads | Complete |
| DASH-02 | Phase 10: Reports & Ads | Complete |
| DASH-03 | Phase 10: Reports & Ads | Complete |
| DASH-04 | Phase 10: Reports & Ads | Complete |
| ADS-01 | Phase 10: Reports & Ads | Complete |
| ADS-02 | Phase 10: Reports & Ads | Complete |
| ADS-03 | Phase 10: Reports & Ads | Complete |
| INFRA-01 | Phase 1: Stack & Auth | Complete |
| INFRA-02 | Phase 11: Hardening | Pending |
| INFRA-03 | Phase 11: Hardening | Pending |
| INFRA-04 | Phase 11: Hardening | Pending |
| INFRA-05 | Phase 1: Stack & Auth | Pending |
| INFRA-06 | Phase 1: Stack & Auth | Complete |
| INFRA-07 | Phase 1: Stack & Auth | Complete |
| INFRA-08 | Phase 4: Crawl Scheduling | Pending |
| INFRA-09 | Phase 3: Crawler Core | Pending |
| INFRA-10 | Phase 11: Hardening | Pending |
| SEC-01 | Phase 1: Stack & Auth | Pending |
| SEC-02 | Phase 2: Site Management | Complete |
| SEC-03 | Phase 1: Stack & Auth | Pending |
| SEC-04 | Phase 1: Stack & Auth | Pending |
| SEC-05 | Phase 11: Hardening | Pending |

**Coverage (v1):**
- v1 requirements: 60 total
- Mapped to phases: 60
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-31*
*Last updated: 2026-04-03 — v4.0 traceability added*
