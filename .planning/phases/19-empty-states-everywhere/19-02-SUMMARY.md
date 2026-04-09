---
phase: 19-empty-states-everywhere
plan: 02
subsystem: templates
tags: [empty-states, ux, analytics, content-pipeline, jinja2, macro]
dependency_graph:
  requires: [19-01]
  provides: [EMP-03, EMP-04, EMP-05]
  affects: [metrika, traffic_analysis, analytics, pipeline, client_reports, keyword_suggest]
tech_stack:
  added: []
  patterns: [jinja2-macro-call, partial-import, htmx-compatible-empty-state]
key_files:
  created: []
  modified:
    - app/templates/metrika/index.html
    - app/templates/traffic_analysis/index.html
    - app/templates/analytics/partials/opportunities_gaps.html
    - app/templates/analytics/partials/dead_content_table.html
    - app/templates/analytics/partials/quick_wins_table.html
    - app/templates/pipeline/jobs.html
    - app/templates/client_reports/partials/history_table.html
    - app/templates/keyword_suggest/index.html
decisions:
  - "keyword_suggest: added empty_state inside #suggest-results div so HTMX replaces it on search (not wrapped in server-side condition since results come via HTMX)"
  - "All partial files received their own import at file top per research Pitfall 2"
  - "SVG icons removed from quick_wins and pipeline empty states per D-02"
metrics:
  duration: 4
  completed_date: "2026-04-09T07:32:08Z"
  tasks: 2
  files: 8
---

# Phase 19 Plan 02: Analytics & Content Pages Empty States Summary

Apply the empty_state macro to 8 analytics and content templates: Metrika (two conditions), Traffic Analysis, Growth Opportunities, Dead Content, Quick Wins, Content Pipeline, Client Reports history, and Keyword Suggest.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Apply empty_state to analytics pages (Metrika, Traffic, Opportunities, Dead Content, Quick Wins) | 06e80a0, 259a00e | 5 files |
| 2 | Apply empty_state to content pages (Pipeline, Client Reports, Keyword Suggest) | d9e6834 | 3 files |

## What Was Built

All 8 analytics and content templates now use the `empty_state` Jinja2 macro from Plan 01 instead of ad-hoc placeholder markup.

**Analytics pages (Task 1):**
- `metrika/index.html`: Two structured empty states — "Счётчик Яндекс.Метрики не настроен" (CTA: настроить) and "Данные из Метрики ещё не загружены" (CTA: обновить)
- `traffic_analysis/index.html`: "Анализы трафика ещё не проводились" with data source prerequisites
- `analytics/partials/opportunities_gaps.html`: "Нет данных по gap-ключам" with gap analysis CTA
- `analytics/partials/dead_content_table.html`: "Мёртвые страницы не обнаружены" with crawl + positions CTAs
- `analytics/partials/quick_wins_table.html`: SVG icon removed; "Quick Wins пока не найдены" with position check CTA

**Content pages (Task 2):**
- `pipeline/jobs.html`: SVG icon removed; "Задач контент-пайплайна ещё нет" with run batch CTA and 3-step how-to
- `client_reports/partials/history_table.html`: "Отчётов пока нет" with generate PDF CTA
- `keyword_suggest/index.html`: "Подсказки ещё не собирались" placed inside `#suggest-results` div so HTMX replaces it on first search

## Decisions Made

1. **keyword_suggest placement**: The empty state is placed server-side inside `#suggest-results` as initial content. When the user submits the form, HTMX replaces the div content with actual results. The CTA URL points to the same page (self-referencing) since the form is above the fold. HTMX attributes (hx-post, hx-target, hx-swap, hx-indicator) on the form are preserved.

2. **Partial imports**: All three partial templates (opportunities_gaps, dead_content_table, quick_wins_table, history_table) have `{% from "macros/empty_state.html" import empty_state %}` at their own top — not relying on any parent template to provide it.

3. **SVG removal (D-02)**: quick_wins_table.html had an SVG checkmark icon and a heading; pipeline/jobs.html had an SVG document icon. Both removed per D-02 decision. The macro's card format provides the visual container.

## Deviations from Plan

None - plan executed exactly as written. The metrika and traffic_analysis files had already been modified before this plan ran (pre-applied changes tracked in git working tree); committed as part of this plan.

## Known Stubs

None. All empty states wire directly to the macro and show Russian text with real CTAs.

## Self-Check: PASSED

Files created/modified exist:
- app/templates/analytics/partials/opportunities_gaps.html: FOUND (import + call)
- app/templates/analytics/partials/dead_content_table.html: FOUND (import + call)
- app/templates/analytics/partials/quick_wins_table.html: FOUND (import + call, SVG removed)
- app/templates/pipeline/jobs.html: FOUND (import + call, SVG removed)
- app/templates/client_reports/partials/history_table.html: FOUND (import + call)
- app/templates/keyword_suggest/index.html: FOUND (import + call in suggest-results)
- app/templates/metrika/index.html: FOUND (import + two calls)
- app/templates/traffic_analysis/index.html: FOUND (import + call)

Commits verified:
- 06e80a0: analytics partials (3 files)
- d9e6834: content pages (3 files)
- 259a00e: metrika + traffic_analysis (2 files)

Total empty_state imports across all templates: 16 (8 from Plan 01 + 8 from Plan 02)
