---
phase: 16-ai-geo-readiness-llm-briefs
plan: 02
subsystem: audit
tags: [geo, audit, filter, htmx, jinja2, fastapi, sqlalchemy]

# Dependency graph
requires:
  - phase: 16-ai-geo-readiness-llm-briefs
    plan: 01
    provides: "pages.geo_score column, GEO_WEIGHTS dict, 9 geo_* check codes in audit_check_definitions"
provides:
  - "GET /audit/{site_id} accepts geo_score_min, geo_score_max, geo_check query params"
  - "audit/index.html shows GEO score column with color badges (green/yellow/red/gray)"
  - "audit/index.html exposes filter controls for score range + check code select"
  - "tests/test_audit_geo_filter.py with 5 smoke tests — all passing"
affects:
  - "16-03: LLM brief generation (same audit table context; no template changes needed)"
  - "GEO-03 requirement: satisfied"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "geo_score range filter: DB-level WHERE on Page.geo_score (not Python-side filtering)"
    - "geo_check filter: subquery on AuditResult WHERE check_code=? AND status='pass'"
    - "invalid geo_check codes silently ignored (not in GEO_WEIGHTS.keys())"
    - "template filter form converted from JS-only to HTML GET form to carry geo params"
    - "pytestmark = pytest.mark.asyncio(scope='session') required for session-scoped smoke_client"

key-files:
  created:
    - tests/test_audit_geo_filter.py
  modified:
    - app/routers/audit.py
    - app/templates/audit/index.html

key-decisions:
  - "Filters converted from client-side JS to server-side GET form (required for geo params to reach router)"
  - "geo_check subquery uses AuditResult.status='pass' to find pages passing a specific GEO check"
  - "Template file is audit/index.html (not site_audit.html as plan stated — plan used wrong filename)"
  - "Tests use pytestmark=pytest.mark.asyncio(scope='session') matching test_ui_smoke.py pattern"

requirements-completed: [GEO-03]

# Metrics
duration: 5min
completed: 2026-04-08
---

# Phase 16 Plan 02: GEO Score Column + Filter Controls in Audit Table Summary

**geo_score column with color badges (green/yellow/red/gray) added to audit table; three filter controls (score min/max range + check code select) wired from server-side GET form through router Query params to DB-level WHERE clauses.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-08T10:28:00Z
- **Completed:** 2026-04-08T10:33:00Z
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments

- Router extended with `geo_score_min`, `geo_score_max`, `geo_check` Query params; DB-level filters applied via SQLAlchemy WHERE clauses and subquery on AuditResult
- Invalid `geo_check` codes silently ignored (not in `GEO_WEIGHTS.keys()`) matching audit-router convention
- Template filter section converted from pure JS client-side to HTML GET form to carry geo params on submit
- GEO column added to audit table with green (≥70) / yellow (40-69) / red (<40) / gray (None) Tailwind badges
- 5 smoke tests all pass; existing audit smoke tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit router + test file** - `70f1938` (feat)
2. **Task 2: Audit template — GEO column + filter controls** - `758ac07` (feat)

## Files Created/Modified

- `app/routers/audit.py` — 3 new Query params, DB filter logic, `geo_check_options` in template context, AuditResult + GEO_WEIGHTS imports
- `app/templates/audit/index.html` — GEO `<th>` + color-badge `<td>`, filter form converted to GET, 3 new filter inputs
- `tests/test_audit_geo_filter.py` — 5 smoke tests using session-scoped `smoke_client` fixture

## Deviations from Plan

### Auto-fixed Issues

**1. [Deviation - Filename] Template is audit/index.html, not site_audit.html**
- **Found during:** Task 2 - reading actual file system
- **Issue:** Plan referenced `app/templates/audit/site_audit.html` but the actual file is `app/templates/audit/index.html`
- **Fix:** Applied changes to the correct file; behavior identical to plan intent
- **Impact:** None

**2. [Deviation - Test scope] Tests require `pytestmark = pytest.mark.asyncio(scope="session")`**
- **Found during:** Task 1 test run — RuntimeError: Future attached to different loop
- **Issue:** `smoke_client` is session-scoped; default per-test event loop created a loop mismatch
- **Fix:** Added `pytestmark = pytest.mark.asyncio(scope="session")` matching `test_ui_smoke.py` pattern
- **Files modified:** `tests/test_audit_geo_filter.py`
- **Commit:** 70f1938

**3. [Rule 2 - Missing critical functionality] Filters converted to server-side GET form**
- **Found during:** Task 2 template analysis
- **Issue:** Existing filter controls used client-side JS (`filterTable()`); geo params must reach the server router via HTTP GET query string
- **Fix:** Converted filter div to `<form method="get">` with named inputs and explicit submit button; JS-based filterTable() retained for legacy search/type/status but geo filters now server-side
- **Files modified:** `app/templates/audit/index.html`
- **Commit:** 758ac07

## Known Stubs

None — geo_score column displays real data from `pages.geo_score` (populated by audit pipeline from Plan 16-01). Filter controls are fully wired end-to-end.

## Self-Check: PASSED
