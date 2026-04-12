# Phase 31: Pages App - Research

**Researched:** 2026-04-12
**Domain:** Mobile FastAPI/Jinja2/HTMX — pages list, WP pipeline approval, quick fix, bulk operations
**Confidence:** HIGH — all findings from direct codebase inspection

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Источник данных — Page model из последнего краула (`crawl_job` с максимальным `crawled_at` для сайта). Не WP REST API.
- **D-02:** Дропдаун сайтов сверху с persist в cookie `m_pages_site_id` (паттерн Phase 30 /m/errors).
- **D-03:** 4 таба-фильтра: Все / Без Schema / Без TOC / Noindex. Каждый таб с count-badge. HTMX swap при переключении (`hx-target="#pages-content"`).
- **D-04:** Карточка страницы в списке — минимум: URL (truncated) + иконки-бейджи статуса (✓/✗ Schema, ✓/✗ TOC, ✓/✗ Index). Без title, без word_count в списке.
- **D-05:** Тап на карточку → inline expand (HTMX `hx-get`, swap outerHTML): полные данные (title, h1, meta_description, word_count, http_status) + кнопки Quick Fix (показывать только релевантные) + кнопка "Создать задачу".
- **D-06:** Пагинация — "Загрузить ещё" (HTMX, паттерн Phase 30), 20 страниц per load.
- **D-07:** Empty state: нет Page для выбранного сайта → "Нет данных о страницах. Запустите краулинг" + CTA кнопка запуска crawl task.
- **D-08:** Approve queue — отдельная страница `/m/pipeline` (не таб в /m/pages). Показывает WpContentJob в статусах awaiting_approval, pushed, failed для выбранного сайта.
- **D-09:** Отображение изменений — HTML diff (green/red) из `diff_json`. Каждый job показывает URL, тип изменения, diff inline.
- **D-10:** 2-tap confirmation: первый тап меняет кнопку текст + цвет, timeout 2 сек через JS setTimeout → сброс. Reject аналогично.
- **D-11:** Auto-push после approve: approve endpoint меняет статус на `approved` и сразу запускает `push_to_wp.delay(job_id)`.
- **D-12:** Rollback с мобильного: для pushed jobs кнопка "Откатить" → 2-tap confirmation → `rollback_to_wp.delay(job_id)`.
- **D-13:** 3 quick fix типа: TOC (direct push), Schema (direct push), Title/Meta (via pipeline to awaiting_approval).
- **D-14:** Quick fix из inline expand карточки. Кнопки показываются только если fix применим.
- **D-15:** Title/meta edit screen `/m/pages/{site_id}/{page_id}/edit` с SERP preview snippet.
- **D-16:** 2 bulk операции: "Добавить Schema на все статьи" + "Добавить TOC на все статьи". Без bulk approve.
- **D-17:** Экран подтверждения со счётчиком страниц для bulk операций.
- **D-18:** Прогресс: HTMX polling с progress bar + счётчик (done/total) + toast по завершению. Паттерн Phase 29. Redis counter.

### Claude's Discretion

- **Celery task структура** для quick fix и bulk — planner решает: один универсальный task с параметром `fix_type` или отдельные tasks.
- **Bottom nav** — нужно ли добавлять "Страницы" в bottom nav или достаточно ссылки с dashboard. Planner решает на основе количества элементов в nav.
- **Pipeline page layout** — как группировать jobs: по дате, по статусу, flat list.
- **SERP preview** на edit screen — точная реализация (CSS, размеры, цвета Google snippet).
- **Error handling** для push/rollback failures — toast + retry кнопка или подробное сообщение.

### Deferred Ideas (OUT OF SCOPE)

