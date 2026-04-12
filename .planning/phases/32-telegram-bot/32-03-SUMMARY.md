---
phase: 32-telegram-bot
plan: 03
subsystem: bot
tags: [telegram, python-telegram-bot, celery, webhook, miniapp, notifications]

requires:
  - phase: 32-01
    provides: bot infrastructure — BotSettings, auth, utils (shell, celery_client, formatters), Dockerfile.bot, docker-compose bot service
  - phase: 32-02
    provides: mini-app UI routes /m/*, telegram service, user.telegram_id + tg_notifications_enabled model

provides:
  - bot/main.py — webhook entry point with post_init, set_chat_menu_button, all 8 commands registered
  - bot/handlers/devops.py — /status /logs /test /deploy with 60s confirmation flow
  - bot/handlers/seo.py — /crawl /check /report with site picker and Celery dispatch
  - bot/handlers/miniapp.py — make_webapp_button(), /start, /help with WebApp inline buttons
  - app/tasks/notification_tasks.dispatch_tg_error_notification — push error alerts via httpx
  - app/routers/profile.POST /tg-notifications-toggle — HTMX toggle endpoint
  - app/templates/profile/index.html — toggle checkbox in Telegram section
  - app/config.py — TELEGRAM_WEBHOOK_SECRET, TELEGRAM_WEBHOOK_BASE_URL, TELEGRAM_BOT_PORT fields

affects:
  - Any phase that adds new bot commands
  - Any phase that needs error notifications pushed to Telegram users

tech-stack:
  added: []
  patterns:
    - "@require_auth decorator gates all bot handlers via DB allowlist check"
    - "make_webapp_button() factory for consistent WebApp InlineKeyboardButton creation"
    - "Confirmation pattern: dangerous ops show inline keyboard, auto-cancel after 60s via asyncio.create_task"
    - "Fire-and-forget Celery dispatch from bot container using send_task (no task module imports)"
    - "dispatch_tg_error_notification uses get_sync_db() context manager for Celery sync task DB access"

key-files:
  created:
    - bot/main.py
    - bot/handlers/__init__.py
    - bot/handlers/devops.py
    - bot/handlers/seo.py
    - bot/handlers/miniapp.py
  modified:
    - app/tasks/notification_tasks.py
    - app/routers/profile.py
    - app/templates/profile/index.html
    - app/config.py

key-decisions:
  - "site-picker callback pattern uses UUID-safe regex pattern r'^(crawl|check|report):[0-9a-f\\-]+$' instead of \\d+ since site IDs are UUIDs"
  - "_get_all_sites() returns all sites (not per-user) — internal tool, trusted team members only, simpler"
  - "report command dispatches send_weekly_summary_report (existing) — no separate per-site report task exists yet"
  - "dispatch_tg_error_notification uses httpx.post directly (not telegram_service.send_message_sync) to send per-user DM rather than channel message"

patterns-established:
  - "Bot handler confirmation flow: dangerous command → InlineKeyboard confirm/cancel → asyncio.create_task auto-cancel after 60s"
  - "WebApp buttons accompany every bot response via make_webapp_button() from bot.handlers.miniapp"

requirements-completed: [BOT-01, BOT-02, BOT-03]

duration: 10min
completed: 2026-04-12
---

# Phase 32 Plan 03: Bot Handlers + Notification Push Summary

**Full bot runtime: 8 command handlers (devops + SEO + miniapp), 60s confirmation flow, Celery dispatch, error push via Telegram DM, profile toggle UI**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-12T13:27:42Z
- **Completed:** 2026-04-12T13:32:21Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Bot entry point (bot/main.py) with webhook server, post_init hook, Menu Button set to /m/, all 8 commands registered
- 3 handler modules: devops (/status /logs /test /deploy), seo (/crawl /check /report with site-picker), miniapp (make_webapp_button, /start, /help)
- Dangerous ops (/test, /deploy) require confirmation via InlineKeyboard; auto-cancel task fires after 60s
- dispatch_tg_error_notification Celery task pushes error-severity notifications as DMs to opted-in users
- Profile settings page gets HTMX toggle checkbox for Telegram notification preference

## Task Commits

1. **Task 1: Bot handlers — devops, seo, miniapp + main.py entry point** - `3b8576a` (feat)
2. **Task 2: Telegram error notification push + profile toggle** - `e8e812d` (feat)

## Files Created/Modified

- `bot/main.py` — webhook entry point, post_init, set_chat_menu_button, all handlers registered
- `bot/handlers/__init__.py` — empty package marker
- `bot/handlers/devops.py` — /status /logs /test /deploy with 60s confirmation flow
- `bot/handlers/seo.py` — /crawl /check /report with site picker + Celery dispatch
- `bot/handlers/miniapp.py` — make_webapp_button(), /start, /help with WebApp inline buttons
- `app/tasks/notification_tasks.py` — added dispatch_tg_error_notification task
- `app/routers/profile.py` — added POST /tg-notifications-toggle HTMX endpoint
- `app/templates/profile/index.html` — toggle checkbox in Telegram section
- `app/config.py` — added TELEGRAM_WEBHOOK_SECRET, TELEGRAM_WEBHOOK_BASE_URL, TELEGRAM_BOT_PORT

## Decisions Made

- Used UUID-safe regex `r'^(crawl|check|report):[0-9a-f\-]+$'` for seo_site_callback since site IDs are UUIDs, not integers
- `_get_all_sites()` returns all sites (not per-user) — the bot is for trusted internal team members only
- For /report, dispatches `send_weekly_summary_report` (existing task); no per-site on-demand report task exists
- `dispatch_tg_error_notification` uses `httpx.post` directly (Telegram Bot API) to send per-user DMs, not the channel-broadcast `telegram_service.send_message_sync`

## Deviations from Plan

None — plan executed exactly as written. The plan noted `_get_all_sites` could query by user; confirmed internal tool approach and used all-sites query as specified.

## Issues Encountered

None.

## User Setup Required

None — no new external service configuration required. Existing TELEGRAM_BOT_TOKEN covers the notification task.

## Next Phase Readiness

- Phase 32 complete — all 3 plans executed
- Bot is fully wired: webhook server, all 8 commands, confirmation flow, SEO dispatch, error push, profile toggle
- Deploy requires: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, TELEGRAM_WEBHOOK_BASE_URL set in .env, plus nginx /webhook/tg route (from Plan 01)

---
*Phase: 32-telegram-bot*
*Completed: 2026-04-12*
