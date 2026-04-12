---
phase: 32-telegram-bot
plan: 01
subsystem: infra
tags: [telegram, python-telegram-bot, pydantic-settings, sqlalchemy, celery, asyncpg]

requires:
  - phase: 17-in-app-notifications
    provides: "Telegram service (send_message) and TELEGRAM_* env vars in app/config.py"
  - phase: 26-mobile-foundation
    provides: "User.telegram_id column (migration 0051) — auth basis for bot allowlist"

provides:
  - "tg_notifications_enabled boolean on User model (migration 0056)"
  - "bot/ Python package: config, auth, database, and utility modules"
  - "BotSettings (pydantic-settings) reading from .env"
  - "Standalone async DB session (AsyncSessionLocal) independent of app.database"
  - "check_user_allowed() + require_auth decorator gating handlers on User.telegram_id"
  - "dispatch() Celery client for fire-and-forget task dispatch from bot container"
  - "run_command() async subprocess runner with timeout and tail truncation"
  - "HTML message formatters: code_block, bold, italic, status_line"

affects:
  - "32-02: handler modules will import bot.auth, bot.database, bot.utils.*"
  - "32-03: webhook entrypoint will import bot.config.settings"

tech-stack:
  added:
    - "python-telegram-bot>=21.0,<22.0 (bot container only)"
  patterns:
    - "bot/ package is self-contained: imports app.models.* for shared ORM types but does NOT import app.main, app.routers, or app.celery_app"
    - "Celery client in bot is broker-only (no backend, no task definitions) — prevents pulling worker deps into bot image"
    - "require_auth decorator pattern for uniform handler gating"

key-files:
  created:
    - "alembic/versions/0056_add_tg_notifications_toggle.py"
    - "bot/__init__.py"
    - "bot/config.py"
    - "bot/database.py"
    - "bot/auth.py"
    - "bot/utils/__init__.py"
    - "bot/utils/shell.py"
    - "bot/utils/celery_client.py"
    - "bot/utils/formatters.py"
  modified:
    - "app/models/user.py"

key-decisions:
  - "bot/ imports app.models.user (shared ORM type) but not app.database or app.main — avoids FastAPI startup in bot container"
  - "BotSettings uses env_prefix='' and reads TELEGRAM_BOT_TOKEN directly (matches existing .env naming)"
  - "Celery client in bot is fire-and-forget only (send_task), no result backend needed"

patterns-established:
  - "require_auth: all bot handlers decorated with @require_auth; decorator checks User.telegram_id DB lookup"
  - "HTML parse_mode throughout: all formatters produce HTML-escaped output for Telegram HTML parse_mode"
  - "Bot container isolation: bot/ never imports app.routers.*, app.main, app.celery_app"

requirements-completed: [BOT-01]

duration: 8min
completed: 2026-04-12
---

# Phase 32 Plan 01: Bot Foundation Summary

**Alembic migration 0056 adds tg_notifications_enabled to users; bot/ package provides BotSettings, async DB session, telegram_id allowlist auth, Celery dispatch client, shell runner, and HTML formatters — all importable without FastAPI startup.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-12T13:18:00Z
- **Completed:** 2026-04-12T13:26:48Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- User.tg_notifications_enabled boolean column added (migration 0056, server_default=false, non-nullable)
- bot/ package with 8 Python modules: config, auth, database, 2 __init__, shell, celery_client, formatters
- Standalone AsyncSessionLocal in bot/database.py — no dependency on app.database/app.main
- require_auth decorator queries User.telegram_id allowlist; returns "Доступ запрещён." on denial
- dispatch() sends Celery tasks via send_task only — keeps bot image free of worker/Playwright deps
- run_command() runs async subprocesses with configurable timeout and 3000-char tail truncation

## Task Commits

Each task was committed atomically:

1. **Task 1: Alembic migration 0056 + User model field** — `4a28e02` (feat)
2. **Task 2: Bot package foundation — config, auth, database, utilities** — `841b38e` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `app/models/user.py` — added tg_notifications_enabled Mapped[bool] column
- `alembic/versions/0056_add_tg_notifications_toggle.py` — migration: add_column + downgrade drop_column
- `bot/__init__.py` — package marker
- `bot/config.py` — BotSettings(BaseSettings) with TELEGRAM_BOT_TOKEN, DATABASE_URL, REDIS_URL, etc.
- `bot/database.py` — standalone create_async_engine + AsyncSessionLocal
- `bot/auth.py` — check_user_allowed(telegram_id) + require_auth decorator
- `bot/utils/__init__.py` — utils package marker
- `bot/utils/shell.py` — async run_command with asyncio.create_subprocess_exec
- `bot/utils/celery_client.py` — Celery(broker=REDIS_URL) + dispatch() via send_task
- `bot/utils/formatters.py` — code_block, bold, italic, status_line (HTML parse_mode)

## Decisions Made

- BotSettings reads TELEGRAM_BOT_TOKEN directly (no alias) — field name matches existing .env key
- bot/database.py pool_size=5 (smaller than app's 10) — bot has fewer concurrent handlers
- Celery client uses no backend — bot only dispatches, never reads results

## Deviations from Plan

None — plan executed exactly as written.

The `python-telegram-bot` package was not installed in the dev environment (bot runs in its own container per Dockerfile.bot). Installed it temporarily to run the import verification, which passed successfully.

## Issues Encountered

- `telegram` module missing from dev environment — installed via pip for verification only. Not a code issue; bot container already had it in `bot/requirements.txt`.

## User Setup Required

None — no external service configuration required beyond existing TELEGRAM_BOT_TOKEN in .env.

## Next Phase Readiness

- bot/ package is ready for Wave 2 handler modules to build on
- All utility imports verified: BotSettings, require_auth, check_user_allowed, run_command, dispatch, code_block, bold, status_line
- Migration 0056 ready to apply: `alembic upgrade 0056`
- Wave 2 (plan 32-02) can register handlers using @require_auth and bot.database.AsyncSessionLocal

---
*Phase: 32-telegram-bot*
*Completed: 2026-04-12*
