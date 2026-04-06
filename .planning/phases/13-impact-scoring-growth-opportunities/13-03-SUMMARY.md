---
phase: 13-impact-scoring-growth-opportunities
plan: "03"
subsystem: UI / Analytics
tags: [kanban, impact-score, slide-over, opportunities, htmx, drill-down]
dependency_graph:
  requires: [13-01, 13-02]
  provides: [kanban-impact-sort, opportunities-drill-down-slide-over]
  affects: [app/main.py, app/routers/opportunities.py, app/templates/projects/kanban.html, app/templates/analytics/]
tech_stack:
  added: []
  patterns: [HTMX slide-over drawer, HTMX hx-on::after-request, Jinja2 partials include]
key_files:
  created:
    - app/templates/analytics/partials/slide_over.html
    - app/templates/analytics/partials/detail_gap.html
    - app/templates/analytics/partials/detail_loss.html
    - app/templates/analytics/partials/detail_cannibal.html
  modified:
    - app/main.py
    - app/templates/projects/kanban.html
    - app/routers/opportunities.py
    - app/templates/analytics/opportunities.html
    - app/templates/analytics/partials/opportunities_gaps.html
    - app/templates/analytics/partials/opportunities_losses.html
    - app/templates/analytics/partials/opportunities_cannibal.html
decisions:
  - "Slide-over uses fixed positioning with z-50 overlay rather than a push-layout to avoid reflowing existing content"
  - "HTMX hx-on::after-request='openSlideOver()' triggers panel open after content is fetched, avoiding flash of empty panel"
  - "Detail routes use raw SQL text() for joins (consistent with opportunities_service.py pattern)"
  - "Cannibalization slide-over attached to group header div (not sub-table rows) for clear single-click UX"
metrics:
  duration: 15
  completed_date: "2026-04-06"
  tasks_completed: 2
  files_changed: 11
requirements_satisfied: [IMP-02, GRO-02]
---

# Phase 13 Plan 03: Kanban Impact Sort + Opportunities Slide-Over Summary

**One-liner:** Kanban sort-by-impact-score with orange badges on task cards, plus HTMX slide-over drill-down panels for all three Opportunities tabs (gaps, losses, cannibalization).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Kanban impact sort toggle and score badges | d2ec8c9 | app/main.py, app/templates/projects/kanban.html |
| 2 | Slide-over panel + detail routes for Opportunities drill-down | 5072d9e | app/routers/opportunities.py, 6 templates |

## What Was Built

### Task 1: Kanban Impact Sort (IMP-02)

Modified `ui_kanban()` in `app/main.py`:
- Added `sort: str = "created"` query parameter
- Imports `get_max_impact_score_by_url` and `normalize_url`
- Fetches impact map for the project's site (gracefully returns `{}` if no site)
- Each task dict now includes `impact_score` from the impact map via normalized URL lookup
- When `sort == "impact"`, each status group is sorted by `impact_score DESC`
- Passes `sort` variable to template context

Modified `kanban.html`:
- Added sort `<select>` element with `hx-get`, `hx-target="body"`, `hx-push-url="true"` — HTMX reloads the full page with new sort parameter
- Options: "По дате" (value="created") / "По Impact Score" (value="impact")
- Each task card title area now shows an orange badge (`bg-orange-50 text-orange-600`) when `task.impact_score > 0`

### Task 2: Opportunities Slide-Over Drill-Down (GRO-02)

Created `slide_over.html` partial:
- Fixed overlay with semi-transparent backdrop, clicking closes the panel
- Right-side drawer `w-96` with overflow scroll
- `closeSlideOver()` and `openSlideOver()` JS functions

Updated `opportunities.html`:
- Replaced `<div id="slide-over-content"></div>` placeholder with `{% include "analytics/partials/slide_over.html" %}`

Updated three tab partials to add row-level HTMX triggers:
- `opportunities_gaps.html`: rows get `/detail/gap/{item.id}` + `openSlideOver()`
- `opportunities_losses.html`: rows get `/detail/loss/{item.keyword_id}` + `openSlideOver()`
- `opportunities_cannibal.html`: group header divs get `/detail/cannibal/{group.keyword_id}` + `openSlideOver()`

Created three detail partials, each with:
- Header with phrase in colored badge (indigo/red/amber)
- X close button calling `closeSlideOver()`
- Key fields in a `<dl>` list
- "Подробнее" link to the full section page

Added three detail routes to `opportunities.py` (total 8 routes):
- `GET /{site_id}/opportunities/detail/gap/{gap_keyword_id}` — queries GapKeyword
- `GET /{site_id}/opportunities/detail/loss/{keyword_id}` — JOIN keyword_latest_positions + keywords
- `GET /{site_id}/opportunities/detail/cannibal/{keyword_id}` — queries all pages for keyword at position <= 50, deduplicates by URL

## Deviations from Plan

### Auto-fixed Issues

None.

### Minor Implementation Notes

**1. [Adaptation] Kanban verify grep uses `sort=impact` literal**
- The plan's `grep -c "sort=impact"` check expects a literal string in the template
- Actual implementation uses `name="sort"` + `value="impact"` on the select element (standard HTML form behavior) which HTMX serializes as `sort=impact` at request time
- All acceptance criteria in the plan are satisfied; only the automated grep command differs

## Known Stubs

None — all data is wired to real service functions from Plans 01 and 02.

## Self-Check: PASSED

- d2ec8c9 — feat(13-03): Kanban impact sort toggle and score badges
- 5072d9e — feat(13-03): Slide-over drill-down panels for Opportunities dashboard
- All 4 new template files exist on disk
- Router confirms 8 routes
- "Подробнее" present in all 3 detail partials