- Bulk approve всех pending jobs
- Внутренняя перелинковка как quick fix
- Редактирование body контента
- Текстовый поиск по страницам
- Фильтрация по page_type
- История изменений страницы
- Approve с комментарием
- Batch rollback
- Desktop /ui/pages
- Создание новых страниц в WP

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAG-01 | Пользователь видит список страниц сайта с аудит-статусом (индексация, позиции, ошибки) | Page model confirmed: has_schema, has_toc, has_noindex fields. Latest crawl query via max(crawled_at) on CrawlJob per site. |
| PAG-02 | Пользователь может одобрить или отклонить изменения из WP Pipeline (approve queue) с 2-tap confirmation | WpContentJob.status enum verified. Desktop approve/reject/rollback endpoints confirmed reusable as pattern. Push chain: job.status=approved → push_to_wp.delay(). |
| PAG-03 | Пользователь может выполнить quick fix: обновить title/meta/schema/TOC одной кнопкой → push в WP | content_pipeline.py pure functions confirmed (extract_headings, generate_toc_html, inject_toc). schema_service.py render_schema_for_page confirmed. push_to_wp task confirmed reusable. Title/meta creates WpContentJob directly. |
| PAG-04 | Пользователь может запустить массовую операцию (обновить Schema на всех статьях, добавить TOC) с подтверждением | Bulk progress pattern from Phase 29 (tool_progress.html + Redis counter). Celery task processes pages one by one with Redis increment. |

</phase_requirements>

---

## Summary

Phase 31 adds ~12 new endpoints to `app/routers/mobile.py` and 2 new template directories (`app/templates/mobile/pages/`, `app/templates/mobile/pipeline/`). All underlying business logic already exists — the phase is primarily about building mobile UI wiring on top of proven services.

The key finding is that **all four backend services are fully implemented and verified**: `WpContentJob` pipeline (approve/reject/rollback), `content_pipeline.py` TOC functions, `schema_service.py` template rendering, and `push_to_wp` Celery task. Phase 31 creates new Celery tasks for quick-fix and bulk operations that compose these existing functions, and new mobile endpoints and templates following Phase 29/30 patterns.

The bottom nav currently has 4 tabs (Дайджест, Сайты, Позиции, Ошибки). Adding "Страницы" as a 5th tab is viable — 5 tabs at `justify-content:space-around` with `padding:0 8px` fits comfortably on a 375px screen. The pipeline page shares the `pages` active_tab (confirmed in UI-SPEC).

**Primary recommendation:** Follow the Phase 30 errors pattern exactly for pages list (site dropdown + cookie + tabs + inline expand). Reuse Phase 29 tool_progress.html pattern for bulk polling. Quick-fix TOC/Schema go directly to WP without pipeline; title/meta creates a WpContentJob.

---

## Standard Stack

### Core (fixed — from CLAUDE.md)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| Python | 3.12 | Runtime | Fixed |
| FastAPI | 0.115.x | ASGI framework | Fixed |
| SQLAlchemy | 2.0.x async | ORM | AsyncSession pattern throughout |
| Jinja2 | 3.1.x | Templates | mobile_templates = Jinja2Templates("app/templates") |
| HTMX | 2.0.3 | Partial page updates | Loaded from CDN in base_mobile.html |
| Celery 5 + Redis | 5.4.x / 7.2.x | Async task queue | queue="wp" for pipeline tasks |

### Supporting (in-scope for this phase)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| redis-py | 5.0.x | Direct Redis client | Bulk progress counter (`bulk:{task_id}:progress`); same pattern as `position_check:{site_id}` |
| loguru | 0.7.x | Logging | All new tasks and endpoints |

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── routers/mobile.py              # Append ~12 new endpoints (all in same file)
├── tasks/
│   └── pages_tasks.py             # New: quick_fix_toc, quick_fix_schema, bulk_fix_schema, bulk_fix_toc
├── templates/mobile/
│   ├── pages/
│   │   ├── index.html             # /m/pages full page
│   │   ├── partials/
│   │   │   ├── pages_content.html # HTMX swap target (#pages-content)
│   │   │   ├── page_row.html      # Single compact page card
│   │   │   ├── page_detail.html   # Inline expanded detail (outerHTML swap)
│   │   │   ├── page_collapsed.html # Collapse partial (restores compact row)
│   │   │   └── bulk_progress.html # Bulk polling partial (reuses tool_progress.html pattern)
│   │   └── bulk_confirm.html      # /m/pages/bulk/{type}/confirm screen
│   │   └── edit.html              # /m/pages/{site_id}/{page_id}/edit screen
│   └── pipeline/
│       ├── index.html             # /m/pipeline full page
│       └── partials/
│           ├── pipeline_content.html # HTMX swap target (#pipeline-content)
│           └── job_card.html         # Single job card (outerHTML swap target)
```

### Pattern 1: Site-Cookie Dropdown (Phase 30 exact pattern)

**What:** Site dropdown that persists selection in cookie; HTMX swaps content on change.
**When to use:** `/m/pages` and `/m/pipeline` site selection.

```python
# Source: app/routers/mobile.py mobile_errors() — Phase 30 pattern
site_id = request.cookies.get("m_pages_site_id")
if not site_id or not any(str(s.id) == site_id for s in sites):
    site_id = str(sites[0].id)

