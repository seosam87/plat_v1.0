---
phase: v3-05-content-gap
plan: "03"
subsystem: ui
tags: [fastapi, jinja2, htmx, gap-analysis, router]

requires:
  - phase: v3-05-01
    provides: GapKeyword, GapGroup, GapProposal models + migration 0024
  - phase: v3-05-02
    provides: gap_service.py (detect, import, score, CRUD, proposals), gap_parser.py

provides:
  - Gap analysis FastAPI router (14 endpoints) at prefix /gap
  - gap/index.html Jinja2 template with import UI, keyword table, groups, proposals
  - Gap-анализ button integrated in site detail quick actions

affects: [v3-06, v3-07, any phase using gap analysis UI]

tech-stack:
  added: []
  patterns:
    - "Gap router follows analytics.py pattern: _get_site_or_404 helper, require_admin on all endpoints, templates.TemplateResponse with full context dict"
    - "File upload via NamedTemporaryFile + shutil.copyfileobj; temp file cleaned up in finally block"
    - "score_formula constant passed to template context for tooltip display"

key-files:
  created:
    - app/routers/gap.py
    - app/templates/gap/index.html
  modified:
    - app/main.py
    - app/templates/sites/detail.html

key-decisions:
  - "Gap router uses /gap/{site_id} prefix (not /gap/sites/{site_id}) for consistency with audit/monitoring pattern"
  - "score-formula endpoint at /gap/score-formula (no site_id) since formula is global"

patterns-established:
  - "Proposal approve/reject endpoints at /gap/proposals/{id}/approve|reject (outside site prefix)"

requirements-completed: []

duration: 5min
completed: 2026-04-03
---

# Phase v3-05 Plan 03: Gap Router, UI, and Integration Summary

**Gap analysis FastAPI router (14 endpoints), Jinja2 UI page with keyword table/groups/proposals/file upload, and site detail button — all wired together at /gap/{site_id}**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T08:13:13Z
- **Completed:** 2026-04-03T08:18:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Created `app/routers/gap.py` with 14 endpoints covering page render, SERP detection, CSV/XLSX import, keyword CRUD, group management, and proposal workflow
- Created `app/templates/gap/index.html` with Russian UI: import section (session/file mode), summary stats, keyword table with selection and sorting, groups panel, proposals table with approve/reject actions, and scoring tooltip
- Registered gap_router in `app/main.py` and confirmed "Gap-анализ" button already present in `app/templates/sites/detail.html`

## Task Commits

Each task was committed atomically:

1. **Task 01: Create gap router** - `cc6526c` (feat)
2. **Task 02: Create gap analysis page template** - `cc6526c` (feat)
3. **Task 03: Register router and add button to site detail** - `cc6526c` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `app/routers/gap.py` — 14-endpoint gap router: page, detect, import, keywords CRUD, groups CRUD, proposals CRUD, score-formula
- `app/templates/gap/index.html` — Full gap analysis UI: Russian copy, import modes, keyword table with checkboxes, scoring tooltip, groups list, proposals with status badges
- `app/main.py` — gap_router imported and registered with `app.include_router`
- `app/templates/sites/detail.html` — Gap-анализ button in quick actions (was already present)

## Decisions Made
None - followed plan as specified.

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria pass:
- `grep -c "@router" app/routers/gap.py` → 14 (plan required ≥13)
- `python -c "from app.routers.gap import router"` → OK
- All template grep checks pass (Gap-анализ, Потенциал, score_formula, Создать предложения, Одобрить, CSV/XLSX)
- `grep -q "gap_router" app/main.py` → YES
- `grep -q "Gap-анализ" app/templates/sites/detail.html` → YES

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Gap analysis end-to-end is complete (models → service → parser → router → UI)
- Phase v3-05 is fully complete (all 3 plans done)
- Ready to advance to next phase

---
*Phase: v3-05-content-gap*
*Completed: 2026-04-03*
