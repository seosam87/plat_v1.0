# SEO Management Platform

## What This Is

An internal SEO management platform for a team managing 20–100 WordPress sites for clients. It centralises keyword tracking, site crawling, content optimisation (TOC, schema.org, internal linking), SEO project management, and reporting — all in one self-hosted web application. Built for a solo developer + Claude workflow, deployed via Docker Compose on a single VPS.

## Core Value

A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Infrastructure & Auth (Iteration 1)**
- [ ] Docker Compose stack: FastAPI + PostgreSQL + Redis + Celery Worker + Celery Beat, starts from scratch with `docker-compose up --build`
- [ ] JWT authentication with three roles: admin (full access), manager (own projects), client (read-only own projects)
- [ ] WordPress site management: add/remove/verify connection via WP REST API with Application Password
- [ ] WP credentials stored encrypted with Fernet
- [ ] Basic CRUD for WP posts/pages via WP REST API
- [ ] All user actions logged to `audit_log`

**Crawler & Change History (Iteration 2)**
- [ ] Playwright-based site crawler: URL, title, H1, meta description, HTTP status, depth, internal link count
- [ ] Page type detection: category / article / landing / product
- [ ] Detect: TOC presence, schema.org presence, noindex
- [ ] Page snapshots with diff vs. previous crawl (stored as JSON)
- [ ] Change feed UI with filters (SEO fields / content / new pages)
- [ ] Celery Beat crawl schedule configurable from UI (no restart required)
- [ ] Auto-create task on 404 or lost indexation

**Semantics & Positions (Iteration 3)**
- [ ] Keyword import: CSV (Key Collector format), XLSX (Topvisor format), manual entry
- [ ] Google Search Console integration via OAuth 2.0
- [ ] Yandex Webmaster and/or DataForSEO integration (token/credentials from .env)
- [ ] Playwright SERP parser: top-100 for Google + Yandex, User-Agent rotation, request delays
- [ ] Position history in `keyword_positions` (geo, device, engine)
- [ ] Positions table UI: filters, delta arrows, colour indicators, Chart.js 90-day history per keyword
- [ ] Manual + auto clustering (SERP intersection)
- [ ] Keyword → page mapping; cannibalization detection
- [ ] Missing page detection → auto-create project task
- [ ] Telegram alerts on position drop (configurable threshold)

**WP Content Pipeline (Iteration 4)**
- [ ] Fetch WP page list; detect pages missing TOC / schema.org
- [ ] Celery pipeline per page: download HTML via Playwright → process → prepare update
- [ ] Generate TOC from H2–H3 headings as HTML block
- [ ] Inject JSON-LD schema.org Article (headline, datePublished, author)
- [ ] Auto internal linking: find relevant pages from DB by keywords → insert link block
- [ ] Update SEO fields via Yoast/RankMath REST API (post_meta)
- [ ] Diff preview (before/after) mandatory before pushing to WP
- [ ] Batch processing by category; history of all jobs with rollback option

**Projects, Tasks, Content Plan (Iteration 5)**
- [ ] SEO project: site + client + semantics + content plan + tasks
- [ ] Kanban board (To Do / In Progress / Done) with drag-and-drop
- [ ] Auto-create tasks from: missing pages, cannibalization, pages without schema.org
- [ ] Content plan: keyword → title → status → date → WP post link
- [ ] One-click draft creation in WP from content plan row
- [ ] Page brief generation (template-based, no LLM): H1–H3 structure + target keywords + volume estimate
- [ ] Brief downloadable as HTML/PDF; linkable to task or content plan row

**Reports & Ad Traffic (Iteration 6)**
- [ ] Dashboard: top positions, tasks in progress, recent site changes across all projects; loads < 3s at 50 projects
- [ ] Project report: position trends + task progress + site changes → PDF + Excel download
- [ ] Scheduled report delivery via Celery Beat → Telegram / SMTP
- [ ] Ad traffic module: CSV upload (source, date, sessions, conversions, cost)
- [ ] Period comparison (before/after): metrics table with % and absolute delta
- [ ] Weekly/monthly traffic trend chart

