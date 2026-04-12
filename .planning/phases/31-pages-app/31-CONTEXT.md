# Phase 31: Pages App - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Мобильные экраны для управления страницами сайта в v4.0 Mobile & Telegram. Пользователь видит список страниц из последнего краула с аудит-статусом (Schema, TOC, noindex), одобряет/отклоняет изменения WP Pipeline, выполняет quick fix (TOC, Schema, title/meta) и запускает массовые операции (Schema/TOC на все статьи).

**Delivers:**
- `GET /m/pages` — список страниц из последнего краула с табами-фильтрами (Все / Без Schema / Без TOC / Noindex), count-badge на каждом табе, дропдаун сайтов + cookie persist, карточки с URL + иконками статуса, "Загрузить ещё" HTMX pagination (20 per page).
- `GET /m/pages/detail/{page_id}` — inline expand HTMX partial: полные данные (title, meta, word_count, h1) + кнопки Quick Fix (TOC, Schema, Title/Meta) + "Создать задачу".
- `GET /m/pipeline` — отдельная страница approve queue: WpContentJob в awaiting_approval/pushed/failed, HTML diff (green/red) из diff_json, 2-tap confirmation (кнопка → "Подтвердить?" с timeout 2 сек), auto-push после approve, статус pushed/failed + toast, rollback кнопка для pushed jobs.
- `POST /m/pipeline/{job_id}/approve` — approve + auto-push_to_wp Celery task.
- `POST /m/pipeline/{job_id}/reject` — reject job.
- `POST /m/pipeline/{job_id}/rollback` — rollback pushed job.
- Quick fix TOC: `POST /m/pages/fix/{page_id}/toc` — сразу push в WP (безопасная операция). Celery task.
- Quick fix Schema: `POST /m/pages/fix/{page_id}/schema` — сразу push в WP (безопасная операция). Celery task.
- Quick fix title/meta: `GET /m/pages/{site_id}/{page_id}/edit` — отдельный экран редактирования с SERP preview. `POST` создаёт WpContentJob в awaiting_approval (через pipeline, т.к. рискованная операция).
- Bulk Schema: `POST /m/pages/bulk/schema` — экран подтверждения ("Добавить Schema на 47 страниц?") → Celery batch task → HTMX polling с progress bar (12/47) + toast по завершению.
- Bulk TOC: `POST /m/pages/bulk/toc` — аналогично bulk schema.
- Empty state: CTA "Запустить краулинг" если нет данных Page для сайта.

**Out of scope (block if suggested):**
- Desktop UI для /ui/pages — Phase 31 **только мобильные экраны**
- Bulk approve всех pending jobs — defer (только поштучный approve)
- Внутренняя перелинковка как quick fix — defer (есть в content_pipeline, но слишком сложно для one-button fix)
- Редактирование контента страницы (body) — defer (только title/meta)
- Создание новых страниц в WP — defer
- Фильтрация по типу страницы (page_type enum) — defer (только аудит-фильтры)
- Текстовый поиск по страницам — defer (только табы)
- История изменений страницы — defer
- Approve с комментарием — defer (только approve/reject)
- Batch rollback — defer (только поштучный)

</domain>

<decisions>
## Implementation Decisions

### Gray Area 1 — Список страниц: источник данных и layout

- **D-01:** Источник данных — Page model из последнего краула (`crawl_job` с максимальным `crawled_at` для сайта). Не WP REST API. Актуальность определяется датой последнего краула.
- **D-02:** Дропдаун сайтов сверху с persist в cookie `m_pages_site_id` (паттерн Phase 30 /m/errors).
- **D-03:** 4 таба-фильтра: Все / Без Schema / Без TOC / Noindex. Каждый таб с count-badge. HTMX swap при переключении (`hx-target="#pages-content"`).
- **D-04:** Карточка страницы в списке — минимум: URL (truncated) + иконки-бейджи статуса (✓/✗ Schema, ✓/✗ TOC, ✓/✗ Index). Без title, без word_count в списке.
- **D-05:** Тап на карточку → inline expand (HTMX `hx-get`, swap outerHTML): полные данные (title, h1, meta_description, word_count, http_status) + кнопки Quick Fix (показывать только релевантные: "Добавить TOC" если !has_toc, "Добавить Schema" если !has_schema, "Изменить Title/Meta" всегда) + кнопка "Создать задачу" (→ /m/tasks/new?mode=task prefilled).
- **D-06:** Пагинация — "Загрузить ещё" (HTMX, паттерн Phase 30), 20 страниц per load.
- **D-07:** Empty state: если нет Page для выбранного сайта → "Нет данных о страницах. Запустите краулинг" + CTA кнопка → запуск Celery crawl task (через существующий `/api/crawl/start`).

### Gray Area 2 — Approve queue: WP Pipeline mobile UI

