# Roadmap: SEO Management Platform

## Milestones

- **v1.0 MVP** — 16 phases (shipped 2026-04-06) — [details](milestones/v1.0-ROADMAP.md)
- **v2.0 SEO Insights & AI** — 7 phases (shipped 2026-04-08) — [details](milestones/v2.0-ROADMAP.md)
- **v2.1 Onboarding & Project Health** — 4 phases (shipped 2026-04-10) — [details](milestones/v2.1-ROADMAP.md)
- **v3.0 Client & Proposal** — 4 phases (shipped 2026-04-10) — [details](milestones/v3.0-ROADMAP.md)
- **v3.1 SEO Tools** — 2 phases (shipped 2026-04-10) — [details](milestones/v3.1-ROADMAP.md)
- **v4.0 Mobile & Telegram** — 9 phases (shipped 2026-04-12) — [details](milestones/v4.0-ROADMAP.md)

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

v3.x analytics phases and v4.x UI overhaul phases also completed within v1.0.

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

</details>

<details>
<summary>v2.1 Onboarding & Project Health (4 phases) — SHIPPED 2026-04-10</summary>

- [x] Phase 18: Project Health Widget (1 plan)
- [x] Phase 19: Empty States Everywhere (3 plans)
- [x] Phase 19.1: UI Scenario Runner — Playwright (5 plans)
- [x] Phase 19.2: Interactive Tour Player (4 plans)

</details>

<details>
<summary>v3.0 Client & Proposal (4 phases) — SHIPPED 2026-04-10</summary>

- [x] Phase 20: Client CRM (4 plans)
- [x] Phase 21: Site Audit Intake (3 plans)
- [x] Phase 22: Proposal Templates & Tariffs (3 plans)
- [x] Phase 23: Document Generator (3 plans)

</details>

<details>
<summary>v3.1 SEO Tools (2 phases) — SHIPPED 2026-04-10</summary>

- [x] Phase 24: Tools Infrastructure & Fast Tools (5 plans)
- [x] Phase 25: SERP Aggregation Tools (5 plans)

</details>

<details>
<summary>v4.0 Mobile & Telegram (9 phases) — SHIPPED 2026-04-12</summary>

- [x] Phase 26: Mobile Foundation (3 plans)
- [x] Phase 27: Digest & Site Health (2 plans)
- [x] Phase 28: Positions & Traffic (2 plans)
- [x] Phase 29: Reports & Tools (3 plans)
- [x] Phase 30: Errors & Quick Task (3 plans)
- [x] Phase 31: Pages App (3 plans)
- [x] Phase 32: Telegram Bot (3 plans)
- [x] Phase 33: Claude Code Agent Spike (2 plans)
- [x] Phase 33.1: Fix Mobile Integration Wiring — INSERTED (1 plan)

</details>

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1–11 + v3.x + v4.x | v1.0 | 56/56 | Complete | 2026-04-06 |
| 12–17 + 15.1 | v2.0 | 24/24 | Complete | 2026-04-08 |
| 18–19.2 | v2.1 | 13/13 | Complete | 2026-04-10 |
| 20–23 | v3.0 | 13/13 | Complete | 2026-04-10 |
| 24–25 | v3.1 | 10/10 | Complete | 2026-04-10 |
| 26–33.1 | v4.0 | 22/22 | Complete | 2026-04-12 |

**Total: 54 phases shipped across 6 milestones, 138 plans**

## Backlog

### Phase 999.3: Smart Route Discovery (response_class filter) (BACKLOG — COMPLETE)

Extends `discover_routes` to auto-filter by `response_class=HTMLResponse`. 2/2 plans complete.

### Phase 999.5: Repo ↔ Deployment Sync Strategy (BACKLOG)

Two deployment-drift incidents caught — no automated sync between git repo and running deployment. Context gathered, no plans yet.

### Phase 999.6: LLM API Integration & Live Verification (BACKLOG)

Complete human-verify checkpoint deferred from Phase 16-04. Requires real Anthropic API key for live testing.

### Phase 999.7: Remove server log from mobile UI (BACKLOG)

**Goal:** Убрать или настроить server log в мобильном интерфейсе — виден в Telegram Mini App, бесполезен для пользователя. Проверить base_mobile.html, digest.html и все /m/ шаблоны на предмет отладочных элементов.
**Requirements:** TBD
**Plans:** 0 plans

### Phase 999.8: Playbook Builder — инструмент сборки плана продвижения из переиспользуемых блоков (BACKLOG — COMPLETE)

6/6 plans complete. Каркас управления SEO-методологиями через переиспользуемые блоки.

### Phase 999.9: Prompt Library — каркас AI-агентов через библиотеку промптов (BACKLOG)

Каталог AI-агентов (промптов с {{переменными}}), создание/редактирование, запуск через Celery + HTMX-поллинг, избранное и форки. Средний приоритет.
**Plans:** 2/2 plans complete

Plans:
- [x] 999.9-01-PLAN.md — Models, migration, service layer, Celery task, call_agent()
- [x] 999.9-02-PLAN.md — Router, 6 Jinja2 templates, sidebar navigation wiring

### Phase 999.10: QA Surface Tracker — десктоп, мобилка, Telegram (BACKLOG)

Retroactive audit system. FeatureSurface реестр с retest_policy. Высокий приоритет.
**Plans:** 0 plans

### Phase 999.11: SEO-курс на основе Playbook-данных (BACKLOG — SEED)

Коммерческий SEO-курс на своей исследовательской базе. Активация через 6 месяцев использования Playbook Builder.
**Plans:** 0 plans
