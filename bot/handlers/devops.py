"""DevOps command handlers for the Telegram bot.

Implements /status, /logs, /test, /deploy with confirmation flow for
dangerous operations per D-05 and D-07.

All handlers are protected by @require_auth (BOT-01).
Dangerous commands (/test, /deploy) require explicit inline-keyboard
confirmation within 60 seconds (D-07).
"""
from __future__ import annotations

import asyncio
import json

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.config import settings
from bot.handlers.miniapp import make_webapp_button
from bot.utils.formatters import bold, code_block, status_line
from bot.utils.shell import run_command

# Track pending auto-cancel tasks keyed by (chat_id, message_id)
_pending: dict[tuple[int, int], asyncio.Task] = {}


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------


@require_auth
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — show docker-compose service statuses."""
    msg = update.effective_message
    await msg.reply_text("Получаю статус сервисов...")

    rc, output = await run_command(
        ["docker", "compose", "ps", "--format", "json"], timeout=15
    )

    if rc != 0 or not output.strip():
        text = bold("Статус сервисов") + "\n" + code_block(output or "Нет данных")
    else:
        lines: list[str] = []
        try:
            # docker compose ps --format json returns one JSON object per line
            for line in output.strip().splitlines():
                if not line.strip():
                    continue
                svc = json.loads(line)
                name = svc.get("Name") or svc.get("Service", "?")
                state = svc.get("State", "?")
                health = svc.get("Health", "")
                is_ok = state in ("running", "Up")
                label = f"{name}"
                value = f"{state}" + (f" ({health})" if health else "")
                lines.append(status_line(label, value, ok=is_ok))
        except Exception:
            lines = [code_block(output)]

        text = bold("Статус сервисов") + "\n\n" + "\n".join(lines)

    webapp_btn = make_webapp_button("Открыть дайджест", "/m/digest", settings.APP_BASE_URL)
    keyboard = InlineKeyboardMarkup([[webapp_btn]])
    await msg.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# /logs
# ---------------------------------------------------------------------------


@require_auth
async def logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/logs — tail last 50 lines from api + worker containers."""
    msg = update.effective_message
    await msg.reply_text("Получаю логи...")

    rc, output = await run_command(
        ["docker", "compose", "logs", "--tail=50", "api", "worker"], timeout=15
    )

    text = bold("Последние логи") + "\n" + code_block(output or "Нет данных")
    # Telegram message limit ~4096; code_block truncation is handled by run_command (3000 chars)
    await msg.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /test — confirmation required
# ---------------------------------------------------------------------------


@require_auth
async def test_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/test — show confirmation keyboard before running pytest."""
    msg = update.effective_message
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Выполнить", callback_data="confirm:test"),
                InlineKeyboardButton("Отмена", callback_data="cancel:test"),
            ]
        ]
    )
    sent = await msg.reply_text(
        bold("Запустить тесты?") + "\n\nВыполнит: <code>pytest --tb=short -q</code>\nАвтоотмена через 60 сек.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    _schedule_auto_cancel(sent.chat_id, sent.message_id, "test", context)


# ---------------------------------------------------------------------------
# /deploy — confirmation required
# ---------------------------------------------------------------------------


@require_auth
async def deploy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/deploy — show confirmation keyboard before running git pull."""
    msg = update.effective_message
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Выполнить", callback_data="confirm:deploy"),
                InlineKeyboardButton("Отмена", callback_data="cancel:deploy"),
            ]
        ]
    )
    sent = await msg.reply_text(
        bold("Запустить деплой?") + "\n\nВыполнит: <code>git pull</code>\nАвтоотмена через 60 сек.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    _schedule_auto_cancel(sent.chat_id, sent.message_id, "deploy", context)


# ---------------------------------------------------------------------------
# Callback handlers
# ---------------------------------------------------------------------------


@require_auth
async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'confirm:*' inline button presses."""
    query = update.callback_query
    await query.answer("Выполняю...")

    key = (query.message.chat_id, query.message.message_id)
    _cancel_pending(key)

    operation = query.data.split(":", 1)[1]

    if operation == "test":
        await query.edit_message_text(
            bold("Запускаю тесты...") + "\nЭто может занять несколько минут.",
            parse_mode="HTML",
        )
        rc, output = await run_command(
            ["python", "-m", "pytest", "--tb=short", "-q"], timeout=120
        )
        result_text = bold("Результат тестов") + "\n" + code_block(output or "Нет вывода")
        await query.edit_message_text(result_text, parse_mode="HTML")

    elif operation == "deploy":
        await query.edit_message_text(
            bold("Запускаю деплой...") + "\nВыполняю git pull.",
            parse_mode="HTML",
        )
        rc, output = await run_command(["git", "pull"], timeout=30)
        ok = rc == 0
        result_text = (
            bold("Деплой завершён" if ok else "Деплой завершён с ошибкой")
            + "\n"
            + code_block(output or "Нет вывода")
        )
        await query.edit_message_text(result_text, parse_mode="HTML")

    else:
        await query.edit_message_text(f"Неизвестная операция: {operation}")


@require_auth
async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'cancel:*' inline button presses."""
    query = update.callback_query
    await query.answer()

    key = (query.message.chat_id, query.message.message_id)
    _cancel_pending(key)

    await query.edit_message_text("Операция отменена.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _schedule_auto_cancel(
    chat_id: int,
    message_id: int,
    operation: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Schedule an auto-cancel task that fires after 60 seconds."""

    async def _auto_cancel() -> None:
        await asyncio.sleep(60)
        key = (chat_id, message_id)
        if key in _pending:
            del _pending[key]
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Операция '{operation}' отменена (тайм-аут 60 сек).",
            )
        except Exception as exc:
            logger.debug("Auto-cancel edit failed: {}", exc)

    task = asyncio.create_task(_auto_cancel())
    _pending[(chat_id, message_id)] = task


def _cancel_pending(key: tuple[int, int]) -> None:
    """Cancel the pending auto-cancel task for the given key."""
    task = _pending.pop(key, None)
    if task and not task.done():
        task.cancel()
