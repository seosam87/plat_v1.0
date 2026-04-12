---
phase: 33-claude-code-agent-spike
plan: 01
subsystem: infra
tags: [claude-code, telegram, docker, git, asyncio, subprocess]

# Dependency graph
requires:
  - phase: 32-telegram-bot
    provides: bot framework with handlers, auth, shell utilities, miniapp buttons

provides:
  - Dockerfile.bot with Node.js 20 and Claude Code CLI installed
  - docker-compose.yml bot service with ANTHROPIC_API_KEY, repo volume, agent_diffs shared volume
  - bot/handlers/agent.py: full /task lifecycle with Claude CLI subprocess and git branch isolation
  - agent_approve_callback and agent_reject_callback for merge/discard flows
  - asyncio.Lock mutex enforcing one-task-at-a-time constraint

affects:
  - 33-02 (next plan: diff viewer WebApp endpoint uses agent_diffs volume)
  - any future phase adding agent capabilities

# Tech tracking
tech-stack:
  added:
    - Node.js 20 (in Dockerfile.bot via nodesource)
    - "@anthropic-ai/claude-code CLI (npm install -g)"
  patterns:
    - asyncio.create_subprocess_exec for Claude CLI subprocess
    - asyncio.Lock for single-task mutex
    - Git branch isolation per agent task (agent/task-{uuid})
    - Shared named Docker volume (agent_diffs) for diff handoff between bot and api containers
    - In-memory AgentTask dataclass (no DB for spike)

key-files:
  created:
    - bot/handlers/agent.py
  modified:
    - Dockerfile.bot
    - docker-compose.yml
    - bot/main.py

key-decisions:
  - "Claude CLI via asyncio.create_subprocess_exec with --print and --dangerously-skip-permissions for spike simplicity"
  - "In-memory AgentTask dataclass — no DB persistence for spike (Research Pattern 1)"
  - "asyncio.Lock mutex for one-task-at-a-time constraint (D-05)"
  - "agent_diffs named volume for diff handoff to future WebApp viewer (D-11)"
  - "merge --no-ff on approve to preserve branch history (D-04)"

patterns-established:
  - "Agent task lifecycle: receive -> lock check -> branch -> Claude -> diff -> approve/reject buttons"
  - "_git() helper wraps run_command with REPO_PATH for all git operations"
  - "_fail_task() always cleans up: checkout master, delete branch, clean working tree"

requirements-completed:
  - AGT-01
  - AGT-02

# Metrics
duration: 12min
completed: 2026-04-12
---

# Phase 33 Plan 01: Claude Code Agent Infrastructure Summary

**Claude Code agent handler with git branch isolation, asyncio.Lock mutex, subprocess CLI runner, and approve/reject inline keyboard wired into existing Telegram bot**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-12T15:35:00Z
- **Completed:** 2026-04-12T15:47:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Dockerfile.bot now installs Node.js 20 and Claude Code CLI (`npm install -g @anthropic-ai/claude-code`) with git identity set for merge commits
- docker-compose.yml bot service gets ANTHROPIC_API_KEY env var, repo volume mount (`.:/opt/app`), and shared `agent_diffs` named volume; api service also mounts `agent_diffs`
- bot/handlers/agent.py implements the full `/task` lifecycle: receive description -> check asyncio.Lock -> create `agent/task-{uuid}` branch -> run Claude CLI as subprocess -> collect git diff -> write diff to shared volume -> send stat summary with approve/reject inline buttons
- Approve flow: `git merge --no-ff` into master, delete agent branch
- Reject flow: `git branch -D` agent branch, return to master
- Error flow: auto-cleanup (checkout master, force-delete branch, `git clean -fd`)

## Task Commits

1. **Task 1: Docker infrastructure — Node.js, Claude CLI, volume mount, env vars** - `d7a1c83` (feat)
2. **Task 2: Agent handler + main.py registration** - `79cb1ce` (feat)

## Files Created/Modified

- `/opt/seo-platform/Dockerfile.bot` - Added curl, git, Node.js 20, claude CLI npm install, git global identity config
- `/opt/seo-platform/docker-compose.yml` - Added ANTHROPIC_API_KEY, repo volume mount and agent_diffs volume to bot service; agent_diffs to api service; agent_diffs top-level named volume
- `/opt/seo-platform/bot/handlers/agent.py` - New file: full agent handler with task_handler, agent_approve_callback, agent_reject_callback, _run_agent_task, _send_approval, _fail_task, _git helper, _run_claude runner
- `/opt/seo-platform/bot/main.py` - Added import of agent handlers, CommandHandler('task'), two CallbackQueryHandlers, /task in set_my_commands

## Decisions Made

- Used `--dangerously-skip-permissions` for spike to avoid interactive permission prompts during unattended CLI execution
- In-memory `AgentTask` dataclass instead of DB persistence — sufficient for single-task spike (per Research Pattern 1)
- `asyncio.Lock` (not a queue) — one task at a time, new requests rejected while running
- `agent/task-{8-char-uuid}` branch naming for easy identification and cleanup
- Diff truncated at 3000 chars for Telegram message limit compatibility
- Git stat summary (not full diff) shown in approval message; full diff written to `agent_diffs` volume for future WebApp viewer

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

`ANTHROPIC_API_KEY` must be set in the `.env` file for the bot container to authenticate Claude Code CLI calls. No other external service configuration required.

## Next Phase Readiness

- Plan 33-02 (diff viewer WebApp endpoint) can now read diffs from `/tmp/agent_diffs/{task_id}.txt` in the api container via the shared named volume
- Bot handlers are live and registered; Docker rebuild required to install Claude CLI in the bot container image

---
*Phase: 33-claude-code-agent-spike*
*Completed: 2026-04-12*
