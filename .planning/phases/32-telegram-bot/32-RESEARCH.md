# Phase 32: Telegram Bot - Research

**Researched:** 2026-04-12
**Domain:** python-telegram-bot 21, Telegram WebApp, Webhook delivery, Docker service, Celery integration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Framework — python-telegram-bot 21 (async-native, ConversationHandler, inline keyboards). Уже рекомендован в PROJECT.md.
- **D-02:** Delivery — Webhook (не long polling). PTB 21 встроенный webhook server (starlette/uvicorn) на отдельном порту, Nginx проксирует `/webhook/tg` на контейнер бота.
- **D-03:** Связь с платформой — прямой доступ к PostgreSQL (read) + Celery tasks через Redis (write). Без промежуточного HTTP к FastAPI.
- **D-04:** Docker — отдельный контейнер `bot` в docker-compose.yml, зависит от redis + postgres. Не падает при недоступности FastAPI (graceful degradation).
- **D-05:** DevOps-команды: `/status`, `/logs`, `/test`, `/deploy`.
- **D-06:** SEO-команды: `/crawl`, `/check`, `/report`.
- **D-07:** Подтверждение опасных операций — inline-кнопки «✅ Выполнить» / «❌ Отмена», timeout 60 секунд → авто-отмена.
- **D-08:** Доступ — allowlist по Telegram ID из конфига/БД. Неизвестные пользователи получают «Доступ запрещён».
- **D-09:** Menu Button открывает /m/ (домашняя страница платформы).
- **D-10:** Inline WebApp-кнопки в контекстных ответах: дайджест, отчёты, позиции, страницы, здоровье, инструменты.
- **D-11:** Контекстные кнопки — после /status → «Открыть дайджест», после /check → «Открыть позиции» и т.д.
- **D-12:** Push только критических уведомлений (severity=error).
- **D-13:** Интеграция с Notification моделью (Phase 17) — при severity=error + telegram_id + toggle=on → дублировать в Telegram.
- **D-14:** Настройки — один тоггл «Получать уведомления в Telegram» в профиле пользователя.

### Claude's Discretion

- Структура модулей внутри контейнера бота (handlers, commands, utils)
- Формат текстовых ответов бота (Markdown vs HTML)
- Конкретная реализация graceful degradation при недоступности FastAPI/DB
- Стратегия регистрации webhook (при старте контейнера vs отдельная команда)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BOT-01 | Бот принимает команды только от разрешённых Telegram ID (allowlist) | User.telegram_id уже в БД; allowlist = DB query против таблицы users; filter middleware pattern |
| BOT-02 | /status, /logs, /test, /deploy через бота с подтверждением | PTB CommandHandler + CallbackQueryHandler; asyncio.create_subprocess_exec для shell; ConversationHandler timeout для 60s |
| BOT-03 | Бот открывает Mini Apps по inline-кнопкам (дайджест, отчёт, позиции) | InlineKeyboardButton(web_app=WebAppInfo(url=...)); MenuButtonWebApp для chat menu button |
</phase_requirements>

---

## Summary

Фаза строит отдельный Docker-контейнер `bot` поверх python-telegram-bot 21 (PTB 21) в webhook-режиме. PTB 21 — асинхронный, строится через `ApplicationBuilder`, обработчики регистрируются как `CommandHandler` / `CallbackQueryHandler`. Webhook-сервер PTB базируется на starlette/uvicorn — контейнер запускает uvicorn на порту 8443 (или 80), Nginx добавляет upstream `bot` и проксирует `/webhook/tg` на него.

Ключевой принцип: бот не ходит в FastAPI по HTTP. Для read-операций он открывает свою AsyncSession к PostgreSQL; для write-операций (запуск crawl, check, report, deploy) отправляет Celery-задачу в Redis. Это делает бот независимым от uptime API-контейнера — при его падении бот продолжает работать.

Три новых артефакта в кодовой базе: 1) директория `bot/` с отдельным Python-пакетом (main.py, handlers/, utils/); 2) Dockerfile.bot на базе `python:3.12-slim`; 3) сервис `bot` в docker-compose.yml. В основной `app/` добавляются: поле `tg_notifications_enabled` в User (миграция 0056), Celery task `dispatch_error_notification_to_telegram`, HTMX-тоггл в профиле.

