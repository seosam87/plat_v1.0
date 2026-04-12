# Phase 32: Telegram Bot - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Отдельный Docker-сервис Telegram Bot: принимает команды от авторизованных пользователей (allowlist по Telegram ID), выполняет DevOps и SEO операции, отправляет критические уведомления, открывает Mini App кнопками.

**In scope:**
- Docker-контейнер `bot` с python-telegram-bot 21 (webhook mode)
- DevOps-команды: /status, /logs, /test, /deploy
- SEO-команды: /crawl, /check, /report
- Inline-кнопки подтверждения опасных операций (timeout 60s)
- Menu Button → /m/ (домашняя) + inline WebApp-кнопки в ответах бота
- Push критических уведомлений (severity=error) из Notification модели в Telegram
- Настройка on/off в профиле пользователя

**Out of scope:**
- Conversation flows (диалоги с состоянием)
- Claude Code Agent интеграция (Phase 33)
- Гранулярные настройки уведомлений (категории, quiet hours)
- Бот для клиентов (только внутренняя команда)

</domain>

<decisions>
## Implementation Decisions

### Архитектура бота
- **D-01:** Фреймворк — python-telegram-bot 21 (async-native, ConversationHandler, inline keyboards). Уже рекомендован в PROJECT.md.
- **D-02:** Delivery — Webhook (не long polling). PTB 21 встроенный webhook server (starlette/uvicorn) на отдельном порту, Nginx проксирует `/webhook/tg` на контейнер бота.
- **D-03:** Связь с платформой — прямой доступ к PostgreSQL (read) + Celery tasks через Redis (write). Без промежуточного HTTP к FastAPI.
- **D-04:** Docker — отдельный контейнер `bot` в docker-compose.yml, зависит от redis + postgres. Не падает при недоступности FastAPI (graceful degradation).

### Набор команд
- **D-05:** DevOps-команды: `/status` (здоровье сервисов), `/logs` (последние N строк), `/test` (pytest), `/deploy` (git pull + restart).
- **D-06:** SEO-команды: `/crawl` (запуск краула для сайта), `/check` (проверка позиций), `/report` (формирование PDF-отчёта).
- **D-07:** Подтверждение опасных операций — inline-кнопки «✅ Выполнить» / «❌ Отмена», timeout 60 секунд → авто-отмена.
- **D-08:** Доступ — allowlist по Telegram ID из конфига/БД. Неизвестные пользователи получают «Доступ запрещён».

### Mini App кнопки
- **D-09:** Menu Button (кнопка внизу чата) открывает /m/ (домашняя страница платформы).
- **D-10:** Inline WebApp-кнопки в контекстных ответах бота. Расширенный набор: дайджест (/m/digest), отчёты (/m/reports), позиции (/m/positions), страницы (/m/pages), здоровье (/m/health), инструменты (/m/tools).
- **D-11:** Контекстные кнопки — после /status показывать кнопку «Открыть дайджест», после /check — «Открыть позиции» и т.д.

### Уведомления в Telegram
- **D-12:** Push только критических уведомлений (severity=error): падение позиций > порога, ошибки краулера, фейл деплоя.
- **D-13:** Интеграция с существующей Notification моделью (Phase 17) — при создании notification с severity=error, если у пользователя telegram_id и включены Telegram-уведомления, дублировать в Telegram.
- **D-14:** Настройки — один тоггл в профиле пользователя: «Получать уведомления в Telegram» (on/off). Без гранулярных категорий в MVP.

### Claude's Discretion
- Структура модулей внутри контейнера бота (handlers, commands, utils)
- Формат текстовых ответов бота (Markdown vs HTML)
- Конкретная реализация graceful degradation при недоступности FastAPI/DB
- Стратегия регистрации webhook (при старте контейнера vs отдельная команда)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Telegram Integration (existing code)
- `app/services/telegram_auth.py` — HMAC-SHA256 валидация WebApp initData, Login Widget flow
- `app/services/telegram_service.py` — Alert service (position drops, changes) — паттерн отправки сообщений
- `app/services/channel_service.py` — Bot API через httpx, `_tg_request()` wrapper — паттерн прямых вызовов
- `app/tasks/channel_tasks.py` — Celery task для публикации постов — паттерн бот + Celery

### Mobile WebApp (Phase 26)
- `app/routers/mobile.py` — /m/ роутер, WebApp auth endpoint `/m/auth/telegram-webapp`
- `app/templates/mobile/base_mobile.html` — базовый мобильный шаблон

### Notifications (Phase 17)
- `app/models/notification.py` — Notification модель (kind, severity, user_id)
- `app/routers/notifications.py` — Notification endpoints
- `app/tasks/notification_tasks.py` — Celery tasks для нотификаций

### Infrastructure
- `docker-compose.yml` — текущая структура сервисов (api, worker, crawler, beat, flower)
- `app/celery_app.py` — конфигурация Celery, очереди, Beat scheduler
- `app/config.py` — TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_BOT_USERNAME, TELEGRAM_CHANNEL_ID

### User Profile
- `app/routers/profile.py` — `/profile/link-telegram` endpoint
- `app/models/user.py` — User модель с telegram_id полем

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `telegram_auth.py`: HMAC-SHA256 валидация — переиспользуется для верификации webhook запросов
- `telegram_service.py`: Паттерн отправки alerts в Telegram — базис для push-уведомлений
- `channel_service.py`: `_tg_request()` httpx wrapper — может служить fallback, но PTB 21 заменит прямые вызовы
- Notification модель: severity поле уже есть — фильтрация error для Telegram dispatch

### Established Patterns
- Celery tasks для всех длительных операций (crawl, position check, reports)
- RedBeatScheduler для периодических задач (channel_tasks каждые 60s)
- Конфиг через pydantic-settings (app/config.py)
- Allowlist pattern: TELEGRAM_CHAT_ID уже в конфиге

### Integration Points
- docker-compose.yml: новый сервис `bot` рядом с api/worker/crawler
- Notification creation hook: при `severity=error` → dispatch в Telegram
- User.telegram_id: уже есть, используется для WebApp auth
- Celery tasks: бот кидает задачи через Redis, результат через Redis pub/sub или polling

</code_context>

<specifics>
## Specific Ideas

- Бот — для внутренней команды (20 пользователей max), не для клиентов
- /deploy выполняет git pull + docker compose restart на VPS — опасная команда, обязательное подтверждение
- Контекстные inline-кнопки: после ответа на команду — кнопка открытия соответствующего Mini App экрана
- Webhook через Nginx на тот же домен, path `/webhook/tg` → контейнер bot

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 32-telegram-bot*
*Context gathered: 2026-04-12*