- **D-08:** Approve queue — отдельная страница `/m/pipeline` (не таб в /m/pages). Показывает WpContentJob в статусах awaiting_approval, pushed, failed для выбранного сайта.
- **D-09:** Отображение изменений — HTML diff (green/red) из `diff_json`. Каждый job показывает: URL страницы, тип изменения (heading_count, has_toc метки), diff inline.
- **D-10:** 2-tap confirmation: первый тап "Принять" → кнопка меняется на "Подтвердить?" (зелёный, accent). Если не нажато 2 секунды → сброс обратно. Reject аналогично ("Отклонить" → "Подтвердить отклонение?").
- **D-11:** Auto-push после approve: approve endpoint меняет статус на `approved` и сразу запускает `push_to_wp.delay(job_id)`. Результат push отображается в списке (pushed ✓ / failed ✗) + toast.
- **D-12:** Rollback с мобильного: для pushed jobs кнопка "Откатить" → 2-tap confirmation → `rollback_to_wp.delay(job_id)`. WpContentJob.rollback_payload уже есть.

### Gray Area 3 — Quick fix: что и как

- **D-13:** 3 quick fix типа:
  1. **Добавить TOC** — сразу push в WP через Celery task. Безопасная операция (добавление, не изменение). Использует `content_pipeline.py` extract_headings + generate_toc.
  2. **Добавить Schema** — сразу push в WP через Celery task. Безопасная операция. Использует `schema_service.py` + `SchemaTemplate` для сайта.
  3. **Изменить Title/Meta** — через pipeline: создаёт WpContentJob в `awaiting_approval`. Рискованная операция (изменение существующего контента).
- **D-14:** Запуск quick fix из inline expand карточки страницы. Кнопки показываются только если fix применим (!has_toc, !has_schema).
- **D-15:** Редактирование title/meta — отдельный экран `/m/pages/{site_id}/{page_id}/edit`: 2 input (title, meta_description) с текущими значениями из Page model, SERP preview snippet (title + URL + description). Submit → создаёт WpContentJob с diff → перенаправление на /m/pipeline.

### Gray Area 4 — Массовые операции

- **D-16:** 2 bulk операции в MVP: "Добавить Schema на все статьи" + "Добавить TOC на все статьи". Без bulk approve.
- **D-17:** Экран подтверждения со счётчиком: "Добавить Schema на N страниц?" (N = count страниц без has_schema для текущего сайта) + кнопка "Подтвердить". Кнопки bulk ops доступны внизу страницы /m/pages (под списком) или в dropdown меню.
- **D-18:** Прогресс: HTMX polling с progress bar + счётчик (12/47) + toast по завершению. Паттерн Phase 29 (hx-trigger="every 3s" + notify() double-safety). Celery task обрабатывает страницы по одной, обновляя Redis counter.

### Claude's Discretion

- **Celery task структура** для quick fix и bulk — planner решает: один универсальный task с параметром `fix_type` или отдельные tasks.
- **Bottom nav** — нужно ли добавлять "Страницы" в bottom nav или достаточно ссылки с dashboard. Planner решает на основе количества элементов в nav.
- **Pipeline page layout** — как группировать jobs: по дате, по статусу, flat list. Planner выбирает.
- **SERP preview** на edit screen — точная реализация (CSS, размеры, цвета Google snippet). Planner решает.
- **Error handling** для push/rollback failures — toast + retry кнопка или подробное сообщение.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### WP Pipeline (существующий код)
- `app/models/wp_content_job.py` — WpContentJob модель: статусы, diff_json, rollback_payload, wp_post_id
- `app/routers/wp_pipeline.py` — desktop approve/reject/push endpoints (reference pattern)
- `app/tasks/wp_content_tasks.py` — `run_content_pipeline`, `push_to_wp`, rollback Celery tasks
- `app/services/content_pipeline.py` — TOC generation, Schema injection, diff computation, heading ID injection

### Page/Audit models
- `app/models/crawl.py` — Page model: url, title, h1, meta_description, has_toc, has_schema, has_noindex, word_count, page_type, crawl_job_id
- `app/models/audit.py` — AuditCheckDefinition, AuditResult, SchemaTemplate

### Schema service
- `app/services/schema_service.py` — Schema.org template rendering, placeholder substitution