**Primary recommendation:** Использовать PTB 21 `Application.run_webhook()` с `listen='0.0.0.0'`, `port=8443`, `url_path='/webhook/tg'`, `webhook_url=HTTPS_URL/webhook/tg`. Middleware-функция `check_auth` проверяет `telegram_id` по БД до передачи update в handler.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | 21.x (21.11.1 latest в серии 21) | Bot framework, webhook, handlers, keyboards | Зафиксирован в D-01; async-native с PTB 20+; ConversationHandler, InlineKeyboard, MenuButton — всё встроено |
| starlette | ~0.40.x | HTTP сервер для webhook (bundled с PTB) | PTB 21 webhook использует starlette под капотом; уже в transitive deps |
| uvicorn[standard] | ~0.30.x | ASGI runner для starlette | PTB 21 customwebhookbot example использует uvicorn |
| asyncpg / SQLAlchemy 2.0 | уже в requirements.txt | PostgreSQL read из контейнера bot | Переиспользуем app.database / app.models напрямую |
| redis-py 5.0 | уже в requirements.txt | Отправка Celery задач через Redis | celery.execute + send_task или прямой Redis pub/sub |
| loguru 0.7 | уже в requirements.txt | Логирование | Единый стандарт проекта |
| pydantic-settings 2.x | уже в requirements.txt | Config (BOT_TOKEN, allowlist, webhook URL) | Единый стандарт проекта |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| celery[redis] 5.4 | уже в requirements.txt | Отправка задач crawl/check/report/deploy | D-03: write через Celery |
| httpx 0.27 | уже в requirements.txt | Fallback HTTP-вызовы если нужны | Резервный вызов API endpoints |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PTB 21 `run_webhook()` | aiogram 3 webhook | aiogram легче, но PTB уже прописан в PROJECT.md и CLAUDE.md |
| PTB 21 `run_webhook()` | PTB 22 | PTB 22 уже вышел (22.7 актуальная), но D-01 фиксирует 21; минимальные breaking changes между 21 и 22 |
| `asyncio.create_subprocess_exec` | `subprocess.run` | subprocess.run блокирует event loop; asyncio.create_subprocess_exec — правильный выбор в async handler |

**Installation (в bot/requirements.txt):**
```bash
python-telegram-bot[webhooks]>=21.0,<22.0
```

Флаг `[webhooks]` добавляет starlette и uvicorn. Остальные зависимости (sqlalchemy, asyncpg, celery, redis, loguru, pydantic-settings) наследуем из основного requirements.txt через общую сборку или копируем нужное подмножество.

**Примечание по версии:** PTB 22.7 — актуальная на апрель 2026. PTB 21.11.1 — последняя в серии 21. Рекомендуем `>=21.0,<22.0` для стабильности согласно D-01.

---

## Architecture Patterns

### Recommended Project Structure
```
bot/
├── __init__.py
├── main.py              # Application build, webhook setup, startup
├── config.py            # BotSettings (BOT_TOKEN, WEBHOOK_URL, ALLOWED_IDS)
├── auth.py              # check_user_allowed() — DB lookup по telegram_id
├── database.py          # AsyncSessionLocal для bot (переиспользует app.database)
├── handlers/
│   ├── __init__.py
│   ├── devops.py        # /status, /logs, /test, /deploy + confirm callbacks
│   ├── seo.py           # /crawl, /check, /report + confirm callbacks
│   └── miniapp.py       # /start, /help, контекстные WebApp кнопки
├── utils/
│   ├── __init__.py
│   ├── formatters.py    # HTML-форматирование ответов
│   └── celery_client.py # send_task() обёртка
Dockerfile.bot
```

В основном `app/`:
```
app/
├── models/user.py       # + tg_notifications_enabled: bool (миграция 0056)
├── tasks/
│   └── notification_tasks.py  # + dispatch_tg_error_notification task
├── routers/
│   └── profile.py       # + POST /profile/tg-notifications-toggle
alembic/versions/0056_add_tg_notifications_toggle.py
```

