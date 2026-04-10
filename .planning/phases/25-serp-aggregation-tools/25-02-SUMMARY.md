---
phase: 25-serp-aggregation-tools
plan: 02
subsystem: ui
tags: [jinja2, htmx, openpyxl, celery, brief, serp]

requires:
  - phase: 25-01
    provides: BriefJob/BriefResult models, brief_tasks 4-step Celery chain, migration 0050

provides:
  - Brief tool landing page with Yandex region selector (213/2/54/43/65/0)
  - Brief results page with 5 sectioned cards (Title/H1, H2 cloud, highlights, thematic words, volume stats)
  - Brief job_status.html with Brief-specific copy (Составляем ТЗ, Готово, частично)
  - Multi-sheet XLSX export (Title-H1 / H2 / Подсветки / Тематические слова / Объём)
  - Router: has_region_field handling, input_region passed to BriefJob, BriefResult passed as 'result' to template

affects: [25-03, 25-04, 25-05]

tech-stack:
  added: []
  patterns:
    - "Per-tool template directories: tools/{slug}/index.html, results.html, partials/job_status.html"
    - "has_region_field in TOOL_REGISTRY triggers region select in landing template"
    - "export_only_xlsx in TOOL_REGISTRY signals XLSX-only download (no CSV link)"
    - "BriefResult passed as 'result' (single object) alongside 'results' list to template"

key-files:
  created:
    - app/templates/tools/brief/index.html
    - app/templates/tools/brief/results.html
    - app/templates/tools/brief/partials/job_status.html
  modified:
    - app/routers/tools.py

key-decisions:
  - "Multi-sheet XLSX: separate sheets per section (Title-H1, H2, Подсветки, Тематические слова, Объём) instead of single flat sheet"
  - "template 'result' context var: single BriefResult object for sectioned rendering, separate from generic 'results' list"
  - "TOOL_REGISTRY limit corrected to 30 (matches plan spec), cta to 'Составить ТЗ'"

requirements-completed: [BRIEF-01]

duration: 8min
completed: 2026-04-10
---

# Phase 25 Plan 02: Brief UI — Region Selector, Sectioned Results, XLSX Export Summary

**Brief tool full UI: region selector on landing, 5-card sectioned results (Title/H1, H2 cloud, highlights, thematic words, volume), Brief-specific status copy, and multi-sheet XLSX export via openpyxl**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-10T12:30:00Z
- **Completed:** 2026-04-10T12:35:05Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `tools/brief/` template directory with `index.html`, `results.html`, and `partials/job_status.html` — matches the per-tool template pattern used by commercialization/meta-parser/relevant-url
- Landing page (`index.html`) renders region dropdown (Москва default, 6 regions) conditionally on `tool.has_region_field`; phrase counter counts toward 30-phrase limit
- Results page (`results.html`) renders 5 semantic section cards: Title/H1 ordered list, H2 cloud with frequency badges, Highlights bullet list, Thematic words table, Volume stats flex row — all gracefully handle empty data
- Status partial (`partials/job_status.html`) shows Brief-specific copy: "Составляем ТЗ... Краулинг ТОП-10 страниц" (running), "Готово — ТЗ сформировано" (complete), "ТЗ сформировано частично — некоторые страницы ТОП-10 недоступны" (partial)
- Router updated: `has_region_field=True` + `export_only_xlsx=True` in registry, region field parsed and cast to `int` with fallback 213, `BriefResult` passed as `result` context variable, multi-sheet XLSX workbook export

## Task Commits

1. **Task 1: Landing page region selector + results page sectioned layout** - `4765ad4` (feat)
2. **Task 2: XLSX export handler for Brief + router region field handling** - `a021b4a` (feat)

**Plan metadata:** (included in final docs commit)

## Files Created/Modified

- `app/templates/tools/brief/index.html` — Brief landing page with region selector and phrase counter
- `app/templates/tools/brief/results.html` — 5-section results cards + XLSX download link
- `app/templates/tools/brief/partials/job_status.html` — Brief-specific status messages
- `app/routers/tools.py` — TOOL_REGISTRY brief entry updated, region field handling, multi-sheet XLSX export, BriefResult passed to template

## Decisions Made

- **Multi-sheet XLSX**: Separate worksheets per section (Title-H1, H2, Подсветки, Тематические слова, Объём) rather than a single worksheet with separators — cleaner for analysts who filter/sort per section
- **'result' vs 'results' context**: Brief needs a single `BriefResult` object for section rendering; added `result=brief_result` alongside `results=results_rows` — no conflict with existing template logic
- **TOOL_REGISTRY corrections**: limit fixed to 30 (spec), cta to "Составить ТЗ" (UI-SPEC copy contract)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected TOOL_REGISTRY brief entry values**
- **Found during:** Task 2 (reviewing router before modifying)
- **Issue:** Brief registry had `limit: 50` (plan spec says 30) and `cta: "Создать ТЗ"` (UI-SPEC says "Составить ТЗ")
- **Fix:** Corrected both values in the same edit that added `has_region_field` and `export_only_xlsx`
- **Files modified:** app/routers/tools.py
- **Committed in:** a021b4a (Task 2 commit)

**2. [Rule 1 - Bug] Replaced single-sheet XLSX with multi-sheet workbook**
- **Found during:** Task 2 (reviewing existing export code)
- **Issue:** Existing brief export used a single "Brief" worksheet — plan spec requires separate sheets
- **Fix:** Rewrote export block with 5 named sheets as per plan spec
- **Files modified:** app/routers/tools.py
- **Committed in:** a021b4a (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 — bug fixes in pre-existing router code)
**Impact on plan:** Both fixes align implementation with plan spec and UI-SPEC copy contract. No scope creep.

## Issues Encountered

None — templates and router changes were straightforward given the established per-tool pattern.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Brief UI complete (landing + status polling + results + XLSX export)
- Plans 03-05 can proceed to implement remaining tools (serp-parser, etc.)
- No blockers

---
*Phase: 25-serp-aggregation-tools*
*Completed: 2026-04-10*
