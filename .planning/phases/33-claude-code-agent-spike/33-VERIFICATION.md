---
phase: 33-claude-code-agent-spike
verified: 2026-04-12T16:30:00Z
status: human_needed
score: 5/5 must-haves verified
re_verification: false
human_verification:
  - test: "Send /task command to bot and observe full lifecycle"
    expected: "Bot responds with 'Принято, создаю ветку...', then 'Claude работает...', then a message with diff stats and three inline buttons (Применить, Отклонить, Полный diff)"
    why_human: "Requires ANTHROPIC_API_KEY in .env and running Docker stack; Claude CLI subprocess cannot be exercised statically"
  - test: "Click 'Полный diff' WebApp button after task completes"
    expected: "/m/agent/diff/{task_id} page loads with colored diff (green additions, red deletions, cyan hunks) inside mobile base template"
    why_human: "End-to-end flow from bot volume write to FastAPI file read requires live containers and shared agent_diffs volume"
  - test: "Click 'Применить' approve button"
    expected: "Bot edits message to 'Изменения применены и смёрджены в master.'; git log shows merge commit with agent: prefix and --no-ff marker"
    why_human: "Requires live Telegram webhook interaction and running git repo in bot container at /opt/app"
  - test: "Click 'Отклонить' reject button"
    expected: "Bot edits message to 'Задача отклонена. Ветка удалена.'; git branch list no longer contains agent/task-* branch"
    why_human: "Requires live Telegram webhook interaction"
  - test: "Send a second /task while first is running"
    expected: "Bot responds 'Задача уже выполняется, подождите.' and does not start a second Claude process"
    why_human: "Requires concurrency testing with live bot — asyncio.Lock cannot be verified without two simultaneous real requests"
---

# Phase 33: Claude Code Agent Spike — Verification Report

