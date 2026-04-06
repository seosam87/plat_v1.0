# Phase 12: Analytical Foundations - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can see which pages are Quick Wins (positions 4-20 with unfixed SEO issues) and which are Dead Content (zero traffic + falling positions), backed by normalized URL JOINs and a fast position lookup table (`keyword_latest_positions`). First phase of v2.0 milestone — builds analytical foundation for subsequent phases.

</domain>

<decisions>
## Implementation Decisions

### Quick Wins Page
- **D-01:** Расширенная таблица — все данные видны сразу без кликов. Колонки: URL, Opportunity Score, TOC (✓/✗), Schema (✓/✗), Links (✓/✗), Контент (✓/✗), Средняя позиция, Трафик.
- **D-02:** Opportunity score = (21 - позиция) × недельный трафик. Позиция — средняя по всем ключам страницы в диапазоне 4–20.
- **D-03:** Фильтры: по типу проблемы (без TOC / без Schema / мало ссылок / тонкий контент) и по типу страницы (информационная / коммерческая / unknown).
- **D-04:** Сортировка по умолчанию — по opportunity score (убывание).

### Dead Content Page
- **D-05:** Таблица: URL, трафик за 30 дней (из Метрики), кол-во привязанных ключей, рекомендация (merge/redirect/rewrite/delete).
- **D-06:** Рекомендация — автоматическая подсказка по правилам, но пользователь может переопределить выбор в UI (dropdown).
- **D-07:** Логика автоподсказки — на усмотрение Claude (на основе наличия ключей, трафика, дельты позиций).
- **D-08:** Можно выбрать страницы и создать SEO-задачи (через существующий task system) для работы с мёртвым контентом.
- **D-09:** Поиск кандидатов для merge (похожие страницы) — отложено на будущее. Сейчас просто пометка «merge».

### Batch Fix (Quick Wins)
- **D-10:** Модальное окно подтверждения перед запуском: список выбранных страниц + чекбоксы каких фиксов применить (☐ TOC ☐ Schema ☐ Links). Потом «Запустить».
- **D-11:** Фиксы уходят в Celery через существующий audit_fix_service → content_pipeline.
- **D-12:** Отображение прогресса — на усмотрение Claude.

### URL Normalization
- **D-13:** normalize_url() должна унифицировать: http/https → https, UTM-параметры → удалять. Trailing slash и www — по усмотрению Claude (на основе реальных данных в БД).
- **D-14:** Когда применять (при записи vs при чтении, нужна ли миграция) — на усмотрение Claude.

### keyword_latest_positions Table
- **D-15:** Плоская таблица, заменяющая DISTINCT ON partition scans. Обновляется после каждого position check run. Детали реализации — на усмотрение Claude.

### Claude's Discretion
- Логика автоподсказки рекомендаций Dead Content (правила на основе ключей/трафика/дельты)
- Отображение прогресса батч-фикса (toast, HTMX polling, или иное)
- Нормализация trailing slash и www — определить по данным в БД
- Стратегия применения normalize_url() (при записи / при чтении / миграция)
- keyword_latest_positions: структура, триггер обновления, индексы

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Position data
- `app/models/position.py` — KeywordPosition model (monthly partitioned table, DISTINCT ON queries)
- `app/services/position_service.py` — get_latest_positions() with DISTINCT ON, position delta computation
- `app/services/dashboard_service.py` — CTE with DISTINCT ON for dashboard queries

### Audit & content pipeline
- `app/models/audit.py` — AuditCheckDefinition (code, severity, auto_fixable, fix_action), AuditResult (site_id, page_url, check_code)
- `app/services/audit_fix_service.py` — batch fix wiring to content pipeline via WpContentJob
- `app/services/content_pipeline.py` — inject_toc(), inject_schema(), insert_links(), generate_schema_article()

### Page & crawl data
- `app/models/crawl.py` — Page (url, title, word_count, content_type), PageType enum, ContentType enum
- `app/models/metrika.py` — MetrikaTrafficPage (page_url, visits, bounce_rate)

### Existing patterns
- `app/models/keyword.py` — Keyword (target_url field for page-keyword linkage)
- `app/services/metrika_service.py` — Metrika data retrieval patterns
- `app/routers/analytics.py` — existing analytics router
- `app/templates/analytics/` — existing analytics templates

### Task system
- `app/models/task.py` — SEO task model for Dead Content → task creation
- `app/services/task_service.py` — task creation service

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `content_pipeline.py`: inject_toc, inject_schema, insert_links — already working, wire through audit_fix_service for batch operations
- `audit_fix_service.py`: batch fix orchestration via WpContentJob — existing pattern for Quick Wins batch fix
- `position_service.py`: get_latest_positions() with DISTINCT ON — will be replaced by keyword_latest_positions flat table
- `dashboard_service.py`: CTE-based latest position queries — candidate for refactoring to use new flat table
- `MetrikaTrafficPage`: page-level visit data — source for Dead Content zero-traffic detection
- `AuditCheckDefinition`: configurable checks with severity + auto_fixable flags — drives Quick Wins issue columns

### Established Patterns
- All position queries use raw SQL with DISTINCT ON (kp.keyword_id, kp.engine) — needs refactoring to flat table
- Audit results linked by page_url string (not FK to pages table) — normalize_url() critical for correct JOINs
- Celery tasks for external operations with retry=3
- HTMX partial updates in templates

### Integration Points
- New routes under `/analytics/` router (quick-wins, dead-content)
- Templates in `app/templates/analytics/`
- Navigation: add Quick Wins and Dead Content to site navigation
- Celery: batch fix tasks dispatched through existing infrastructure

</code_context>

<specifics>
## Specific Ideas

- Расширенная таблица Quick Wins — пользователь хочет видеть все проблемы (TOC/Schema/Links/Content) как отдельные колонки ✓/✗ — «всё видно сразу без кликов»
- Dead Content — не просто отчёт, а возможность создать SEO-задачи для работы с мёртвыми страницами
- Реальные проблемы с URL: http vs https и UTM-параметры (не trailing slash)

</specifics>

<deferred>
## Deferred Ideas

- Автоматический поиск кандидатов для merge (страницы с пересекающимися ключами) — отдельная фича
- Todo «Fix position check ignores keyword engine preference» — рассмотрено, может быть учтено при реализации keyword_latest_positions
- Todo «Proxy management, XMLProxy integration» — не относится к этой фазе

</deferred>

---

*Phase: 12-analytical-foundations*
*Context gathered: 2026-04-06*