### Mobile patterns (reuse)
- `app/routers/mobile.py` — все /m/* endpoints, Phase 26-30 patterns
- `app/templates/mobile/base_mobile.html` — layout, bottom nav
- `app/templates/mobile/errors/partials/` (Phase 30) — REFERENCE для inline expand, HTMX partial patterns
- `app/templates/mobile/tools/partials/tool_progress.html` (Phase 29) — REFERENCE для HTMX polling progress bar

### Bulk patterns
- `app/routers/bulk.py` — existing bulk operations pattern (service layer + count returns)

### Phase 29 contracts
- `.planning/phases/29-reports-tools/29-CONTEXT.md` — D-07: showToast() pattern, D-12: HTMX polling every 3s + notify()
- `.planning/phases/29-reports-tools/29-UI-SPEC.md` — spacing, colors, typography, Heroicons

### Phase 30 contracts
- `.planning/phases/30-errors-quick-task/30-CONTEXT.md` — D-06/D-07: site dropdown + cookie persist, tab sections with count-badge, "Загрузить ещё" pagination pattern

### ROADMAP and REQUIREMENTS
- `.planning/ROADMAP.md` §Phase 31 — goal, success criteria, REQ IDs
- `.planning/REQUIREMENTS.md` §PAG-01, PAG-02, PAG-03, PAG-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`WpContentJob` model** — полный pipeline уже существует: pending → processing → awaiting_approval → approved → pushed (+ rolled_back, failed). Есть diff_json, original_content, processed_content, rollback_payload.
- **`content_pipeline.py`** — extract_headings, generate_toc, inject schema, find_link_opportunities, compute_diff. Всё для quick fix.
- **`schema_service.py`** — SchemaTemplate rendering. Quick fix Schema использует этот сервис.
- **`push_to_wp` Celery task** — уже умеет пушить processed_content в WP REST API. Rollback тоже.
- **`bulk.py` router + `bulk_service.py`** — паттерн batch operations с count returns.
- **`app/routers/mobile.py`** — 50+ endpoints от Phase 26-30. Phase 31 добавляет ещё ~12 endpoints.
- **`showToast()`** JS helper (Phase 28/29) — feedback после действий.

### Established Patterns
- **HTMX polling** (Phase 29): `hx-trigger="every 3s"` с остановкой в done/error ветках.
- **Inline expand** (Phase 30): `hx-get` + `hx-target="closest .row"` + swap outerHTML.
- **Site dropdown + cookie** (Phase 30): persist selection в session cookie.
- **Tabs with count-badge** (Phase 30): `hx-target="#content"` при переключении.
- **SQLAlchemy 2.0 async** с `AsyncSession = Depends(get_db)`.
- **Celery retry=3** для external API calls.
- **Loguru** logging.

### Integration Points
- **`app/routers/mobile.py`** — все новые endpoints append сюда:
  - GET /m/pages (+ query params: site_id, tab, offset)
  - GET /m/pages/detail/{page_id} (inline expand partial)
  - GET /m/pages/{site_id}/{page_id}/edit (title/meta edit screen)
  - POST /m/pages/{site_id}/{page_id}/edit (submit → WpContentJob)
  - POST /m/pages/fix/{page_id}/toc (quick fix TOC)
  - POST /m/pages/fix/{page_id}/schema (quick fix Schema)
  - POST /m/pages/bulk/schema (bulk Schema)
  - POST /m/pages/bulk/toc (bulk TOC)
  - GET /m/pages/bulk/progress/{task_id} (polling)
  - GET /m/pipeline (approve queue)
  - POST /m/pipeline/{job_id}/approve
  - POST /m/pipeline/{job_id}/reject
  - POST /m/pipeline/{job_id}/rollback
- **`app/tasks/`** — новые Celery tasks для quick fix и bulk operations
- **`app/templates/mobile/pages/`** — новая директория шаблонов
- **`app/templates/mobile/pipeline/`** — новая директория шаблонов

</code_context>

<specifics>
## Specific Ideas

- **2-tap confirmation** — первый тап меняет кнопку текст + цвет, timeout 2 сек через JS setTimeout → сброс. Простейшая реализация без модалов.
- **HTML diff** — `diff_json` из WpContentJob содержит structured diff. Рендерим как `<ins>` (green) / `<del>` (red) в HTML partial.
- **SERP preview** на edit screen — Google-style snippet: синий title (truncated ~60 chars), зелёный URL, серый description (truncated ~160 chars). Обновляется при вводе через JS (без HTMX — client-side preview).
- **Bulk progress в Redis** — `bulk:{task_id}:progress` = JSON `{"done": 12, "total": 47, "errors": []}`. Celery task инкрементирует после каждой страницы.
- **Quick fix TOC/Schema — без WpContentJob** — эти операции безопасны (additive), поэтому идут напрямую через push_to_wp, минуя pipeline approval. Создаём temporary content job для rollback capability.

</specifics>

<deferred>
## Deferred Ideas

- **Bulk approve** — одобрение всех pending jobs одной кнопкой. Defer: поштучный approve достаточен для MVP.
- **Внутренняя перелинковка** как quick fix — есть в content_pipeline, но слишком сложно для one-button fix (нужен выбор anchor text и target).
- **Редактирование body** контента — только title/meta в MVP.
- **Текстовый поиск** по страницам — только табы-фильтры.
- **Фильтрация по page_type** (статья/категория/главная) — defer.
- **История изменений** страницы (audit trail) — defer.
- **Approve с комментарием** — defer.
- **Batch rollback** — только поштучный.
- **Desktop /ui/pages** — Phase 31 = mobile only.
- **Создание новых страниц** в WP — defer.

### Reviewed Todos (not folded)

- **Fix position check ignores keyword engine preference** — matched на "app", но это position-check bug. Остаётся в backlog.
- **Proxy management, XMLProxy integration** — matched на "app", но относится к crawler/proxy. Остаётся в backlog.

</deferred>

---

*Phase: 31-pages-app*
*Context gathered: 2026-04-12*
