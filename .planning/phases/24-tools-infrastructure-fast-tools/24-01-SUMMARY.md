---
phase: 24-tools-infrastructure-fast-tools
plan: 01
subsystem: ui
tags: [tools, navigation, sidebar, celery, htmx, openpyxl, smoke-test]

requires:
  - phase: 23-document-generator
    provides: smoke seed pattern (SMOKE_IDS, seed_core/seed_extended) reused here

provides:
  - TOOL_REGISTRY dispatch dict with per-tool field mappings (form_field, input_col, count_col)
  - 7 route handlers under /ui/tools/ (index, landing, submit, status, export, delete, results)
  - Sidebar "Инструменты" entry with wrench icon
  - Celery includes for 3 tool task modules
  - Smoke seed entry for CommerceCheckJob

affects:
  - 24-02-commercialization
  - 24-03-meta-parser
  - 24-04-relevant-url
  - 24-05-smoke-wire

tech-stack:
  added: []
  patterns:
    - "TOOL_REGISTRY dispatch: slug → {name, form_field, input_col, count_col, limit, has_domain_field}"
    - "Lazy model/task import via _get_tool_models/_get_tool_task to avoid circular imports"
    - "POST handler reads form field dynamically via registry[slug]['form_field']"
    - "Job kwargs constructed via **{registry[slug]['input_col']: lines, registry[slug]['count_col']: len(lines)}"

key-files:
  created:
    - app/templates/tools/index.html (replaced stub with card grid)
  modified:
    - app/navigation.py (added tools flat nav entry after keyword-suggest)
    - app/templates/components/sidebar.html (added wrench icon to both icon blocks)
    - app/routers/tools.py (replaced stub with full TOOL_REGISTRY + 7 handlers)
    - app/celery_app.py (added 3 tool task modules to include list)
    - tests/fixtures/smoke_seed.py (added tool_job_id/tool_slug + CommerceCheckJob seed)
    - tests/_smoke_helpers.py (slug in param_map, /status as partial, export in SMOKE_SKIP)

key-decisions:
  - "Lazy imports for tool models/tasks prevent circular import errors before Plans 02-04 create the files"
  - "TOOL_REGISTRY includes form_field/input_col/count_col so POST handler is generic across all 3 tools"
  - "Export route added to SMOKE_SKIP (StreamingResponse, not HTML)"
  - "Route order matters: /status and /export declared before /{job_id} catch-all per RESEARCH Pitfall 5"

patterns-established:
  - "Pattern: tool slug → TOOL_REGISTRY lookup → dynamic field names; avoids hardcoded input_phrases/phrase_count"
  - "Pattern: smoke seed tool job uses CommerceCheckJob (first available model); other tool models seeded by their respective plans"

requirements-completed:
  - TOOL-INFRA-01
  - TOOL-INFRA-02

duration: 15min
completed: 2026-04-09
---

# Phase 24 Plan 01: Tools Infrastructure Summary

**Shared tools infrastructure: TOOL_REGISTRY dispatch router with 7 handlers, sidebar "Инструменты" entry, Celery task registration, and smoke seed foundation for Plans 02-04**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-09T23:46:00Z
- **Completed:** 2026-04-09T23:50:41Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Built TOOL_REGISTRY with per-tool field mappings enabling a single generic POST handler for all 3 tools
- Replaced stub tools router with 7 full route handlers (index, landing, submit, status, export, delete, results) with lazy model imports
- Added "Инструменты" sidebar entry with wrench icon and 3-card grid index page
- Registered 3 new Celery task modules; smoke infrastructure updated with slug param and status partial detection

## Task Commits

1. **Task 1: Sidebar entry + TOOL_REGISTRY router + card grid index page** - `782908a` (feat)
2. **Task 2: Celery registration + smoke seed + partial detection** - `02b4800` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `app/navigation.py` — Added "tools" flat entry with wrench icon after keyword-suggest
- `app/templates/components/sidebar.html` — Added wrench SVG to both icon dispatch blocks
- `app/routers/tools.py` — Full rewrite: TOOL_REGISTRY + _get_tool_models + _get_tool_task + 7 handlers
- `app/templates/tools/index.html` — Replaced 6-item empty-state list with 3-card grid using TOOL_REGISTRY
- `app/celery_app.py` — Added commerce_check_tasks, meta_parse_tasks, relevant_url_tasks
- `tests/fixtures/smoke_seed.py` — tool_job_id/tool_slug in SMOKE_IDS; CommerceCheckJob + Result seeded
- `tests/_smoke_helpers.py` — slug in build_param_map; /status as partial; export in SMOKE_SKIP

## Decisions Made

- Lazy imports for tool models/tasks (inside `_get_tool_models`/`_get_tool_task`) prevent ImportError before Plans 02-04 create those files
- TOOL_REGISTRY carries `form_field`, `input_col`, `count_col` so the POST handler doesn't hardcode per-tool column names
- Export route skipped in smoke tests (returns StreamingResponse binary, not HTML)
- Route registration order preserved: specific paths (/status, /export) before catch-all (/{job_id})

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plans 02, 03, 04 can now create their model files and tasks; the router's lazy imports will resolve automatically
- Plan 05 smoke test will find tool routes via SMOKE_IDS slug/job_id params and status partial detection
- The tools index page renders 3 cards from TOOL_REGISTRY; individual tool pages (landing/results) require model files from Plans 02-04

---
*Phase: 24-tools-infrastructure-fast-tools*
*Completed: 2026-04-09*
