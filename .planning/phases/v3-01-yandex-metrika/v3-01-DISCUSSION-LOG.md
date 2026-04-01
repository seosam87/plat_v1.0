# Phase 1: Yandex Metrika - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** v3-01-yandex-metrika
**Areas discussed:** Connection, Data & Metrics, Period Comparison, UI & Integration

---

## Connection & Auth

| Option | Description | Selected |
|--------|-------------|----------|
| OAuth | Full OAuth flow, как GSC — сложнее, но "правильнее" | |
| API-токен | Статический токен из настроек Яндекса — проще, не истекает | ✓ |

**User's choice:** API-токен
**Notes:** Внутренний инструмент, OAuth избыточен. 1 сайт = 1 счётчик. Хранение — на усмотрение Claude.

---

## Data & Metrics

| Option | Description | Selected |
|--------|-------------|----------|
| По страницам | Трафик на конкретные URL | ✓ |
| Весь сайт (агрегат) | Общий поисковый трафик | ✓ |
| По источникам | Органика / прямые / реферальные | |

**User's choice:** По страницам + весь поисковый трафик
**Metrics:** визиты, отказы, глубина, время на сайте
**Search engines:** общий поток, без разбивки

---

## Period Comparison

| Option | Description | Selected |
|--------|-------------|----------|
| Фиксированные периоды | Месяц vs месяц, неделя vs неделя | |
| Произвольные диапазоны | Пользователь выбирает два любых периода | ✓ |

**User's choice:** Произвольные диапазоны дат, дельта между ними

| Option | Description | Selected |
|--------|-------------|----------|
| Автосбор (Celery Beat) | Фоновый ежедневный сбор данных | |
| По запросу | Кнопка "обновить данные" | ✓ |

**User's choice:** Только по запросу

---

## UI & Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Отдельная страница "Трафик" | В навигации сайта, таблица + график | ✓ |
| Только виджет | Без отдельной страницы | |

**User's choice:** Отдельная страница + виджет в Site Overview (при наличии данных)

| Option | Description | Selected |
|--------|-------------|----------|
| Автометки из системы | События из pipeline, content plan, crawl автоматически | |
| Ручные метки | Пользователь сам ставит метки на графике | ✓ |

**User's choice:** Ручные метки-события на графике

---

## Claude's Discretion

- Token storage method (Fernet vs plaintext)
- API response caching strategy
- Table pagination defaults

## Deferred Ideas

None
