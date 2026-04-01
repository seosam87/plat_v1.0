# Phase 1: Yandex Metrika - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Integrate Yandex Metrika API to show search traffic per page alongside technical SEO state and actions taken on the site. User can see visitors and their quality in the same system where they manage crawls, positions, and content pipeline.

</domain>

<decisions>
## Implementation Decisions

### Connection & Auth
- **D-01:** API-токен (статический), не OAuth. Внутренний инструмент — OAuth избыточен.
- **D-02:** 1 сайт = 1 счётчик Метрики. Поле `metrika_counter_id` + `metrika_token` на модели Site.
- **D-03:** Хранение токена — Claude's discretion (Fernet или plaintext, исходя из threat model).

### Data & Metrics
- **D-04:** Поисковый трафик по страницам + агрегат по всему сайту.
- **D-05:** Метрики: визиты (`visits`), отказы (`bounce_rate`), глубина просмотра (`page_depth`), время на сайте (`avg_duration`).
- **D-06:** Поисковые системы — общий поток, без разбивки Яндекс/Google.

### Period Comparison
- **D-07:** Два произвольных диапазона дат, выбираемых пользователем. Дельта между периодами — это и есть "новый трафик".
- **D-08:** Сбор данных только по запросу (кнопка). Без Celery Beat автосбора.

### UI & Integration
- **D-09:** Отдельная страница "Трафик" в навигации сайта — таблица страниц + график с overlay событий.
- **D-10:** Ручные метки-события на графике (даты внедрений, микроразметки, новых страниц и т.д.). Не автоматические — пользователь ставит сам.
- **D-11:** Виджет в Site Overview — краткая сводка трафика, отображается при наличии данных.

### Core Idea
- **D-12:** Ключевая ценность — трафик + качество посетителей в одной системе с техническим состоянием сайта и действиями над ним. Наложение дат действий на график трафика показывает причинно-следственную связь.

### Claude's Discretion
- Token storage method (Fernet vs plaintext) — based on existing patterns and threat model
- Metrika API response caching strategy
- Table pagination and sorting defaults

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing integration patterns
- `app/services/yandex_webmaster_service.py` — existing Yandex API integration pattern (token-based)
- `app/services/gsc_service.py` — external API service pattern with token storage
- `app/services/crypto_service.py` — Fernet encryption for credentials
- `app/models/site.py` — Site model (metrika fields will be added here)
- `app/models/file_upload.py` — already has `yandex_metrika` enum value

### UI patterns
- `app/templates/` — existing Jinja2 + HTMX template patterns
- Site Overview page — widget integration point

### Roadmap
- `.planning/ROADMAP-v3.md` §Phase 1 — phase scope and goals

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `yandex_webmaster_service.py` — Yandex API call pattern, token handling
- `gsc_service.py` — OAuth/token service pattern, can adapt for simpler API-token flow
- `crypto_service.py` — Fernet encrypt/decrypt for token storage
- `position_service.py` — period comparison logic (delta computation)
- `ad_traffic.py` model — period comparison UI pattern (already has before/after delta table)
- Chart.js integration — already used in positions for 90-day charts

### Established Patterns
- Service layer: `{module}_service.py` with async methods
- Router: `app/routers/{module}.py` with FastAPI endpoints
- Models: SQLAlchemy 2.0 async, Alembic migrations
- UI: Jinja2 + HTMX partial updates, Tailwind CSS
- On-demand tasks: Celery task triggered by button click (not Beat-scheduled)

### Integration Points
- Site model — add `metrika_counter_id` and `metrika_token` fields
- Site navigation — add "Traffic" link
- Site Overview — add traffic widget
- Alembic — new migration for metrika fields + traffic data table

</code_context>

<specifics>
## Specific Ideas

- **Event overlay on traffic chart:** User manually places date markers on the traffic graph (e.g., "deployed schema.org", "published 5 new pages"). This visually links actions to traffic outcomes.
- **Quality context:** The value is not just traffic numbers, but seeing them next to what you're doing on the site — crawl issues, position changes, content pipeline activity.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: v3-01-yandex-metrika*
*Context gathered: 2026-04-01*
