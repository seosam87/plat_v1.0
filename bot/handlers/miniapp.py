"""Mini App utilities + /start and /help command handlers.

Provides:
- make_webapp_button() — factory for Telegram WebApp inline buttons
- start_handler — /start with main menu WebApp buttons (D-09, D-10)
- help_handler — /help with full command list

Per D-09: Menu Button opens /m/ (home).
Per D-10, D-11: contextual WebApp buttons accompany each handler response.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.config import settings
from bot.utils.formatters import bold


def make_webapp_button(text: str, path: str, base_url: str) -> InlineKeyboardButton:
    """Return an InlineKeyboardButton that opens a Telegram Mini App URL.

    Args:
        text: Button label.
        path: Path relative to base_url, e.g. "/m/digest".
        base_url: Platform base URL, e.g. "https://example.com".

    Returns:
        InlineKeyboardButton with web_app set.
    """
    url = f"{base_url.rstrip('/')}{path}"
    return InlineKeyboardButton(text, web_app=WebAppInfo(url=url))


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


@require_auth
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — welcome message with main menu WebApp buttons."""
    msg = update.effective_message
    base = settings.APP_BASE_URL

    keyboard = InlineKeyboardMarkup(
        [
            [
                make_webapp_button("Дайджест", "/m/digest", base),
                make_webapp_button("Позиции", "/m/positions", base),
            ],
            [
                make_webapp_button("Отчёты", "/m/reports", base),
                make_webapp_button("Страницы", "/m/pages", base),
            ],
            [
                make_webapp_button("Инструменты", "/m/tools", base),
                make_webapp_button("Сайты", "/m/sites", base),
            ],
        ]
    )

    text = (
        bold("SEO Platform") + "\n\n"
        "Управляйте сайтами прямо из Telegram.\n\n"
        "Используйте кнопки ниже для открытия разделов или команды:\n"
        "/status — статус сервисов\n"
        "/crawl — краул сайта\n"
        "/help — все команды"
    )
    await msg.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------


@require_auth
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — list all available commands with descriptions."""
    msg = update.effective_message

    text = (
        bold("Доступные команды") + "\n\n"
        "<b>/status</b> — Статус сервисов\n"
        "<b>/logs</b> — Последние логи\n"
        "<b>/test</b> — Запустить тесты\n"
        "<b>/deploy</b> — Деплой (git pull + restart)\n"
        "<b>/crawl</b> — Запустить краул сайта\n"
        "<b>/check</b> — Проверить позиции\n"
        "<b>/report</b> — Сформировать отчёт\n"
        "<b>/help</b> — Помощь"
    )
    await msg.reply_text(text, parse_mode="HTML")
