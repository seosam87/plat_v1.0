"""Claude Code agent handler for /task command.

Spike: user sends /task <description> -> bot creates git branch ->
runs Claude Code CLI -> collects diff -> shows approve/reject buttons.

Per D-01: Claude CLI via subprocess.
Per D-04: Git branch isolation.
Per D-05: One task at a time (asyncio.Lock).
"""
from __future__ import annotations

import asyncio
import pathlib
import uuid
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.config import settings
from bot.handlers.miniapp import make_webapp_button
from bot.utils.formatters import bold, code_block
from bot.utils.shell import run_command

# ---------------------------------------------------------------------------
# Constants and in-memory state
# ---------------------------------------------------------------------------

REPO_PATH = "/opt/app"
DIFF_DIR = pathlib.Path("/tmp/agent_diffs")


@dataclass
class AgentTask:
    """In-memory state for a single agent task (no DB for spike per Research Pattern 1)."""

    task_id: str
    chat_id: int
    message_id: int
    branch: str
    task_text: str
    diff: str = ""
    summary: str = ""
    status: str = "running"  # running | awaiting_approval | done | error


_current_task: Optional[AgentTask] = None
_task_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Git helper
# ---------------------------------------------------------------------------


async def _git(args: list[str]) -> tuple[int, str]:
    """Run a git command inside REPO_PATH and return (returncode, output)."""
    return await run_command(["git", "-C", REPO_PATH] + args, timeout=30)


# ---------------------------------------------------------------------------
# Claude CLI runner
# ---------------------------------------------------------------------------


