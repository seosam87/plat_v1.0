# Phase 18 — Project Health Widget — Context

**Derived from:** ROADMAP.md Phase 18 section + v2.1 REQUIREMENTS.md (PHW-01..06)
**Discuss-phase skipped:** scope is unambiguous, read-path derivation only, no new models

## Goal

A user returning to any site after weeks of inactivity immediately sees a 7-step setup checklist on the Site Overview page showing what's done, what's next, and a one-click link to the next required action — derived from existing DB state with zero new queries or Celery tasks.

## Requirements

- **PHW-01**: 7-step checklist widget on Site Overview
- **PHW-02**: ✅/⏳/⚠️ status per step from existing DB (no new tables)
- **PHW-03**: Per-step explanation + "Сделать сейчас" CTA
- **PHW-04**: N/7 progress + highlight "next step"
- **PHW-05**: `site_service.compute_site_health()` — single reusable function returning `{step: {done, message, next_url}}`
- **PHW-06**: Fully complete widget collapses (not blocking)

## The 7 Steps (fixed ordering, sequential)

| # | Step | Signal (existing DB) | Next URL |
|---|------|----------------------|----------|
| 1 | Site created | always ✓ (site row exists) | — |
| 2 | WordPress access | `site.wp_password IS NOT NULL AND site.wp_url != ''` | `/sites/{id}/edit` |
| 3 | Keywords added | `SELECT count(*) FROM keywords WHERE site_id = ? > 0` | `/sites/{id}/keywords/import` |
| 4 | Competitors added | `SELECT count(*) FROM competitors WHERE site_id = ? > 0` | `/sites/{id}/competitors` |
| 5 | First crawl run | `SELECT count(*) FROM crawl_jobs WHERE site_id = ? > 0` | `/sites/{id}/crawls/` |
| 6 | First position check | `SELECT count(*) FROM position_check_runs WHERE site_id = ? > 0` | `/sites/{id}/positions/` |
| 7 | Schedule configured | `SELECT count(*) FROM scheduled_tasks WHERE site_id = ? AND active = true > 0` | `/sites/{id}/crawls/schedule/` |

**Optional secondary** (does NOT block "fully set up"):
- Analytics connected — Metrika token OR GSC token configured on site

## Constraints

- **Zero new DB tables, zero migrations** — all signals derived from existing models
- **Zero new Celery tasks** — synchronous read-path only
- **Zero new external API calls** — purely internal state
- **Reuse existing `get_site_detail()` query paths** — most counts are already loaded, just expose them
- **UI must fit existing Overview layout** — placement (right rail vs full card) TBD during implementation based on current template
- **Widget must render in under 200ms** — user opens Overview, sees it immediately
- **Smoke crawler** — Site Overview page already in Phase 15.1 fixture, no new fixture work

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `site_service.compute_site_health()` returns `{steps: [...], current_step_index, completed_count, is_fully_set_up}` | Single source of truth; can be consumed by Overview template, future dashboards, and `/api/health` endpoint if needed |
| Analytics step is secondary (not blocking) | Not every client has Metrika/GSC, shouldn't trap the widget in "incomplete" forever |
| Fully-complete state = collapsed widget with "Показать снова" CTA | Don't waste vertical space on solved problem, but keep it discoverable |
| Use existing `get_site_detail()` — add fields, don't duplicate queries | Avoid N+1 on Overview page load |
| Jinja macro `project_health_widget(health)` in `app/templates/macros/health.html` | Reusable if needed on other dashboards later |

## Success Criteria (from ROADMAP)

1. Site Overview page contains a Project Health widget showing 7 steps as vertical checklist — each with status icon, title, link, one-line description
2. Widget derives status from `site_service.get_site_detail()` (or a sibling call) — no new Celery tasks, no extra round-trips
3. Widget highlights exactly one step as "current" — first incomplete in sequence; below checklist: "Следующий шаг: [name] →"
4. If all 7 complete → success state "Проект полностью настроен" with link to Overview dashboard; widget collapsible
5. 7 steps + signals as per the table above
6. Analytics step (7b) shown as secondary, does NOT block fully-set-up state
7. Widget route covered by Phase 15.1 smoke crawler (Site Overview already in fixture)

## Dependencies

- Depends on Phase 17 (which is shipped). No blockers.
- Reuses existing services: `site_service`, existing models (Site, Keyword, Competitor, CrawlJob, PositionCheckRun, ScheduledTask)

## Open Questions

None — all 7 signals and their source tables are explicit.

## Out of Scope

- Multi-site health dashboard (aggregate across all sites) — future
- Email nudges "you're stuck on step 3" — future
- Health score history over time — future
- Client-facing onboarding copy — RU only, developer-facing
