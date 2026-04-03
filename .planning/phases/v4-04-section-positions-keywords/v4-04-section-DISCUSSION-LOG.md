# Phase v4-04: Секция «Позиции и ключи» - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** v4-04-section-positions-keywords
**Areas discussed:** Навигация и загрузки, Реакция на site selector

---

## Навигация и загрузки

| Option | Description | Selected |
|--------|-------------|----------|
| Добавить в «Позиции» | Добавить 7-й child «Загрузка данных» в NAV_SECTIONS | |
| Оставить как есть | Не трогать /ui/uploads, доступна через ссылку | |
| Перенести в «Настройки» | Загрузка данных — админ-функция, логичнее в настройках | ✓ |

**User's choice:** Перенести в «Настройки»
**Notes:** Will be handled in Phase v4-07

| Option | Description | Selected |
|--------|-------------|----------|
| Оставить 6 пунктов | Текущая структура OK | ✓ |
| Уменьшить | Объединить некоторые (Кластеры+Каннибализация+Интент) | |

**User's choice:** Оставить 6 пунктов
**Notes:** None

---

## Реакция на site selector

| Option | Description | Selected |
|--------|-------------|----------|
| window.location редирект | JS меняет {site_id} в URL и переходит. Полная перезагрузка, sidebar остаётся. | ✓ |
| HTMX подмена #content | HTMX hx-get заменяет только область контента. Сложнее: нужен partial endpoint. | |
| На усмотрение Claude | | |

**User's choice:** window.location редирект
**Notes:** Простой и надёжный подход

---

## Tailwind-миграция

User selected "На усмотрение Claude" — all 6 templates get pure Tailwind migration following v4-02/v4-03 pattern.

## Claude's Discretion

- Tailwind class choices for all 6 templates
- Plan splitting strategy (how many plans, grouping)

## Deferred Ideas

- Upload page migration to «Настройки» → Phase v4-07