### Pattern 1: Application Build + Webhook (PTB 21)
**What:** Стандартный способ запуска PTB 21 в webhook-режиме без Updater
**When to use:** Всегда — Updater нужен только для polling

```python
# bot/main.py — Source: PTB 21 docs / customwebhookbot example
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

async def main():
    app = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .build()
    )
    
    # Регистрируем handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("deploy", deploy_handler))
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^confirm:"))
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern="^cancel:"))

    # Запуск webhook (starlette + uvicorn под капотом)
    await app.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path="/webhook/tg",
        secret_token=settings.WEBHOOK_SECRET,
        webhook_url=f"{settings.WEBHOOK_BASE_URL}/webhook/tg",
    )
```

### Pattern 2: Auth Middleware (allowlist)
**What:** Проверка Telegram ID до выполнения любой команды
**When to use:** Для каждого handler-а через обёртку или TypeHandler

```python
# bot/auth.py
from sqlalchemy import select
from app.models.user import User

async def check_user_allowed(telegram_id: int, db: AsyncSession) -> bool:
    """Returns True if telegram_id is linked to an active platform user."""
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id, User.is_active == True)
    )
    return result.scalar_one_or_none() is not None

# Декоратор для handlers:
def require_auth(handler_func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        tg_id = update.effective_user.id
        async with AsyncSessionLocal() as db:
            if not await check_user_allowed(tg_id, db):
                await update.message.reply_text("Доступ запрещён.")
                return
        return await handler_func(update, context)
    return wrapper
```

**ВАЖНО:** Реализация allowlist через таблицу `users` (User.telegram_id), а не через env-переменную. Это соответствует D-08 и позволяет управлять доступом без рестарта контейнера. Только пользователи с `telegram_id IS NOT NULL AND is_active = TRUE` имеют доступ.

### Pattern 3: Confirmation с timeout 60s
**What:** Inline-кнопки подтверждения с авто-отменой через asyncio.create_task + sleep
**When to use:** /deploy, /test (опасные операции согласно D-07)

```python
# bot/handlers/devops.py
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

_pending_confirmations: dict[int, asyncio.Task] = {}  # message_id → timeout task

async def deploy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Выполнить", callback_data="confirm:deploy"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel:deploy"),
    ]])
    msg = await update.message.reply_text(
        "⚠️ <b>Деплой</b>: git pull + restart. Подтверди:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    # Auto-cancel after 60s
    async def _auto_cancel():
        await asyncio.sleep(60)
        await context.bot.edit_message_text(
            chat_id=msg.chat_id,
            message_id=msg.message_id,
            text="⏱ Время истекло. Операция отменена.",
        )
    task = asyncio.create_task(_auto_cancel())
    _pending_confirmations[msg.message_id] = task

async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg_id = query.message.message_id
    # Отменяем auto-cancel task
    if task := _pending_confirmations.pop(msg_id, None):
        task.cancel()
    op = query.data.split(":")[1]  # "deploy", "test", etc.
    await query.edit_message_text(f"⏳ Выполняю {op}...")
    # Dispatch в Celery или subprocess
    await _execute_operation(op, query.message.chat_id, context)
```

**Альтернатива (рекомендованная PTB):** `ConversationHandler` с `conversation_timeout=60` — но для простых yes/no confirmations достаточно `_pending_confirmations` dict + `asyncio.create_task`.

### Pattern 4: WebApp Inline Button
**What:** Кнопка, открывающая Mini App по конкретному /m/ маршруту
**When to use:** В ответах на команды (D-10, D-11)

```python
# bot/handlers/miniapp.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

def make_webapp_button(text: str, path: str, base_url: str) -> InlineKeyboardButton:
    """Returns InlineKeyboardButton that opens a Mini App URL."""
    # ВАЖНО: URL должен быть HTTPS для WebApp
    url = f"{base_url}{path}"
    return InlineKeyboardButton(text, web_app=WebAppInfo(url=url))

# Пример: после /status
keyboard = InlineKeyboardMarkup([[
    make_webapp_button("📊 Открыть дайджест", "/m/digest", settings.APP_BASE_URL)
]])

# Пример: после /check
keyboard = InlineKeyboardMarkup([[
    make_webapp_button("📈 Позиции", "/m/positions", settings.APP_BASE_URL),
    make_webapp_button("📋 Отчёты", "/m/reports", settings.APP_BASE_URL),
]])
```