# At response end:
response.set_cookie(key="m_pages_site_id", value=site_id, httponly=True, samesite="lax", max_age=86400 * 30)
```

Both `/m/pages` and `/m/pipeline` share `m_pages_site_id` cookie (confirmed in UI-SPEC).

### Pattern 2: Latest Crawl Query (D-01)

**What:** Get pages from the most recent completed crawl for a site.
**When to use:** `/m/pages` list endpoint.

```python
# Source: verified from CrawlJob + Page model structure
from sqlalchemy import select, func
from app.models.crawl import CrawlJob, CrawlJobStatus, Page

# Subquery: latest done crawl_job_id for the site
latest_crawl_sq = (
    select(CrawlJob.id)
    .where(CrawlJob.site_id == site_uuid, CrawlJob.status == CrawlJobStatus.done)
    .order_by(CrawlJob.finished_at.desc())
    .limit(1)
    .scalar_subquery()
)

# Count query per tab
base_q = select(func.count()).where(Page.crawl_job_id == latest_crawl_sq)
tab_filters = {
    "all": base_q,
    "no_schema": base_q.where(Page.has_schema == False),
    "no_toc": base_q.where(Page.has_toc == False),
    "noindex": base_q.where(Page.has_noindex == True),
}

# Page list query with pagination
pages_q = (
    select(Page)
    .where(Page.crawl_job_id == latest_crawl_sq)
    .order_by(Page.url)
    .limit(20)
    .offset(offset)
)
```

### Pattern 3: HTMX Partial vs Full Page (Phase 29/30 pattern)

**What:** Single endpoint handles both full-page render and HTMX partial based on `HX-Request` header.
**When to use:** `/m/pages`, `/m/pipeline`.

```python
# Source: app/routers/mobile.py mobile_errors() and mobile_traffic()
if request.headers.get("HX-Request"):
    response = mobile_templates.TemplateResponse("mobile/pages/partials/pages_content.html", ctx)
else:
    response = mobile_templates.TemplateResponse("mobile/pages/index.html", ctx)
response.set_cookie(...)
return response
```

### Pattern 4: Quick Fix TOC — Direct Push (D-13)

**What:** TOC fix fetches WP content, applies TOC via content_pipeline functions, pushes directly without pipeline approval.
**When to use:** `POST /m/pages/fix/{page_id}/toc`.

```python
# New Celery task in app/tasks/pages_tasks.py
# Uses get_sync_db() pattern from wp_content_tasks.py
# Steps:
# 1. Load Page from DB (get url, site_id, wp_post_id equivalent)
# 2. Fetch current WP content via _fetch_wp_content(site_id, wp_post_id)
# 3. headings = extract_headings(content)
# 4. content = add_heading_ids(content, headings) + inject_toc(content, generate_toc_html(headings))
# 5. Push directly via httpx POST to /wp-json/wp/v2/posts/{wp_post_id}
# 6. Update Page.has_toc = True in DB
# 7. Return {"status": "pushed"} or {"status": "failed", "error": ...}