**Client Access & Hardening (Iteration 7)**
- [ ] Role enforcement: admin sees all, manager sees own projects, client read-only own projects (403 on others)
- [ ] Invite links: generate URL → client registers → auto-bound to project
- [ ] Rate limiting on API (slowapi)
- [ ] Celery Flower or basic task queue UI
- [ ] `GET /health` endpoint: DB + Redis + Celery status
- [ ] Structured JSON logging (loguru), rotation 10 MB / 30 days
- [ ] OpenAPI docs auto-generated at `/docs`
- [ ] README: deploy from zero in < 30 min

### Out of Scope

- **LLM-generated content** — explicitly deferred; brief generation is template-based only. LLM can be added as an option in a later phase.
- **Direct ad platform API integrations** (Google Ads, Yandex Direct, Facebook API) — ad data is upload-only (CSV). API integrations add auth complexity and are not in scope.
- **SPA / React / Vue frontend** — Jinja2 + HTMX chosen for simplicity; no heavy client-side framework.
- **SQLite** — PostgreSQL from iteration 1 (scalability, proper async support).
- **APScheduler** — Celery + Redis chosen over APScheduler for multi-worker scalability.
- **Selenium** — Playwright chosen; no Selenium.
- **Mobile app** — web-only.

## Context

- **Target sites:** 20–100 WordPress sites, all with WP REST API enabled and Application Passwords.
- **Users:** Small SEO team (admin + managers) + client stakeholders (read-only). Bilingual UI: Russian primary, English in code/templates.
- **Deployment:** Single VPS, Docker Compose. No Kubernetes, no managed cloud services.
- **Developer:** Solo developer + Claude as co-pilot. Quality over speed — months timeline, no hard deadline.
- **External APIs used:** Google Search Console (OAuth), Yandex Webmaster (token), DataForSEO (login/password), WP REST API, Yoast/RankMath post_meta, Telegram Bot API, SMTP.
- **Parsing sensitivity:** SERP parsing via Playwright must use User-Agent rotation and delays to avoid bans. DataForSEO is the safe fallback.
- **No existing codebase** — greenfield from iteration 1.

## Constraints

- **Tech Stack**: Python 3.12, FastAPI 0.111+, SQLAlchemy 2.0 async, Alembic, asyncpg, Celery 5 + Redis 7, Playwright 1.45+, Jinja2 + HTMX — fixed, no substitutions.
- **Database**: PostgreSQL 16 only; all schema changes via Alembic migrations, no direct schema edits in production.
- **Security**: Passwords bcrypt, WP credentials Fernet-encrypted, JWT exp=24h, HTTPS in production, rate limiting (slowapi) from iteration 7.
- **Celery**: retry=3 for all external API calls; one site failure must not stop processing of others.
- **Performance**: UI pages < 3s; long operations (position checks, crawling) are always async via Celery — UI never blocks.
- **Testing**: pytest + httpx AsyncClient; service layer coverage > 60% by iteration 4.
- **Logging**: loguru, JSON format, DEBUG/INFO/ERROR levels, 10 MB rotation, 30-day retention.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PostgreSQL from iteration 1 (not SQLite) | Async support, proper JSON columns, migration-friendly; SQLite would require a painful migration later | — Pending |
| Celery + Redis over APScheduler | Multi-worker scalability; APScheduler doesn't scale horizontally | — Pending |
| Playwright over Selenium | Faster, async-native, better headless support | — Pending |
| Jinja2 + HTMX over SPA | Eliminates frontend build toolchain; server-side rendering fits team size and complexity | — Pending |
| WP pipeline = download→process→upload (not just CRUD) | Core value is content enrichment (TOC, schema, links), not just post management | — Pending |
| Ad traffic = CSV upload only (no API) | API integrations add OAuth complexity; upload covers 90% of use cases with zero maintenance | — Pending |
| Template-based brief generation (no LLM) | Deterministic output; LLM can be added later as opt-in without rearchitecting | — Pending |
| Bilingual UI (RU primary, EN in code) | Team is Russian-speaking; English code keeps codebase readable for Claude collaboration | — Pending |
| Self-hosted VPS + Docker Compose | Cost, control, no cloud vendor lock-in; fits 20–100 sites load easily | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-31 after initial project questioning*
