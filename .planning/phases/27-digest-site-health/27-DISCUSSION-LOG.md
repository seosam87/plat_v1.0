# Phase 27: Digest & Site Health - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 27-digest-site-health
**Areas discussed:** Digest Content, Digest Navigation, Site Health Card, Health Card Actions

---

## Digest Content — Block Order

| Option | Description | Selected |
|--------|-------------|----------|
| Позиции → Ошибки → Алерты → Задачи | SEO-critical first, operational second | ✓ |
| Алерты → Позиции → Ошибки → Задачи | Urgent first, then analytics | |
| На усмотрение Claude | | |

**User's choice:** Позиции → Ошибки → Алерты → Задачи
**Notes:** —

## Digest Content — Items Per Block

| Option | Description | Selected |
|--------|-------------|----------|
| TOP-5 на блок | Компактно, один экран | ✓ |
| TOP-10 на блок | Больше деталей, скролл | |
| На усмотрение Claude | | |

**User's choice:** TOP-5
**Notes:** —

## Digest Content — Data Source

| Option | Description | Selected |
|--------|-------------|----------|
| Новый mobile_digest_service.py | Отдельный сервис для мобильного UI | |
| Расширить morning_digest_service.py | Добавить метод со структурированными данными | |
| На усмотрение Claude | | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** —

---

## Digest Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| На desktop-страницы | Тап ведёт на обычные страницы с sidebar | |
| На /m/ заглушки | Placeholder-страницы "Скоро" | |
| Смешанный | Если /m/ существует → туда, иначе → desktop | |
| На усмотрение Claude | | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** Мобильные страницы позиций/ошибок ещё не существуют (Phases 28-31).

---

## Site Health Card — Metrics

| Option | Description | Selected |
|--------|-------------|----------|
| Минимум (4 блока) | Доступность, ошибки, краулинг, позиции | |
| Расширенный (6 блоков) | Минимум + просроченные задачи + индексация | ✓ |
| На усмотрение Claude | | |

**User's choice:** Расширенный (6 блоков)
**Notes:** —

## Site Health Card — Visualization

| Option | Description | Selected |
|--------|-------------|----------|
| Карточки с числами | Иконка + число + подпись + цвет | |
| Список | Вертикальный список с иконками статуса | ✓ |
| На усмотрение Claude | | |

**User's choice:** Простой список с иконками статуса
**Notes:** —

---

## Health Card Actions — API Approach

| Option | Description | Selected |
|--------|-------------|----------|
| HTMX inline | hx-post + hx-swap-oob для тоста | |
| Fetch API | JS fetch + тост | |
| На усмотрение Claude | | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** —

## Health Card Actions — Task Creation Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Одна кнопка | Создать задачу сразу с предзаполнением | |
| Мини-форма | 2-3 поля inline (текст, приоритет), кнопка "Сохранить" | ✓ |
| На усмотрение Claude | | |

**User's choice:** Мини-форма
**Notes:** Текст предзаполнен из ошибки, привязка к проекту/сайту.

---

## Claude's Discretion

- Digest data source architecture (D-03)
- Deep link strategy from digest items (D-04)
- API approach for health card actions (D-07)

## Deferred Ideas

None — discussion stayed within phase scope.