# IMPORTANT: Page model does NOT have wp_post_id field.
# Must find wp_post_id from WpContentJob history for the page URL, or fetch from WP API.
# See: WpContentJob.wp_post_id (nullable) — latest job for this page_url may have it.
```

**CRITICAL FINDING:** The `Page` model does NOT contain a `wp_post_id` field. Only `WpContentJob` has `wp_post_id`. For quick fix to work, the task must resolve the WP post ID from the latest WpContentJob for that page URL, or look it up via the WP REST API by URL slug. This is a key planning decision.

### Pattern 5: Quick Fix Schema — Direct Push (D-13)

**What:** Schema fix uses schema_service.render_schema_for_page(), appends to content, pushes directly.
**When to use:** `POST /m/pages/fix/{page_id}/schema`.

```python
# Source: app/services/schema_service.py render_schema_for_page()
# Inputs needed: site_id, page.content_type, page.page_type, page.title, page.url, page.meta_description
# Note: render_schema_for_page is async — need async Celery task pattern OR get_sync_db with sync template rendering
# render_schema_template() is a PURE SYNC function — use it directly in sync task
# get_template() is async — need sync equivalent or use get_sync_db with session.execute()
```

### Pattern 6: Title/Meta Quick Fix — Via Pipeline (D-13, D-15)

**What:** Creates a WpContentJob with `processed_content` (original with title/meta changed) and `diff_json`, then redirects to /m/pipeline.
**When to use:** `POST /m/pages/{site_id}/{page_id}/edit`.

```python
# Source: app/routers/wp_pipeline.py approve_job() pattern
# New WpContentJob:
job = WpContentJob(
    site_id=site_id,
    wp_post_id=...,  # from last job for this URL or None
    page_url=page.url,
    original_content=current_content,
    processed_content=updated_content_with_new_title_meta,
    diff_json=compute_content_diff(original, updated),
    rollback_payload={"original_content": current_content, "wp_post_id": ...},
    status=JobStatus.awaiting_approval,
)
# Then RedirectResponse("/m/pipeline", status_code=303)
```

Note: Title and meta_description for WordPress posts are separate fields in the WP REST API (`/wp-json/wp/v2/posts/{id}` with `"title"` and `"excerpt"` keys), distinct from post body `"content"`. The quick-fix edit must understand this difference — title/meta fix sends different WP API fields than content pipeline.

### Pattern 7: Bulk Fix with Redis Progress (D-18)

**What:** Celery task processes pages one by one, updating a Redis JSON counter. HTMX polls every 3s.
**When to use:** `POST /m/pages/bulk/schema` and `POST /m/pages/bulk/toc`.

```python
# Source: Phase 29 tool_progress.html pattern + Redis pattern from mobile_positions
# Redis key: f"bulk:{task_id}:progress" = JSON {"done": N, "total": M, "errors": []}
# Celery task increments after each page processed
# Polling endpoint reads Redis key, returns bulk_progress.html partial
# Stop polling when status == "done" or "error" (same as tool_progress.html)

# For bulk schema: query pages WHERE has_schema=False AND latest crawl for site
# For bulk toc: query pages WHERE has_toc=False AND latest crawl for site
# Count returned to confirm screen (D-17)
```

### Pattern 8: 2-Tap Confirmation (D-10)

**What:** First tap transforms button text/style; if not tapped again within 2s, resets. Second tap fires HTMX POST.
**When to use:** Approve / Reject / Rollback on pipeline jobs.

Exact JS implementation specified in UI-SPEC `## Interaction Contracts` (data-confirm-text, data-confirm-class, data-action-url, data-target pattern). See `initTwoTapButton()` function in UI-SPEC. Place inline `<script>` at bottom of pipeline template.

### Pattern 9: HX-Trigger for Toast (Phase 29 pattern)

**What:** Server returns `HX-Trigger` response header to fire client-side toast from HTMX response.
**When to use:** Quick fix success/error responses, bulk operation completion.

```python
# Source: Phase 29 pattern (confirmed used in tools endpoints)
from fastapi.responses import HTMLResponse
response = mobile_templates.TemplateResponse("mobile/pages/partials/page_detail.html", ctx)
response.headers["HX-Trigger"] = json.dumps({"showToast": {"msg": "TOC добавлен", "type": "success"}})
return response
```

