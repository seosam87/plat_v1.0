# Phase 33: Claude Code Agent (Spike) - Research

**Researched:** 2026-04-12
**Domain:** Claude Code CLI subprocess integration in Telegram bot, git branch isolation, diff WebApp
**Confidence:** HIGH (all key components verified against live codebase and running Claude CLI)

## Summary

Phase 33 implements a spike experiment: a Telegram `/task` command that runs Claude Code CLI as a subprocess, isolates work in a git branch, collects a diff, and presents it via inline buttons (approve → merge, reject → delete branch). The scope is deliberately narrow — prove the mechanic works, then document go/no-go.

All infrastructure is already in place from Phase 32: the bot has subprocess runner (`run_command()`), inline confirmation flow (`devops.py`), WebApp buttons, and `@require_auth`. The mobile `/m/` router has an established template pattern. The only missing pieces are the agent handler (`bot/handlers/agent.py`), an in-memory mutex (module-level dict), Docker changes to install Claude CLI, and the diff-viewer WebApp endpoint.

**Primary recommendation:** Build `bot/handlers/agent.py` modeled directly on `devops.py` confirmation pattern. Run Claude CLI with `asyncio.create_subprocess_exec()` (extend `run_command()` with a configurable timeout). Store task state in a module-level dataclass (no DB needed for spike). Render diff in `/m/agent/diff/{task_id}` with a `<pre>` block — no JS syntax highlighting required for spike validity.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Claude Code CLI через subprocess — `claude --print -p '{task}' --allowedTools Edit,Write,Bash,Read`. Запускается внутри bot контейнера.
- **D-02:** Claude CLI устанавливается в Dockerfile.bot (npm install -g @anthropic-ai/claude-code). Рабочая директория — монтированный репозиторий проекта.
- **D-03:** ANTHROPIC_API_KEY передаётся как env variable в docker-compose.yml для bot сервиса.
- **D-04:** Git branch flow: создать `agent/task-{uuid}` → Claude работает в ней → `git diff master` → показать пользователю → approve=merge+delete branch, reject=delete branch.
- **D-05:** Одна задача одновременно. Если Claude занят — ответить «Задача выполняется, подождите».
- **D-06:** Статус-сообщения в чат: «⏳ Принято, создаю ветку...» → «🔄 Claude работает...» → «✅ Готово, вот diff:» или «❌ Ошибка: {message}».
- **D-07:** Минимальные ограничения для spike: `--allowedTools Edit,Write,Bash,Read` — полный набор инструментов Claude Code.
- **D-08:** Timeout — Claude's discretion (рекомендуется 5-10 минут в зависимости от сложности).
- **D-09:** Claude работает в репозитории проекта (volume mount). Изменения изолированы в отдельной git ветке.
- **D-10:** Краткий summary в чате: список изменённых файлов + stat (lines added/removed) + inline-кнопки «✅ Применить» / «❌ Отклонить» + WebApp-кнопка «Полный diff».
- **D-11:** Полный diff на WebApp-странице `/m/agent/diff/{task_id}` — отдельный мобильный endpoint с подсветкой синтаксиса.
- **D-12:** При ошибке Claude (timeout, crash) — сообщение с ошибкой + авто-удаление ветки.
- **D-13:** SPIKE-REPORT.md в .planning/phases/33-claude-code-agent-spike/ — что попробовали, что работает, что нет, go/no-go рекомендация для production.

### Claude's Discretion

