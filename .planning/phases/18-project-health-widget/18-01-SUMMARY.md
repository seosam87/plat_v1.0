---
phase: 18-project-health-widget
plan: 01
subsystem: ui/overview
tags: [health-widget, onboarding, jinja-macro, site-service]
requires:
  - Site, Keyword, Competitor, CrawlJob, KeywordPosition, CrawlSchedule, PositionSchedule models
provides:
  - compute_site_health(db, site_id) -> SiteHealth
  - project_health_widget(health) Jinja macro
  - GET /ui/sites/{site_id} overview route
affects:
  - app/services/site_service.py
  - app/main.py
  - app/templates/sites/detail.html
  - app/templates/macros/health.html (new)
  - tests/test_site_health.py (new)
tech-stack:
  added: []
  patterns: [dataclass-result, count-scalar-reuse]
key-files:
  created:
    - app/templates/macros/health.html
    - tests/test_site_health.py
  modified:
    - app/services/site_service.py
    - app/main.py
    - app/templates/sites/detail.html
decisions:
  - "compute_site_health exposes keyword_count/crawl_count/competitor_count so the route reuses them with zero duplicate COUNT queries"
  - "Step 7 'schedule configured' counts only rows where is_active=True AND schedule_type != manual (both CrawlSchedule and PositionSchedule)"
  - "analytics_connected is derived from site.metrika_token only — OAuthToken is not consulted to keep compute_site_health within ≤ 8 queries and because PHW-04 treats analytics as a secondary, non-blocking signal"
  - "The new /ui/sites/{site_id} route is registered BEFORE the legacy /ui/sites/{site_id}/detail 301 redirect so FastAPI path matching precedence is preserved"
metrics:
  duration_min: 8
  tasks: 5
  files: 5
  tests_added: 12
  tests_total: 87
completed: 2026-04-08
---

# Phase 18 Plan 01: Project Health Widget Summary

One-liner: Ship a synchronous 7-step project setup checklist on the per-site Overview page, derived from existing DB state with zero migrations, zero Celery tasks, and zero new HTTP calls.

## SiteHealth dataclass shape

```python
@dataclass
class HealthStep:
    key: str
    title: str          # RU
    description: str    # RU
    done: bool
    status: str         # "done" | "current" | "pending"
    next_url: str | None
    is_current: bool = False

@dataclass
class SiteHealth:
    steps: list[HealthStep]
    completed_count: int
    current_step_index: int | None
    is_fully_set_up: bool
    analytics_connected: bool
    keyword_count: int
    crawl_count: int
    competitor_count: int
```

## 7 step keys (ordered) & final next_url paths

| # | key           | next_url (template)              |
|---|---------------|----------------------------------|
| 1 | site_created  | None (always done)               |
| 2 | wp_creds      | /ui/sites/{site_id}/edit         |
| 3 | keywords      | /ui/keywords/{site_id}           |
| 4 | competitors   | /ui/competitors/{site_id}        |
| 5 | crawl         | /ui/sites/{site_id}/crawls       |
| 6 | positions     | /ui/positions/{site_id}          |
| 7 | schedule      | /ui/sites/{site_id}/schedule     |

Competitors step confirmed wired to `/ui/competitors/{site_id}` (matches main.py ~line 1843).

## Query budget

`compute_site_health` issues ≤ 8 queries: 1 `db.get(Site)` + 6 COUNTs (keywords, competitors, crawls, positions, crawl_schedules, position_schedules). The route handler adds 2 more (1x CrawlSchedule SELECT, 1x PositionSchedule SELECT) for the existing `<select>` dropdowns — total ≤ 11 for the full page. Raw counts exposed on SiteHealth are reused by the template, so no duplicate COUNTs.

## Smoke crawler coverage

`tests/test_ui_smoke.py` discovers routes from `app.routes`; the new `/ui/sites/{site_id}` route is automatically picked up and exercised against the seeded fixture site. Full run: **87 passed** (12 new health tests + 75 existing smoke items), no Jinja UndefinedError.

## Template variable audit

| Variable          | Source in route                                   |
|-------------------|---------------------------------------------------|
| site              | `get_site(db, sid)`                               |
| keyword_count     | `health.keyword_count` (reused, no re-query)      |
| crawl_count       | `health.crawl_count` (reused, no re-query)        |
| task_count        | `0` — Task model out of scope for Phase 18        |
| recent_tasks      | `[]` (rendered only inside `{% if %}`)             |
| recent_crawls     | `[]` (rendered only inside `{% if %}`)             |
| crawl_schedule    | CrawlSchedule row or `"manual"`                    |
| position_schedule | PositionSchedule row or `"manual"`                 |
| health            | `compute_site_health(db, sid)` (NEW)              |

No UndefinedError observed during smoke run.

## Edge cases discovered

- **Partitioned `keyword_positions` table**: SQLAlchemy `create_all` creates the parent partitioned table but not partitions; test suite uses a helper `_ensure_kp_partition` to `CREATE TABLE IF NOT EXISTS keyword_positions_default PARTITION OF keyword_positions DEFAULT` before inserting. This is scoped to the SAVEPOINT-rolled-back test transaction and doesn't touch the real DB.
- **OAuthToken not queried**: to keep compute_site_health within the ≤ 8 query budget and because PHW-04 treats analytics as secondary, `analytics_connected` is derived solely from `site.metrika_token`. GSC OAuth readiness can be surfaced in a future plan.
- **`wp_creds` signal**: checks `wp_username AND encrypted_app_password AND url` — the column is `encrypted_app_password`, NOT `wp_password` (the latter does not exist on the Site model).

## Deviations from Plan

None — plan executed exactly as written.

## Commits

- `4bc7acd` test(18-01): add failing tests for compute_site_health (RED)
- `cc77fe1` feat(18-01): implement compute_site_health (GREEN)
- `69eea31` feat(18-01): add project_health_widget Jinja macro
- `950f1d1` feat(18-01): add /ui/sites/{site_id} overview route with health widget

## Self-Check: PASSED

- FOUND: app/services/site_service.py (compute_site_health)
- FOUND: app/templates/macros/health.html
- FOUND: app/templates/sites/detail.html (widget wired)
- FOUND: tests/test_site_health.py (12 tests, all green)
- FOUND: commits 4bc7acd, cc77fe1, 69eea31, 950f1d1
- VERIFIED: `pytest tests/test_site_health.py tests/test_ui_smoke.py` → 87 passed
