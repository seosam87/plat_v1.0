# Phase 4: Analytics Workspace - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Full analytical workflow: advanced keyword filters → save analysis session → check positions per group → SERP parse per group → detect top competitors by site type → compare our positions vs competitor → compare SEO fields (light) or full crawl (heavy) → create content brief (ТЗ) from the session. Standalone "Аналитика" page with wizard-like step-by-step UI.

</domain>

<decisions>
## Implementation Decisions

### Analysis Session
- **D-01:** Отдельная сущность `AnalysisSession` в своей таблице. Хранит набор keyword_ids, фильтры, результаты. Можно выгрузить (CSV/Excel). На основе сессии можно создать ТЗ (content brief) для копирайтера.
- **D-02:** Пример use case: отфильтровали ключи → увидели что ключи бьют на некорректные страницы → создаём задачу "доработка пропущенного кластера" → на основе неё создаём ТЗ с SEO-полями, местом в структуре, ключами и структурой заголовков.

### Position Checking
- **D-03:** Отдельный flow `check_group_positions` — новая Celery-задача для проверки позиций по подмножеству ключей из сессии.

### SERP Analysis
- **D-04:** Группа ~30 ключей. Парсим SERP, выдаём типы сайтов (коммерческие/инфо/агрегаторы) и топовых конкурентов (кто чаще всего в TOP-10 по этой группе).

### Competitor Comparison
- **D-05:** Два варианта сравнения:
  - **Лёгкий:** Только SEO-поля (title, H1, meta, schema наличие) — через одноразовый Playwright fetch страницы конкурента.
  - **Тяжёлый:** Полный краул страницы конкурента — все данные как у наших страниц.
  - Пользователь выбирает вариант в UI.

### UI
- **D-06:** Отдельная страница "Аналитика" в навбаре. Wizard-подобный интерфейс: шаг за шагом (фильтр → сессия → позиции → SERP → конкурент → сравнение → ТЗ).

### Content Brief (ТЗ)
- **D-07:** На основе сессии генерируется ТЗ для копирайтера/контент-менеджера:
  - SEO-поля (рекомендуемый title, H1, meta description)
  - Место в структуре сайта (URL, раздел)
  - Ключевые слова из сессии (phrase + frequency)
  - Структура заголовков (H2/H3 на основе кластера/конкурента)
  - Экспорт в текстовый формат

### Scope
- **D-08:** Максимальный скоуп — все 7 шагов workflow + ТЗ.

### Claude's Discretion
- AnalysisSession model schema (what metadata to store)
- SERP site type classification logic
- Content brief template structure
- Wizard UI step transitions (JS or HTMX)
- How to store SERP results per session (JSON field or separate table)

</decisions>

<canonical_refs>
## Canonical References

### Keywords (existing)
- `app/models/keyword.py` — Keyword (phrase, frequency, region, engine, group_id, cluster_id, target_url)
- `app/models/keyword.py` — KeywordGroup (name, site_id, parent_id)
- `app/routers/keywords.py` — basic keyword filtering (group_id, limit, offset)
- `app/services/keyword_service.py` — CRUD, bulk import

### Positions (existing)
- `app/models/position.py` — KeywordPosition (monthly partitioned, position, delta, engine, region, url)
- `app/services/position_service.py` — get_latest_positions, get_position_history, compare_positions_by_date
- `app/tasks/position_tasks.py` — check_positions Celery task (DataForSEO + GSC + Yandex + Playwright)

### SERP (existing)
- `app/services/serp_parser_service.py` — Playwright SERP parsing (<50 req/day), returns {results: [{position, url, title}], features: [...]}

### Competitors (existing)
- `app/models/competitor.py` — Competitor (site_id, domain, name)
- `app/services/competitor_service.py` — compare_positions, detect_serp_competitors(min_shared=3)

### Clusters (existing)
- `app/models/cluster.py` — KeywordCluster (name, target_url, intent enum)
- `app/services/cluster_service.py` — auto-cluster by SERP intersection

### Content briefs (existing pattern)
- `app/models/task.py` — SeoTask model (used for project tasks)
- Pipeline brief generation exists in roadmap Phase 9 scope

</canonical_refs>

<code_context>
## Existing Code Insights

### What Can Be Reused
- `position_tasks.check_positions` — adapt for per-group checking (add keyword_ids param)
- `serp_parser_service.py` — parse SERP per keyword
- `competitor_service.detect_serp_competitors` — find top competitors from SERP overlap
- `competitor_service.compare_positions` — compare our vs competitor positions
- `crawler_service.py` — Playwright page crawl for competitor SEO field extraction
- Existing Jinja2 + HTMX patterns for wizard-like UI

### New Components Needed
- `AnalysisSession` model — stores session with keyword_ids, filters, results
- `SessionSerpResult` model or JSON field — SERP TOP-10 per keyword per session
- `ContentBrief` model — generated brief with SEO fields, keywords, headings
- `analytics_service.py` — orchestrates the workflow steps
- `brief_service.py` — generates content brief from session data
- `app/routers/analytics.py` — workspace router
- `app/templates/analytics/` — wizard UI templates
- `app/tasks/analytics_tasks.py` — Celery tasks for group position check and SERP parse

</code_context>

<deferred>
## Deferred Ideas

- Auto-generated heading structure from competitor analysis (ML/NLP)
- Brief export to PDF/DOCX
- Integration with external copywriting platforms
- Session sharing between users

</deferred>

---

*Phase: v3-04-analytics-workspace*
*Context gathered: 2026-04-02*
