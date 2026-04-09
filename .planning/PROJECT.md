# SEO Management Platform

## What This Is

An internal SEO management platform for a team managing 20–100 WordPress sites for clients. It centralises keyword tracking, site crawling, content optimisation (TOC, schema.org, internal linking), SEO project management, and reporting — all in one self-hosted web application. Built for a solo developer + Claude workflow, deployed via Docker Compose on a single VPS.

## Core Value

A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.

## Current State (v3.0 in progress — 2026-04-09)

**v3.0 Client & Proposal — in progress:**
- Phase 20: CRM Core — client model, contact management, site↔client linking (complete)
- Phase 21: Site Audit Intake — structured intake form per site with 5-tab layout, section-save, auto-checklist, status badges on site list/detail (complete)
- Phase 22: Proposal Templates — admin-managed Jinja2 templates with CodeMirror editor, ~15 variable resolution, client/site preview, clone support (complete)

**v2.1 Onboarding & Project Health — shipped:** 4 phases, 13 plans, 143 commits, +25,090 LOC
- Phase 18: Project Health Widget — 7-step setup checklist on Site Overview, status signals from DB
- Phase 19: Empty States Everywhere — reusable Jinja2 macro across 17+ pages (core, analytics, content, tools)
- Phase 19.1 (INSERTED): UI Scenario Runner — YAML-based Playwright pytest plugin, CI docker-compose, 2 P0 scenarios
- Phase 19.2 (INSERTED): Interactive Tour Player — Shepherd.js IIFE overlay consuming scenario YAMLs, admin-only

**v2.0 SEO Insights & AI — shipped:** 7 phases, 24 plans, 147 commits, +92,913 LOC
- Phase 12: `normalize_url()` + `keyword_latest_positions` + Quick Wins + Dead Content
- Phase 13: Impact scoring + Growth Opportunities dashboard + Kanban drill-down
- Phase 14: Client Instructions PDF (subprocess-isolated WeasyPrint, 7 RU templates)
- Phase 15: Keyword Suggest (Yandex/Google + Wordstat opt-in, Redis cache)
- Phase 15.1 (INSERTED): UI Smoke Crawler — 74 routes under pytest gate
- Phase 16: GEO readiness scoring + Claude LLM Briefs (per-user key, circuit breaker)
- Phase 17: In-app Notifications (bell + dropdown + /notifications, HTMX 30s polling, D-02 guard)

**Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, PostgreSQL 16, Redis 7, Celery 5.4, Playwright, Jinja2 + HTMX 2.0, Tailwind CSS, Anthropic SDK (opt-in), WeasyPrint (subprocess)

**What's built:**
- JWT auth (3 roles), WP site management with Fernet-encrypted credentials
- Playwright crawler with snapshot diffs, change feed, auto-task on 404/noindex
- Keyword import (Topvisor/KC/SF), position tracking (monthly-partitioned), XMLProxy for Yandex
- SERP clustering, cannibalization detection, keyword-to-page mapping
- WP content pipeline (TOC, schema.org, internal links) with mandatory diff approval and rollback
- Kanban board, content plan, one-click WP draft, PDF briefs
- Dashboard, PDF/Excel reports, scheduled Telegram/SMTP delivery, ad traffic module
- Yandex Metrika, content audit, change monitoring, analytics workspace, gap analysis, site architecture, traffic analysis
- Sidebar UI with 6 sections, Tailwind CSS, smoke test agent
- Rate limiting, RBAC, invite links, health endpoint, Flower, HTTPS, full README
- Project health widget, empty states, UI scenario runner (Playwright YAML), interactive tour player (Shepherd.js)

**Known tech debt:**
- Dark mode (VIS-02) not implemented
- Formal migration audit (MIG-01/02/03) deferred
- Duplicate breadcrumbs in some templates (auto + custom)
- LLM API live verification deferred (backlog 999.6)

## Requirements

### Validated (v1.0)

- Docker Compose stack, JWT auth, 3 roles, audit logging
- WP site management with Fernet encryption
- Playwright crawler with snapshot diffs, change feed, auto-tasks
- Crawl scheduling via redbeat, survives Redis flush
- Keyword import (Topvisor/KC/SF/manual), GSC OAuth, DataForSEO, Yandex Webmaster
- Position tracking with monthly partitioning, Chart.js, filters, Telegram alerts
- XMLProxy integration for Yandex SERP
- Semantic clustering, cannibalization, keyword-page mapping
- WP content pipeline (TOC, schema, links), diff approval, rollback
- Projects, Kanban, content plan, one-click WP draft, PDF briefs
- Dashboard, PDF/Excel reports, scheduled delivery, ad traffic module
- Rate limiting, RBAC, invite links, health check, Flower, HTTPS, README
- Sidebar UI overhaul (6 sections), Tailwind CSS migration
- Yandex Metrika, content audit, change monitoring, analytics workspace
- Gap analysis, site architecture, bulk operations, intent detection, traffic analysis

