# Phase 32: Telegram Bot - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 32-telegram-bot
**Areas discussed:** Архитектура бота, Набор команд, Mini App кнопки, Уведомления в Telegram

---

## Архитектура бота

### Фреймворк

| Option | Description | Selected |
|--------|-------------|----------|
| python-telegram-bot 21 | Async-native, ConversationHandler, command routing, inline keyboards. В PROJECT.md как рекомендация | ✓ |
| Чистый httpx | Уже используется в channel_service.py. Нет новых зависимостей, но надо самому писать polling/command parsing | |
| aiogram 3 | Более feature-complete, но PROJECT.md рекомендует PTB для push-only use case | |

**User's choice:** python-telegram-bot 21
**Notes:** Уже рекомендован в PROJECT.md stack

### Delivery

| Option | Description | Selected |
|--------|-------------|----------|
| Long polling | Проще, не нужен SSL/публичный URL | |
| Webhook | Telegram сам шлёт POST, нужен HTTPS | ✓ |

**User's choice:** Webhook
**Notes:** —

### Webhook routing

| Option | Description | Selected |
|--------|-------------|----------|
| PTB встроенный | Отдельный порт, Nginx проксирует /webhook/tg | ✓ |
| Через FastAPI роутер | Webhook endpoint в FastAPI, передаёт через Redis | |

**User's choice:** PTB встроенный
**Notes:** —

### API связь

| Option | Description | Selected |
|--------|-------------|----------|
| Прямой DB + Redis | Бот читает PostgreSQL, кидает Celery-таски через Redis | ✓ |
| HTTP API к FastAPI | Бот ходит по HTTP, более изолированно | |

**User's choice:** Прямой DB + Redis
**Notes:** Проще, нет лишнего HTTP-хопа

---

## Набор команд

| Option | Description | Selected |
|--------|-------------|----------|
| DevOps-команды | /status, /logs, /test, /deploy | |
| SEO-команды | /crawl, /check, /report | |
| ��ба набора | DevOps + SEO | ✓ |

**User's choice:** Оба набора
**Notes:** —

### Подтверждение

| Option | Description | Selected |
|--------|-------------|----------|
| Inline-кнопки Да/Нет | «✅ Выполнить» / «❌ Отмена», timeout 60s | ✓ |
| Текстовый ответ | Пользователь пишет «да» | |

**User's choice:** Inline-кнопки
**Notes:** —

---

## Mini App кнопки

### Навигация

| Option | Description | Selected |
|--------|-------------|----------|
| Меню-кнопка + inline | Menu Button → /m/, inline WebApp-кнопки в ответах | ✓ |
| Только Menu Button | Одна кнопка «Открыть платформу» | |
| Reply keyboard | Постоянная клавиатура внизу | |

**User's choice:** Меню-кнопка + inline
**Notes:** —

### Экраны

| Option | Description | Selected |
|--------|-------------|----------|
| Точно по BOT-03 | Дайджест, отчёт, позиции | |
| Расширенный набор | + страницы, здоровье, инструменты | ✓ |

**User's choice:** Расширенный набор
**Notes:** Полный доступ ко всем /m/ экранам

---

## Уведомления в Telegram

### Push

| Option | Description | Selected |
|--------|-------------|----------|
| Да, критичные | Только severity=error | ✓ |
| Да, все уведомления | Дублировать всё | |
| Нет, отложить | Push в отдельную фазу | |

**User's choice:** Только критичные (severity=error)
**Notes:** —

### Настройки

| Option | Description | Selected |
|--------|-------------|----------|
| Минимум: on/off | Один тоггл в профиле | ✓ |
| Гранулярные | Категории, quiet hours, пороги | |
| Ты решай | Claude's discretion | |

**User's choice:** Минимум: on/off
**Notes:** —

---

## Claude's Discretion

- Структура модулей внутри контейнера бота
- Формат текстовых ответов (Markdown vs HTML)
- Graceful degradation при недоступности DB/FastAPI
- Стратегия регистрации webhook

## Deferred Ideas

None — discussion stayed within phase scope
