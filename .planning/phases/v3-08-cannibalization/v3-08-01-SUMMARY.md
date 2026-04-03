---
phase: v3-08-cannibalization
plan: "01"
subsystem: seo
tags: [cannibalization, resolution, htmx, fastapi, sqlalchemy]

requires:
  - phase: v3-07-bulk
    provides: cluster and keyword infrastructure
  - phase: v3-06-architecture
    provides: cluster/keyword models and detect_cannibalization service

provides:
  - CannibalizationResolution model with ResolutionType/ResolutionStatus enums
  - Alembic migration 0026 for cannibalization_resolutions table
  - Pure functions: suggest_resolution_type, generate_action_plan (4 resolution types)
  - Async CRUD: create_resolution, create_resolution_task (SeoTask), list_resolutions, update_resolution_status, check_resolution
  - Router endpoints: POST resolve, GET resolutions, POST status, POST check
  - Cannibalization UI with action buttons, primary URL selector, resolution history

affects: [v3-09, v3-10]

tech-stack:
  added: []
  patterns:
    - "Resolution proposals stored with auto-generated action plans (Russian text)"
    - "check_resolution re-runs detect_cannibalization for live status"
    - "UI router passes serialized resolutions dict list to template (not ORM objects)"

key-files:
  created:
    - app/models/cannibalization.py
    - alembic/versions/0026_add_cannibalization_resolver.py
    - app/services/cannibalization_service.py
    - tests/test_cannibalization_service.py
  modified:
    - app/routers/clusters.py
    - app/templates/clusters/cannibalization.html
    - app/main.py

key-decisions:
  - "check_resolution uses 'phrase' key (not 'keyword') from detect_cannibalization dict — fixed bug in auto-fix"
  - "ui_cannibalization handler serializes resolution ORM objects to dicts before template — avoids lazy-load in Jinja2"
  - "Resolution action buttons use HTMX hx-post with hx-vals for status updates — no separate JS"

requirements-completed: []

duration: 4min
completed: 2026-04-03
---

# Phase v3-08 Plan 01: Cannibalization Resolver Summary

**Cannibalization resolution proposals with 4 action types (merge/canonical/redirect/split), Russian action plan generation, SeoTask creation, and HTMX-powered UI with status tracking**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-03T12:53:14Z
- **Completed:** 2026-04-03T12:57:03Z
- **Tasks:** 4
- **Files modified:** 6

## Accomplishments

- CannibalizationResolution model + migration 0026 with PostgreSQL ENUMs for type/status
- suggest_resolution_type heuristic (same path prefix → merge, default → canonical) and generate_action_plan for all 4 types in Russian
- 4 router endpoints for resolution CRUD + re-check; SeoTask auto-creation via create_resolution_task
- Cannibalization template updated with per-keyword resolution buttons, primary URL dropdown, and collapsible action plan history

## Task Commits

1. **Task 1-2-4: Model, migration, service, tests** - `e8d597d` (feat)
2. **Task 3: Router endpoints + UI** - `8867f11` (feat)

## Files Created/Modified

- `app/models/cannibalization.py` — ResolutionType, ResolutionStatus enums, CannibalizationResolution ORM model
- `alembic/versions/0026_add_cannibalization_resolver.py` — cannibalization_resolutions table with PG ENUM types
- `app/services/cannibalization_service.py` — suggest_resolution_type, generate_action_plan, CRUD functions
- `tests/test_cannibalization_service.py` — 7 unit tests covering all resolution types (all passing)
- `app/routers/clusters.py` — 4 new endpoints: /resolve, /resolutions, /{id}/status, /{id}/check
- `app/templates/clusters/cannibalization.html` — action buttons, primary URL selector, resolution history with status badges
- `app/main.py` — ui_cannibalization passes serialized resolutions to template

## Decisions Made

- check_resolution uses `phrase` key from detect_cannibalization (not `keyword`) — pre-existing bug was auto-fixed
- UI handler serializes resolution ORM objects to dicts before passing to Jinja2 template
- HTMX `hx-vals` used for status updates (no extra JS, no form needed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed wrong dict key in check_resolution**
- **Found during:** Task 2 review
- **Issue:** `check_resolution` compared `c.get("keyword")` but detect_cannibalization returns dicts with key `"phrase"`
- **Fix:** Changed to `c.get("phrase")`
- **Files modified:** app/services/cannibalization_service.py
- **Verification:** Logic now correctly identifies if keyword is still cannibalized
- **Committed in:** e8d597d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Essential correctness fix. No scope creep.

## Issues Encountered

None beyond the auto-fixed bug above.

## Known Stubs

None — resolution proposals are fully wired: created from UI, stored in DB, retrievable, status-updatable, and re-checkable against live position data.

## Next Phase Readiness

- Cannibalization detection + resolution system fully implemented
- SeoTask integration ready (cannibalization type in task board)
- check_resolution ready for live use once position data is populated
- No blockers for next phase

---
*Phase: v3-08-cannibalization*
*Completed: 2026-04-03*