Note: Verify that `showToast()` in `base_mobile.html` responds to HTMX custom events, or use `hx-on` attribute pattern. Current `base_mobile.html` `showToast()` is called directly by JS. The HTMX trigger pattern requires either: (a) an `htmx:afterSettle` event listener that calls `showToast`, or (b) explicit inline `hx-on:htmx:after-settle="showToast(...)"`. This needs careful implementation to match Phase 29 pattern.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TOC generation | Custom heading parser | `content_pipeline.extract_headings` + `generate_toc_html` + `inject_toc` | Already handles H2/H3, slugs, position-after-first-p |
| Schema injection | Custom JSON-LD builder | `schema_service.render_schema_for_page()` + `inject_schema()` | Already handles template selection (Article/Product/Service), site-specific overrides |
| Diff rendering | Custom diff HTML | `diff_json` from `WpContentJob` — render `diff_text` field directly in template | `compute_content_diff()` already produces unified diff format |
| WP content push | Custom WP REST client | `push_to_wp` Celery task or direct `httpx.post` to WP API with `_sync_auth_headers()` | Auth headers, error handling, status tracking already solved |
| Crawl trigger | Custom crawl launcher | `crawl_site_task.delay(str(site_id))` — already used in `mobile_trigger_crawl()` | No new endpoint needed — use existing `/m/health/{site_id}/crawl` pattern or call task directly |
| Cookie site persist | Custom session store | FastAPI `response.set_cookie()` — Phase 30 pattern exact | Already proven in `/m/errors` |
| Progress polling | Custom WebSocket | HTMX `hx-trigger="every 3s"` + Redis key — Phase 29 pattern | No additional infra needed |

---

## Key Technical Findings

### WpContentJob Model (verified)

Fields: `id`, `site_id`, `wp_post_id` (nullable int), `page_url`, `post_type`, `status` (JobStatus enum), `heading_count`, `has_toc`, `original_content`, `processed_content`, `diff_json` (JSON), `rollback_payload` (JSON), `error_message`, `created_at`, `processed_at`, `pushed_at`.

**JobStatus enum values:** `pending`, `processing`, `awaiting_approval`, `approved`, `pushed`, `rolled_back`, `failed`.

**diff_json structure** (from `compute_content_diff()`): `{"has_changes": bool, "added_lines": int, "removed_lines": int, "diff_text": str}`. The `diff_text` is unified diff format. The pipeline page renders `diff_text` line-by-line, wrapping lines starting with `+` in `<ins class="bg-green-100 text-green-800">` and `-` in `<del class="bg-red-100 text-red-800 line-through">`.

**rollback_payload structure:** `{"original_content": str, "wp_post_id": int|null}`.

### Page Model (verified)

Fields relevant to Phase 31: `id`, `site_id`, `crawl_job_id`, `url`, `title`, `h1`, `meta_description`, `http_status`, `depth`, `has_toc` (bool), `has_schema` (bool), `has_noindex` (bool), `word_count`, `page_type` (PageType enum), `content_type` (ContentType enum), `crawled_at`.

**No wp_post_id field.** Page does not store a WordPress post ID. This is a critical gap for quick fix: the task needs to resolve the WP post ID for push. Options: (a) query latest WpContentJob for matching page_url to get wp_post_id, (b) look up WP post by URL via WP REST API (`/wp-json/wp/v2/posts?link={url}` or slug), (c) require wp_post_id in the Page model (schema change — deferred). The planner must choose — option (a) is safest with no schema change.

### Page Source Query (latest crawl)

To get pages from the latest crawl: join CrawlJob to filter for max `finished_at` per site with status `done`. Subquery pattern avoids N+1 queries.

### Bottom Nav (verified)

Current nav: 4 items — Дайджест, Сайты, Позиции, Ошибки. Adding "Страницы" as a 5th item is the correct approach (confirmed by UI-SPEC: `active_tab: 'pages'` specified for all Pages screens). The nav uses `justify-content:space-around` — 5 items at `padding:0 8px` each fits on 375px. Recommend document-text Heroicon (24x24, stroke 1.5) matching UI-SPEC suggestion.

### Pipeline Endpoint Already Exists (desktop)

