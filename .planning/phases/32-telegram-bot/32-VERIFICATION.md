---
phase: 32-telegram-bot
verified: 2026-04-12T00:00:00Z
status: passed
score: 8/8 must-haves verified
re_verification: false
---

# Phase 32: Telegram Bot Verification Report

**Phase Goal:** Отдельный Docker-сервис принимает команды от авторизованных пользователей и открывает Mini App кнопки
**Verified:** 2026-04-12
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Бот отвечает только на сообщения от Telegram ID из allowlist — неизвестные получают "Доступ запрещён" | VERIFIED | `bot/auth.py`: `check_user_allowed()` queries `User.telegram_id` in DB; `require_auth` decorator applied to all 14 handler functions across devops.py, seo.py, miniapp.py |
| 2 | /status, /logs, /test, /deploy — бот запрашивает подтверждение и выполняет операцию | VERIFIED | `bot/handlers/devops.py`: /status and /logs execute immediately; /test and /deploy show `InlineKeyboardMarkup` with "Выполнить"/"Отмена", auto-cancel at 60s; `confirm_callback` runs the operation via `run_command()` |
| 3 | Бот отвечает inline-кнопками, открывающими Mini App: дайджест, отчёт, позиции | VERIFIED | `bot/handlers/miniapp.py`: `make_webapp_button()` returns `InlineKeyboardButton(web_app=WebAppInfo(url=...))` pointing to /m/digest, /m/positions, /m/reports, /m/pages, /m/tools, /m/health; used throughout all handler modules |
| 4 | Telegram Bot работает как отдельный контейнер в docker-compose.yml и не падает при недоступности FastAPI | VERIFIED | `docker-compose.yml` line 121: `bot:` service with `dockerfile: Dockerfile.bot`, `depends_on: postgres + redis` only (no `api` dependency), `restart: unless-stopped`; `docker compose config --services` returns `bot` |