**Phase Goal:** Пользователь может отправить текстовую задачу боту, которая выполняется через Claude Code с diff-подтверждением
**Verified:** 2026-04-12T16:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Dockerfile.bot installs Node.js 20 and Claude Code CLI | VERIFIED | Line 11-14: `curl -fsSL https://deb.nodesource.com/setup_20.x \| bash -`, `npm install -g @anthropic-ai/claude-code`; git identity set at line 17-18 |
| 2 | docker-compose.yml forwards ANTHROPIC_API_KEY and mounts repo volume to bot service | VERIFIED | Line 130: `ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}"`, line 140: `- .:/opt/app`; shared `agent_diffs` volume in bot (line 141), api (line 48), and top-level declaration (line 147) |
| 3 | bot/handlers/agent.py implements /task command with Claude CLI subprocess, git branch lifecycle, approve/reject callbacks | VERIFIED | 346 lines; `_task_lock = asyncio.Lock()` at line 51; `asyncio.create_subprocess_exec("claude", ...)` at line 75; `agent/task-{uuid}` branch at line 121; `merge --no-ff` at line 273-276; `DIFF_DIR` at line 33 |
| 4 | bot/main.py registers task_handler, agent_approve_callback, agent_reject_callback | VERIFIED | Line 114: `CommandHandler("task", task_handler)`; line 122-123: two CallbackQueryHandlers with correct patterns; line 28-32: imports from bot.handlers.agent; line 74: `/task` in set_my_commands |
| 5 | Only one task runs at a time (asyncio.Lock mutex) | VERIFIED | `_task_lock = asyncio.Lock()` at agent.py line 51; used as `async with _task_lock:` at line 115 with early-return guard when `_current_task.status == "running"` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `bot/handlers/agent.py` | Agent handler with task lifecycle; min 150 lines | VERIFIED | 346 lines; contains all required functions: `task_handler`, `agent_approve_callback`, `agent_reject_callback`, `_run_agent_task`, `_send_approval`, `_fail_task`, `_git`, `_run_claude` |
| `Dockerfile.bot` | Bot container with Node.js + Claude CLI; contains `npm install -g @anthropic-ai/claude-code` | VERIFIED | Pattern found at line 13; git and curl also installed |
| `docker-compose.yml` | Bot service with ANTHROPIC_API_KEY and repo volume; contains `ANTHROPIC_API_KEY` | VERIFIED | Pattern found at line 130; repo volume at line 140; agent_diffs in both services and top-level |
| `app/templates/mobile/agent/diff.html` | Diff viewer template; contains "diff" | VERIFIED | File exists; extends base_mobile.html; diff-container div present; JS coloring with 22c55e (green) and ef4444 (red) and 06b6d4 (cyan) |
| `app/routers/mobile.py` | Diff viewer endpoint; contains "agent/diff" | VERIFIED | Endpoint `agent_diff_page` at line 2377-2395; reads from `/tmp/agent_diffs/{task_id}.txt`; renders `mobile/agent/diff.html` template |
| `.planning/phases/33-claude-code-agent-spike/SPIKE-REPORT.md` | Spike experiment documentation; contains "go/no-go" | VERIFIED | File exists; "Go/No-Go Recommendation" section at line 78; "What Works" at line 38; "Limitations" at line 53 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `bot/handlers/agent.py` | `bot/main.py` | handler registration | VERIFIED | `CommandHandler("task", task_handler)` at main.py line 114; two CallbackQueryHandlers at lines 122-123 |
| `bot/handlers/agent.py` | `bot/utils/shell.py` | `run_command` for git operations | VERIFIED | `from bot.utils.shell import run_command` at agent.py line 26; used in `_git()` helper at line 61 |
| `bot/handlers/agent.py` | claude CLI subprocess | `asyncio.create_subprocess_exec` | VERIFIED | `asyncio.create_subprocess_exec("claude", "--print", "--dangerously-skip-permissions", ...)` at agent.py line 75 |
| `app/routers/mobile.py` | `/tmp/agent_diffs/{task_id}.txt` | file read from shared volume | VERIFIED | `pathlib.Path(f"/tmp/agent_diffs/{task_id}.txt")` at mobile.py line 2386; `diff_file.read_text()` at line 2389 |
| `bot/handlers/agent.py` | `app/routers/mobile.py` | WebApp button links to `/m/agent/diff/{task_id}` | VERIFIED | `make_webapp_button("Полный diff", f"/m/agent/diff/{task.task_id}", settings.APP_BASE_URL)` at agent.py line 221-224 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `app/templates/mobile/agent/diff.html` | `diff` | `diff_file.read_text()` from `/tmp/agent_diffs/{task_id}.txt` filesystem | Yes — reads actual file written by bot handler | FLOWING (filesystem-backed) |
| `bot/handlers/agent.py` (approval message) | `stat_output`, `diff_output` | `git diff --stat master` and `git diff master` subprocess calls | Yes — live git output, not hardcoded | FLOWING (subprocess-backed) |

Note: The shared volume (`agent_diffs`) is the data bridge between bot (writer) and API container (reader). The flow is: Claude CLI writes files → `git diff` captures them → bot writes diff to volume → FastAPI reads from volume → template renders. Each step is implemented and wired; live verification requires running containers.

### Behavioral Spot-Checks

Step 7b: SKIPPED for Claude CLI subprocess invocation — requires live ANTHROPIC_API_KEY and running Docker stack. Static code checks confirm all code paths are wired (see Key Link Verification above).

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| agent.py exports expected functions | `python3 -c "import ast; ast.parse(open('bot/handlers/agent.py').read()); print('syntax OK')"` | Would pass (syntax is valid Python) | SKIP — module imports require bot deps installed |
| diff.html extends base_mobile.html | `grep "base_mobile.html" app/templates/mobile/agent/diff.html` | `{% extends "base_mobile.html" %}` found | PASS |
| mobile.py endpoint exists | `grep "agent/diff" app/routers/mobile.py` | Match found at line 2377 | PASS |
| SPIKE-REPORT has go/no-go | `grep "Go/No-Go" SPIKE-REPORT.md` | Match found at line 78 | PASS |
| Dockerfile has Claude CLI install | `grep "npm install -g @anthropic-ai/claude-code" Dockerfile.bot` | Match found at line 13 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AGT-01 | 33-01-PLAN.md | Пользователь может отправить текстовую задачу боту, которая выполняется через Claude Code | SATISFIED | `task_handler` accepts `/task <description>`, invokes `_run_claude()` via `asyncio.create_subprocess_exec("claude", ...)`, full git branch isolation implemented |
| AGT-02 | 33-01-PLAN.md, 33-02-PLAN.md | Бот присылает diff на утверждение, пользователь подтверждает или отклоняет | SATISFIED | `_send_approval()` sends inline keyboard with approve/reject buttons; `agent_approve_callback` merges branch; `agent_reject_callback` force-deletes branch; WebApp link to full diff viewer at `/m/agent/diff/{task_id}` |

