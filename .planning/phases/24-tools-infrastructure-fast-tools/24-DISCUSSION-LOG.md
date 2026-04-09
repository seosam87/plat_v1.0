# Phase 24: Tools Infrastructure & Fast Tools - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 24-tools-infrastructure-fast-tools
**Areas discussed:** Job UX-паттерн, Результаты и экспорт, Навигация и структура, XMLProxy и лимиты

---

## Job UX-паттерн

| Option | Description | Selected |
|--------|-------------|----------|
| Одна страница | Форма + результаты на одной странице (как Keyword Suggest) | |
| Две страницы | Страница 1: форма + список jobs. Страница 2: результаты job | ✓ |
| На усмотрение Claude | Выбрать оптимальный паттерн | |

**User's choice:** Две страницы
**Notes:** —

### HTMX Polling интервал

| Option | Description | Selected |
|--------|-------------|----------|
| 3 секунды | Быстрый отклик, небольшая нагрузка | |
| 5 секунд | Компромисс | |
| 10 секунд | Минимальная нагрузка | ✓ |

**User's choice:** 10 секунд

### Визуализация прогресса

| Option | Description | Selected |
|--------|-------------|----------|
| Простой статус | "Обработка... 45/200 фраз" + spinner | ✓ |
| Progress bar | Полоса прогресса (проценты) | |
| Streaming результатов | Построчное появление | |

**User's choice:** Простой статус

---

## Результаты и экспорт

### Формат экспорта

| Option | Description | Selected |
|--------|-------------|----------|
| Только CSV | Универсальный формат | |
| CSV + XLSX | Оба формата, openpyxl уже в стеке | ✓ |
| Только XLSX | Excel с форматированием | |

**User's choice:** CSV + XLSX

### Хранение jobs

| Option | Description | Selected |
|--------|-------------|----------|
| 30 дней | Автоудаление через Celery Beat | |
| Без лимита | Хранить всё, удалять вручную | ✓ |
| Последние 50 на пользователя | Автоудаление старых | |

**User's choice:** Без лимита

---

## Навигация и структура

### Сайдбар

| Option | Description | Selected |
|--------|-------------|----------|
| Один пункт → index | "Инструменты" → /ui/tools/ | ✓ |
| Раскрывающийся список | Подпункты для каждого инструмента | |
| На усмотрение Claude | По текущему паттерну | |

**User's choice:** Один пункт → index

### URL-схема

| Option | Description | Selected |
|--------|-------------|----------|
| /ui/tools/{slug}/ | Список + форма, /ui/tools/{slug}/{job_id} для результатов | ✓ |
| /ui/tools/{slug}/ только | Всё на одной странице через HTMX | |

**User's choice:** /ui/tools/{slug}/ + /ui/tools/{slug}/{job_id}

---

## XMLProxy и лимиты

### Исчерпание баланса

| Option | Description | Selected |
|--------|-------------|----------|
| Partial результат | Сохранить полученное, пометить как partial | ✓ |
| Ошибка всего job | Пометить как failed | |
| Поставить в очередь | Возобновить при пополнении | |

**User's choice:** Partial результат

### Лимиты ввода

| Option | Description | Selected |
|--------|-------------|----------|
| По ROADMAP (200/500/100) | Коммерциализация 200, Мета 500, Релевантный URL 100 | ✓ |
| Увеличить | Новые лимиты | |
| Уменьшить | Новые лимиты | |

**User's choice:** По ROADMAP

---

## Claude's Discretion

- Структура моделей Job+Result
- Распределение по Celery workers
- Формат таблиц результатов
- Тексты UI на русском

## Deferred Ideas

None
