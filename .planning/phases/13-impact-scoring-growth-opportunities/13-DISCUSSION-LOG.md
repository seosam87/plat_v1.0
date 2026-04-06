# Phase 13: Impact Scoring & Growth Opportunities - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 13-impact-scoring-growth-opportunities
**Areas discussed:** Формула Impact Score, Макет Growth Dashboard, Навигация Drill-Down

---

## Todo Triage

| Todo | Decision | Selected |
|------|----------|----------|
| Fix position check ignores keyword engine preference | Включить в фазу 13 | ✓ |
| Proxy management, XMLProxy integration | Отложить | |

**User's choice:** Включить todo про engine preference в фазу 13
**Notes:** Данные позиций влияют на impact scores

---

## Формула Impact Score

### Назначение severity_weight

| Option | Description | Selected |
|--------|-------------|----------|
| Фиксированные веса по severity | warning=1, error=3, critical=5. impact = weight × трафик. Без UI. | ✓ |
| Настраиваемые веса в UI | Пользователь меняет вес каждого типа ошибки | |
| Вес на уровне check_code | Каждый check_code получает индивидуальный вес | |

**User's choice:** Фиксированные веса по severity

### Источник трафика

| Option | Description | Selected |
|--------|-------------|----------|
| Метрика (MetrikaTrafficPage) | visits за 30 дней. Уже есть в БД. | ✓ |
| Позиции × средний CTR | Расчётный трафик из keyword_latest_positions | |

**User's choice:** Метрика (MetrikaTrafficPage)

---

## Макет Growth Dashboard

### Организация дашборда

| Option | Description | Selected |
|--------|-------------|----------|
| Карточки сеткой 2×2 | 4 карточки: gaps, потери, каннибализации, тренд | |
| Сводка + таблица | Стат-стрип + единая таблица | |
| Табы по категориям | Gaps \| Потери \| Каннибализация \| Тренд | ✓ |

**User's choice:** Табы по категориям

### Visibility trend

| Option | Description | Selected |
|--------|-------------|----------|
| Спарклайн + число | Маленький график + текущее значение и дельта | |
| Полноразмерный график | Line chart на всю ширину | |
| Только числа | Текущий показатель + % изменения | ✓ |

**User's choice:** Только числа

---

## Навигация Drill-Down

### Переход к деталям

| Option | Description | Selected |
|--------|-------------|----------|
| Прямые ссылки на существующие страницы | Клик ведёт на gap analysis/positions/clusters | |
| Раскрытие внутри таба (inline expand) | Клик раскрывает детали в таблице | |
| Выдвижная панель (slide-over) | Боковая панель с деталями без ухода с дашборда | ✓ |

**User's choice:** Выдвижная панель (slide-over)

### Содержимое табов

| Option | Description | Selected |
|--------|-------------|----------|
| Таблица с ключевыми метриками | Gaps: ключ + трафик. Потери: URL + позиции. | |
| Стат-стрип + таблица | Суммарные числа + таблица | |
| На усмотрение Claude | Claude решает какую информацию показывать | ✓ |

**User's choice:** На усмотрение Claude

---

## Claude's Discretion

- Способ переключения сортировки Kanban по impact_score
- Содержимое и колонки каждого таба Growth Opportunities
- Детали в slide-over панели
- Celery task параметры

## Deferred Ideas

- Настраиваемые веса severity через UI
- Индивидуальные веса per check_code
- Графики для visibility trend
