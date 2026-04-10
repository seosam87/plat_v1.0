# Roadmap: SEO Management Platform

## Milestones

- **v1.0 MVP** — 16 phases (shipped 2026-04-06) — [details](milestones/v1.0-ROADMAP.md)
- **v2.0 SEO Insights & AI** — 7 phases (shipped 2026-04-08) — [details](milestones/v2.0-ROADMAP.md)
- **v2.1 Onboarding & Project Health** — 4 phases (shipped 2026-04-10) — [details](milestones/v2.1-ROADMAP.md)
- **v3.0 Client & Proposal** — 4 phases (shipped 2026-04-10) — [details](milestones/v3.0-ROADMAP.md)
- **v3.1 SEO Tools** — 2 phases (shipped 2026-04-10) — [details](milestones/v3.1-ROADMAP.md)

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

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1–11 + v3.x + v4.x | v1.0 | 56/56 | Complete | 2026-04-06 |
| 12–17 + 15.1 | v2.0 | 24/24 | Complete | 2026-04-08 |
| 18–19.2 | v2.1 | 13/13 | Complete | 2026-04-10 |
| 20–23 | v3.0 | 13/13 | Complete | 2026-04-10 |
| 24–25 | v3.1 | 10/10 | Complete | 2026-04-10 |

**Total: 45 phases, 137 plans, 5 milestones shipped**

## Backlog

### Phase 999.3: Smart Route Discovery (response_class filter) (BACKLOG — COMPLETE)

Extends `discover_routes` to auto-filter by `response_class=HTMLResponse`. 2/2 plans complete.

### Phase 999.5: Repo ↔ Deployment Sync Strategy (BACKLOG)

Two deployment-drift incidents caught — no automated sync between git repo and running deployment. Context gathered, no plans yet.

### Phase 999.6: LLM API Integration & Live Verification (BACKLOG)

Complete human-verify checkpoint deferred from Phase 16-04. Requires real Anthropic API key for live testing.
