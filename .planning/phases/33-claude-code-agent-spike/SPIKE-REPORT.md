# Spike Report: Claude Code Agent via Telegram Bot

**Date:** 2026-04-12
**Phase:** 33-claude-code-agent-spike
**Status:** untested — requires live testing with ANTHROPIC_API_KEY

## What We Built

A Telegram bot `/task` command that:
1. Accepts a text task description from an authorized user
2. Creates an isolated git branch (`agent/task-{uuid}`)
3. Runs Claude Code CLI (`claude --print --dangerously-skip-permissions --allowedTools Edit,Write,Bash,Read -p '{task}'`) as a subprocess in the bot container
4. Commits any changes Claude makes, then collects `git diff master`
5. Sends diff summary (file stats) to chat with inline approve/reject buttons
6. Provides a WebApp link to full diff view with syntax coloring
7. On approve: merges branch into master with `--no-ff`
8. On reject: force-deletes the branch
9. On error/timeout: auto-cleans up the branch

## Architecture

### Components
- **bot/handlers/agent.py** — handler + subprocess + git lifecycle
- **Dockerfile.bot** — Node.js 20 + `@anthropic-ai/claude-code` CLI
- **docker-compose.yml** — ANTHROPIC_API_KEY env, repo volume mount (`.:/opt/app`), shared `agent_diffs` named volume
- **app/routers/mobile.py** + **app/templates/mobile/agent/diff.html** — WebApp diff viewer

### Key Decisions
- In-memory state (no DB) — sufficient for one-task-at-a-time constraint
- `asyncio.Lock` mutex — prevents concurrent Claude runs; new requests rejected while one is running
- Shared filesystem volume (`/tmp/agent_diffs`) — simplest cross-container diff delivery from bot to api
- `--output-format text` — simpler than JSON for spike; actual changes captured by `git diff`
- `--dangerously-skip-permissions` — required for non-interactive container context
- `--allowedTools Edit,Write,Bash,Read` — restricts Claude tool access to file operations only
- Claude output truncated to last 3000 chars to stay within Telegram message limits
- Git stat summary (not full diff) shown in approval message; full diff written to `agent_diffs` volume for WebApp viewer

## What Works

- [ ] Bot accepts /task command and validates single-task mutex
- [ ] Git branch creation and isolation (`agent/task-{8-char-uuid}`)
- [ ] Claude CLI subprocess invocation with 360s timeout
- [ ] Auto-commit of Claude changes before diff collection
- [ ] Diff collection and stat formatting
- [ ] Diff written to shared volume for WebApp viewer
- [ ] Inline keyboard approve/reject flow
- [ ] WebApp diff viewer with syntax coloring (green/red/cyan)
- [ ] Branch merge on approve (`--no-ff`), deletion on reject
- [ ] Error cleanup (checkout master, force-delete branch, `git clean -fd`)

*Note: Checkboxes above represent implemented code paths. Live verification requires ANTHROPIC_API_KEY in the deployment environment.*

## What Doesn't Work / Limitations

1. **Single task at a time** — by design for spike; production needs a task queue (Celery)
2. **No conversation** — Claude gets one prompt, no follow-up; may need clarification for complex tasks
3. **In-memory state** — bot restart loses current task state; production needs DB/Redis persistence
4. **No task history** — no record of past tasks; production needs audit log table
5. **Large diffs** — Telegram message limit forces truncation; WebApp shows full diff but mobile UX may suffer for 1000+ line diffs
6. **No cost tracking** — Claude API costs are not logged or limited per task
7. **Security** — `--dangerously-skip-permissions` gives Claude full system access within the container; production needs sandboxing (restricted filesystem, no network access for agent)
8. **No staging environment** — Claude runs directly against the production repo; mistakes go to master immediately on approve

## Performance Observations

- Claude CLI startup: TBD — requires live testing with ANTHROPIC_API_KEY
- Typical task execution: TBD — requires live testing with ANTHROPIC_API_KEY
- Git operations: < 1s each (expected)
- Diff viewer page load: < 1s (expected, reads from local filesystem)
- Subprocess timeout configured at 360s (6 minutes)

## Cost Observations

- Typical small task: TBD — requires live testing with ANTHROPIC_API_KEY
- ANTHROPIC_API_KEY is shared; no per-user billing or cost caps implemented
- `--allowedTools Edit,Write,Bash,Read` limits tool calls, which reduces token consumption vs unrestricted mode

## Go/No-Go Recommendation

### Go (with conditions)
The mechanic is architecturally sound for simple, well-defined tasks. All code paths are implemented and wired end-to-end. Recommended path to production:

1. **Phase 1 (hardening):** Add Redis-backed task state + task history table + cost logging per task
2. **Phase 2 (safety):** Add file path restrictions, cost caps per task, sandboxed Docker execution (read-only mounts except repo dir)
3. **Phase 3 (UX):** Add conversation mode (follow-up questions), task templates, progress streaming via WebApp
4. **Phase 4 (scale):** Task queue (Celery), concurrent execution, per-user quotas

### No-Go conditions
- If Claude CLI latency > 5 minutes for typical tasks — reconsider approach, use streaming API instead
- If API costs > $1/task average — add cost caps before production
- If merge conflicts are frequent — need conflict resolution UX before enabling for team

## Files Created/Modified

| File | Action |
|------|--------|
| bot/handlers/agent.py | Created — full agent handler with /task lifecycle |
| bot/main.py | Modified — CommandHandler('task'), two CallbackQueryHandlers, /task in set_my_commands |
| Dockerfile.bot | Modified — curl, git, Node.js 20, claude CLI npm install, git global identity config |
| docker-compose.yml | Modified — ANTHROPIC_API_KEY, repo volume mount, agent_diffs named volume (bot + api services) |
| app/routers/mobile.py | Modified — /m/agent/diff/{task_id} endpoint reading from /tmp/agent_diffs/ |
| app/templates/mobile/agent/diff.html | Created — diff viewer template with JS syntax coloring |
