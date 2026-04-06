# Phase 14: Client Instructions PDF - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 14-client-instructions-pdf
**Areas discussed:** Report Content, Instruction Format, Entry Point & UX

---

## Report Content

### Q1: What blocks to include in client PDF?

| Option | Description | Selected |
|--------|-------------|----------|
| Всё вместе | Quick Wins + ошибки + Dead Content + статистика — полная картина | |
| Только actionable | Quick Wins + ошибки (то, что клиент может исправить) | |
| Конфигурируемо | Чекбоксы перед генерацией: какие блоки включить | ✓ |

**User's choice:** Конфигурируемо
**Notes:** —

### Q2: How many items per block?

| Option | Description | Selected |
|--------|-------------|----------|
| TOP-N с лимитом | Топ по score, остальные — "и ещё N проблем" | ✓ |
| Все без ограничений | Полный список, отчёт 20+ страниц | |
| Настраиваемый лимит | Пользователь задаёт 10/20/50/все | |

**User's choice:** TOP-N с лимитом
**Notes:** Конкретное N — на усмотрение Claude

### Q3: Summary at the top?

| Option | Description | Selected |
|--------|-------------|----------|
| Да, краткая сводка | 3-5 строк: страницы, ошибки, Quick Wins, оценка | ✓ |
| Нет, сразу к делу | Клиенту нужны инструкции, не статистика | |

**User's choice:** Да, краткая сводка

---

## Instruction Format

### Q1: Target audience?

| Option | Description | Selected |
|--------|-------------|----------|
| Клиент сам правит в WP | Максимально пошаговые инструкции по WP admin | |
| Клиент передаёт специалисту | Более технические инструкции | ✓ |
| Зависит от клиента | Два уровня детализации на выбор | |

**User's choice:** Клиент передаёт специалисту

### Q2: Problem grouping?

| Option | Description | Selected |
|--------|-------------|----------|
| По страницам | Для каждой страницы — её проблемы | |
| По типу проблемы | Все "нет TOC" вместе, потом "нет schema" и т.д. | ✓ |
| По приоритету | Сортировка по impact/opportunity score | |

**User's choice:** По типу проблемы

### Q3: Tone and language?

| Option | Description | Selected |
|--------|-------------|----------|
| Формальный | "Рекомендуется добавить разметку..." | |
| Деловой-прямой | "Добавьте FAQ schema через Yoast →..." | ✓ |
| На усмотрение Claude | Главное — понятно и кратко | |

**User's choice:** Деловой-прямой, императив

---

## Entry Point & UX

### Q1: Where to generate?

| Option | Description | Selected |
|--------|-------------|----------|
| Со страницы сайта | Кнопка на overview сайта | |
| Отдельный раздел в sidebar | "Клиентские отчёты" как самостоятельная страница | ✓ |
| Внутри существующих reports | Тип "client instructions" рядом с brief/detailed | |

**User's choice:** Отдельный раздел в sidebar

### Q2: Page layout?

| Option | Description | Selected |
|--------|-------------|----------|
| Всё на одной странице | Выбор сайта + блоки + генерация + история | ✓ |
| Две страницы | Список отдельно, генерация через модальное | |

**User's choice:** Одна страница

### Q3: Delivery channels?

| Option | Description | Selected |
|--------|-------------|----------|
| Только скачивание | Кнопка "Скачать" | |
| Скачивание + email | Ввод email клиента | |
| Скачивание + email + Telegram | Все каналы | ✓ |

**User's choice:** Все три канала

### Q4: Report history?

| Option | Description | Selected |
|--------|-------------|----------|
| Да, список с датой и сайтом | Повторное скачивание, повторная отправка | ✓ |
| Нет, одноразовая генерация | Не хранится в БД | |

**User's choice:** Да, история в БД

---

## Claude's Discretion

- Subprocess isolation approach for WeasyPrint
- TOP-N limit value per block
- Whether to migrate existing report PDF to subprocess too
- Summary assessment logic
- PDF visual design
- Sidebar icon and placement

## Deferred Ideas

None — discussion stayed within phase scope
