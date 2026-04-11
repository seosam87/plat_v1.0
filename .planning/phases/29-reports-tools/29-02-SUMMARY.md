---
phase: 29-reports-tools
plan: "02"
subsystem: ui
tags: [mobile, htmx, celery, jinja2, tools, polling]

requires:
  - phase: 29-01
    provides: mobile.py with /m/reports endpoints, mobile_templates instance
  - phase: 24-25-tools
    provides: TOOL_REGISTRY, _get_tool_models, _get_tool_task, _check_oauth_token_sync, 6 Job models

provides:
  - "GET /m/tools — single-column card list of 6 SEO tools"
  - "GET /m/tools/{slug}/run — tool entry form with textarea+file upload and OAuth redirect"
  - "POST /m/tools/{slug}/run — input parsing, Job creation, Celery dispatch, polling partial"
  - "GET /m/tools/{slug}/jobs/{job_id}/status — HTMX polling partial (stops on done/error)"
  - "app/services/mobile_tools_service.py — parse_tool_input (D-11) + get_job_for_user"

affects:
  - 29-03
  - phase-36-recurring-jobs

tech-stack:
  added: []
  patterns:
    - "parse_tool_input: mutual exclusivity guard for textarea vs file upload (D-11)"
    - "HTMX polling every 3s stops by omitting hx-trigger on done/error branches (Research Pitfall 3)"
    - "D-10: OAuth redirect via asyncio.run_in_executor for sync _check_oauth_token_sync"
    - "brief slug uses 4-step celery_chain (reused verbatim from tools.py)"

key-files:
  created:
    - app/services/mobile_tools_service.py
    - app/templates/mobile/tools/list.html
    - app/templates/mobile/tools/run.html
    - app/templates/mobile/tools/partials/tool_progress.html
  modified:
    - app/routers/mobile.py

key-decisions:
  - "TOOL_REGISTRY and helpers imported lazily inside endpoint functions to avoid circular imports"
  - "OAuth check uses asyncio.get_event_loop().run_in_executor for sync helper"
  - "Status normalization: pending/running/started → started; complete/done/partial → done"
  - "processed_count falls back to total on done (not all job models have this column)"

patterns-established:
  - "Tool progress partial: hx-trigger present only in started/running state — stops polling automatically"
  - "File upload via enctype=multipart/form-data + hx-encoding=multipart/form-data in HTMX form"

requirements-completed:
  - TLS-01

duration: 2min
completed: "2026-04-11"
---

# Phase 29 Plan 02: Tools List & Run Summary

**Mobile /m/tools UI layer: 4 endpoints + 3 templates + input parsing service — users can list and launch all 6 SEO tools from phone with HTMX 3s polling progress**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-11T22:21:37Z
- **Completed:** 2026-04-11T22:23:58Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `mobile_tools_service.py` with `parse_tool_input` (D-11 mutual exclusivity, XLSX via openpyxl, TXT via splitlines) and `get_job_for_user` ownership check
- 4 new endpoints appended to `mobile.py`: tools list, run form, run submit, status polling — all reuse TOOL_REGISTRY and task helpers from `tools.py` without duplication
- 3 Jinja2 templates: `list.html` (card list with amber Wordstat badge), `run.html` (textarea+file+optional domain/region fields), `tool_progress.html` (polling partial that stops on done/error per Research Pitfall 3)

## Task Commits

1. **Task 1: mobile_tools_service.py** - `fbbbb65` (feat)
2. **Task 2: Mobile tools endpoints** - `b7844ae` (feat)
3. **Task 3: Mobile tool templates** - `df93dbb` (feat)

## Files Created/Modified

- `app/services/mobile_tools_service.py` — parse_tool_input + get_job_for_user helpers
- `app/routers/mobile.py` — 4 new /m/tools/* endpoints appended, new imports added
- `app/templates/mobile/tools/list.html` — single-column card list with OAuth badge
- `app/templates/mobile/tools/run.html` — multipart form with JS D-11 guard
- `app/templates/mobile/tools/partials/tool_progress.html` — HTMX polling partial

## Decisions Made

- Lazy imports inside endpoint functions for TOOL_REGISTRY and helpers to avoid circular import (tools.py → mobile.py → tools.py)
- `asyncio.get_event_loop().run_in_executor` for `_check_oauth_token_sync` since it's a sync function called from async context
- Status normalization handles both older `complete` and newer `done` status values across all 6 Job models
- `processed_count` field fallback to `total` on done state since not all job models track incremental progress

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TLS-01 complete: tool list + run form + polling progress
- Plan 03 adds: in-app notify on completion + `/m/tools/{slug}/jobs/{job_id}` result view (TLS-02)
- All 6 tool slugs registered and reachable from mobile UI

---
*Phase: 29-reports-tools*
*Completed: 2026-04-11*

## Self-Check: PASSED

All 5 files found. All 3 task commits verified in git log.
