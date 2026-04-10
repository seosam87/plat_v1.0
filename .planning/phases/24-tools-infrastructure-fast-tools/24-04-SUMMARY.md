---
phase: 24-tools-infrastructure-fast-tools
plan: 04
subsystem: tools
tags: [relevant-url, xmlproxy, celery, htmx, jinja2, openpyxl, pytest]

requires:
  - phase: 24-tools-infrastructure-fast-tools
    plan: 01
    provides: TOOL_REGISTRY router + sidebar + Celery task registration

provides:
  - RelevantUrlJob + RelevantUrlResult ORM models with target_domain column
  - relevant_url_service.find_relevant_url domain-filtering service
  - run_relevant_url Celery task with XMLProxy integration and partial-result handling
  - tools/relevant-url/ template set (index, results, partials/job_status)
  - Generic tools/tool_landing.html + tool_results.html + partials/job_status.html shared templates
  - Migration 0049 creating both relevant_url tables
  - 9 unit tests for find_relevant_url service

affects:
  - 24-05-smoke-wire (relevant-url routes now routable)

tech-stack:
  added: []
  patterns:
    - "Per-tool template dispatch: router uses tools/{slug}/index.html and tools/{slug}/results.html"
    - "HTMX polling: hx-trigger=load delay:10s on pending/running, static on complete/partial/failed"
    - "Domain normalization: _normalize_domain strips www., lowercases, handles full URLs"
    - "Balance exhaustion: XMLProxyError codes 32/33 → save partial results, mark job partial"

key-files:
  created:
    - app/models/relevant_url_job.py
    - app/services/relevant_url_service.py
    - app/tasks/relevant_url_tasks.py
    - alembic/versions/0049_add_relevant_url_tables.py
    - app/templates/tools/relevant-url/index.html
    - app/templates/tools/relevant-url/results.html
    - app/templates/tools/relevant-url/partials/job_status.html
    - app/templates/tools/tool_landing.html
    - app/templates/tools/tool_results.html
    - app/templates/tools/partials/job_status.html
    - tests/test_relevant_url_service.py
    - app/models/commerce_check_job.py (stub, unlocks smoke_seed imports)
  modified:
    - app/routers/tools.py (template dispatch, import fixes, export columns, target_domain key)

key-decisions:
  - "Tool-specific templates (tools/{slug}/*.html) rather than single generic template — each plan owns its templates, no parallel write conflict"
  - "target_domain column (not domain) — matches model column, router updated to pass target_domain kwarg"
  - "commerce_check_job.py stub created — unblocks conftest/smoke_seed imports in parallel worktree"

requirements-completed:
  - REL-01

duration: 7min
completed: 2026-04-10
---

# Phase 24 Plan 04: Relevant URL Finder Summary

**Relevant URL Finder tool: XMLProxy-powered search for which domain pages rank in Yandex TOP-10 per keyword, with www/subdomain normalization, partial-result handling, and CSV/XLSX export**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-10T08:15:34Z
- **Completed:** 2026-04-10T08:21:58Z
- **Tasks:** 2
- **Files created:** 12, modified: 1

## Accomplishments

- Built `RelevantUrlJob` + `RelevantUrlResult` models with `target_domain` column and JSONB `top_competitors`
- Implemented `find_relevant_url` service with domain normalization (strips www., handles full URLs, lowercases), subdomain matching, and top-3 competitor collection
- Created Alembic migration 0049 for both tables with composite indexes
- Built `run_relevant_url` Celery task: reads XMLProxy credentials, loops phrases, handles balance exhaustion (codes 32/33) with partial save
- Created `tools/relevant-url/` template set: index page with domain input + counter, results page with URL/position/competitor columns, HTMX polling partial (10s)
- Created generic shared templates (`tool_landing.html`, `tool_results.html`, `partials/job_status.html`) for reuse by tools 02/03
- Updated router to dispatch to tool-specific templates by slug, fixed 3 import errors, fixed export column names
- 9 service unit tests all pass including edge cases (www, subdomain, empty SERP, first-match-wins, top-3 limit)

## Task Commits

1. **Task 1: Models + service + migration** - `de01f1b` (feat)
2. **Task 2: Celery task + templates + tests** - `e9500f0` (feat)

## Files Created/Modified