`app/routers/wp_pipeline.py` has complete approve/reject/rollback/list endpoints. The mobile endpoints follow the same logic but return HTML partials (Jinja2 templates) instead of JSON, and use `get_current_user` instead of `require_admin`. The mobile versions go into `mobile.py` as new endpoints that replicate the business logic with HTML responses.

### Crawl Start for Empty State (D-07)

The empty state CTA should trigger `crawl_site_task.delay(str(site_id))`. The existing `POST /m/health/{site_id}/crawl` endpoint in `mobile.py` already does exactly this. The empty state CTA can point to that existing endpoint (with HTMX POST) rather than requiring a new endpoint.

### schema_service.render_schema_for_page() — Async

`render_schema_for_page()` is async (uses `AsyncSession`). Quick fix Schema Celery task runs in sync context (`get_sync_db()`). Solution: use `get_sync_db()` to directly call `session.execute(select(SchemaTemplate)...)` inline in the Celery task, then call the pure sync functions `select_schema_type_for_page()`, `render_schema_template()`, `generate_schema_tag()`, `inject_schema()`. Do not call the async version from a sync task.

### push_to_wp Task — Expects JobStatus.approved

`push_to_wp(job_id)` checks `job.status != JobStatus.approved` and skips if not approved. For quick-fix TOC/Schema that bypass the pipeline, the task must either: (a) create a real WpContentJob with status=approved and call push_to_wp, or (b) perform the WP push directly in the quick-fix task (inlining the httpx call from push_to_wp). Option (b) is simpler since quick-fix is a direct operation.

### WP REST API for Title/Meta Updates

WordPress title is updated via `PATCH /wp-json/wp/v2/posts/{id}` with `{"title": {"raw": "..."}}`; meta description is typically stored as a meta field (Yoast SEO: `meta_description` or `_yoast_wpseo_metadesc`). The platform's existing `push_to_wp` only updates `"content"`. Title/meta WP push requires extending the push to include `"title"` and the meta field. The WpContentJob for title/meta edit must carry the title and meta in `processed_content` or in `rollback_payload` — a special job type. Planner must decide how to represent this (suggest: `post_type = "title_meta"` to distinguish from content pipeline jobs, with custom push logic).

---

## Common Pitfalls

### Pitfall 1: Page.wp_post_id Does Not Exist

**What goes wrong:** Quick fix tasks try to access `page.wp_post_id` — NameError at runtime.
**Why it happens:** Page model only tracks crawl data. WP post IDs are stored in WpContentJob.
**How to avoid:** Query `WpContentJob` by `site_id` + `page_url` ORDER BY `created_at` DESC LIMIT 1 to get `wp_post_id`. If no prior job exists, wp_post_id is None and direct push is impossible without a WP API lookup by URL.
**Warning signs:** `AttributeError: Page has no attribute wp_post_id`.

### Pitfall 2: Rendering diff_text in Template — XSS

**What goes wrong:** `diff_json.diff_text` contains raw HTML content from WP pages. Rendering it as `{{ diff_text|safe }}` exposes XSS.
**Why it happens:** The content pipeline processes real WordPress HTML content.
**How to avoid:** The template must escape the diff lines and add `<ins>`/`<del>` wrapper spans, NOT use the raw HTML. Parse `diff_text` line-by-line in a Jinja2 macro or in the endpoint, classify each line as added/removed/context, escape each line's content, then wrap.
**Warning signs:** JavaScript in page content appearing unescaped in the pipeline view.

### Pitfall 3: push_to_wp Skips Non-Approved Jobs

**What goes wrong:** Calling `push_to_wp.delay(job_id)` on a job that was just created with status=pending or processing causes silent skip.
**Why it happens:** `push_to_wp` checks `job.status != JobStatus.approved` at task start.
**How to avoid:** In approve endpoint, commit `job.status = JobStatus.approved` before dispatching `push_to_wp.delay()`. For quick-fix direct push, do NOT call `push_to_wp` — use inline httpx push in the quick-fix task.

### Pitfall 4: Cookie `m_pages_site_id` vs `m_errors_site_id`

**What goes wrong:** Pipeline page uses wrong cookie, getting errors site instead of pages site.
**Why it happens:** Copy-paste from errors endpoint.
**How to avoid:** Both `/m/pages` and `/m/pipeline` use `m_pages_site_id` (shared). The errors page uses `m_errors_site_id`. Do not mix them.