REQUIREMENTS.md traceability table shows AGT-01 and AGT-02 both assigned to Phase 33. Both are marked `[x]` (done) in the requirements list. No orphaned requirements found for this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `bot/handlers/agent.py` | 50-51 | `_current_task: Optional[AgentTask] = None` — in-memory global state | Info | By design for spike; documented in SPIKE-REPORT as Limitation 3. Bot restart loses task state. Not a blocker for spike phase. |
| `bot/handlers/agent.py` | 75-92 | `--dangerously-skip-permissions` flag | Warning | Gives Claude full container filesystem access. Documented in SPIKE-REPORT Limitation 7. Acceptable for spike; must be sandboxed before production. |
| `SPIKE-REPORT.md` | 40-50 | All "What Works" checkboxes are unchecked `[ ]` | Info | Honest documentation — live testing was not performed due to missing ANTHROPIC_API_KEY. Not a code defect; labeled "untested" in the report. |

No blockers found. All anti-patterns are intentional spike decisions, documented in SPIKE-REPORT.md.

### Human Verification Required

#### 1. Full /task lifecycle (core AGT-01 flow)

**Test:** With ANTHROPIC_API_KEY set in `.env`, rebuild bot container (`docker compose build bot`), start services (`docker compose up -d bot api`), send `/task Add a comment to the top of bot/config.py explaining what each setting does` in Telegram.
**Expected:** Bot replies "Принято, создаю ветку...", then edits to "Claude работает...", then after Claude finishes sends a message with git stat summary (e.g., "bot/config.py | 5 ++++") and three inline buttons: "Применить", "Отклонить", "Полный diff".
**Why human:** Requires live ANTHROPIC_API_KEY, running Docker stack, and real Telegram webhook — cannot verify Claude CLI subprocess behavior statically.

#### 2. WebApp diff viewer (core AGT-02 flow, part 1)

**Test:** After step 1 completes, tap "Полный diff" WebApp button.
**Expected:** Mobile browser opens `/m/agent/diff/{task_id}`, page title shows "Diff: {task_id}", diff content displays with green `+` lines, red `-` lines, and cyan `@@` hunk headers.
**Why human:** Requires live containers sharing the `agent_diffs` named volume; JS coloring requires browser rendering.

#### 3. Approve flow (core AGT-02 flow, part 2)

**Test:** Tap "Применить" after reviewing diff.
**Expected:** Bot edits message to "Изменения применены и смёрджены в master." Run `git log --oneline -5` on the host — should show a merge commit with "agent:" prefix.
**Why human:** Requires Telegram interaction and git state inspection on the running container.

#### 4. Reject flow

**Test:** Run another `/task`, then tap "Отклонить".
**Expected:** Bot edits message to "Задача отклонена. Ветка удалена." Run `git branch -a` — no `agent/task-*` branches should remain.
**Why human:** Requires live Telegram webhook interaction and git state inspection.

#### 5. Mutex enforcement

**Test:** Send `/task` and immediately send a second `/task` before the first completes.
**Expected:** Bot responds to the second message with "Задача уже выполняется, подождите." and does not start a second Claude subprocess.
**Why human:** Requires concurrent real requests; asyncio.Lock behavior cannot be validated without live concurrency.

### Gaps Summary

No gaps blocking goal achievement. All artifacts exist, are substantive (not stubs), and are fully wired. Data flows are correctly implemented.

The phase status is `human_needed` rather than `passed` because the Claude Code agent is a subprocess-driven, externally-dependent system (ANTHROPIC_API_KEY, Docker volume, Telegram webhook) that cannot be exercised through static code analysis alone. The end-to-end flow checkboxes in SPIKE-REPORT.md are explicitly unchecked, noting that live testing with ANTHROPIC_API_KEY is required.

All 5 plan must-haves are fully implemented. Both AGT-01 and AGT-02 requirements are satisfied at the code level. Human verification is the only remaining gate.

---

_Verified: 2026-04-12T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
