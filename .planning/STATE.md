---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Onboarding & Project Health
status: executing
stopped_at: Completed 25-01-PLAN.md — Brief pipeline, 3 model files, migration 0050, 20 tests passing
last_updated: "2026-04-10T12:29:29.570Z"
last_activity: 2026-04-10
progress:
  total_phases: 45
  completed_phases: 39
  total_plans: 137
  completed_plans: 124
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-06)

**Core value:** A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.
**Current focus:** Phase 25 — serp-aggregation-tools

## Current Position

Milestone: v2.1 Onboarding & Project Health
Phase: 25 (serp-aggregation-tools) — EXECUTING
Plan: 2 of 5
Status: Ready to execute
Last activity: 2026-04-10

Progress: v2.1 [__________] 0%

## Performance Metrics

### v2.0 Velocity

| Metric | Value |
|--------|-------|
| Phases total | 6 |
| Phases complete | 0 |
| Plans complete | 0 |
| Milestone start | 2026-04-06 |
| Phase 12-analytical-foundations P01 | 524064min | 2 tasks | 8 files |
| Phase 12-analytical-foundations P03 | 10 | 2 tasks | 7 files |
| Phase 12-analytical-foundations P02 | 5 | 2 tasks | 8 files |
| Phase 13-impact-scoring-growth-opportunities P01 | 15 | 2 tasks | 8 files |
| Phase 13 P02 | 15 | 2 tasks | 10 files |
| Phase 13-impact-scoring-growth-opportunities P03 | 15 | 2 tasks | 11 files |
| Phase 14-client-instructions-pdf P01 | 4 | 2 tasks | 5 files |
| Phase 14-client-instructions-pdf P03 | 8 | 2 tasks | 2 files |
| Phase 14-client-instructions-pdf P02 | 12 | 2 tasks | 8 files |
| Phase 15-keyword-suggest P01 | 9 | 2 tasks | 8 files |
| Phase 15-keyword-suggest P03 | 5 | 2 tasks | 6 files |
| Phase 15-keyword-suggest P02 | 12 | 2 tasks | 9 files |
| Phase 15.1-ui-smoke-crawler P02 | 8 | 1 tasks | 2 files |
| Phase 15.1 P01 | 15 | 3 tasks | 5 files |
| Phase 15.1-ui-smoke-crawler P03 | 10 | 2 tasks | 3 files |
| Phase 15.1-ui-smoke-crawler P05 | 3 | 2 tasks | 2 files |
| Phase 15.1-ui-smoke-crawler P04 | 6 | 1 tasks | 1 files |
| Phase 999.3 P01 | 6 | 4 tasks | 3 files |
| Phase 16-ai-geo-readiness-llm-briefs P01 | 6 | 2 tasks | 6 files |
| Phase 16-ai-geo-readiness-llm-briefs P02 | 5 | 2 tasks | 3 files |
| Phase 16-ai-geo-readiness-llm-briefs P03 | 10 | 2 tasks | 12 files |
| Phase 17-in-app-notifications P01 | 4 | 2 tasks | 8 files |
| Phase 17-in-app-notifications P02 | 12 | 3 tasks | 10 files |
| Phase 17-in-app-notifications P03 | 12 | 2 tasks | 8 files |
| Phase 18-project-health-widget P01 | 8 | 5 tasks | 5 files |
| Phase 19.1-ui-scenario-runner-playwright P01 | 3 | 2 tasks | 5 files |
| Phase 19.1 P02 | 3 min | 3 tasks | 9 files |
| Phase 19.1 P03 | 9 min | 3 tasks | 9 files |
| Phase 19.1-ui-scenario-runner-playwright P04 | 3 | 2 tasks | 2 files |
| Phase 19.1-ui-scenario-runner-playwright P05 | 18 | 3 tasks | 11 files |
| Phase 23-document-generator P01 | 4 | 2 tasks | 8 files |
| Phase 23-document-generator P02 | 4 | 2 tasks | 6 files |
| Phase 24-tools-infrastructure-fast-tools P01 | 15 | 2 tasks | 7 files |
| Phase 24-tools-infrastructure-fast-tools P03 | 5 | 2 tasks | 9 files |
| Phase 24-tools-infrastructure-fast-tools P05 | 10 | 2 tasks | 9 files |
| Phase 25-serp-aggregation-tools P01 | 7 | 2 tasks | 9 files |

## Accumulated Context

### Roadmap Evolution

- Phase 15.1 inserted after Phase 15: UI Smoke Crawler — pytest+httpx runner hitting every GET route with seeds, asserts 200 + no Jinja errors. Motivated by repeated 500s on new UI (today: `data.items` dict collision on opportunities page). (URGENT / INSERTED)

### Key Decisions (v2.0)

| Decision | Rationale |
|----------|-----------|
| `normalize_url()` + `keyword_latest_positions` in Phase 12 | All analytical JOINs fail silently without URL normalization; DISTINCT ON on partitioned table causes 8–15s scans at 100K keywords |
| WeasyPrint subprocess isolation in Phase 14 | WeasyPrint memory leak (GitHub #2130, #1977) cannot be deferred — established before any new PDF code is written |
| Keyword Suggest in isolated Phase 15 | IP ban risk from autocomplete scraping is entirely separate from analytical features and must not block Phase 13 work |
| LLM Briefs + GEO Readiness co-located in Phase 16 | Both depend on existing crawl + content audit data; both are additive extensions to existing services; anthropic SDK introduced once |
| In-app Notifications last (Phase 17) | Touches global sidebar chrome; cleanest to add after all feature surfaces are finalized |
| HTMX polling (30s) over SSE for notifications | Under 20 users; polling is simpler and sufficient; SSE deferred unless real-time delivery required |
| Template brief always generated first; LLM is enhancement only | Prevents LLM API failures from blocking brief delivery |
| Yandex Suggest primary, Google secondary (opt-in), Wordstat opt-in | User note: focus on Yandex, no complex Google services |

### Pending Todos

- Phase 15: Verify XMLProxy suggest endpoint availability before designing routing strategy
- Phase 16: Confirm LLM model — claude-3-5-haiku-20241022 (10–20x cheaper, appropriate for batch) vs claude-opus-4-6

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260402-v3j | Fix position check engine bug | 2026-04-02 | 23e77f6 | [260402-v3j-fix-position-check-engine-bug](./quick/260402-v3j-fix-position-check-engine-bug/) |

## Session Continuity

Last session: 2026-04-10T12:29:29.561Z
Stopped at: Completed 25-01-PLAN.md — Brief pipeline, 3 model files, migration 0050, 20 tests passing
Resume file: None
