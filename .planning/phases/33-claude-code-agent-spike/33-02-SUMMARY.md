---
phase: 33-claude-code-agent-spike
plan: 02
subsystem: ui
tags: [telegram, claude-code, mobile-webapp, diff-viewer, jinja2, htmx]

# Dependency graph
requires:
  - phase: 33-01
    provides: bot/handlers/agent.py writing diffs to /tmp/agent_diffs/{task_id}.txt shared volume

provides:
  - /m/agent/diff/{task_id} FastAPI endpoint reading diff from shared agent_diffs volume
  - app/templates/mobile/agent/diff.html diff viewer with JS syntax coloring (green/red/cyan)
  - SPIKE-REPORT.md documenting experiment architecture, limitations, and go/no-go recommendation

affects:
  - any future agent hardening phase that wires persistent state or Celery task queue

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Shared named Docker volume (agent_diffs) read by FastAPI endpoint, written by bot handler
    - JS-based diff syntax coloring without external libraries (inline script, textContent split)

key-files:
  created:
    - app/templates/mobile/agent/diff.html
    - .planning/phases/33-claude-code-agent-spike/SPIKE-REPORT.md
  modified:
    - app/routers/mobile.py

key-decisions:
  - "Diff viewer is a standard /m/ endpoint (Depends(get_current_user), Depends(get_db)) consistent with all other mobile endpoints"
  - "JS syntax coloring applied client-side to avoid server-side HTML escaping conflicts with Jinja2 | e filter"
  - "SPIKE-REPORT status set to untested — no ANTHROPIC_API_KEY available for live verification in this environment"

patterns-established:
  - "Mobile agent pages live under app/templates/mobile/agent/ following existing mobile directory structure"

requirements-completed:
  - AGT-02

# Metrics
duration: 8min
completed: 2026-04-12
---

# Phase 33 Plan 02: Diff Viewer WebApp and Spike Report Summary

**Mobile WebApp diff viewer at /m/agent/diff/{task_id} with JS syntax coloring, reading from shared agent_diffs volume, plus SPIKE-REPORT.md documenting go/no-go recommendation for Claude Code agent production path**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-12T15:50:00Z
- **Completed:** 2026-04-12T15:58:00Z
- **Tasks:** 3 (Task 2 auto-approved as informational gate — no ANTHROPIC_API_KEY available)
- **Files modified:** 3

## Accomplishments

- Added `/m/agent/diff/{task_id}` endpoint to `app/routers/mobile.py` that reads diff from `/tmp/agent_diffs/{task_id}.txt` shared volume
- Created `app/templates/mobile/agent/diff.html` extending `base_mobile.html` with dark monospace pre block and client-side JS coloring (green for additions, red for deletions, cyan for hunks, grey for file headers)
- Created SPIKE-REPORT.md documenting full experiment architecture, 8 limitations, and a Go recommendation with 4-phase hardening path to production

## Task Commits

1. **Task 1: Diff viewer WebApp endpoint and template** - `238eef2` (feat)
2. **Task 2: End-to-end flow verification** - auto-approved (informational gate, status: untested)
3. **Task 3: Write SPIKE-REPORT.md** - `6898f1c` (docs)

## Files Created/Modified

- `/opt/seo-platform/app/routers/mobile.py` - Added `agent_diff_page` endpoint at `/m/agent/diff/{task_id}` (lines 2372-2395)
- `/opt/seo-platform/app/templates/mobile/agent/diff.html` - New diff viewer template with JS syntax coloring
- `/opt/seo-platform/.planning/phases/33-claude-code-agent-spike/SPIKE-REPORT.md` - Spike experiment documentation

## Decisions Made

- Jinja2 `| e` filter escapes the diff before rendering into the pre block; JS coloring then replaces `textContent` (already safe) with colored HTML spans — this avoids double-escaping
- Endpoint follows the exact same pattern as all other `/m/` endpoints (HTMLResponse, Depends(get_current_user), Depends(get_db)) for consistency
- SPIKE-REPORT marked as "untested" with TBD performance/cost fields — honest documentation of what requires live ANTHROPIC_API_KEY to verify

## Deviations from Plan

None - plan executed exactly as written. Task 2 checkpoint auto-approved per execution instructions (informational gate, no ANTHROPIC_API_KEY available).

## Issues Encountered

None.

## User Setup Required

`ANTHROPIC_API_KEY` must be set in `.env` for live end-to-end testing of the bot /task command. The diff viewer endpoint (`/m/agent/diff/{task_id}`) works without it — it reads from the filesystem. See SPIKE-REPORT.md for full test procedure.

## Next Phase Readiness

- Phase 33 (claude-code-agent-spike) is complete — all planned code is implemented and committed
- The spike is ready for live verification whenever ANTHROPIC_API_KEY is available: rebuild bot container, run `docker compose up -d bot api`, send `/task` in Telegram
- Production hardening roadmap documented in SPIKE-REPORT.md: Redis task state, cost logging, file path restrictions, Celery task queue

---
*Phase: 33-claude-code-agent-spike*
*Completed: 2026-04-12*
