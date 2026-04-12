"""SEO command handlers for the Telegram bot.

Implements /crawl, /check, /report per D-06 and D-07.

All handlers are protected by @require_auth (BOT-01).
When the user has multiple sites an InlineKeyboard site-picker is shown.
Each command dispatches a Celery task via the lightweight celery_client.dispatch().
"""
from __future__ import annotations

from loguru import logger
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.models.site import Site
from app.models.user import User
from bot.auth import require_auth
from bot.config import settings
from bot.database import AsyncSessionLocal
from bot.handlers.miniapp import make_webapp_button
from bot.utils.celery_client import dispatch
from bot.utils.formatters import bold

# Celery task names (verified from task source files)
_TASK_CRAWL = "app.tasks.crawl_tasks.crawl_site"
_TASK_CHECK = "app.tasks.position_tasks.check_positions"
_TASK_REPORT = "app.tasks.report_tasks.send_weekly_summary_report"


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------


async def _get_all_sites() -> list[tuple[str, str]]:
    """Return list of (site_id_str, domain) for all sites.

    The platform is an internal tool with at most ~100 sites, so we
    return all sites regardless of user — the DB allowlist already
    ensures the caller is a trusted team member.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Site.id, Site.name, Site.url).order_by(Site.name)
        )
        rows = result.all()
        return [(str(row.id), row.name or row.url) for row in rows]


# ---------------------------------------------------------------------------
# /crawl
# ---------------------------------------------------------------------------


@require_auth
async def crawl_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/crawl — dispatch crawl task for one site or show site picker."""
    msg = update.effective_message
    sites = await _get_all_sites()

    if not sites:
        await msg.reply_text("Нет доступных сайтов.")
        return

    if len(sites) == 1:
        site_id, domain = sites[0]
        _dispatch_crawl(site_id)
        webapp_btn = make_webapp_button(
            "Открыть краулер", f"/m/health/{site_id}", settings.APP_BASE_URL
        )
        await msg.reply_text(
            f"Краул запущен для {bold(domain)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[webapp_btn]]),
        )
        return

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(domain, callback_data=f"crawl:{site_id}")]
         for site_id, domain in sites]
    )
    await msg.reply_text(
        bold("Выберите сайт для краула:"), parse_mode="HTML", reply_markup=keyboard
    )


# ---------------------------------------------------------------------------
# /check
# ---------------------------------------------------------------------------


@require_auth
async def check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/check — dispatch position check task for one site or show site picker."""
    msg = update.effective_message
    sites = await _get_all_sites()

    if not sites:
        await msg.reply_text("Нет доступных сайтов.")
        return

    if len(sites) == 1:
        site_id, domain = sites[0]
        _dispatch_check(site_id)
        webapp_btn = make_webapp_button(
            "Открыть позиции", "/m/positions", settings.APP_BASE_URL
        )
        await msg.reply_text(
            f"Проверка позиций запущена для {bold(domain)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[webapp_btn]]),
        )
        return

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(domain, callback_data=f"check:{site_id}")]
         for site_id, domain in sites]
    )
    await msg.reply_text(
        bold("Выберите сайт для проверки позиций:"), parse_mode="HTML", reply_markup=keyboard
    )


# ---------------------------------------------------------------------------
# /report
# ---------------------------------------------------------------------------


@require_auth
async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/report — dispatch report generation task for one site or show site picker."""
    msg = update.effective_message
    sites = await _get_all_sites()

    if not sites:
        await msg.reply_text("Нет доступных сайтов.")
        return

    if len(sites) == 1:
        site_id, domain = sites[0]
        _dispatch_report(site_id)
        webapp_btn = make_webapp_button(
            "Открыть отчёты", "/m/reports", settings.APP_BASE_URL
        )
        await msg.reply_text(
            f"Отчёт формируется для {bold(domain)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[webapp_btn]]),
        )
        return

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(domain, callback_data=f"report:{site_id}")]
         for site_id, domain in sites]
    )
    await msg.reply_text(
        bold("Выберите сайт для отчёта:"), parse_mode="HTML", reply_markup=keyboard
    )


# ---------------------------------------------------------------------------
# Callback handler — site picker
# ---------------------------------------------------------------------------


@require_auth
async def seo_site_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle crawl:{id}, check:{id}, report:{id} callback queries."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 1)
    if len(parts) != 2:
        await query.edit_message_text("Неверный формат запроса.")
        return

    operation, site_id = parts

    # Look up site name for confirmation message
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Site.name, Site.url).where(Site.id == site_id))
            row = result.one_or_none()
        domain = (row.name or row.url) if row else site_id
    except Exception:
        domain = site_id

    if operation == "crawl":
        _dispatch_crawl(site_id)
        webapp_btn = make_webapp_button(
            "Открыть краулер", f"/m/health/{site_id}", settings.APP_BASE_URL
        )
        text = f"Краул запущен для {bold(domain)}"
    elif operation == "check":
        _dispatch_check(site_id)
        webapp_btn = make_webapp_button(
            "Открыть позиции", "/m/positions", settings.APP_BASE_URL
        )
        text = f"Проверка позиций запущена для {bold(domain)}"
    elif operation == "report":
        _dispatch_report(site_id)
        webapp_btn = make_webapp_button(
            "Открыть отчёты", "/m/reports", settings.APP_BASE_URL
        )
        text = f"Отчёт формируется для {bold(domain)}"
    else:
        await query.edit_message_text(f"Неизвестная операция: {operation}")
        return

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[webapp_btn]]),
    )


# ---------------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------------


def _dispatch_crawl(site_id: str) -> None:
    task_id = dispatch(_TASK_CRAWL, kwargs={"site_id": site_id})
    logger.info("Dispatched crawl task {} for site {}", task_id, site_id)


def _dispatch_check(site_id: str) -> None:
    task_id = dispatch(_TASK_CHECK, kwargs={"site_id": site_id})
    logger.info("Dispatched check task {} for site {}", task_id, site_id)


def _dispatch_report(site_id: str) -> None:
    task_id = dispatch(_TASK_REPORT, kwargs={"site_id": site_id})
    logger.info("Dispatched report task {} for site {}", task_id, site_id)