- `app/models/relevant_url_job.py` — RelevantUrlJob + RelevantUrlResult models
- `app/services/relevant_url_service.py` — find_relevant_url domain-filtering service
- `app/tasks/relevant_url_tasks.py` — run_relevant_url Celery task (soft_time_limit=300)
- `alembic/versions/0049_add_relevant_url_tables.py` — migration creating both tables
- `app/templates/tools/relevant-url/index.html` — landing page with domain input, counter
- `app/templates/tools/relevant-url/results.html` — results with URL/position/competitor columns
- `app/templates/tools/relevant-url/partials/job_status.html` — HTMX polling partial
- `app/templates/tools/tool_landing.html` — generic tool landing (all 3 tools)
- `app/templates/tools/tool_results.html` — generic results (all 3 tools, conditional columns)
- `app/templates/tools/partials/job_status.html` — generic HTMX partial
- `tests/test_relevant_url_service.py` — 9 unit tests
- `app/models/commerce_check_job.py` — stub model (Rule 3 fix)
- `app/routers/tools.py` — template dispatch + import fixes + export column fixes

## Decisions Made

- Created tool-specific templates at `tools/{slug}/index.html` to avoid parallel-write conflicts when plans 02/03/04 all run concurrently
- Used `target_domain` as the model column (matching plan spec); updated router from `domain` to `target_domain` key
- Created commerce_check_job stub to unblock conftest imports — plan 02 will replace it with the full model

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Router used `domain` key for has_domain_field tools**
- **Found during:** Task 1
- **Issue:** `app/routers/tools.py` stored domain as `job_kwargs["domain"]` but model column is `target_domain`
- **Fix:** Changed to `job_kwargs["target_domain"]`
- **Files modified:** `app/routers/tools.py`
- **Commit:** de01f1b

**2. [Rule 1 - Bug] Router export used wrong column names for relevant-url**
- **Found during:** Task 1
- **Issue:** `_result_to_row` used `relevant_url` and `top3_competitors` (non-existent), correct names are `url` and `top_competitors`
- **Fix:** Updated to use correct column names + join list for competitors
- **Files modified:** `app/routers/tools.py`
- **Commit:** de01f1b

**3. [Rule 1 - Bug] Router imported `get_db` from `app.database` (doesn't exist there)**
- **Found during:** Task 2 test run
- **Issue:** `from app.database import get_db` fails; function lives in `app.dependencies`
- **Fix:** Changed import to `from app.dependencies import get_db`
- **Files modified:** `app/routers/tools.py`
- **Commit:** e9500f0

**4. [Rule 1 - Bug] Router imported `get_current_user` from `app.auth` (wrong path)**
- **Found during:** Task 2 test run
- **Issue:** `from app.auth import get_current_user` fails; should be `app.auth.dependencies`
- **Fix:** Changed import to `from app.auth.dependencies import get_current_user`
- **Files modified:** `app/routers/tools.py`
- **Commit:** e9500f0

**5. [Rule 1 - Bug] Router used generic templates that plan 24-01 referenced but never existed**
- **Found during:** Task 2
- **Issue:** Router hardcoded `tools/tool_landing.html`, `tools/tool_results.html` — templates not created by plan 01; plans 02-04 create tool-specific templates
- **Fix:** Updated router to dispatch to `tools/{slug}/index.html` and `tools/{slug}/results.html`; also created generic templates for backwards compat
- **Files modified:** `app/routers/tools.py`
- **Commit:** e9500f0

**6. [Rule 3 - Blocking] Missing `app.models.commerce_check_job` blocked test imports**
- **Found during:** Task 2 test run
- **Issue:** `tests/fixtures/smoke_seed.py` hard-imports `CommerceCheckJob` (plan 02 deliverable not yet created in this worktree)
- **Fix:** Created minimal stub `app/models/commerce_check_job.py` to satisfy import; plan 02 will replace with full model
- **Files modified:** `app/models/commerce_check_job.py` (created)
- **Commit:** e9500f0

## Known Stubs

- `app/models/commerce_check_job.py` — stub model with correct schema structure; will be replaced by plan 24-02 with full implementation including migration

## Self-Check: PASSED

All files exist on disk. Both task commits confirmed in git log.

| Check | Result |
|-------|--------|
| app/models/relevant_url_job.py | FOUND |
| app/services/relevant_url_service.py | FOUND |
| app/tasks/relevant_url_tasks.py | FOUND |
| alembic/versions/0049_add_relevant_url_tables.py | FOUND |
| app/templates/tools/relevant-url/index.html | FOUND |
| app/templates/tools/relevant-url/results.html | FOUND |
| app/templates/tools/relevant-url/partials/job_status.html | FOUND |
| tests/test_relevant_url_service.py | FOUND |
| Commit de01f1b (Task 1) | FOUND |
| Commit e9500f0 (Task 2) | FOUND |
