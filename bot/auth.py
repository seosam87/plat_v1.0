"""Telegram ID allowlist authentication for the bot.

Per BOT-01 and D-08: only users with a registered telegram_id in the
platform DB are allowed to interact with the bot.

Usage (in handlers):
    @require_auth
    async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        ...
"""
import functools

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from app.models.user import User
from bot.database import AsyncSessionLocal


async def check_user_allowed(telegram_id: int) -> bool:
    """Return True if telegram_id belongs to an active platform user."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User.id).where(
                User.telegram_id == telegram_id,
                User.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None


def require_auth(handler_func):
    """Decorator that gates any handler behind the DB allowlist check."""

    @functools.wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not await check_user_allowed(user.id):
            if update.message:
                await update.message.reply_text("Доступ запрещён.")
            elif update.callback_query:
                await update.callback_query.answer("Доступ запрещён.", show_alert=True)
            return
        return await handler_func(update, context)

    return wrapper