### Pitfall 5: HTMX `beforeend` Swap — Duplicate "Загрузить ещё" Links

**What goes wrong:** Each "Загрузить ещё" appended block includes another "Загрузить ещё" link, leading to multiple pagination links visible.
**Why it happens:** The pages_content partial includes the pagination link, and `beforeend` swaps append the whole partial.
**How to avoid:** Separate the "Загрузить ещё" link from the `pages_content` partial — the link must be rendered outside the swap target (or as a separate element that replaces itself on click). Phase 30 errors pattern uses `hx-swap="innerHTML"` on the list container, not `beforeend`. For `beforeend` pattern: the link element should have `hx-swap="outerHTML"` targeting itself, replacing itself with more rows + a new link (or nothing if no more rows).

### Pitfall 6: Bulk Task with Async schema_service

**What goes wrong:** Bulk Schema Celery task calls `await render_schema_for_page(...)` inside a sync task — `RuntimeError: no running event loop`.
**Why it happens:** Celery workers run sync tasks by default.
**How to avoid:** Use only the pure sync functions from schema_service: `select_schema_type_for_page()`, `render_schema_template()`, `generate_schema_tag()`. Load the SchemaTemplate via `get_sync_db()` + `session.execute(select(SchemaTemplate)...)` directly.

### Pitfall 7: 2-Tap Timeout Race Condition

**What goes wrong:** User taps confirm very fast — timer hasn't started yet on first tap — two taps fire as two first-taps.
**Why it happens:** `btn.dataset.ready = 'true'` is set synchronously but event propagation.
**How to avoid:** The `initTwoTapButton` pattern from UI-SPEC handles this correctly — check `btn.dataset.ready === 'true'` before acting. Copy the exact pattern from the UI-SPEC `## Interaction Contracts` section.

---

## Code Examples

### Inline Expand Pattern (from Phase 30)

```html
<!-- Source: app/templates/mobile/errors/partials/section.html -->
<div class="page-row p-3 min-h-[44px] flex items-center justify-between"
     hx-get="/m/pages/detail/{{ page.id }}"
     hx-target="closest .page-row"
     hx-swap="outerHTML">
  <span class="text-xs text-gray-500 truncate flex-1">{{ page.url }}</span>
  <div class="flex items-center gap-1">
    <!-- Status icons -->
  </div>
</div>
```

### Site Dropdown Cookie Persist (from Phase 30)

```python
# Source: app/routers/mobile.py mobile_errors()
site_id = request.query_params.get("site_id") or request.cookies.get("m_pages_site_id")
if not site_id or not any(str(s.id) == site_id for s in sites):
    site_id = str(sites[0].id)
# ... build response ...
response.set_cookie(key="m_pages_site_id", value=site_id, httponly=True, samesite="lax", max_age=86400 * 30)
```

### HTMX Polling Progress (from Phase 29 tool_progress.html)

```html
<!-- Running state — hx-trigger causes periodic re-fetch and outerHTML swap -->
<div id="bulk-progress-slot"
     hx-get="/m/pages/bulk/progress/{{ task_id }}"
     hx-trigger="every 3s"
     hx-target="this"
     hx-swap="outerHTML"
     aria-live="polite">
  <!-- spinner + progress bar -->
</div>
<!-- Done/error states omit hx-trigger so polling stops -->
```

### WP Post ID Resolution for Quick Fix

```python
# Source: pattern derived from wp_content_tasks.py
from sqlalchemy import select
from app.models.wp_content_job import WpContentJob

with get_sync_db() as db:
    result = db.execute(
        select(WpContentJob.wp_post_id)
        .where(WpContentJob.site_id == site_uuid, WpContentJob.page_url == page.url,
               WpContentJob.wp_post_id != None)
        .order_by(WpContentJob.created_at.desc())
        .limit(1)
    )
    wp_post_id = result.scalar_one_or_none()
# If wp_post_id is None: cannot push directly — return error to mobile caller
```

---

## Environment Availability