- Конкретный timeout значение (5-10 мин)
- Формат system prompt для Claude Code (контекст проекта, ограничения)
- Структура модели AgentTask для хранения состояния задачи
- Реализация diff-viewer WebApp страницы (простой pre-formatted text vs syntax highlighting)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGT-01 | Пользователь может отправить текстовую задачу боту, которая выполняется через Claude Code | D-01/D-02 verified: Claude CLI 2.1.104 installed at /usr/bin/claude, `--print` mode confirmed, `asyncio.create_subprocess_exec()` from existing `run_command()` pattern |
| AGT-02 | Бот присылает diff на утверждение, пользователь подтверждает или отклоняет | D-04/D-10 verified: git diff + inline buttons pattern confirmed from `devops.py` confirmation flow, callback_data routing already established |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | 21.x (pinned in bot/requirements.txt) | Handler registration, InlineKeyboard, CallbackQuery | Already in use across all bot handlers |
| asyncio | stdlib | Subprocess management, mutex via asyncio.Lock | Used by existing `run_command()` in shell.py |
| Claude Code CLI | 2.1.104 (verified at /usr/bin/claude) | Task execution engine | Locked by D-01; `--print` mode confirmed |
| git | system | Branch create/diff/merge/delete | Available in python:3.12-slim; run via subprocess |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| loguru | 0.7.x | Structured logging | Already in all bot handlers; use for task lifecycle events |
| FastAPI + Jinja2 | 0.115.x / 3.1.x | Diff viewer WebApp endpoint | Extend existing mobile router (`app/routers/mobile.py`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Module-level `asyncio.Lock` for mutex | Redis SETNX | Redis is overkill for a spike with one worker process; module-level lock is correct for single-process bot |
| `asyncio.create_subprocess_exec()` | `subprocess.run()` | `subprocess.run()` blocks the event loop — never use in async context |
| `git diff master` | `git diff origin/master` | Local master is sufficient for spike; no fetch needed |

**Installation (Dockerfile.bot additions):**
```bash
# Node.js + Claude CLI
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*
```

**Environment (docker-compose.yml bot service addition):**
```yaml
environment:
  TELEGRAM_BOT_PORT: "8443"
  ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}"
```

**Volume (docker-compose.yml bot service addition):**
```yaml
volumes:
  - .:/opt/app  # mount entire repo so Claude can edit files
```

## Architecture Patterns

### Recommended Project Structure (additions only)
```
bot/
├── handlers/
│   └── agent.py          # NEW: /task handler, approve/reject callbacks
└── utils/
    └── shell.py          # EXTEND: add run_command_long() with 600s timeout

app/
├── routers/
│   └── mobile.py         # EXTEND: add /m/agent/diff/{task_id} endpoint
└── templates/
    └── mobile/
        └── agent/
            └── diff.html # NEW: diff viewer template
```

### Pattern 1: AgentTask State (in-memory, spike-only)
**What:** Module-level singleton holding the current task state. No DB, no Redis.
**When to use:** Single-task-at-a-time constraint (D-05) means one live state object suffices.
**Example:**
```python
# bot/handlers/agent.py
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentTask:
    task_id: str
    chat_id: int
    message_id: int          # message to edit with status updates
    branch: str
    task_text: str
    diff: str = ""
    summary: str = ""
    status: str = "running"  # running | awaiting_approval | done | error

_current_task: Optional[AgentTask] = None
_task_lock = asyncio.Lock()
```

### Pattern 2: /task Command Handler Flow
**What:** Non-blocking handler — immediately acknowledges, spawns background asyncio.Task.
**When to use:** Long operations in PTB (python-telegram-bot) must never block the event loop.
**Example:**
```python
@require_auth
async def task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_task
    msg = update.effective_message
    task_text = " ".join(context.args) if context.args else ""

    if not task_text.strip():
        await msg.reply_text("Использование: /task <описание задачи>")
        return

    async with _task_lock:
        if _current_task and _current_task.status == "running":
            await msg.reply_text("⏳ Задача уже выполняется, подождите.")
            return

        task_id = str(uuid.uuid4())[:8]
        branch = f"agent/task-{task_id}"
        sent = await msg.reply_text("⏳ Принято, создаю ветку...")
        _current_task = AgentTask(
            task_id=task_id,
            chat_id=msg.chat_id,
            message_id=sent.message_id,
            branch=branch,
            task_text=task_text,
        )

    asyncio.create_task(_run_agent_task(context, _current_task))
```

### Pattern 3: Subprocess Claude CLI Invocation
**What:** Run Claude CLI in the repo directory with a long timeout; collect stdout.
**When to use:** D-01 mandates `claude --print -p '{task}' --allowedTools Edit,Write,Bash,Read`
**Critical flags verified:**
- `--print` / `-p`: non-interactive, returns result to stdout and exits
- `--allowedTools`: space or comma-separated; `Edit,Write,Bash,Read` is valid
- `--output-format json`: returns structured JSON with `result`, `cost_usd`, `num_turns` fields
- `--dangerously-skip-permissions`: bypasses workspace trust dialog in container context (no interactive TTY)
- Working directory: set via `cwd` parameter of `create_subprocess_exec()`

```python
async def run_claude_task(task_text: str, repo_path: str, timeout: int = 360) -> tuple[int, str]:
    """Run Claude CLI and return (returncode, stdout)."""
    proc = await asyncio.create_subprocess_exec(
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--allowedTools", "Edit,Write,Bash,Read",
        "--output-format", "json",
        "-p", task_text,
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ},  # forward ANTHROPIC_API_KEY
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(errors="replace")
    except asyncio.TimeoutError:
        proc.kill()
        return 1, f"Timeout: Claude did not complete within {timeout}s"
```

### Pattern 4: Git Branch Lifecycle
**What:** Create branch → Claude works → diff → merge or delete.
**When to use:** D-04 mandates this exact flow.
**Example:**
```python
REPO_PATH = "/opt/app"  # volume-mounted repo root in bot container

async def _git(args: list[str]) -> tuple[int, str]:
    return await run_command(["git", "-C", REPO_PATH] + args, timeout=30)

async def _run_agent_task(context, task: AgentTask) -> None:
    # 1. Create branch
    rc, out = await _git(["checkout", "-b", task.branch])
    if rc != 0:
        await _fail_task(context, task, f"Не удалось создать ветку: {out}")
        return

    # 2. Status update
    await context.bot.edit_message_text(
        chat_id=task.chat_id, message_id=task.message_id,
        text="🔄 Claude работает..."
    )

    # 3. Run Claude
    rc, output = await run_claude_task(task.task_text, REPO_PATH, timeout=360)
    if rc != 0:
        await _cleanup_branch(task.branch)
        await _fail_task(context, task, output[-500:])
        return

    # 4. Collect diff
    _, diff_output = await _git(["diff", "master"])
    _, stat_output = await _git(["diff", "--stat", "master"])

    task.diff = diff_output
    task.summary = stat_output
    task.status = "awaiting_approval"

    # 5. Present to user
    await _send_approval_message(context, task, stat_output)
```

### Pattern 5: Approval Message with Inline Buttons
**What:** Edit status message or send new message with diff summary + inline buttons.
**When to use:** D-10 mandates inline buttons + WebApp diff link.
**Example:**
```python
async def _send_approval_message(context, task: AgentTask, stat: str) -> None:
    from bot.utils.formatters import bold, code_block
    from bot.handlers.miniapp import make_webapp_button
    from bot.config import settings

    webapp_btn = make_webapp_button(
        "Полный diff", f"/m/agent/diff/{task.task_id}", settings.APP_BASE_URL
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Применить", callback_data=f"agent_approve:{task.task_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"agent_reject:{task.task_id}"),
        ],
        [webapp_btn],
    ])
    text = bold("✅ Claude завершил задачу") + "\n\n" + code_block(stat or "Нет изменений")
    await context.bot.send_message(
        chat_id=task.chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
```

### Pattern 6: Approve/Reject Callbacks
**What:** Callback handlers for `agent_approve:*` and `agent_reject:*` patterns.
**When to use:** Mirrors `confirm_callback`/`cancel_callback` pattern from `devops.py`.
**Example:**
```python
@require_auth
async def agent_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Применяю...")
    task_id = query.data.split(":", 1)[1]

    if not _current_task or _current_task.task_id != task_id:
        await query.edit_message_text("Задача не найдена или уже обработана.")
        return

    # git merge --no-ff branch into master
    rc, out = await _git(["merge", "--no-ff", _current_task.branch, "-m", f"agent: {_current_task.task_text[:60]}"])
    if rc == 0:
        await _git(["branch", "-d", _current_task.branch])
        await query.edit_message_text("✅ Изменения применены и смёрджены в master.")
    else:
        await query.edit_message_text(f"❌ Merge failed:\n<pre>{out[-500:]}</pre>", parse_mode="HTML")

    _current_task.status = "done"


@require_auth
async def agent_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    task_id = query.data.split(":", 1)[1]

    if _current_task and _current_task.task_id == task_id:
        await _git(["checkout", "master"])
        await _git(["branch", "-D", _current_task.branch])
        _current_task.status = "done"

    await query.edit_message_text("❌ Задача отклонена. Ветка удалена.")
```

### Pattern 7: Diff Viewer WebApp Endpoint
**What:** New mobile endpoint in `app/routers/mobile.py` that serves the full diff.
**When to use:** D-11 mandates `/m/agent/diff/{task_id}` page.
**Challenge:** The diff lives in the bot process (in-memory). The FastAPI process is separate. Solutions for spike:
- **Option A (recommended for spike):** Write diff to a temp file at `/tmp/agent_diff_{task_id}.txt`; FastAPI reads the file. Simple, works across container boundary only if both containers share `/tmp` volume.
- **Option B:** Store diff in Redis (shared between bot and API containers). More robust but adds complexity.
- **Option C:** Bot calls FastAPI internal API to register diff. Introduces coupling.

For a spike, **Option A with a shared volume** is cleanest. The bot and API containers both mount a shared volume (e.g., `agent_diffs:/tmp/agent_diffs`). Bot writes diff file; FastAPI reads it.

```python
# app/routers/mobile.py — new endpoint
@router.get("/agent/diff/{task_id}", response_class=HTMLResponse)
async def agent_diff_page(
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    import pathlib
    diff_file = pathlib.Path(f"/tmp/agent_diffs/{task_id}.txt")
    diff_content = diff_file.read_text(errors="replace") if diff_file.exists() else "Diff не найден."
    return mobile_templates.TemplateResponse(
        "mobile/agent/diff.html",
        {"request": request, "task_id": task_id, "diff": diff_content},
    )
```

### Anti-Patterns to Avoid
- **Blocking subprocess in async handler:** Never call `subprocess.run()` or any sync I/O directly in an async handler. Always use `asyncio.create_subprocess_exec()`.
- **Not switching back to master after branch:** After Claude finishes (success or failure), always run `git checkout master` before any cleanup — otherwise the next branch create will fail.
- **Editing the same message after PTB timeout:** If Claude takes > 60s, the message the handler sent may be stale. Always use `context.bot.edit_message_text()` with stored `chat_id`/`message_id` rather than `update.message.reply_text()`.
- **Not passing `--dangerously-skip-permissions`:** In a Docker container there's no interactive TTY. Claude CLI will pause waiting for workspace trust confirmation unless this flag is passed (or `--print` implicitly handles it — verified: `--print` skips the workspace trust dialog per CLI help text).
- **Using `git diff HEAD` instead of `git diff master`:** `git diff HEAD` shows nothing if Claude committed; `git diff master` shows all changes relative to the base branch.
- **Merging with fast-forward:** Use `--no-ff` to preserve branch history and make the merge clearly attributable as an agent task.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Subprocess async | Custom process wrapper | `asyncio.create_subprocess_exec()` | Already proven in `run_command()` |
| Confirmation flow | New pattern | Mirror `devops.py` `confirm_callback` | Same inline keyboard + callback_data routing |
| WebApp buttons | New factory | `make_webapp_button()` from `miniapp.py` | Already handles WebAppInfo construction |
| HTML formatting | Custom escape | `bold()`, `code_block()` from `formatters.py` | Already HTML-escape-safe |
| Auth gate | New decorator | `@require_auth` from `bot/auth.py` | DB allowlist check in one line |
| Git operations | Python GitPython | subprocess `git` commands via `run_command()` | No new dependency; git already in image |

**Key insight:** 90% of the infrastructure is already in Phase 32. This phase is wiring Claude CLI into the existing confirmation + WebApp patterns.

## Common Pitfalls

### Pitfall 1: Claude CLI workspace trust dialog blocks container
**What goes wrong:** `claude --print` without `--dangerously-skip-permissions` may print a trust confirmation prompt to stdout instead of the task result, causing the subprocess to hang until timeout.
**Why it happens:** Claude Code normally asks "Do you trust this workspace?" on first run per directory. In Docker with no TTY, this blocks.
**How to avoid:** Always pass `--dangerously-skip-permissions` in the subprocess call. The CLI help confirms: "Bypass all permission checks. Recommended only for sandboxes with no internet access." The bot container qualifies (no public internet access needed for task execution).
**Warning signs:** subprocess returns non-zero exit code with "trust" in output, or hangs exactly at timeout.

### Pitfall 2: git checkout fails when agent branch has uncommitted work
**What goes wrong:** If Claude crashes mid-edit leaving unstaged changes, `git checkout master` fails with "Your local changes would be overwritten."
**Why it happens:** Claude edits files without always committing them. A crash or timeout leaves dirty state.
**How to avoid:** In the error cleanup path, always run `git checkout -f master` (force) and then `git branch -D branch_name`. Also consider `git clean -fd` to remove untracked files Claude may have created.
**Warning signs:** cleanup git operations return non-zero; subsequent task attempts fail to create a new branch.

### Pitfall 3: Diff too large for Telegram message
**What goes wrong:** `git diff --stat` output can be very long for large tasks. Telegram messages cap at 4096 chars.
**Why it happens:** Claude may modify many files; stat listing grows linearly.
**How to avoid:** Truncate stat to last 3000 chars (consistent with existing `run_command()` pattern). Always show full diff only in the WebApp endpoint.
**Warning signs:** `MessageTextIsEmpty` or `MessageTooLong` errors from PTB.

### Pitfall 4: Multiple callback handlers triggered for stale task_id
**What goes wrong:** User presses approve/reject, then presses again (or previous task's buttons are still visible). Handler receives task_id that no longer matches `_current_task`.
**Why it happens:** Inline buttons persist in chat history; old messages keep their buttons active.
**How to avoid:** Always validate `_current_task.task_id == task_id` before acting. After approve/reject, edit the message to remove the keyboard (`reply_markup=None` or empty `InlineKeyboardMarkup([])`).
**Warning signs:** Double-merge errors from git; `_current_task` is None when callback fires.

### Pitfall 5: ANTHROPIC_API_KEY not forwarded to Claude subprocess
**What goes wrong:** `claude` CLI exits with authentication error even though the key is set in the container environment.
**Why it happens:** `asyncio.create_subprocess_exec()` inherits the parent process environment by default — but only if `env` parameter is not explicitly overridden. If `env={}` is passed (empty dict), the key is not available.
**How to avoid:** Either omit the `env` parameter (inherits everything) or pass `env={**os.environ}` explicitly. Never pass a partial dict without including `ANTHROPIC_API_KEY`.
**Warning signs:** Claude exits with code 1 and "authentication" in output immediately (no timeout).

### Pitfall 6: Bot and API containers can't share diff storage
**What goes wrong:** Bot writes diff to `/tmp/agent_diffs/task_id.txt`; FastAPI can't read it because they're separate containers with separate filesystems.
**Why it happens:** Docker containers don't share `/tmp` unless both mount the same named volume.
**How to avoid:** Add a named volume `agent_diffs` in docker-compose.yml, mount it at `/tmp/agent_diffs` in both `bot` and `api` services.
**Warning signs:** FastAPI diff endpoint always returns "Diff не найден."

## Code Examples

### Running Claude CLI with JSON output format
```python
# Source: Claude CLI --help verified 2026-04-12
# --output-format json returns: {"type":"result","subtype":"success","result":"...","cost_usd":0.003,"num_turns":5}
import json

rc, raw = await run_claude_task(task_text, REPO_PATH, timeout=360)
if rc == 0:
    try:
        data = json.loads(raw)
        claude_result = data.get("result", raw)
    except json.JSONDecodeError:
        claude_result = raw  # fallback: plain text
```

### Registering new handlers in bot/main.py
```python
# Source: bot/main.py pattern (Phase 32)
from bot.handlers.agent import (
    task_handler,
    agent_approve_callback,
    agent_reject_callback,
)

# In main():
app.add_handler(CommandHandler("task", task_handler))
app.add_handler(CallbackQueryHandler(agent_approve_callback, pattern=r"^agent_approve:"))
app.add_handler(CallbackQueryHandler(agent_reject_callback, pattern=r"^agent_reject:"))

# In post_init() — add to set_my_commands list:
("task", "Выполнить задачу через Claude Code"),
```

### Dockerfile.bot Node.js installation
```dockerfile
# Source: verified against python:3.12-slim base; nodesource is the standard approach
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*
```

### Git branch cleanup on error
```python
# Source: established pattern for error cleanup
async def _fail_task(context, task: AgentTask, error_msg: str) -> None:
    global _current_task
    # Force checkout to master, then delete branch
    await _git(["checkout", "-f", "master"])
    await _git(["branch", "-D", task.branch])  # -D = force delete even if unmerged
    task.status = "error"
    _current_task = None

    await context.bot.send_message(
        chat_id=task.chat_id,
        text=f"❌ Ошибка Claude:\n<pre>{task.branch}</pre>\n{error_msg[-400:]}",
        parse_mode="HTML",
    )
```

### Diff viewer template (mobile/agent/diff.html)
```html
{% extends "base_mobile.html" %}
{% block title %}Diff задачи {{ task_id }}{% endblock %}
{% block content %}
<div style="padding: 16px;">
  <h2 style="font-size:1rem;font-weight:600;margin-bottom:12px;">Diff: {{ task_id }}</h2>
  <pre style="font-size:0.75rem;overflow-x:auto;background:#1e1b4b;color:#e5e7eb;
              padding:12px;border-radius:8px;white-space:pre-wrap;word-break:break-all;">
{{ diff | e }}
  </pre>
</div>
{% endblock %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `subprocess.run()` in handlers | `asyncio.create_subprocess_exec()` | Phase 32 established | Non-blocking; required for PTB async handlers |
| Direct Telegram message edits | Store message_id + edit later | Phase 32 established | Long-running tasks can update status without losing message context |
| Interactive Claude Code | `claude --print -p` non-interactive mode | Claude Code 1.x+ | Enables headless subprocess invocation |

**Deprecated/outdated:**
- `claude --print` without `--dangerously-skip-permissions`: will hang on workspace trust dialog in container context with no TTY.

## Open Questions

1. **REPO_PATH in bot container**
   - What we know: docker-compose.yml mounts `.:/opt/app` for api service; bot service uses `WORKDIR /opt/app` but has no volume mount currently
   - What's unclear: The bot container needs the repo mounted at a known path; currently Dockerfile.bot COPY-s source files but doesn't mount the live repo
   - Recommendation: Add volume mount `. :/opt/app` to bot service in docker-compose.yml. Claude will then edit the live repo files. This is consistent with D-09 "volume mount репозитория."

2. **git identity in bot container**
   - What we know: git merge requires `user.email` and `user.name` to be set
   - What's unclear: python:3.12-slim may not have git configured; merge commits will fail with "Please tell me who you are"
   - Recommendation: Add to Dockerfile.bot (or docker-compose bot environment): `GIT_AUTHOR_NAME=Claude Agent`, `GIT_AUTHOR_EMAIL=agent@localhost`, `GIT_COMMITTER_NAME=Claude Agent`, `GIT_COMMITTER_EMAIL=agent@localhost`

3. **Claude CLI `--output-format json` result structure**
   - What we know: CLI help confirms `json` format returns "single result"; verified fields via help: `result`, `cost_usd`, `num_turns`
   - What's unclear: Whether Claude actually commits files or just edits them (depends on system prompt / task)
   - Recommendation: Use plain text `--output-format text` for spike simplicity. Claude's stdout will be its narrative description of what it did. The actual file changes are captured by `git diff master`.

4. **Shared volume for diff storage**
   - What we know: Bot and API are separate containers; `/tmp` is not shared
   - What's unclear: Whether adding a named volume is acceptable or if Redis (already shared) is better
   - Recommendation: Use Redis for diff storage — already shared between bot and api containers. `redis-py` is already in requirements. Store as `SETEX agent:diff:{task_id} 3600 {diff_content}`. Read from FastAPI endpoint via the same Redis connection.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Claude Code CLI | D-01 (subprocess invocation) | ✓ | 2.1.104 at /usr/bin/claude | — |
| Node.js | D-02 (npm install in Dockerfile.bot) | ✓ | v20.20.2 on host; must be added to Dockerfile.bot | — |
| npm | D-02 (claude CLI install) | ✓ | 10.8.2 on host | — |
| git | D-04 (branch lifecycle) | ✓ (in python:3.12-slim via apt) | system | — |
| Redis | Diff storage (Open Question 4) | ✓ | 7.2 (docker service) | Named volume /tmp share |
| ANTHROPIC_API_KEY env var | D-03 (Claude CLI auth) | Unknown — not in .env currently | — | Must be added to .env + docker-compose.yml |

**Missing dependencies with no fallback:**
- `ANTHROPIC_API_KEY` env variable: not present in current `.env` or `.env.example`. Must be added before the spike can run. Note: the existing per-user encrypted key (in User model) is NOT usable here — Claude CLI reads from environment variable only.

**Missing dependencies with fallback:**
- Node.js in Dockerfile.bot: not installed in current `python:3.12-slim` image; must be added via apt + nodesource. Fallback: could bind-mount the host's `claude` binary directly, but Dockerfile change is cleaner.

## Sources

### Primary (HIGH confidence)
- Live `claude --help` output — confirmed all CLI flags (`--print`, `--dangerously-skip-permissions`, `--allowedTools`, `--output-format json`) — verified 2026-04-12
- `bot/handlers/devops.py` — confirmation flow, inline buttons, auto-cancel pattern — read directly
- `bot/utils/shell.py` — `run_command()` subprocess pattern — read directly
- `bot/main.py` — handler registration pattern — read directly
- `bot/handlers/miniapp.py` — `make_webapp_button()` pattern — read directly
- `bot/auth.py` — `@require_auth` decorator — read directly
- `bot/config.py` — `BotSettings` structure — read directly
- `Dockerfile.bot` — current base image (python:3.12-slim) and deps — read directly
- `docker-compose.yml` — service structure, volume patterns — read directly
- `app/routers/mobile.py` — mobile endpoint pattern, Jinja2Templates usage — read directly
- `app/templates/base_mobile.html` — mobile base template structure — read directly

### Secondary (MEDIUM confidence)
- Claude Code CLI `--dangerously-skip-permissions` behavior in containers: inferred from `--print` help text ("workspace trust dialog is skipped when Claude is run with the -p mode") combined with container context knowledge

### Tertiary (LOW confidence)
- Node.js 20 via nodesource install in python:3.12-slim: standard pattern, not verified against this specific Dockerfile — flag for testing during Wave 0

## Metadata

**Confidence breakdown:**
- Claude CLI flags and modes: HIGH — verified against running CLI 2.1.104
- Subprocess pattern: HIGH — directly mirrors existing `run_command()` in shell.py
- Git branch lifecycle: HIGH — standard git commands, no exotic features
- Bot handler registration: HIGH — directly mirrors Phase 32 patterns in main.py
- Dockerfile Node.js install: MEDIUM — nodesource method is standard but not tested in this specific image
- Shared diff storage via Redis: MEDIUM — Redis is present and confirmed, but implementation pattern is new to this codebase

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (Claude CLI version may update; verify version pin if needed)
