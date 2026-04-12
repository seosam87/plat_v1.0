"""Bot entry point — starts the webhook server and registers all handlers.

Per D-02: webhook mode, port 8443, secret token validation.
Per D-09: Menu Button opens /m/ (home screen) on startup.
"""
from __future__ import annotations

import os
import sys

# Ensure project root is in sys.path so `from app.models...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from telegram import MenuButtonWebApp, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.config import settings
from bot.handlers.devops import (
    cancel_callback,
    confirm_callback,
    deploy_handler,
    logs_handler,
    status_handler,
    test_handler,
)
from bot.handlers.miniapp import help_handler, start_handler
from bot.handlers.agent import (
    agent_approve_callback,
    agent_reject_callback,
    task_handler,
)
from bot.handlers.seo import (
    check_handler,
    crawl_handler,
    report_handler,
    seo_site_callback,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger.remove()
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


# ---------------------------------------------------------------------------
# Startup hook
# ---------------------------------------------------------------------------


async def post_init(application: Application) -> None:
    """One-time setup: Menu Button + command list."""
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Открыть платформу",
            web_app=WebAppInfo(url=f"{settings.APP_BASE_URL}/m/"),
        )
    )
    await application.bot.set_my_commands(
        [
            ("status", "Статус сервисов"),
            ("logs", "Последние логи"),
            ("test", "Запустить тесты"),
            ("deploy", "Деплой (git pull + restart)"),
            ("crawl", "Запустить краул сайта"),
            ("check", "Проверить позиции"),
            ("report", "Сформировать отчёт"),
            ("task", "Выполнить задачу через Claude Code"),
            ("help", "Помощь"),
        ]
    )
    logger.info("Bot initialized, webhook commands registered")


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


async def error_handler(update: object, context) -> None:
    logger.error("Update {} caused error: {}", update, context.error)


# ---------------------------------------------------------------------------
# Application factory + runner
# ---------------------------------------------------------------------------


def main() -> None:
    """Build the Application, register handlers, and start the webhook server."""
    app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("logs", logs_handler))
    app.add_handler(CommandHandler("test", test_handler))
    app.add_handler(CommandHandler("deploy", deploy_handler))
    app.add_handler(CommandHandler("crawl", crawl_handler))
    app.add_handler(CommandHandler("check", check_handler))
    app.add_handler(CommandHandler("report", report_handler))
    app.add_handler(CommandHandler("task", task_handler))

    # Callback handlers (confirmation buttons + site-picker)
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern=r"^cancel:"))
    app.add_handler(
        CallbackQueryHandler(seo_site_callback, pattern=r"^(crawl|check|report):[0-9a-f\-]+$")
    )
    app.add_handler(CallbackQueryHandler(agent_approve_callback, pattern=r"^agent_approve:"))
    app.add_handler(CallbackQueryHandler(agent_reject_callback, pattern=r"^agent_reject:"))

    app.add_error_handler(error_handler)

    logger.info("Starting bot webhook on port {}", settings.TELEGRAM_BOT_PORT)
    app.run_webhook(
        listen="0.0.0.0",
        port=settings.TELEGRAM_BOT_PORT,
        url_path="/webhook/tg",
        secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
        webhook_url=f"{settings.TELEGRAM_WEBHOOK_BASE_URL}/webhook/tg",
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