### Pattern 5: Menu Button (один раз при старте)
**What:** Установка кнопки меню чата, открывающей /m/
**When to use:** В `post_init` приложения при старте бота

```python
# bot/main.py
from telegram import MenuButtonWebApp, WebAppInfo

async def post_init(application: Application) -> None:
    """Called after application.initialize() — идеальное место для one-time setup."""
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Открыть платформу",
            web_app=WebAppInfo(url=f"{settings.APP_BASE_URL}/m/"),
        )
    )
    await application.bot.set_my_commands([
        ("status", "Статус сервисов"),
        ("logs", "Последние логи"),
        ("test", "Запустить тесты"),
        ("deploy", "Деплой (git pull + restart)"),
        ("crawl", "Запустить краул сайта"),
        ("check", "Проверить позиции"),
        ("report", "Сформировать отчёт"),
        ("help", "Помощь"),
    ])

app = Application.builder().token(TOKEN).post_init(post_init).build()
```

**ВАЖНО:** `set_chat_menu_button()` без `chat_id` устанавливает меню для ВСЕХ чатов бота. Это именно то, что нужно для внутреннего инструмента.

### Pattern 6: DevOps команды через asyncio.create_subprocess_exec
**What:** Выполнение shell-команд без блокировки event loop
**When to use:** /status (docker stats), /logs, /deploy

```python
# bot/utils/shell.py
import asyncio

async def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run shell command, return (returncode, output)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(errors="replace")[-3000:]  # Telegram limit
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "Timeout: команда не завершилась за отведённое время"
```

/deploy — это **docker compose pull + docker compose restart api worker** из директории проекта. Контейнер `bot` должен иметь смонтированный `/var/run/docker.sock` или доступ к docker CLI для этого. **Это архитектурное решение на усмотрение Claude (discretion):** либо `docker.sock` mount, либо `/deploy` отправляет Celery-задачу которая вызывает subprocess на worker-е. Рекомендация: отправлять специальную Celery task `run_deploy_task` на worker — worker имеет доступ к shell на хосте. Так избегаем привилегированного доступа в bot-контейнере.

### Pattern 7: Celery task dispatch из бота
**What:** Отправка задачи в существующие Celery очереди без импорта всего app
**When to use:** /crawl, /check, /report

```python
# bot/utils/celery_client.py
from celery import Celery

# Lightweight Celery app — только для send_task, без include задач
_celery = Celery(broker=settings.REDIS_URL)

def dispatch(task_name: str, args: list = None, kwargs: dict = None, queue: str = "default"):
    """Send a task to existing Celery workers."""
    _celery.send_task(task_name, args=args or [], kwargs=kwargs or {}, queue=queue)
```

Пример: `/crawl` отправляет `app.tasks.crawl_tasks.run_site_crawl` с `site_id`.

### Pattern 8: Push-уведомления severity=error
**What:** Celery task, дублирующая error-notification в Telegram
**When to use:** При создании Notification с severity="error" в основном app

```python
# app/tasks/notification_tasks.py (добавить новую task)
@celery_app.task(name="app.tasks.notification_tasks.dispatch_tg_error_notification", ...)
def dispatch_tg_error_notification(user_id: str, title: str, body: str) -> None:
    """Send error notification to Telegram if user has telegram_id + toggle=on."""
    with get_sync_db() as db:
        user = db.execute(select(User).where(User.id == uuid.UUID(user_id))).scalar_one_or_none()
        if not user or not user.telegram_id or not user.tg_notifications_enabled:
            return
        # Reuse existing send_message_sync pattern
        from app.services.telegram_service import send_message_sync
        text = f"🔴 <b>{title}</b>\n{body}"
        send_message_sync_to_user(user.telegram_id, text)
```

