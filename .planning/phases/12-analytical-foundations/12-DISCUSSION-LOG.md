# Phase 12: Analytical Foundations - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 12-analytical-foundations
**Areas discussed:** Quick Wins page, Dead Content logic, Batch fix behavior, URL normalization

---

## Quick Wins Page — Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Компактная таблица | URL, score, кол-во проблем, позиция, трафик. Проблемы — по клику | |
| Расширенная таблица | URL, score, каждая проблема отдельной колонкой (✓/✗), позиция, трафик | ✓ |
| Карточки | Каждая страница — карточка с URL, score, списком проблем и кнопкой | |

**User's choice:** Расширенная таблица — всё видно сразу без кликов
**Notes:** —

---

## Quick Wins Page — Filters

| Option | Description | Selected |
|--------|-------------|----------|
| По типу проблемы | Показать только страницы без TOC / без Schema / мало ссылок / тонкий контент | ✓ |
| По диапазону позиций | Слайдер или ввод: позиции 4–10, 10–20 | |
| По минимальному трафику | Страницы с трафиком > N визитов/неделю | |
| По типу страницы | Информационная / коммерческая / unknown | ✓ |

**User's choice:** По типу проблемы + по типу страницы
**Notes:** —

---

## Quick Wins Page — Position Display

| Option | Description | Selected |
|--------|-------------|----------|
| Лучшая позиция | Минимальная позиция среди ключей 4–20 | |
| Средняя позиция | Средняя позиция по всем ключам 4–20 | ✓ |
| Кол-во ключей + лучшая | Две колонки: лучшая позиция и количество ключей | |

**User's choice:** Средняя позиция
**Notes:** —

---

## Dead Content — Recommendation Logic

| Option | Description | Selected |
|--------|-------------|----------|
| Автоматически по правилам | Система сама выбирает merge/redirect/rewrite/delete | |
| Подсказка + ручной выбор | Система предлагает рекомендацию, пользователь может переопределить | ✓ |
| Только ручной выбор | Нет автоматики, пользователь сам выбирает | |

**User's choice:** Подсказка + ручной выбор
**Notes:** —

---

## Dead Content — Table Columns

| Option | Description | Selected |
|--------|-------------|----------|
| Трафик (0 / N) | Визиты из Метрики за 30 дней | ✓ |
| Дельта позиций | Изменение позиции за 30 дней | |
| Кол-во ключей | Сколько ключей привязано к странице | ✓ |
| Дата последнего визита | Когда последний раз был трафик | |

**User's choice:** Трафик + кол-во ключей
**Notes:** —

---

## Dead Content — Actions

| Option | Description | Selected |
|--------|-------------|----------|
| Только отчёт | Данные видны, действия вручную в WP | |
| Отчёт + задачи | Выбрать страницы → создать SEO-задачи в task system | ✓ |
| Отчёт + действия в WP | Redirect/delete прямо из таблицы через WP REST API | |

**User's choice:** Отчёт + задачи
**Notes:** —

---

## Dead Content — Recommendation Rules

| Option | Description | Selected |
|--------|-------------|----------|
| По наличию ключей + трафика | Есть ключи нет трафика → rewrite, нет ключей → delete, падение → redirect | |
| Просто по трафику | 0 визитов → delete, падение > 50% → rewrite, остальное → redirect | |
| На усмотрение Claude | Claude определит логику на основе доступных данных | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** —

---

## Dead Content — Merge Candidates

| Option | Description | Selected |
|--------|-------------|----------|
| Да, по ключам | Искать страницы с пересекающимися ключами | |
| Нет, только пометка | Просто пометить как «merge» | |
| В будущем | Поиск кандидатов — отдельная фича | ✓ |

**User's choice:** В будущем
**Notes:** —

---

## Batch Fix — Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Сразу в очередь | Нажал → задачи сразу уходят в Celery | |
| Подтверждение + выбор фиксов | Модальное окно: список страниц + чекбоксы фиксов, потом «Запустить» | ✓ |
| Только задачи | Кнопка создаёт SEO-задачи, пользователь запускает из pipeline | |

**User's choice:** Подтверждение + выбор фиксов
**Notes:** —

---

## Batch Fix — Progress

| Option | Description | Selected |
|--------|-------------|----------|
| Тост-уведомление | «Запущено 5 задач» → смотреть статус на Tasks | |
| HTMX обновление | Статус обновляется прямо в таблице Quick Wins | |
| На усмотрение Claude | Claude решит оптимальный способ | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** —

---

## URL Normalization — Problem Types

| Option | Description | Selected |
|--------|-------------|----------|
| Trailing slash | /page vs /page/ | |
| http vs https | Разные протоколы из разных источников | ✓ |
| UTM-параметры | ?utm_source=... из Метрики | ✓ |
| Другие проблемы | www, регистр, фрагменты | |

**User's choice:** http vs https + UTM-параметры
**Notes:** Основные реальные проблемы с JOIN в данных пользователя

---

## URL Normalization — When to Apply

| Option | Description | Selected |
|--------|-------------|----------|
| При записи (рекоменд.) | normalize_url() при сохранении + миграция существующих данных | |
| При чтении | normalize_url() в запросах при JOIN | |
| На усмотрение Claude | Claude решит оптимальный подход | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** —

---

## Claude's Discretion

- Логика автоподсказки рекомендаций Dead Content
- Отображение прогресса батч-фикса
- Нормализация trailing slash и www
- Стратегия применения normalize_url() (при записи / при чтении / миграция)
- keyword_latest_positions: структура, обновление, индексы

## Deferred Ideas

- Автоматический поиск кандидатов для merge — отдельная фича в будущем