**Score:** 4/4 success criteria verified

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `alembic/versions/0056_add_tg_notifications_toggle.py` | VERIFIED | Contains `tg_notifications_enabled`, `op.add_column("users"`, `def downgrade` |
| `bot/config.py` | VERIFIED | `class BotSettings(BaseSettings)` with `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL`, `APP_BASE_URL`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_PORT` |
| `bot/auth.py` | VERIFIED | `async def check_user_allowed` queries `User.telegram_id`; `def require_auth` decorator returns "Доступ запрещён." |
| `bot/utils/celery_client.py` | VERIFIED | `def dispatch` calls `_celery.send_task()`, returns task ID |
| `bot/utils/shell.py` | VERIFIED | `async def run_command` with `asyncio.create_subprocess_exec`, timeout, 3000-char tail truncation |
| `bot/utils/formatters.py` | VERIFIED | `code_block`, `bold`, `status_line`, `italic` — HTML parse_mode throughout |
| `bot/database.py` | VERIFIED | `AsyncSessionLocal = async_sessionmaker(...)`, standalone engine — does NOT import `app.database` |
| `Dockerfile.bot` | VERIFIED | `FROM python:3.12-slim`, copies `app/`, `bot/`, `alembic/`; `CMD ["python", "-m", "bot.main"]`; no playwright/weasyprint |
| `docker-compose.yml` (bot service) | VERIFIED | `dockerfile: Dockerfile.bot`, `depends_on: postgres, redis` (no api), `restart: unless-stopped` |
| `nginx/conf.d/app.conf` | VERIFIED | `upstream bot_upstream { server bot:8443; }`, `location /webhook/tg { proxy_pass http://bot_upstream; }` |
| `bot/requirements.txt` | VERIFIED | `python-telegram-bot[webhooks]>=21.0,<22.0` |
| `bot/main.py` | VERIFIED | `run_webhook(...)` on port 8443, `post_init` sets MenuButton + command list, all 9 commands registered, `CallbackQueryHandler` for confirm/cancel/seo patterns, `secret_token=` set |
| `bot/handlers/devops.py` | VERIFIED | `@require_auth` on all 6 handlers; /test and /deploy show confirmation keyboard; `_schedule_auto_cancel` uses `asyncio.sleep(60)`; `confirm:deploy`, `cancel:` patterns handled |
| `bot/handlers/seo.py` | VERIFIED | `/crawl`, `/check`, `/report` with site picker; `dispatch()` called with correct task names (`app.tasks.crawl_tasks.crawl_site`, `app.tasks.position_tasks.check_positions`, `app.tasks.report_tasks.send_weekly_summary_report`) — all verified to exist in codebase |
| `bot/handlers/miniapp.py` | VERIFIED | `make_webapp_button()` using `WebAppInfo`; `/m/digest`, `/m/positions`, `/m/reports`; `start_handler` 6-button 2×3 grid; `help_handler` lists all 8 commands |
| `app/tasks/notification_tasks.py` | VERIFIED | `dispatch_tg_error_notification` task with `max_retries=3`, checks `tg_notifications_enabled`, POSTs to Telegram sendMessage API; `get_sync_db()` confirmed to exist in `app/database.py` |
| `app/routers/profile.py` | VERIFIED | `POST /tg-notifications-toggle` endpoint toggles `current_user.tg_notifications_enabled`, returns HTMX partial or redirect |
| `app/config.py` | VERIFIED | Contains `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_BASE_URL` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `bot/auth.py` | `app/models/user.py` | `select(User.id).where(User.telegram_id == telegram_id)` | WIRED | SQLAlchemy query on `User.telegram_id` confirmed |
| `bot/database.py` | PostgreSQL | standalone `create_async_engine(settings.DATABASE_URL)` | WIRED | Own engine, does not import app.database |
| `bot/main.py` | `bot/handlers/devops.py` | `CommandHandler("status", status_handler)` etc. | WIRED | All 4 devops commands registered |
| `bot/main.py` | `bot/handlers/seo.py` | `CommandHandler("crawl", crawl_handler)` etc. | WIRED | All 3 SEO commands registered |
| `bot/main.py` | `bot/handlers/miniapp.py` | `CommandHandler("start", start_handler)` | WIRED | start + help registered |
| `bot/handlers/devops.py` | `bot/utils/shell.py` | `run_command(["docker", "compose", ...])` | WIRED | Called in status_handler, logs_handler, confirm_callback |
| `bot/handlers/seo.py` | `bot/utils/celery_client.py` | `dispatch(_TASK_CRAWL, kwargs={"site_id": ...})` | WIRED | All 3 dispatch helpers call `dispatch()` |
| `bot/handlers/miniapp.py` | `bot/config.py` | `settings.APP_BASE_URL` used in `make_webapp_button` calls | WIRED | Confirmed in start_handler |
| `app/tasks/notification_tasks.py` | `app/services/telegram_service.py` | Direct httpx POST (not via telegram_service — implementation difference) | WIRED | Uses `httpx.post` to Telegram API directly; functionally equivalent |
| `docker-compose.yml` | `Dockerfile.bot` | `dockerfile: Dockerfile.bot` | WIRED | Confirmed at line 124 |
| `nginx/conf.d/app.conf` | `docker-compose.yml bot service` | `proxy_pass http://bot_upstream` → `server bot:8443` | WIRED | Upstream and location blocks confirmed |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `bot/auth.py` | `result` (scalar_one_or_none) | SQLAlchemy query on users table via `AsyncSessionLocal` | Yes — live DB query | FLOWING |
| `bot/handlers/seo.py` | `sites` list | `_get_all_sites()` queries `select(Site.id, Site.name, Site.url)` | Yes — live DB query | FLOWING |
| `bot/handlers/devops.py` | `output` from shell | `run_command(["docker", "compose", "ps", "--format", "json"])` | Yes — subprocess execution | FLOWING |
| `app/tasks/notification_tasks.py` | `user` lookup | `select(User).where(User.id == user_id)` via `get_sync_db()` | Yes — live DB query | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All bot foundation modules import cleanly | `python -c "from bot.config import BotSettings; from bot.auth import require_auth..."` | "All bot modules import OK" | PASS |
| All handler modules import cleanly | `python -c "from bot.handlers.miniapp import make_webapp_button..."` | "All handlers import OK" | PASS |
| Bot main entry point importable | `python -c "from bot.main import main; print('main() importable OK')"` | "main() importable OK" | PASS |
| Notification task registered with correct name | `python -c "from app.tasks.notification_tasks import dispatch_tg_error_notification; print(dispatch_tg_error_notification.name)"` | "app.tasks.notification_tasks.dispatch_tg_error_notification" | PASS |
| docker compose validates bot service | `docker compose config --services` | includes "bot" | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BOT-01 | 32-01, 32-03 | Бот принимает команды только от разрешённых Telegram ID (allowlist) | SATISFIED | `bot/auth.py` `check_user_allowed()` + `@require_auth` on all 14 handler functions; unknown users receive "Доступ запрещён." |
| BOT-02 | 32-03 | Пользователь может выполнить /status, /logs, /test, /deploy с подтверждением | SATISFIED | All 4 DevOps commands implemented; /test and /deploy show confirmation keyboard with 60s auto-cancel; result returned in chat |
| BOT-03 | 32-02, 32-03 | Бот может открывать Mini Apps по inline-кнопкам (дайджест, отчёт, позиции) | SATISFIED | `make_webapp_button()` with `WebAppInfo`; /start shows 6-button grid; each SEO/DevOps handler adds contextual WebApp button; bot runs as independent Docker container |

All three requirement IDs from PLAN frontmatter are accounted for. REQUIREMENTS.md lists all three as Phase 32 with no orphaned requirements.

---

### Anti-Patterns Found

No significant anti-patterns detected.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `bot/handlers/seo.py` | 27 | Task name `send_weekly_summary_report` used for /report command | Info | Semantically ambiguous — a weekly-summary task is being dispatched on-demand via /report. Functionally works but the task may not be designed for ad-hoc execution. No blocker. |
| `app/templates/profile/settings.html` | — | File does not exist (plan artifact) — toggle UI is in `index.html` instead | Info | Plan referenced `settings.html` but the profile page is `index.html`. The toggle is fully implemented in `index.html` lines 122–129. No functional gap. |

---

### Human Verification Required

#### 1. Bot Webhook Registration

**Test:** With a real `TELEGRAM_BOT_TOKEN` and public HTTPS URL, start the bot container and send `/start` from a registered Telegram account.
**Expected:** Bot responds with welcome message and 6 Mini App buttons (Дайджест, Позиции, Отчёты, Страницы, Инструменты, Здоровье).
**Why human:** Requires live Telegram API connection and real bot token.

#### 2. Access Denial for Unknown Users

**Test:** Send any command to the bot from a Telegram account not registered in the platform DB.
**Expected:** Bot responds "Доступ запрещён." with no command execution.
**Why human:** Requires live Telegram interaction.

#### 3. Mini App Button Opens Correct URL

**Test:** Press "Дайджест" button after /start, verify it opens the platform at `/m/digest` path.
**Expected:** Telegram Mini App webview opens the platform page.
**Why human:** Requires Telegram client with Mini App support.

#### 4. Confirmation Flow with Auto-Cancel

**Test:** Send /deploy, wait 60 seconds without pressing any button.
**Expected:** Bot edits the message to show "Операция 'deploy' отменена (тайм-аут 60 сек)."
**Why human:** Requires live bot session and timing verification.

---

### Gaps Summary

No gaps. All 4 success criteria are verified with substantive, wired, and data-flowing implementations.

The only minor discrepancy is that `app/templates/profile/settings.html` does not exist as a separate file — the toggle UI was placed in `app/templates/profile/index.html` instead, which is the actual profile page. This is functionally correct and not a gap.

---

_Verified: 2026-04-12_
_Verifier: Claude (gsd-verifier)_