Вызов этой task добавляется в сервисный слой при создании Notification с severity="error" (или в create_notification хелпер).

### Anti-Patterns to Avoid
- **Long polling в production:** Out of scope (REQUIREMENTS.md). Только webhook.
- **PTB `Updater` класс:** Устарел для webhook-only режима в PTB 21. Использовать `Application.builder().updater(None)` для custom webhook.
- **Синхронный subprocess.run в handlers:** Блокирует asyncio event loop. Использовать `asyncio.create_subprocess_exec`.
- **Import всего `app.*` в bot-контейнер:** Нужны только `app.models`, `app.database`, `app.config`. Не импортировать `app.main` (создаст FastAPI приложение).
- **HTTP-запросы к FastAPI:** Нарушает D-03. Прямой DB + Redis.
- **WebApp URL без HTTPS:** Telegram Mini Apps требуют HTTPS. URL в `WebAppInfo` должен быть HTTPS. В dev — либо ngrok, либо настроен SSL.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bot framework | Собственный HTTP-сервер + Bot API wrapper | python-telegram-bot 21 | PTB обрабатывает webhook parsing, update routing, rate limits, error handling |
| HMAC webhook verification | Ручная проверка заголовка | `secret_token` параметр в `run_webhook()` | PTB автоматически проверяет `X-Telegram-Bot-Api-Secret-Token` при `secret_token=` |
| Keyboard confirmation | Свой state machine | CallbackQueryHandler + `asyncio.create_task` timeout | PTB routing по `callback_data` pattern уже есть |
| Async subprocess | threading.Thread | `asyncio.create_subprocess_exec` | Не блокирует event loop |
| User auth | Ручной парсинг update.from | `update.effective_user.id` + DB lookup | PTB предоставляет parsed user object |
| Message formatting | HTML-шаблоны | f-string с `parse_mode="HTML"` | PTB поддерживает HTML + MarkdownV2 out of the box |

**Key insight:** PTB 21 — полноценный async framework с routing, handler registration, error handling, rate limiting (via `Application.create(rate_limiter=...)`). Не нужно писать middleware вручную — auth реализуется как обёртка над handler функцией.

---

## Common Pitfalls

### Pitfall 1: Webhook требует HTTPS
**What goes wrong:** Telegram отклоняет `setWebhook` если URL не HTTPS. Mini App кнопки (`WebAppInfo`) тоже требуют HTTPS URL.
**Why it happens:** Telegram Bot API security requirement.
**How to avoid:** В production — за Nginx с Let's Encrypt. В dev — либо ngrok tunnel, либо self-signed cert через `cert=` параметр `run_webhook()`. APP_BASE_URL в config должен быть `https://`.
**Warning signs:** `setWebhook` возвращает `"HTTPS webhook required"`.

### Pitfall 2: Telegram поддерживает только 4 порта для webhook
**What goes wrong:** Контейнер слушает на нестандартном порту, Telegram не может достучаться.
**Why it happens:** Telegram Bot API ограничение: только порты 443, 80, 88, 8443.
**How to avoid:** Использовать Nginx как reverse proxy на стандартном 443/80. Bot-контейнер может слушать на любом порту — Nginx проксирует.
**Warning signs:** Webhook установлен, но updates не приходят.

### Pitfall 3: Import app.main в bot-контейнере
**What goes wrong:** `from app.main import app` создаёт FastAPI приложение + все lifespan hooks + попытку открыть playwright.
**Why it happens:** bot/ и app/ в одном Docker image, Python path включает оба.
**How to avoid:** В Dockerfile.bot не запускать `app.main`. Bot импортирует только: `app.models.*`, `app.database`, `app.config`, `app.tasks.*` (для send_task имён), `app.services.telegram_service`.
**Warning signs:** Celery worker_process_init запускает Playwright при старте бота.

### Pitfall 4: CallbackQuery без `answer()`
**What goes wrong:** Telegram показывает spinner на кнопке бесконечно, пользователь видит "бот не отвечает".
**Why it happens:** PTB требует вызова `await query.answer()` для каждого callback query.
**How to avoid:** Первая строка любого `CallbackQueryHandler` — `await query.answer()` (можно с текстом: `await query.answer("Выполняю...")`).
**Warning signs:** Inline кнопки "зависают" после нажатия.

