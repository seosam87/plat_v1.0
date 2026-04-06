# Phase 13: Impact Scoring & Growth Opportunities - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Все ошибки аудита (404, noindex, missing schema) получают числовой impact_score, видимый в UI и используемый для сортировки Kanban. Единый Growth Opportunities дашборд с табами агрегирует gap-ключи, потерянные позиции, каннибализации и тренд видимости. Celery task предрассчитывает impact scores в таблицу `error_impact_scores`.

</domain>

<decisions>
## Implementation Decisions

### Impact Score Formula
- **D-01:** impact_score = severity_weight × месячный трафик страницы из Метрики (MetrikaTrafficPage.visits за 30 дней).
- **D-02:** Фиксированные веса по severity: warning=1, error=3, critical=5. Без UI для настройки весов.
- **D-03:** Веса применяются на уровне severity (не per check_code). Все warning-ошибки имеют одинаковый вес.

### Kanban Integration
- **D-04:** Добавить сортировку по impact_score в существующий Kanban (/ui/projects/{id}/kanban) — на усмотрение Claude (toggle/dropdown/кнопка).

### Growth Opportunities Dashboard
- **D-05:** Табы по категориям: Gaps | Потери | Каннибализация | Тренд. Каждый таб — отдельная секция с данными.
- **D-06:** Visibility trend — только числа: текущий показатель + % изменения за неделю/месяц. Без графиков и спарклайнов.
- **D-07:** Содержимое каждого таба — на усмотрение Claude (какие колонки, какие метрики показывать).

### Drill-Down Navigation
- **D-08:** Клик по записи в табе открывает выдвижную боковую панель (slide-over) с деталями, не уходя с дашборда.
- **D-09:** Из панели можно перейти на полную страницу (gap analysis, positions, clusters) по кнопке «Подробнее».

### Claude's Discretion
- Kanban: способ переключения сортировки (toggle, dropdown, кнопка)
- Содержимое каждого таба (колонки, метрики, сортировка)
- Slide-over панель: какие детали показывать для каждого типа записи
- Celery task: частота пересчёта impact scores, batch size
- Определение «потерянных позиций» (порог дельты)
- Определение «активных каннибализаций» (логика кластеризации)

### Folded Todos
- **Fix position check ignores keyword engine preference** — исправить в рамках Phase 13, т.к. данные позиций влияют на impact scores и потерянные позиции в Opportunities

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit & Impact
- `app/models/audit.py` — AuditCheckDefinition (severity field), AuditResult (site_id, page_url, check_code)
- `app/services/audit_fix_service.py` — existing batch fix wiring

### Position data
- `app/models/keyword_latest_position.py` — KeywordLatestPosition flat table (from Phase 12)
- `app/services/position_service.py` — refresh_latest_positions(), write_positions_batch()

### Traffic data
- `app/models/metrika.py` — MetrikaTrafficPage (page_url, visits)
- `app/services/metrika_service.py` — Metrika data retrieval

### Kanban
- `app/templates/projects/kanban.html` — existing Kanban board template

### Clusters & Gap Analysis
- `app/models/cluster.py` — KeywordCluster model
- `app/routers/clusters.py` — clusters router
- `app/tasks/intent_tasks.py` — intent/clustering tasks

### Navigation & Templates
- `app/navigation.py` — sidebar navigation entries
- `app/templates/analytics/` — existing analytics templates (Quick Wins, Dead Content from Phase 12)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `keyword_latest_positions` table (Phase 12) — position delta can be computed for lost positions
- `MetrikaTrafficPage` — already used in Dead Content for 30-day traffic
- `normalize_url()` (Phase 12) — for URL JOINs between audit, metrika, positions
- Existing Kanban template at `projects/kanban.html` — needs impact_score integration
- HTMX partial updates pattern — established in Quick Wins and Dead Content

### Established Patterns
- Celery tasks with retry=3 for external calls
- Stats strip pattern from Dead Content (top summary numbers)
- HTMX tab switching (can reuse for Opportunities tabs)
- Sidebar navigation entries via `app/navigation.py`

### Integration Points
- New Celery task for impact score pre-computation
- New routes under `/analytics/` for Growth Opportunities
- Kanban template modification for sort toggle
- Sidebar: add Growth Opportunities entry

</code_context>

<specifics>
## Specific Ideas

- Impact score видим прямо в UI — пользователь понимает ПОЧЕМУ эта ошибка важнее
- Slide-over панель позволяет быстро просмотреть детали без потери контекста дашборда
- Табы вместо карточек — больше информации на экране, подробные таблицы в каждой категории

</specifics>

<deferred>
## Deferred Ideas

- Настраиваемые веса severity через UI (D-02 зафиксировал фиксированные веса)
- Индивидуальные веса per check_code (вместо per severity level)
- Графики и спарклайны для visibility trend

### Reviewed Todos (not folded)
- "Proxy management, XMLProxy integration and health checker" — не относится к Phase 13, остаётся отдельной задачей

</deferred>

---

*Phase: 13-impact-scoring-growth-opportunities*
*Context gathered: 2026-04-06*
