# Phase v4-07: Settings Section - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** v4-07-settings-section
**Areas discussed:** Состав подпунктов sidebar, Разграничение доступа, Особенности миграции шаблонов

---

## Состав подпунктов sidebar

| Option | Description | Selected |
|--------|-------------|----------|
| Оставить как есть | 6 подпунктов в текущем порядке — не менять | |
| Разделить «Прокси и настройки» | Прокси — пул и XMLProxy/rucaptcha. Параметры — остальные настройки | ✓ |
| Изменить порядок | Переставить подпункты в другом порядке | |

**User's choice:** Разделить «Прокси и настройки»

### Follow-up: Как разделить

| Option | Description | Selected |
|--------|-------------|----------|
| Прокси + Параметры | Два подпункта: proxy pool и общие настройки | ✓ |
| Прокси + Интеграции + Параметры | Три подпункта: proxy, API-ключи, общие | |
| Прокси + Креденшиалы | Proxy pool + XMLProxy/rucaptcha/API credentials | |

**User's choice:** Прокси + Параметры

---

## Разграничение доступа

| Option | Description | Selected |
|--------|-------------|----------|
| Только admin | Вся секция admin_only — как сейчас | |
| Manager видит часть | Manager доступ к некоторым подпунктам | ✓ |

**User's choice:** Manager видит часть
**Notes:** Manager должен иметь доступ к Прокси, Источникам данных, API-подключениям

### Follow-up: Конкретное распределение

| Option | Description | Selected |
|--------|-------------|----------|
| Вариант A | Manager: Прокси + Источники + Параметры + Задачи. Admin: Пользователи, Группы, Аудит | ✓ |
| Вариант B | Manager: Прокси + Источники. Admin: всё остальное | |

**User's choice:** Вариант A (с уточнением — Задачи платформы тоже для менеджеров)
**Notes:** Задачи для проектов должны быть видны менеджерам

---

## Особенности миграции шаблонов

| Option | Description | Selected |
|--------|-------------|----------|
| Как в v4-06 | Чистая Tailwind-миграция без изменения функционала | ✓ |
| Улучшить UX | Помимо миграции улучшить конкретные элементы | |

**User's choice:** Как в v4-06

---

## Claude's Discretion

- Plan splitting strategy
- Proxy/Parameters split implementation approach
- All Tailwind class choices, badge colors, form styling

## Deferred Ideas

None — discussion stayed within phase scope.