async def _run_claude(task_text: str, timeout: int = 360) -> tuple[int, str]:
    """Run Claude Code CLI with --print mode. Returns (returncode, stdout).

    Per D-01: use Claude CLI subprocess.
    Per D-07/D-08: 360s timeout.
    """
    proc = await asyncio.create_subprocess_exec(
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--allowedTools", "Edit,Write,Bash,Read",
        "--output-format", "text",
        "-p", task_text,
        cwd=REPO_PATH,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode(errors="replace")
        return proc.returncode, output[-3000:] if len(output) > 3000 else output
    except asyncio.TimeoutError:
        proc.kill()
        return 1, f"Timeout: Claude did not complete within {timeout}s"


# ---------------------------------------------------------------------------
# /task command handler
# ---------------------------------------------------------------------------


@require_auth
async def task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/task <description> — run a task via Claude Code.

    Per D-05: only one task at a time enforced via asyncio.Lock.
    Per D-06: immediate status feedback, then background processing.
    """
    global _current_task
    msg = update.effective_message
    task_text = msg.text.replace("/task", "", 1).strip() if msg.text else ""

    if not task_text:
        await msg.reply_text("Использование: /task <описание задачи>")
        return

    async with _task_lock:
        if _current_task and _current_task.status == "running":
            await msg.reply_text("Задача уже выполняется, подождите.")
            return

        task_id = str(uuid.uuid4())[:8]
        branch = f"agent/task-{task_id}"
        sent = await msg.reply_text("Принято, создаю ветку...")
        _current_task = AgentTask(
            task_id=task_id,
            chat_id=msg.chat_id,
            message_id=sent.message_id,
            branch=branch,
            task_text=task_text,
        )

    asyncio.create_task(_run_agent_task(context))


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_agent_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Background task: create branch -> run Claude -> collect diff -> present.

    Per D-04: git branch isolation.
    Per D-06: edit status message as progress changes.
    Per D-10: send diff summary with approve/reject buttons.
    Per D-12: error handling with auto-cleanup.
    """
    global _current_task
    task = _current_task
    if not task:
        return

    try:
        # 1. Ensure we're on master first
        await _git(["checkout", "-f", "master"])

        # 2. Create branch (per D-04)
        rc, out = await _git(["checkout", "-b", task.branch])
        if rc != 0:
            await _fail_task(context, task, f"Не удалось создать ветку: {out}")
            return

        # 3. Status update (per D-06)
        await context.bot.edit_message_text(
            chat_id=task.chat_id,
            message_id=task.message_id,
            text="Claude работает...",
        )

        # 4. Run Claude (per D-01)
        rc, output = await _run_claude(task.task_text)
        logger.info("Claude finished: rc={}, output_len={}", rc, len(output))

        if rc != 0:
            await _fail_task(context, task, output[-500:])
            return

        # 5. Commit any uncommitted changes Claude may have left
        await _git(["add", "-A"])
        await _git(["commit", "-m", f"agent: {task.task_text[:60]}", "--allow-empty"])

        # 6. Collect diff (per D-04)
        _, diff_output = await _git(["diff", "master"])
        _, stat_output = await _git(["diff", "--stat", "master"])

        if not diff_output.strip():
            await _fail_task(context, task, "Claude не внёс изменений.")
            return

        task.diff = diff_output
        task.summary = stat_output
        task.status = "awaiting_approval"

        # 7. Write diff to shared volume for WebApp viewer (per D-11)
        DIFF_DIR.mkdir(parents=True, exist_ok=True)
        (DIFF_DIR / f"{task.task_id}.txt").write_text(diff_output, encoding="utf-8")

        # 8. Send approval message (per D-10)
        await _send_approval(context, task, stat_output)

    except Exception as exc:
        logger.exception("Agent task failed: {}", exc)
        if task:
            await _fail_task(context, task, str(exc)[-500:])


# ---------------------------------------------------------------------------
# Approval message sender
# ---------------------------------------------------------------------------


async def _send_approval(
    context: ContextTypes.DEFAULT_TYPE,
    task: AgentTask,
    stat: str,
) -> None:
    """Send diff summary with approve/reject buttons and WebApp link.

    Per D-10: inline approve/reject buttons.
    Per D-11: WebApp link to full diff viewer.
    """
    webapp_btn = make_webapp_button(
        "Полный diff",
        f"/m/agent/diff/{task.task_id}",
        settings.APP_BASE_URL,
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Применить", callback_data=f"agent_approve:{task.task_id}"
            ),
            InlineKeyboardButton(
                "Отклонить", callback_data=f"agent_reject:{task.task_id}"
            ),
        ],
        [webapp_btn],
    ])
    text = bold("Claude завершил задачу") + "\n\n" + code_block(stat or "Нет изменений")
    # Truncate to Telegram limit
    if len(text) > 4000:
        text = text[:4000] + "..."
    await context.bot.send_message(
        chat_id=task.chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ---------------------------------------------------------------------------
# Approve callback — merge branch into master
# ---------------------------------------------------------------------------


@require_auth
async def agent_approve_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle agent_approve:* callback — merge branch into master.

    Per D-04: merge with --no-ff, then delete agent branch.
    """
    global _current_task
    query = update.callback_query
    await query.answer("Применяю...")
    task_id = query.data.split(":", 1)[1]

    if not _current_task or _current_task.task_id != task_id:
        await query.edit_message_text("Задача не найдена или уже обработана.")
        return

    # Switch to master and merge
    await _git(["checkout", "master"])
    rc, out = await _git([
        "merge", "--no-ff", _current_task.branch,
        "-m", f"agent: {_current_task.task_text[:60]}",
    ])

    if rc == 0:
        await _git(["branch", "-d", _current_task.branch])
        await query.edit_message_text("Изменения применены и смёрджены в master.")
        logger.info("Agent task {} approved and merged", task_id)
    else:
        await query.edit_message_text(
            f"Merge failed:\n<pre>{out[-500:]}</pre>", parse_mode="HTML"
        )

    _current_task.status = "done"
    _current_task = None


# ---------------------------------------------------------------------------
# Reject callback — discard branch
# ---------------------------------------------------------------------------


@require_auth
async def agent_reject_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle agent_reject:* callback — discard branch.

    Per D-04: delete agent branch, return to master.
    """
    global _current_task
    query = update.callback_query
    await query.answer()
    task_id = query.data.split(":", 1)[1]

    if _current_task and _current_task.task_id == task_id:
        await _git(["checkout", "-f", "master"])
        await _git(["branch", "-D", _current_task.branch])
        _current_task.status = "done"
        _current_task = None
        logger.info("Agent task {} rejected, branch deleted", task_id)

    await query.edit_message_text("Задача отклонена. Ветка удалена.")


# ---------------------------------------------------------------------------
# Error cleanup helper
# ---------------------------------------------------------------------------


async def _fail_task(
    context: ContextTypes.DEFAULT_TYPE,
    task: AgentTask,
    error_msg: str,
) -> None:
    """Clean up branch and notify user of failure.

    Per D-12: auto-cleanup on error.
    """
    global _current_task
    await _git(["checkout", "-f", "master"])
    rc, _ = await _git(["branch", "-D", task.branch])
    await _git(["clean", "-fd"])
    task.status = "error"
    _current_task = None

    text = f"Ошибка:\n<pre>{error_msg[-400:]}</pre>"
    try:
        await context.bot.send_message(
            chat_id=task.chat_id, text=text, parse_mode="HTML"
        )
    except Exception as exc:
        logger.error("Failed to send error message: {}", exc)