### Pitfall 5: PTB 21 asyncio event loop конфликт с Celery
**What goes wrong:** Если bot-контейнер пытается импортировать Celery workers с `@beat_init`, возникает конфликт event loops.
**Why it happens:** Celery сигналы `beat_init`, `worker_process_init` в `celery_app.py` запускают Playwright при init.
**How to avoid:** Bot создаёт lightweight Celery instance только для `send_task()` (без `include=[]`). НЕ запускать celery worker в bot-контейнере — только отправка задач.
**Warning signs:** `RuntimeError: This event loop is already running` при старте bot-контейнера.

### Pitfall 6: tg_notifications_enabled — нужна Alembic миграция
**What goes wrong:** Поле отсутствует в User модели, toggle в профиле падает с AttributeError.
**Why it happens:** D-14 требует нового boolean поля в `users` таблице.
**How to avoid:** Миграция 0056 добавляет `tg_notifications_enabled BOOLEAN NOT NULL DEFAULT FALSE`. Wave 0 плана.
**Warning signs:** `AttributeError: User has no attribute 'tg_notifications_enabled'`.

### Pitfall 7: WebApp URL — domain должен совпадать с App
**What goes wrong:** Telegram не открывает Mini App если домен не внесён в список разрешённых для бота через BotFather.
**Why it happens:** BotFather требует указать домены для Mini Apps (`/setdomain` или через Bot Settings > Domain).
**How to avoid:** После деплоя — зайти в BotFather → Bot Settings → Menu Button → Set Domain. В `WebAppInfo` URL должен содержать именно этот домен.
**Warning signs:** Mini App не открывается, Telegram показывает ошибку домена.

---

## Code Examples

### Minimal webhook bot setup (PTB 21)
```python
# bot/main.py
# Source: PTB 21 docs + customwebhookbot example
import asyncio
from telegram import MenuButtonWebApp, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.config import BotSettings
from bot.handlers.devops import status_handler, deploy_handler, logs_handler, test_handler
from bot.handlers.seo import crawl_handler, check_handler, report_handler
from bot.handlers.miniapp import start_handler, help_handler, confirm_callback, cancel_callback

settings = BotSettings()

async def post_init(application: Application) -> None:
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Открыть платформу",
            web_app=WebAppInfo(url=f"{settings.APP_BASE_URL}/m/"),
        )
    )

def main():
    app = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("logs", logs_handler))
    app.add_handler(CommandHandler("test", test_handler))
    app.add_handler(CommandHandler("deploy", deploy_handler))
    app.add_handler(CommandHandler("crawl", crawl_handler))
    app.add_handler(CommandHandler("check", check_handler))
    app.add_handler(CommandHandler("report", report_handler))
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern=r"^cancel:"))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(settings.BOT_PORT),
        url_path="/webhook/tg",
        secret_token=settings.WEBHOOK_SECRET,
        webhook_url=f"{settings.WEBHOOK_BASE_URL}/webhook/tg",
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
```

### docker-compose.yml service block
```yaml
  bot:
    build:
      context: .
      dockerfile: Dockerfile.bot
    command: python -m bot.main
    env_file: .env
    environment:
      BOT_PORT: "8443"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    # НЕ зависит от api — graceful degradation (D-04)
```

### Nginx upstream добавление
```nginx
upstream bot {
    server bot:8443;
}

# Добавить в server block:
location /webhook/tg {
    proxy_pass http://bot;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Alembic migration 0056
```python
# alembic/versions/0056_add_tg_notifications_toggle.py
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "tg_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

def downgrade() -> None:
    op.drop_column("users", "tg_notifications_enabled")
