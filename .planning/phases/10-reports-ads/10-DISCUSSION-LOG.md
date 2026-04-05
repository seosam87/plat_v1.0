# Phase 10: Reports & Ads - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 10-reports-ads
**Areas discussed:** Dashboard layout, Report content, Delivery & scheduling, Ad traffic

---

## Dashboard layout & widgets

| Option | Description | Selected |
|--------|-------------|----------|
| Таблица проектов | Список всех проектов с ключевыми метриками в строках | ✓ |
| Карточки + сводка | Сверху сводные числа, ниже карточки с мини-графиками | |
| Карта здоровья | Цветные блоки по общему здоровью проекта | |

**User's choice:** Таблица проектов
**Notes:** Компактно, много данных сразу

| Option | Description | Selected |
|--------|-------------|----------|
| Минимум колонок | Проект, Сайты, TOP-10, Задачи, Последнее изменение | |
| Расширенный | TOP-3/10/30, динамика, задачи по статусам, изменения, статус | |
| На моё усмотрение | Claude подберёт оптимальный набор | ✓ |

**User's choice:** На моё усмотрение

| Option | Description | Selected |
|--------|-------------|----------|
| Стартовая страница | После логина пользователь сразу видит дашборд | ✓ |
| Отдельный раздел | Дашборд как отдельный пункт в меню | |

**User's choice:** Стартовая страница

---

## Report content & format

| Option | Description | Selected |
|--------|-------------|----------|
| Краткий | 1-2 страницы PDF: тренды, задачи, изменения | |
| Подробный | 5-10 страниц: полная таблица ключевых слов, графики, все задачи | |
| Оба варианта | Пользователь выбирает тип при генерации | ✓ |

**User's choice:** Оба варианта

| Option | Description | Selected |
|--------|-------------|----------|
| PDF = клиенту, Excel = себе | PDF красивый для клиента, Excel сырые данные | ✓ |
| Одинаковые данные | Оба формата содержат одни и те же данные | |
| На моё усмотрение | Claude решит | |

**User's choice:** PDF = клиенту, Excel = себе

---

## Delivery & scheduling

| Option | Description | Selected |
|--------|-------------|----------|
| Текстовое сообщение | Компактный Markdown в Telegram | ✓ |
| PDF-вложение | Полный PDF файлом в Telegram | |
| Текст + PDF | Краткое сообщение + прикреплённый PDF | |

**User's choice:** Текстовое сообщение

| Option | Description | Selected |
|--------|-------------|----------|
| Только админу | Один Telegram-чат/email, без подписок | ✓ |
| По проекту | Каждый проект может иметь свой список получателей | |

**User's choice:** Только админу

| Option | Description | Selected |
|--------|-------------|----------|
| Ежедневно/еженедельно | Дайджест каждое утро + недельный сводный отчёт | ✓ |
| Полный cron | Произвольное расписание (cron-выражение) | |

**User's choice:** Ежедневно/еженедельно

---

## Ad traffic

| Option | Description | Selected |
|--------|-------------|----------|
| Яндекс Директ + Google Ads | Два основных источника | |
| Произвольные | Свободное поле source в CSV | |
| Только Яндекс Директ | Основной рынок — Рунет | ✓ |

**User's choice:** Только Яндекс Директ

| Option | Description | Selected |
|--------|-------------|----------|
| Два date-picker | Пользователь выбирает Период A и Период B через календарь | ✓ |
| Пресеты | Готовые варианты: эта неделя vs прошлой | |
| Пресеты + календарь | Быстрые кнопки + произвольные даты | |

**User's choice:** Два date-picker

---

## Claude's Discretion

- Dashboard table columns — Claude selects optimal set based on available DB data
- Chart styling and colors
- Report template design

## Deferred Ideas

None — discussion stayed within phase scope