### Validated (v2.1)

- Project health widget with 7-step setup checklist, status signals from existing DB state
- Reusable empty_state Jinja2 macro across all core, analytics, content, and tools pages
- YAML-based Playwright scenario runner (pytest plugin) with CI docker-compose overlay
- Shepherd.js interactive tour player consuming scenario YAMLs with admin-only trigger

### Active

(Defining requirements for v3.0 — see REQUIREMENTS.md)

### Out of Scope

| Feature | Reason |
|---------|--------|
| LLM content generation | Deterministic output preferred; can be added as opt-in later |
| Direct ad platform APIs (Google Ads, Yandex Direct, Facebook) | OAuth complexity; CSV upload covers 90% of use cases |
| SPA / React / Vue frontend | Jinja2 + HTMX chosen for simplicity |
| Mobile app | Web-first; mobile browser works for read-only views |
| Backlink crawling | Ahrefs/Majestic do this better |
| Real-time SERP polling | Scheduled checks are the right model at this scale |

## Context

- **Target sites:** 20–100 WordPress sites, all with WP REST API and Application Passwords
- **Users:** Small SEO team (admin + managers) + client stakeholders (read-only). Russian-speaking team, bilingual UI
- **Deployment:** Single VPS (Spain), Docker Compose. Timezone: Europe/Moscow for scheduled tasks
- **Developer:** Solo developer + Claude as co-pilot
- **External APIs:** GSC (OAuth), Yandex Webmaster (token), DataForSEO, XMLProxy.ru, WP REST API, Yoast/RankMath, Telegram Bot API, SMTP, Yandex Metrika

## Constraints

- **Tech Stack**: Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic, asyncpg, Celery 5 + Redis 7, Playwright 1.45+, Jinja2 + HTMX — fixed, no substitutions.
- **Database**: PostgreSQL 16 only; all schema changes via Alembic migrations.
- **Security**: Passwords bcrypt, WP credentials Fernet-encrypted, JWT exp=24h, HTTPS in production, rate limiting.
- **Celery**: retry=3 for all external API calls; one site failure must not stop others.
- **Performance**: UI pages < 3s; long operations always async via Celery.
- **Testing**: pytest + httpx AsyncClient; service layer coverage > 60%.
- **Logging**: loguru, JSON format, DEBUG/INFO/ERROR, 10 MB rotation, 30-day retention.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PostgreSQL from day 1 (not SQLite) | Async support, JSON columns, partitioning | Good |
| Celery + Redis over APScheduler | Multi-worker scalability | Good |
| Playwright over Selenium | Faster, async-native | Good |
| Jinja2 + HTMX over SPA | No frontend build toolchain; fits team size | Good |
| Monthly partitioning on keyword_positions | 18M rows/year without it = full table scans | Good |
| DataForSEO primary, Playwright SERP fallback | Cost vs ban risk balance | Good |
| XMLProxy for Yandex SERP | Reliable Yandex positions without bans | Good |
| redbeat for schedules | Survives Redis flush; UI-driven schedule changes | Good |
| WeasyPrint for PDF | Renders Jinja2 HTML to PDF; no headless Chrome needed | Good |
| Sidebar UI (v4.0) over top-nav | Progressive disclosure; scales to 50+ pages | Good |
| Tailwind CSS via CDN | Rapid prototyping; no build step | Revisit for production |
| Template-based briefs (no LLM) | Deterministic; LLM opt-in later | Good |
| Ad traffic = CSV upload only | API integrations deferred; covers 90% of needs | Good |
| Celery timezone Europe/Moscow | Server in Spain, team in Moscow | Good |

## Current Milestone: v3.0 Client & Proposal

**Goal:** Превратить платформу из инструмента мониторинга в инструмент продаж — карточки клиентов, аудит-анкеты, шаблоны КП и генератор документов.

**Target features:**
- Client CRM — карточки клиентов с контактами, привязанными сайтами, историей взаимодействий
- Site Audit Intake — аудит-анкеты для новых сайтов, структурированные чеклисты проверок
- Proposal Templates — шаблоны коммерческих предложений с переменными из данных платформы
- Document Generator — генерация КП/аудитов в PDF из шаблонов и агрегированных данных

## Evolution

This document evolves at phase transitions and milestone boundaries.

---
*Last updated: 2026-04-09 after Phase 21 (Site Audit Intake) completion*