```

---

## Existing Code Analysis

### Reusable Assets (подтверждено чтением кода)

| Asset | File | Что переиспользуем |
|-------|------|--------------------|
| HMAC WebApp validation | `app/services/telegram_auth.py` | Готовый `validate_telegram_webapp_initdata()` — можно переиспользовать в боте для верификации webhook secret (хотя PTB делает это автоматически) |
| send_message_sync | `app/services/telegram_service.py:38` | Паттерн синхронной отправки для Celery task `dispatch_tg_error_notification` |
| `_tg_request()` | `app/services/channel_service.py:18` | Паттерн httpx wrapper — можно переиспользовать если нужен прямой Bot API вызов вне PTB |
| HTML parse_mode | `app/services/telegram_service.py:27` | Проект уже использует HTML parse_mode — единообразно использовать HTML в боте тоже |
| `AsyncSessionLocal` | `app/database.py` | Прямой импорт в bot/ для read-запросов |
| User.telegram_id | `app/models/user.py:47` | `BigInteger, nullable=True, unique=True` — уже есть, allowlist строится на нём |
| Notification.severity | `app/models/notification.py:45` | String(16), server_default='info' — фильтр `severity == 'error'` для D-12 |
| Celery send_task pattern | `app/tasks/channel_tasks.py` | Паттерн публикации через httpx.post напрямую показывает что tasks используют sync httpx — dispatch из бота идёт через `celery.send_task()` |

### Missing Assets (нужно создать)

| What | Where | Why |
|------|-------|-----|
| `tg_notifications_enabled` field | `app/models/user.py` | D-14: тоггл в профиле; нужна миграция 0056 |
| `dispatch_tg_error_notification` task | `app/tasks/notification_tasks.py` | D-13: push при severity=error |
| Toggle endpoint | `app/routers/profile.py` | D-14: HTMX POST `/profile/tg-notifications-toggle` |
| `bot/` package | корень проекта | Весь новый код бота |
| `Dockerfile.bot` | корень проекта | Отдельный image для bot-контейнера |
| `bot` service | `docker-compose.yml` | D-04 |
| Nginx upstream + location | `nginx/conf.d/app.conf` | D-02: `/webhook/tg` → bot:8443 |

### Config новые переменные (в `app/config.py`)

```python
# Добавить в Settings:
TELEGRAM_WEBHOOK_SECRET: str = ""      # secret_token для PTB run_webhook
TELEGRAM_WEBHOOK_BASE_URL: str = ""    # HTTPS base URL для webhook_url
TELEGRAM_BOT_PORT: int = 8443          # порт бота в контейнере
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PTB polling (Updater) | PTB webhook (Application без Updater) | PTB v20 (2022) | run_webhook() — стандарт для production; polling только для dev/testing |
| PTB v13 sync API | PTB v20+ async API | PTB v20 (2022) | Весь код — async/await; ConversationHandler async |
| Ручной HTTP endpoint для webhook | `application.run_webhook()` встроенный | PTB v20 | PTB сам запускает starlette/uvicorn, регистрирует webhook в Telegram |
| `Updater.start_webhook()` | `Application.run_webhook()` | PTB v20 | Updater — legacy, ApplicationBuilder — new standard |

**PTB 22 (вышла в 2025):** Актуальная серия — 22.7. Серия 21 (21.11.1) — LTS-стабильная. Между 21 и 22 только незначительные breaking changes (дефолты таймаутов, типы PassportFile). Для нас различий нет — CLAUDE.md фиксирует 21, используем `>=21.0,<22.0`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Bot runtime | ✓ | 3.12 (system) | — |
| PostgreSQL | Bot DB reads | ✓ | 16 (docker) | — |
| Redis | Celery dispatch | ✓ | 7.2 (docker) | — |
| python-telegram-bot | Bot framework | ✗ не в requirements.txt | 21.11.1 доступна | Добавить в Dockerfile.bot |
| Docker | Контейнеризация | ✓ | docker compose v2 | — |
| Nginx | Webhook proxy | ✓ (конфиг есть) | nginx в docker | Добавить upstream + location |
| HTTPS / SSL | Webhook + WebApp | Требуется | nginx.conf SSL закомментирован | Wave 0: убедиться что APP_BASE_URL=https:// или dev-only: skip webhook |

**Missing dependencies with no fallback:**
- `python-telegram-bot[webhooks]>=21.0,<22.0` — не в requirements.txt. Нужен в Dockerfile.bot (или отдельный bot/requirements.txt).

