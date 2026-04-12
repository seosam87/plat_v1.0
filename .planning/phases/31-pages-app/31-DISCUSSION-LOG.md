# Phase 31: Pages App - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 31-pages-app
**Areas discussed:** Список страниц, Approve queue, Quick fix, Массовые операции

---

## Список страниц — что показывать

| Option | Description | Selected |
|--------|-------------|----------|
| Из последнего краула | Page model (crawl results) — title, h1, meta, has_toc, has_schema, word_count | ✓ |
| Из WP REST API (live) | Свежее, но медленнее и нет аудит-данных | |
| Гибрид: краул + обогащение | Page + JOIN с positions и errors | |

**User's choice:** Из последнего краула
**Notes:** Актуальность = дата последнего краула. Аудит-данные уже есть.

| Option | Description | Selected |
|--------|-------------|----------|
| Табы-фильтры сверху | Все / Без Schema / Без TOC / Ошибки / Noindex | ✓ |
| Дропдаун-фильтр | Один select с предустановками | |
| Текстовый поиск + фильтр | Поисковая строка + dropdown | |

**User's choice:** Табы-фильтры сверху

| Option | Description | Selected |
|--------|-------------|----------|
| Минимум: URL + иконки статуса | Компактно, много страниц на экран | ✓ |
| Средний: URL + title + статусы + дата | Баланс информации и компактности | |
| Полный: + word_count + позиции | Макс инфо, меньше на экран | |

**User's choice:** Минимум: URL + иконки статуса

| Option | Description | Selected |
|--------|-------------|----------|
| Загрузить ещё (HTMX) | Паттерн Phase 30 | ✓ |
| Infinite scroll | hx-trigger="revealed" | |

**User's choice:** Загрузить ещё

| Option | Description | Selected |
|--------|-------------|----------|
| Дропдаун сверху + cookie | Как /m/errors Phase 30 | ✓ |
| site_id в URL | /m/pages/{site_id} shareable | |

**User's choice:** Дропдаун + cookie

| Option | Description | Selected |
|--------|-------------|----------|
| CTA запустить краул | Кнопка → Celery task | ✓ |
| Просто текст | Без действия | |

**User's choice:** CTA запустить краул

| Option | Description | Selected |
|--------|-------------|----------|
| Inline expand с действиями | HTMX expand: данные + кнопки | ✓ |
| Отдельная страница деталей | /m/pages/{site_id}/{page_id} | |

**User's choice:** Inline expand

| Option | Description | Selected |
|--------|-------------|----------|
| Все / Без Schema / Без TOC / Noindex | 4 таба по аудит-проблемам | ✓ |
| Все / Проблемы / Pipeline | 3 таба | |
| Все / Проблемы / Ожидают / Готовы | 4 таба с pipeline | |

**User's choice:** 4 таба с count-badge

---

## Approve queue — flow одобрения

| Option | Description | Selected |
|--------|-------------|----------|
| Отдельная страница /m/pipeline | Чисто отделено от списка | ✓ |
| Таб в /m/pages | Смешивает pages и jobs | |
| Бейдж в bottom nav + отдельная | Badge count + /m/pipeline | |

**User's choice:** Отдельная /m/pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| Список изменений (текст) | Простой список без diff | |
| HTML diff (green/red) | Цветной diff из diff_json | ✓ |
| Summary + expandable diff | Список сверху + collapse diff | |

**User's choice:** HTML diff (green/red)

| Option | Description | Selected |
|--------|-------------|----------|
| Кнопка → подтверждение | 2-tap: "Принять" → "Подтвердить?" (2 сек timeout) | ✓ |
| Swipe действия | Swipe right = approve, left = reject | |

**User's choice:** 2-tap confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Авто-push после approve | Approve → push_to_wp task сразу | ✓ |
| Approve + отдельно push | Два этапа контроля | |

**User's choice:** Авто-push

| Option | Description | Selected |
|--------|-------------|----------|
| Да, статус + toast | Job остаётся с pushed/failed | ✓ |
| Только toast, убирать | Pushed job исчезает | |

**User's choice:** Статус + toast

| Option | Description | Selected |
|--------|-------------|----------|
| Да, кнопка «Откатить» | rollback_payload уже есть | ✓ |
| Нет, только десктоп | Rollback опасно | |

**User's choice:** Rollback с мобильного

---

## Quick fix — что и как чинить

| Option | Description | Selected |
|--------|-------------|----------|
| Добавить TOC | content_pipeline.py уже умеет | ✓ |
| Добавить Schema.org | schema_service.py уже умеет | ✓ |
| Обновить title/meta | Push через WP REST API | ✓ |
| Внутренняя перелинковка | content_pipeline.py умеет, но сложно | |

**User's choice:** TOC + Schema + title/meta (3 из 4)

| Option | Description | Selected |
|--------|-------------|----------|
| Сразу push (одна кнопка) | PAG-03: "одной кнопкой" | |
| Через pipeline (preview) | Безопаснее | |
| Настраиваемо | TOC/Schema сразу, title/meta через pipeline | ✓ |

**User's choice:** Настраиваемо (risk-based)

| Option | Description | Selected |
|--------|-------------|----------|
| Из inline expand | Кнопки в развёрнутой карточке | ✓ |
| Отдельная страница | /m/pages/{site_id}/{page_id} | |

**User's choice:** Из inline expand

| Option | Description | Selected |
|--------|-------------|----------|
| Inline form в expand | 2 input прямо в карточке | |
| Отдельный экран редактирования | /m/pages/{site_id}/{page_id}/edit с SERP preview | ✓ |

**User's choice:** Отдельный экран с SERP preview

---

## Массовые операции — scope и UX

| Option | Description | Selected |
|--------|-------------|----------|
| Schema на все статьи | SchemaTemplate batch | ✓ |
| TOC на все статьи | TOC generation batch | ✓ |
| Одобрить все pending | Bulk approve | |

**User's choice:** Schema + TOC (без bulk approve)

| Option | Description | Selected |
|--------|-------------|----------|
| Экран подтверждения с счётчиком | "Добавить Schema на 47 страниц?" | ✓ |
| Просто 2-tap | Без отдельного экрана | |

**User's choice:** Экран подтверждения

| Option | Description | Selected |
|--------|-------------|----------|
| HTMX polling с progress bar | hx-trigger="every 3s", 12/47 + toast | ✓ |
| Только spinner + toast | Проще | |

**User's choice:** HTMX polling с progress bar

---

## Claude's Discretion

- Celery task structure for quick fix and bulk ops
- Bottom nav — add "Страницы" or not
- Pipeline page layout — grouping strategy
- SERP preview implementation details
- Error handling for push/rollback failures

## Deferred Ideas

- Bulk approve — поштучный approve достаточен
- Внутренняя перелинковка как quick fix — слишком сложно для one-button
- Редактирование body — только title/meta
- Текстовый поиск по страницам — только табы
- Фильтрация по page_type — defer
- История изменений — defer
- Approve с комментарием — defer
- Batch rollback — defer
- Desktop /ui/pages — mobile only
- Создание новых страниц в WP — defer