Step 2.6: SKIPPED — no external dependencies beyond project's own code. All required infrastructure (PostgreSQL, Redis, Celery, WP REST API) is already in use by Phase 26-30.

---

## Open Questions

1. **WP post_id resolution when no prior job exists**
   - What we know: Page model has no wp_post_id. Latest WpContentJob for the URL may have it.
   - What's unclear: For pages that have never had a WpContentJob, wp_post_id is unknown without WP API lookup by URL slug.
   - Recommendation: Planner should add a fallback: if no wp_post_id in job history, show error toast "Страница не связана с WordPress постом" and don't attempt push. Mark the quick fix buttons as disabled in that case. Keep scope narrow.

2. **Title/meta WP REST API field mapping**
   - What we know: `push_to_wp` only sends `{"content": ...}`. Title in WP REST API is `{"title": {"raw": "..."}}`. Meta description depends on SEO plugin (Yoast: `_yoast_wpseo_metadesc` as post meta).
   - What's unclear: Does the platform have Yoast SEO installed on target sites? Is the meta field consistent?
   - Recommendation: Planner should create a separate `push_title_meta_to_wp` helper that sends `{"title": {"raw": title}}` to the WP REST API. For meta description, use the Yoast meta key `_yoast_wpseo_metadesc` as the default (most common) with a site-level config option if needed. Alternatively, defer meta description push and only push title for MVP.

3. **Pipeline page: job grouping strategy**
   - What we know: UI-SPEC specifies flat list with 3 status tabs (awaiting_approval / pushed / failed).
   - What's unclear: Should jobs be sorted by date desc or grouped by page URL?
   - Recommendation: Flat list sorted `created_at DESC` within selected status tab. Simple and consistent with existing `list_jobs` endpoint in wp_pipeline.py.

4. **Crawl start empty state CTA**
   - What we know: `POST /m/health/{site_id}/crawl` already triggers crawl_site_task.delay().
   - What's unclear: The UI-SPEC shows `hx-post="/api/crawl/start"` — this endpoint doesn't exist. The existing route is `/m/health/{site_id}/crawl`.
   - Recommendation: Use `POST /m/health/{site_id}/crawl` for the empty-state CTA (requires site_id from dropdown), or add a new `POST /m/pages/crawl` endpoint that wraps crawl_site_task.delay(). The latter is cleaner for the pages context.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `app/models/wp_content_job.py` — WpContentJob model, JobStatus enum, all fields
- `app/models/crawl.py` — Page model, CrawlJob model, all fields
- `app/models/audit.py` — SchemaTemplate model
- `app/routers/wp_pipeline.py` — desktop approve/reject/rollback endpoints
- `app/tasks/wp_content_tasks.py` — run_content_pipeline, push_to_wp, rollback_job
- `app/services/content_pipeline.py` — all TOC/schema/diff functions (pure functions, confirmed sync)
- `app/services/schema_service.py` — render_schema_for_page (async), render_schema_template (sync), select_schema_type_for_page (sync)
- `app/routers/mobile.py` — Phase 26-30 patterns, site cookie, HTMX partials, Celery dispatch
- `app/templates/base_mobile.html` — bottom nav (4 tabs confirmed), toast JS, HTMX 2.0.3
- `app/templates/mobile/errors/partials/section.html` — inline expand pattern, count badge
- `app/templates/mobile/tools/partials/tool_progress.html` — HTMX polling progress pattern
- `app/routers/bulk.py` — bulk operations pattern (service layer, count returns)
- `.planning/phases/31-pages-app/31-UI-SPEC.md` — complete visual contract, interaction patterns
- `.planning/phases/31-pages-app/31-CONTEXT.md` — 18 decisions, canonical references

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — fixed by CLAUDE.md, all in use by Phase 26-30
- Architecture: HIGH — all patterns verified from existing mobile.py code
- Model fields: HIGH — direct inspection of all model files
- Pitfalls: HIGH — derived from actual code gaps (no wp_post_id on Page, async schema_service, push_to_wp status check)
- Open questions: MEDIUM — identified real gaps requiring planner decisions

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable stack, slow-moving codebase)