**Missing dependencies with fallback:**
- HTTPS: в dev-среде можно временно использовать long polling вместо webhook для тестирования логики handlers.

---

## Open Questions

1. **Deploy через /deploy — docker.sock vs Celery worker**
   - What we know: D-05 говорит "/deploy (git pull + restart)". Bot-контейнер не должен иметь privileged доступ.
   - What's unclear: Должен ли bot-контейнер монтировать `/var/run/docker.sock` или dispatch специальную Celery task на worker который имеет доступ?
   - Recommendation: Celery task `run_deploy_task` на `default` queue — worker запускает subprocess. Безопаснее, соответствует D-03 (write через Celery).

2. **Site selection для /crawl, /check, /report**
   - What we know: D-06 говорит "/crawl (запуск краула для сайта)" — но у пользователя много сайтов.
   - What's unclear: Как выбирать сайт? Inline-кнопки со списком? Аргумент команды `/crawl site_slug`?
   - Recommendation: Если у пользователя 1 сайт — запускать его автоматически. Если несколько — показывать InlineKeyboard со списком (PTB `CallbackQueryHandler`). Плановое решение на усмотрение Claude (discretion).

3. **Webhook registration при старте**
   - What we know: `app.run_webhook()` автоматически вызывает `set_webhook()` при старте, если передан `webhook_url`.
   - What's unclear: Нужно ли добавлять `drop_pending_updates=True` в production?
   - Recommendation: Да — `drop_pending_updates=True` при первом старте предотвращает replay старых updates.

---

## Project Constraints (from CLAUDE.md)

- **Tech Stack FIXED:** Python 3.12, FastAPI 0.111+, SQLAlchemy 2.0 async, Alembic, asyncpg, Celery 5 + Redis 7, Playwright 1.45+, Jinja2 + HTMX — no substitutions. Bot-контейнер наследует эти constraints (использует те же SQLAlchemy/asyncpg/Celery).
- **Database:** All schema changes via Alembic migrations. Field `tg_notifications_enabled` требует миграции 0056.
- **Celery:** retry=3 for all external API calls. `dispatch_tg_error_notification` task должна иметь `max_retries=3`.
- **Logging:** loguru, JSON format, 10MB rotation, 30-day retention — применяется в bot/ тоже.
- **GSD Workflow:** No direct repo edits outside GSD workflow.
- **python-telegram-bot 21:** Зафиксирован в CLAUDE.md (supporting libraries section).

---

## Sources

### Primary (HIGH confidence)
- PTB 21 customwebhookbot example (starlettebot.py) — webhook setup, Application without Updater
- PTB 21 docs — `ApplicationBuilder`, `run_webhook()`, `CallbackQueryHandler`, `MenuButtonWebApp`, `WebAppInfo`
- Codebase read: `app/models/user.py`, `app/models/notification.py`, `app/config.py`, `app/services/telegram_service.py`, `app/services/channel_service.py`, `app/tasks/channel_tasks.py`, `app/tasks/notification_tasks.py`, `app/celery_app.py`, `docker-compose.yml`, `nginx/conf.d/app.conf`

### Secondary (MEDIUM confidence)
- PyPI `pip index versions python-telegram-bot` — confirmed 21.11.1 as latest in 21.x series, 22.7 as latest overall
- WebSearch: PTB 21 webhook `run_webhook()` parameters — confirmed port constraints, `secret_token`, `url_path`
- WebSearch: PTB 22 changelog — confirmed minimal breaking changes irrelevant to this use case

### Tertiary (LOW confidence)
- `/deploy` security architecture (docker.sock vs Celery) — architecture recommendation based on reasoning, not docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PTB 21 зафиксирован решением D-01; версии проверены через pip index
- Architecture: HIGH — основан на реальном чтении кодовой базы + PTB официальных примерах
- Pitfalls: HIGH — большинство верифицированы через официальную документацию PTB + Telegram Bot API

**Research date:** 2026-04-12
**Valid until:** 2026-07-12 (PTB стабилен; следить за PTB 22 breaking changes если решат обновить)
