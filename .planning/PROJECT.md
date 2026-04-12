# SEO Management Platform

## What This Is

An internal SEO management platform for a team managing 20–100 WordPress sites for clients. It centralises keyword tracking, site crawling, content optimisation (TOC, schema.org, internal linking), SEO project management, and reporting — all in one self-hosted web application. Built for a solo developer + Claude workflow, deployed via Docker Compose on a single VPS.

## Core Value

A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.

## Current State (v4.0 shipped — 2026-04-12)

**6 milestones shipped, 54 phases, 138 plans.**

**v4.0 Mobile & Telegram — shipped 2026-04-12:**
- Phase 26: Mobile Foundation — base_mobile.html, /m/ routing, Telegram WebApp HMAC auth, PWA manifest
- Phase 27: Digest & Site Health — утренний дайджест (4 блока) + карточка здоровья (6 метрик, 2 действия)
- Phase 28: Positions & Traffic — проверка позиций с HTMX-поллингом + сравнение трафика Метрики
- Phase 29: Reports & Tools — PDF-отчёты с доставкой в TG/email + 6 SEO-инструментов с телефона
- Phase 30: Errors & Quick Task — ошибки Yandex Webmaster + быстрые задачи и ТЗ копирайтеру
- Phase 31: Pages App — approve queue, quick fix (TOC/Schema → WP), bulk operations
- Phase 32: Telegram Bot — отдельный Docker-сервис (PTB 21, webhook), DevOps+SEO команды, Mini App
- Phase 33: Claude Code Agent (Spike) — /task → Claude CLI → diff → approve/reject. Untested (ANTHROPIC_API_KEY)
- Phase 33.1: Integration wiring — 6 gap fixes (routes, templates, toast, digest links)

**v3.1 SEO Tools — shipped 2026-04-10:**
- Phase 24: Tools Infrastructure — shared TOOL_REGISTRY, Job-архитектура, 3 быстрых инструмента (коммерциализация, мета-теги, релевантный URL)
- Phase 25: SERP Aggregation Tools — копирайтерский бриф (TOP-10 + Playwright), PAA парсер (XMLProxy + BS4), пакетный Wordstat (до 1000 фраз, OAuth)

**v3.0 Client & Proposal — shipped 2026-04-10:**
- Phase 20: Client CRM — карточки клиентов, контакты, привязка сайтов, история взаимодействий
- Phase 21: Site Audit Intake — 5-tab аудит-анкета, импорт XLSX/CSV, авто-чеклист
- Phase 22: Proposal Templates — Jinja2 шаблоны КП, CodeMirror редактор, ~15 переменных
- Phase 23: Document Generator — PDF/DOCX генерация, версионирование, Telegram/SMTP отправка

**v2.1 Onboarding & Project Health — shipped 2026-04-10:**
- Project health widget, empty states, YAML scenario runner, interactive tour player

**v2.0 SEO Insights & AI — shipped 2026-04-08:**
- Analytical foundations, impact scoring, client instructions PDF, keyword suggest, UI smoke crawler, GEO/LLM briefs, in-app notifications

**v1.0 MVP — shipped 2026-04-06:**
- Full stack, auth, crawler, keywords, positions, semantics, WP pipeline, projects, reports, hardening, analytics, UI overhaul

**Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, PostgreSQL 16, Redis 7, Celery 5.4, Playwright, Jinja2 + HTMX 2.0, Tailwind CSS, Anthropic SDK (opt-in), WeasyPrint (subprocess)

**Known tech debt:**
- Dark mode (VIS-02) not implemented
- Formal migration audit (MIG-01/02/03) deferred
- LLM API live verification deferred (backlog 999.6)
- Deployment sync (backlog 999.5) — no automated git→production sync
- Claude Code Agent spike untested (Phase 33 — requires ANTHROPIC_API_KEY)
- Playbook Builder UAT incomplete (Phase 999.8 — 16 human_needed items)

## Requirements

### Validated (v1.0–v3.1)

- Docker Compose stack, JWT auth, 3 roles, audit logging
- WP site management with Fernet encryption, Playwright crawler, change feed
- Keyword import, position tracking, XMLProxy, semantic clustering
- WP content pipeline, projects/Kanban, PDF/Excel reports, scheduled delivery
- Yandex Metrika, content audit, change monitoring, analytics workspace, gap analysis
- Rate limiting, RBAC, health check, Flower, HTTPS
- Project health widget, empty states, scenario runner, tour player
- Client CRM, site audit intake, proposal templates, document generator
- SEO tools: commercialization, meta parser, relevant URL, brief, PAA, batch wordstat

### Active

(Defining requirements for v4.0 — see REQUIREMENTS.md)

### Out of Scope

| Feature | Reason |
|---------|--------|
| Direct ad platform APIs | OAuth complexity; CSV upload covers 90% |
| SPA / React / Vue frontend | Jinja2 + HTMX chosen for simplicity |
| Backlink crawling | Ahrefs/Majestic do this better |
| Real-time SERP polling | Scheduled checks sufficient at this scale |

## Context

- **Target sites:** 20–100 WordPress sites, all with WP REST API and Application Passwords
- **Users:** Small SEO team (admin + managers) + client stakeholders (read-only). Russian-speaking team
- **Deployment:** Single VPS (Spain), Docker Compose. Timezone: Europe/Moscow
- **Developer:** Solo developer + Claude as co-pilot
- **External APIs:** GSC (OAuth), Yandex Webmaster (token), DataForSEO, XMLProxy.ru, WP REST API, Yoast/RankMath, Telegram Bot API, SMTP, Yandex Metrika, Anthropic (opt-in)

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
| XMLProxy for Yandex SERP | Reliable Yandex positions without bans | Good |
| redbeat for schedules | Survives Redis flush; UI-driven schedule changes | Good |
| WeasyPrint for PDF (subprocess) | Memory leak isolation; renders Jinja2 HTML | Good |
| Sidebar UI (v4.0) over top-nav | Progressive disclosure; scales to 50+ pages | Revisit — UI overload reported |
| Tailwind CSS via CDN | Rapid prototyping; no build step | Revisit for production |
| TOOL_REGISTRY dispatch pattern | Unified Job model → reusable router/templates | Good |
| Per-tool template dirs (Phase 25) | Cleaner than slug-conditional shared templates | Good |

## Current Milestone: v4.0 Mobile & Telegram

**Goal:** Мобильные фокус-приложения + Telegram-бот — упрощённые точки входа в платформу с возможностью не только просматривать, но и действовать (quick fix, approve, ТЗ, отправка).

**Completed:**
- Phase 26 (Mobile Foundation): `base_mobile.html` с bottom nav, `/m/` router, Telegram WebApp auth (HMAC-SHA256), PWA manifest + service worker

**Target features:**
- Mobile foundation: `base_mobile.html`, роутинг `/m/`, Telegram WebApp обёртка
- 8 фокус-приложений: Дайджест, Позиции, Отчёт клиенту, Здоровье сайта, Трафик, Страницы (approve queue + quick fix), Быстрая задача, Инструменты
- Telegram Bot: бот-командир (/deploy, /test, /logs, /status) + Claude Code агент

## Evolution

This document evolves at phase transitions and milestone boundaries.

---
*Last updated: 2026-04-12 after Phase 31 (Pages App — approve queue, quick fix, bulk operations) complete*
