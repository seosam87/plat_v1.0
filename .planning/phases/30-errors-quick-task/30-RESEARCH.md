# Phase 30: Errors & Quick Task — Research

**Researched:** 2026-04-12
**Domain:** Yandex Webmaster API v4, HTMX inline forms, SQLAlchemy async Postgres enum extension, Celery sync task, Jinja2 text templates, mobile FastAPI endpoints
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Only Yandex Webmaster API. 3 error types: indexing (samples), crawl (broken internal links), sanctions. Yandex Metrika excluded from MVP.
- **D-02:** Site↔host mapping via `Site.domain` ↔ `ascii_host_url` from Webmaster `/user/{user_id}/hosts/`. Cached in Redis `yandex:host_map:{user_id}` TTL 1 day. No new fields in Site model. If site not found → "Хост не привязан, проверьте верификацию в Webmaster".
- **D-03:** Hybrid: cached + manual refresh. New table `yandex_errors` in DB. `/m/errors` reads from DB. Pull-to-refresh button → Celery task `sync_yandex_errors.delay(site_id)`, progress via HTMX polling every 3s (Phase 29 pattern). No Celery Beat auto-schedule.
- **D-04:** `yandex_errors` schema: `id UUID PK`, `site_id FK→sites`, `error_type Enum(indexing/crawl/sanction)`, `subtype String(100)`, `url String(2000) nullable`, `title String(500)`, `detail Text nullable`, `detected_at DateTime`, `fetched_at DateTime`, `status Enum(open/ignored/resolved) default open`. Indexes: `(site_id, error_type)`, `(site_id, status)`.
- **D-05:** `sync_yandex_errors(site_id)` task: resolve host_id → fetch 3 error types (3 API calls) → upsert by `(site_id, error_type, subtype, url)` unique key → soft-close absent errors to `status='resolved'`. Celery retry=3.
- **D-06:** `/m/errors` = 3 sections (Индексация / Краулинг / Санкции), top-5 per section + "Показать все (N)" HTMX expand. Count-badge per section. Site dropdown persists in cookie `m_errors_site_id`.
- **D-07:** Site dropdown shows all user sites. Change → HTMX swap `#errors-content`. If host not in Webmaster → "Хост не привязан к Yandex Webmaster."
- **D-08:** ТЗ saved as `SeoTask`. TaskType enum extended: `+yandex_indexing`, `+yandex_crawl`, `+yandex_sanction`. New nullable FK `SeoTask.source_error_id → yandex_errors.id ondelete=SET NULL`.
- **D-09:** Inline HTMX expand in error row. "Составить ТЗ" → `hx-get="/m/errors/{error_id}/brief/form"` → `hx-target="closest .error-row"` outerHTML swap. Form: textarea + priority radio P1-P4 default P3 + project select nullable. POST → creates SeoTask → success block "✓ ТЗ создано — открыть".
- **D-10:** Quick task auto-fills SeoTask: `title=text[:80].strip()`, `description=text`, `url=""`, `site_id=Project.site_id`, `task_type=manual`, `project_id=user selected (required)`. 422 if `Project.site_id is null`.
- **D-11:** ТЗ копирайтеру: textarea `keywords` + `tone` select + `length` select + `project` select (required) + `recipient` select (clients with email OR telegram_username NOT NULL, nullable). Renders `app/templates/briefs/copywriter_brief.txt.j2`. Saves SeoTask. If recipient → sends via Telegram (inline text <4000 chars, else .txt attachment) or email (plain text body). Success: showToast + redirect `/m/`.
- **D-12:** Mode toggle on `/m/tasks/new`: [Задача] [ТЗ копирайтеру]. Active tab persisted in `?mode=task|brief` query-param. Toggle → `hx-get="/m/tasks/new/form?mode={mode}"` → `hx-target="#task-form"` innerHTML. JS `history.pushState` syncs URL.

### Claude's Discretion

- Jinja2 template exact placeholder structure for copywriter brief (5 required: project_name, site_url, length, tone, keywords list)
- HTMX inline form HTML markup structure for row-swap partial
- Empty state copywriting ("Нет ошибок", "Нет задач", "Нет клиентов с контактами")
- Error section icons from Heroicons: `document-magnifying-glass` (indexing), `arrow-path` (crawl), `shield-exclamation` (sanction)
- Priority radio UI: 4 pills with color (P1 red / P2 orange / P3 gray / P4 blue)

### Deferred Ideas (OUT OF SCOPE)

- Yandex Metrika errors
- Celery Beat auto-schedule for `sync_yandex_errors`
- `Site.yandex_host_id` new field + desktop UI
- Separate `Brief` or `QuickTask` models
- Reusing Celery brief-tool from Phase 29 for TSK-02
- Desktop `/ui/errors`
- Assignee field in quick task
- Bulk error actions
- Multi-site aggregated view
- Error filtering/search inside section
- PDF rendering for copywriter brief
- Error notifications after sync
- "Ignore" / "Resolve" buttons in UI
- Error status change audit log
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ERR-01 | Пользователь видит ошибки из Yandex Webmaster API (индексация, краулинг, санкции) | API endpoints identified: indexing/samples + links/internal/broken/samples + host summary. DB schema in D-04. Upsert pattern in D-05. |
| ERR-02 | Пользователь может составить ТЗ на исправление ошибки прямо из списка | Inline HTMX expand pattern (D-09). SeoTask extension with source_error_id FK (D-08). Alembic migration for enum + FK. |
| TSK-01 | Пользователь может быстро добавить задачу в проект с телефона (текст + приоритет) | Auto-fill SeoTask pattern (D-10). `/m/tasks/new?mode=task`. 3-field form. |
| TSK-02 | Пользователь может создать ТЗ копирайтеру из данных аналитики и отправить в TG/email | Jinja2 txt template + Phase 29 Telegram/email helpers (D-11). `/m/tasks/new?mode=brief`. |
</phase_requirements>

---

## Summary

Phase 30 extends the mobile SEO platform with two surfaces: an errors dashboard (`/m/errors`) pulling data from Yandex Webmaster API, and a quick task creator (`/m/tasks/new`). Both surfaces are fully mobile, built with the established Jinja2+HTMX+Tailwind pattern from Phase 29. No new frontend frameworks are introduced.

The most technically significant work is the Yandex Webmaster API integration for errors. The API exposes three relevant resource families: **indexing samples** (`/indexing/samples?status=HTTP_4XX&HTTP_5XX&OTHER`), **broken internal links** (`/links/internal/broken/samples`), and **sanctions** (covered via `/summary` host statistics — the API does not expose a dedicated sanctions endpoint). Research reveals an important architectural gap: no standalone "sanctions endpoint" exists in Yandex Webmaster API v4. Sanctions are surfaced only through the `site_problems` field in the summary endpoint with severity levels FATAL/CRITICAL. The planner must decide how to handle this gracefully (either show FATAL/CRITICAL problems as "sanctions" or label the section "Проблемы сайта" for MVP accuracy).

The database work (new `yandex_errors` table + Alembic migration + PostgreSQL enum extension for `tasktype`) follows established patterns from migrations 0007 and 0030. The Celery task pattern is well-established in `suggest_tasks.py`. The inline HTMX form expand (outerHTML swap on `.error-row`) is a new pattern but straightforward given existing HTMX usage in the codebase. The Client model uses `email` field on `Client` directly — the TSK-02 recipient filter needs `Client.email IS NOT NULL OR` checking `ClientContact.telegram_username IS NOT NULL` (different tables — see pitfall below).

**Primary recommendation:** Build in the order DB schema → Celery task → service layer → router endpoints → templates. The "sanctions" section should use `site_problems` FATAL/CRITICAL data from `/user/{user_id}/hosts/{host_id}/summary` for MVP rather than a non-existent dedicated endpoint.

---

## Standard Stack

All libraries are already installed in the project. No new packages needed for Phase 30.

### Core (already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.x | ASGI router for new `/m/errors` and `/m/tasks/new` endpoints | Project constraint — locked |
| SQLAlchemy 2.0 async | 2.0.30+ | `yandex_errors` table, SeoTask upsert, async queries | Project constraint — locked |
| Alembic | 1.13.x | Migration 0055: new table + enum extension | Project constraint — locked |
| Celery 5.4 | 5.4.x | `sync_yandex_errors` task, retry=3 | Project constraint — locked |
| httpx | 0.27.x | Yandex Webmaster API calls inside Celery task | Project constraint — locked |
| Redis (redis-py 5.x) | 5.0.x | Host map cache `yandex:host_map:{user_id}` TTL 1d | Project constraint — locked |
| Jinja2 | 3.1.x | Error templates, copywriter brief text rendering | Project constraint — locked |
| HTMX | 2.0.x | Polling, inline swap, mode toggle | Project constraint — locked |
| loguru | 0.7.x | Structured logging in service and task | Project constraint — locked |

### No New Installations Required

All dependencies are already present. Phase 30 is pure extension of existing code.

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
app/
├── models/
│   └── yandex_errors.py              # YandexError model + ErrorType/ErrorStatus enums
├── tasks/
│   └── yandex_errors_tasks.py        # sync_yandex_errors Celery task
├── services/
│   └── yandex_errors_service.py      # DB read helpers (list_errors, get_error)
│   └── mobile_brief_service.py       # Copywriter brief render + send helpers (TSK-02)
├── templates/
│   ├── mobile/
│   │   ├── errors/
│   │   │   ├── index.html            # /m/errors page
│   │   │   ├── partials/
│   │   │   │   ├── errors_content.html     # #errors-content swap target (3 sections)
│   │   │   │   ├── section.html            # single error section with rows
│   │   │   │   ├── brief_form.html         # inline brief form (outerHTML swap)
│   │   │   │   ├── brief_result.html       # success confirmation block
│   │   │   │   └── sync_progress.html      # polling partial (same as tool_progress.html)
│   │   └── tasks/
│   │       ├── new.html                    # /m/tasks/new page with toggle
│   │       └── partials/
│   │           ├── task_form.html          # mode=task form fields
│   │           └── brief_form.html         # mode=brief form fields
│   └── briefs/
│       └── copywriter_brief.txt.j2         # TSK-02 text template
alembic/versions/
└── 0055_add_yandex_errors.py         # new table + enum extensions
```

### Pattern 1: Postgres Enum Extension via Alembic

**What:** Adding new values to an existing PostgreSQL `ENUM` type requires `ALTER TYPE ... ADD VALUE` (cannot use `op.alter_column`).
**When to use:** Phase 30 extends `tasktype` enum with `yandex_indexing`, `yandex_crawl`, `yandex_sanction`.

```python
# Source: verified from existing alembic/versions/0030_add_priority_to_seo_tasks.py pattern
def upgrade() -> None:
    # Step 1: Add new values to tasktype enum
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_indexing'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_crawl'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_sanction'")

    # Step 2: Add source_error_id FK to seo_tasks
    op.add_column(
        "seo_tasks",
        sa.Column(
            "source_error_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("yandex_errors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
```

**Critical:** `ALTER TYPE ... ADD VALUE` is NOT transactional in PostgreSQL. It cannot be run inside a transaction block. Alembic must use `op.execute()` after disabling autocommit, or use the `with op.get_context().autocommit_block()` pattern. Use `IF NOT EXISTS` for safety on re-run.

### Pattern 2: Upsert (INSERT ... ON CONFLICT) for yandex_errors

**What:** Sync task must not create duplicate rows when same error reappears across syncs.
**Unique key:** `(site_id, error_type, subtype, url)` — combined business identity of an error.

```python
# Source: SQLAlchemy 2.0 async insert + on_conflict_do_update pattern
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(YandexError).values(**error_data)
stmt = stmt.on_conflict_do_update(
    index_elements=["site_id", "error_type", "subtype", "url"],
    set_={
        "fetched_at": stmt.excluded.fetched_at,
        "detail": stmt.excluded.detail,
        # Do NOT update status — preserve user changes (ignored/resolved)
        # EXCEPT for soft-close logic handled separately
    },
)
await db.execute(stmt)
```

Note: `url` can be NULL for sanctions. PostgreSQL unique constraints treat NULLs as distinct, so `(site_id, 'sanction', 'adult_content', NULL)` will create a new row each sync. Use a sentinel empty string `""` for sanctions url or handle deduplication in Python before upsert.

### Pattern 3: HTMX Inline outerHTML Swap (new for Phase 30)

**What:** Clicking "Составить ТЗ" expands the error row into a form, preserving scroll position.
**When to use:** ERR-02 flow. The `.error-row` div becomes the swap target.

```html
<!-- Source: CONTEXT.md D-09, HTMX 2.0 docs -->
<div class="error-row p-3 min-h-[44px] flex items-center justify-between">
  <div class="flex-1">
    <span class="text-sm truncate">{{ error.title }}</span>
    {% if error.url %}
    <span class="text-xs text-gray-400 truncate block">{{ error.url }}</span>
    {% endif %}
  </div>
  <button
    hx-get="/m/errors/{{ error.id }}/brief/form"
    hx-target="closest .error-row"
    hx-swap="outerHTML"
    class="text-xs font-semibold text-indigo-600 underline min-h-[44px] px-2 flex items-center">
    Составить ТЗ
  </button>
</div>
```

The partial returned by `GET /m/errors/{error_id}/brief/form` must include `hx-post` on the form element targeting `this` (the form itself), with `hx-swap="outerHTML"` to replace the form with the success block on POST.

### Pattern 4: Celery Sync Task with Redis Host Cache

**What:** `sync_yandex_errors` runs in Celery (synchronous context), uses `get_sync_db()` and `sync_redis`.
**Reference:** `app/tasks/suggest_tasks.py` — exact pattern for `redis.from_url` + `get_sync_db`.

```python
# Source: suggest_tasks.py pattern, adapted for yandex_errors_tasks.py
@celery_app.task(
    name="app.tasks.yandex_errors_tasks.sync_yandex_errors",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def sync_yandex_errors(self, site_id: str, user_id: str) -> dict:
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)

    # 1. Resolve host_id from Redis cache or API call
    cache_key = f"yandex:host_map:{user_id}"
    host_map = r.get(cache_key)
    if host_map:
        host_map = json.loads(host_map)
    else:
        # run_sync(get_user_id()) — use asyncio.run() or equivalent
        ...

    # 2. Fetch 3 error types synchronously (httpx sync client)
    # 3. Upsert via get_sync_db()
    # 4. Soft-close absent errors
```

**Note:** `yandex_webmaster_service.py` uses async httpx. Inside Celery tasks, use `httpx.Client` (sync) or wrap async calls with `asyncio.run()`. The existing pattern in other tasks uses `asyncio.run()` sparingly; prefer creating sync wrappers in the service for these 3 new API functions.

### Pattern 5: Redis Host Map Cache

**What:** Avoid fetching host list from Webmaster API on every error page load.
**Key format:** `yandex:host_map:{user_id}` → JSON dict `{domain: host_id}` TTL 86400s.

```python
# Source: CONTEXT.md D-02
import json
CACHE_KEY = "yandex:host_map:{user_id}"
TTL = 86400  # 1 day

# Write (in Celery task, sync redis):
r.set(cache_key, json.dumps(host_map), ex=TTL)

# Read (in FastAPI endpoint, async redis):
raw = await r.get(cache_key)
host_map = json.loads(raw) if raw else None
```

### Pattern 6: Jinja2 Text Template Render

**What:** Render `copywriter_brief.txt.j2` to a plain-text string in a FastAPI endpoint.
**When:** TSK-02 mode=brief form submission.

```python
# Source: Jinja2 3.1.x docs — template rendering to string
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("app/templates"))
tmpl = env.get_template("briefs/copywriter_brief.txt.j2")
rendered = tmpl.render(
    project_name=project.name,
    site_url=site.domain,
    length=length_str,
    tone=tone_str,
    keywords=[k.strip() for k in keywords_raw.split("\n") if k.strip()],
)
```

Note: Use `Environment` directly (not `Jinja2Templates`) to render to string, not to HTTP response.

### Anti-Patterns to Avoid

- **Using `op.create_table` for enum extension:** Cannot drop and re-create `tasktype` — existing rows reference it. Use `ALTER TYPE ... ADD VALUE IF NOT EXISTS` only.
- **Blocking async loop in FastAPI endpoints:** Do not call `asyncio.run()` inside an `async def` endpoint. All DB and Redis operations must use `await`.
- **NULL in unique constraint for url:** PostgreSQL treats `NULL != NULL` in unique indexes — two rows with `url=NULL` for the same `(site_id, error_type, subtype)` are NOT considered duplicates. Use `""` (empty string) as sentinel for sanctions.
- **Loading full host list on every request:** Always check Redis cache before calling Webmaster API.
- **Inline Jinja2 rendering via `mobile_templates.TemplateResponse` for text:** Use `jinja2.Environment` directly when you need a string (for Telegram/email send), not a Response.
- **Using `hx-swap="innerHTML"` instead of `outerHTML` for error row swap:** innerHTML would insert the form inside the row div, not replace it — breaking the layout.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Redis host map caching | Custom TTL dict | `r.set(key, val, ex=86400)` | Built-in Redis TTL |
| Upsert logic | Python IF-EXISTS-UPDATE | `pg_insert().on_conflict_do_update()` | Atomic, race-condition-safe |
| Text template rendering | Python string concatenation | `jinja2.Environment().get_template()` | Already installed, handles escaping |
| Telegram message send | Custom httpx bot calls | Phase 29 helpers in `mobile_reports_service.py` / notification services | Tested pattern already in codebase |
| HTMX progress polling | WebSockets or SSE | `hx-trigger="every 3s" hx-swap="outerHTML"` | Already established in Phase 29 tool_progress.html |
| Cookie persistence | JS localStorage | FastAPI `response.set_cookie()` on site select | HttpOnly, survives page reload |

**Key insight:** Phase 30 is almost entirely wiring together existing building blocks. The only genuinely new code is the Yandex error API calls and the `yandex_errors` table.

---

## Yandex Webmaster API — Verified Endpoints

### Indexing Errors (HTTP_4XX + HTTP_5XX + OTHER)

```
GET https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/indexing/samples
    ?status=HTTP_4XX&status=HTTP_5XX&status=OTHER
    &limit=100&offset=0
```

**Response:**
```json
{
  "count": 42,
  "samples": [
    {
      "status": "HTTP_4XX",
      "http_code": 404,
      "url": "https://example.com/old-page",
      "access_date": "2026-03-01T12:00:00Z"
    }
  ]
}
```

**Confidence:** MEDIUM — endpoint URL verified via official docs. Status filter values (`HTTP_4XX`, `HTTP_5XX`, `OTHER`) verified via docs. MEDIUM not HIGH because live testing not performed.

### Crawl Errors (Broken Internal Links)

```
GET https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/links/internal/broken/samples
    ?indicator=SITE_ERROR&indicator=DISALLOWED_BY_USER&indicator=UNSUPPORTED_BY_ROBOT
    &limit=100&offset=0
```

**Response:**
```json
{
  "count": 18,
  "links": [
    {
      "source_url": "https://example.com/page",
      "destination_url": "https://example.com/broken",
      "discovery_date": "2026-03-10",
      "source_last_access_date": "2026-03-15"
    }
  ]
}
```

**Available indicators:**
- `SITE_ERROR` — page returns error response
- `DISALLOWED_BY_USER` — page forbidden by robots.txt or noindex
- `UNSUPPORTED_BY_ROBOT` — unsupported content type

**Confidence:** HIGH — endpoint URL and response structure confirmed from official Yandex docs.

### "Sanctions" — IMPORTANT FINDING

**No dedicated sanctions API endpoint exists in Yandex Webmaster API v4.** The CONTEXT.md decision D-01 assumes a sanctions endpoint exists. Research shows the closest available data is `site_problems` from the summary endpoint:

```
GET https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/summary
```

**Response includes:**
```json
{
  "sqi": 75,
  "excluded_pages_count": 12,
  "searchable_pages_count": 450,
  "site_problems": {
    "FATAL": 2,
    "CRITICAL": 5,
    "POSSIBLE_PROBLEM": 8,
    "RECOMMENDATION": 3
  }
}
```

`FATAL` severity in `site_problems` maps to "security and compliance with Yandex guidelines" violations — the closest proxy to sanctions.

**Recommendation for planner:** The "Санкции" section should use FATAL + CRITICAL site_problems counts from the summary endpoint. Since the summary returns counts (not URLs or details), the section can display: count of FATAL/CRITICAL problems with a note "Проверьте раздел Безопасность в Yandex Webmaster". Alternatively, rename the section "Проблемы сайта" and show FATAL/CRITICAL. The `yandex_errors` table still stores these as `error_type='sanction'` with `url=NULL`, `title` = problem severity label, `subtype` = severity level string.

**Confidence:** MEDIUM — confirmed from official docs that no dedicated sanctions endpoint exists. Summary endpoint fields confirmed. How Yandex populates `site_problems` severity categories internally is not fully documented.

---

## Runtime State Inventory

Phase 30 is not a rename/refactor phase. No runtime state migration required.

Step 2.5: SKIPPED — greenfield feature addition, no strings being renamed.

---

## Environment Availability

All Phase 30 dependencies are already running in the project environment.

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| Yandex Webmaster token | `yandex_webmaster_service.py` `is_configured()` | Conditionally | Must be set in `settings.YANDEX_WEBMASTER_TOKEN`. If not configured, sync task returns error gracefully. |
| Redis | Host map cache, Celery broker | ✓ | Running as part of Docker Compose |
| PostgreSQL | `yandex_errors` table | ✓ | Running, Alembic migrations applied |
| Celery worker | `sync_yandex_errors` task | ✓ | Worker running, `default` queue |

**Missing dependencies with no fallback:**
- None — all infra dependencies running

**Conditional dependency:**
- `YANDEX_WEBMASTER_TOKEN` — if not configured, `/m/errors/sync` endpoint should return a toast "Yandex Webmaster не настроен. Добавьте токен в настройках." rather than 500.

---

## Common Pitfalls

### Pitfall 1: PostgreSQL Enum Extension Not Transactional

**What goes wrong:** `ALTER TYPE tasktype ADD VALUE 'yandex_indexing'` fails with "ALTER TYPE ... ADD VALUE cannot run inside a transaction block" during Alembic migration.
**Why it happens:** Alembic runs migrations inside a transaction by default. PostgreSQL does not allow adding enum values inside transactions.
**How to avoid:** Wrap the `ALTER TYPE` calls in `op.execute()` AFTER setting `connection.execution_options(isolation_level="AUTOCOMMIT")`, OR use Alembic's `with op.get_context().autocommit_block():` context manager (Alembic 1.13+).

```python
# Correct pattern in Alembic migration:
def upgrade() -> None:
    op.execute("COMMIT")  # end current transaction
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_indexing'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_crawl'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_sanction'")
    # Then create new table (starts new implicit transaction)
```

**Warning signs:** Migration fails with `ProgrammingError: ALTER TYPE ... cannot run inside a transaction block`.

### Pitfall 2: NULL in Composite Unique Key for Sanctions

**What goes wrong:** Each sync creates a new "sanction" row instead of upserting, because `url=NULL` breaks the unique constraint — PostgreSQL treats `NULL != NULL`.
**Why it happens:** `(site_id, error_type, subtype, NULL)` will never match existing `(site_id, error_type, subtype, NULL)` in a unique index.
**How to avoid:** Store sanctions with `url=""` (empty string) not NULL. Adjust the migration to make `url` NOT NULL with a default of `""`, or handle in application code before upsert by replacing `None` with `""` for sanctions.

**Warning signs:** `yandex_errors` grows unboundedly for sanction-type errors across multiple syncs.

### Pitfall 3: HTMX `hx-target="closest .error-row"` Requires Class on Parent

**What goes wrong:** HTMX cannot find `closest .error-row` if the button is not inside an element with class `error-row`.
**Why it happens:** The `closest` CSS selector walks up the DOM tree; if the class is not present on any ancestor, the target is `null` and HTMX does nothing.
**How to avoid:** Ensure every error item `<div>` has class `error-row`. The Jinja2 template loop must render `<div class="error-row ...">` not just `<div class="...">`.

**Warning signs:** "Составить ТЗ" click does nothing — no HTMX request fires in DevTools.

### Pitfall 4: Client Model Has No `telegram_username`

**What goes wrong:** TSK-02 recipient filter `email IS NOT NULL OR telegram_username IS NOT NULL` fails because `telegram_username` is on `ClientContact`, not `Client`.
**Why it happens:** `Client` model has only `email` field. `telegram_username` lives on `ClientContact` (contact persons). Phase 29's `list_clients_for_reports` filters by `Client.email IS NOT NULL` only.
**How to avoid:** For TSK-02 recipient select, filter by `Client.email IS NOT NULL` (matching Phase 29 pattern). The `telegram_username` filter from CONTEXT.md D-05 refers to client-level telegram, but this field does not exist on `Client`. Either: (a) use `Client.email IS NOT NULL` only for simplicity, or (b) check if any `ClientContact` for this client has `telegram_username IS NOT NULL` via subquery. Option (a) is simpler and safer for MVP.

**Warning signs:** `AttributeError: 'Client' object has no attribute 'telegram_username'` at query build time.

### Pitfall 5: Celery Task Needs user_id to Resolve Host Map

**What goes wrong:** `sync_yandex_errors(site_id)` cannot call `get_user_id()` without the Yandex Webmaster token — but the task also needs the Yandex `user_id` (not the platform user id) to query the host list.
**Why it happens:** The Yandex API requires `user_id` (obtained from `GET /v4/user/`) in every URL path. This is different from the platform's internal user UUID.
**How to avoid:** Either (a) pass `yandex_user_id` as a task argument (caller looks it up before enqueuing), or (b) resolve it inside the task — call `get_user_id()` if not cached in Redis. Pattern (b) is self-contained but adds one more API call. The existing service `get_user_id()` is async; in Celery use `asyncio.run(get_user_id())` or a sync wrapper.

**Warning signs:** `KeyError` on host map lookup, or 403 from Webmaster API ("INVALID_USER_ID").

### Pitfall 6: `history.pushState` and HTMX Back-Navigation

**What goes wrong:** User switches from `?mode=brief` to `?mode=task` via HTMX swap, then presses browser Back — URL reverts but form does not. The page shows stale mode=brief content with `?mode=task` in URL.
**Why it happens:** HTMX swaps DOM without navigating; `history.pushState` updates URL but not the full page state.
**How to avoid:** On the server, `GET /m/tasks/new` must inspect `?mode=` param and render the correct initial form. The JS `history.pushState` call should run after the HTMX swap (`htmx:afterSwap` event). This is a cosmetic issue for MVP — browser Back goes to full page reload which re-reads `?mode=` from URL correctly.

**Warning signs:** Browser Back shows wrong form mode after HTMX toggle.

---

## Code Examples

### 1. YandexError Model (new file `app/models/yandex_errors.py`)

```python
# Source: existing app/models/task.py pattern + CONTEXT.md D-04
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class YandexErrorType(str, PyEnum):
    indexing = "indexing"
    crawl = "crawl"
    sanction = "sanction"


class YandexErrorStatus(str, PyEnum):
    open = "open"
    ignored = "ignored"
    resolved = "resolved"


class YandexError(Base):
    __tablename__ = "yandex_errors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    error_type: Mapped[YandexErrorType] = mapped_column(SAEnum(YandexErrorType, name="yandex_error_type"), nullable=False)
    subtype: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(2000), nullable=False, default="")  # "" for sanctions
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[YandexErrorStatus] = mapped_column(SAEnum(YandexErrorStatus, name="yandex_error_status"), nullable=False, default=YandexErrorStatus.open)
```

### 2. TaskType Enum Extension in `app/models/task.py`

```python
# Source: CONTEXT.md D-08 — extend existing enum
class TaskType(str, PyEnum):
    page_404 = "page_404"
    lost_indexation = "lost_indexation"
    missing_page = "missing_page"
    cannibalization = "cannibalization"
    manual = "manual"
    yandex_indexing = "yandex_indexing"   # NEW — Phase 30
    yandex_crawl = "yandex_crawl"         # NEW — Phase 30
    yandex_sanction = "yandex_sanction"   # NEW — Phase 30
```

The Python enum change alone is not enough — the Postgres `tasktype` type must also be altered via migration 0055.

### 3. SeoTask source_error_id FK (addition to `app/models/task.py`)

```python
# Source: CONTEXT.md D-08 — add nullable FK to SeoTask
source_error_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("yandex_errors.id", ondelete="SET NULL"),
    nullable=True,
)
```

### 4. Copywriter Brief Template (`app/templates/briefs/copywriter_brief.txt.j2`)

```jinja2
# ТЗ копирайтеру

**Проект:** {{ project_name }}
**Сайт:** {{ site_url }}
**Объём:** {{ length }} слов
**Tone of voice:** {{ tone }}

## Ключевые слова

{% for kw in keywords %}
- {{ kw }}
{% endfor %}

## Требования к тексту

- Статья должна отвечать на поисковый запрос пользователя
- Используйте ключевые слова органично, без переспама
- Структура: заголовок H1, подзаголовки H2/H3, список или таблица где уместно
- Объём: не менее {{ length }} слов в основном тексте
- Tone of voice: {{ tone }}
- Уникальность: минимум 90% по Текст.ру
- Изображения: не требуются (добавляет редактор)

## Дополнительные пожелания

[Добавьте здесь специфические требования для данного проекта]
```

### 5. Alembic Migration 0055 Structure

```python
# Source: alembic/versions/0030_add_priority_to_seo_tasks.py pattern

def upgrade() -> None:
    # 1. Create new enum types for yandex_errors table
    op.execute("DO $$ BEGIN CREATE TYPE yandex_error_type AS ENUM ('indexing', 'crawl', 'sanction'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE yandex_error_status AS ENUM ('open', 'ignored', 'resolved'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # 2. Create yandex_errors table
    op.create_table("yandex_errors", ...)
    op.create_index("ix_yandex_errors_site_id_type", "yandex_errors", ["site_id", "error_type"])
    op.create_index("ix_yandex_errors_site_id_status", "yandex_errors", ["site_id", "status"])
    op.create_unique_constraint("uq_yandex_errors_identity", "yandex_errors", ["site_id", "error_type", "subtype", "url"])

    # 3. Extend tasktype enum (NOT in transaction)
    op.execute("COMMIT")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_indexing'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_crawl'")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_sanction'")
    op.execute("BEGIN")

    # 4. Add source_error_id FK to seo_tasks
    op.add_column("seo_tasks", sa.Column("source_error_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("yandex_errors.id", ondelete="SET NULL"), nullable=True))
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `op.create_type()` + `op.alter_column()` for enum extension | `ALTER TYPE ... ADD VALUE IF NOT EXISTS` with COMMIT/BEGIN wrapper | Required — no other way in Postgres |
| Separate `Brief` model for copywriter briefs | `SeoTask` with `task_type=manual` + extended description | Simpler, fewer tables, established in CONTEXT.md |
| HTMX swap of entire section for row action | `hx-target="closest .error-row" hx-swap="outerHTML"` | Preserves scroll position, minimal DOM mutation |
| Blocking Redis `hmset` | `r.set(key, json.dumps(val), ex=TTL)` string value | Single key, JSON-serialized dict is simpler than hash for this use case |

---

## Open Questions

1. **Sanctions endpoint — confirmed absent**
   - What we know: No dedicated sanctions endpoint in Yandex Webmaster API v4. `site_problems` from `/summary` gives FATAL/CRITICAL counts without URL details.
   - What's unclear: Whether planner wants to (a) show count-only sanction section using summary, or (b) rename section to "Проблемы сайта", or (c) leave "Санкции" section but show "Нет данных от API — проверьте Webmaster вручную".
   - Recommendation: Use option (a) for MVP — show FATAL count from `/summary` as "sanction" rows with `url=""`, `subtype="fatal_problem"`, `title="FATAL: {count} критических проблем"`. This is honest and matches the UX decisions already in CONTEXT.md.

2. **TSK-02 recipient `telegram_username` filter**
   - What we know: `Client` model has no `telegram_username` field. `ClientContact` has it.
   - What's unclear: Whether planner wants to filter by `ClientContact.telegram_username IS NOT NULL` (requires JOIN) or just `Client.email IS NOT NULL` (simpler, matching Phase 29 pattern).
   - Recommendation: Use `Client.email IS NOT NULL` only for Phase 30 MVP. The CONTEXT.md D-05 filter is correctly achievable only with a subquery on `ClientContact`, which adds complexity. Document the simplification.

3. **`sync_yandex_errors` task signature — user_id argument**
   - What we know: Yandex API requires the Yandex `user_id` (from `GET /v4/user/`) in every URL path. This is not the platform's UUID.
   - What's unclear: Should the caller pass `yandex_user_id` to the task, or should the task resolve it internally?
   - Recommendation: Task resolves internally — call `asyncio.run(get_user_id())` on first invocation, cache result in Redis key `yandex:user_id` with long TTL (7 days). Keeps task signature simple: `sync_yandex_errors.delay(str(site_id))`.

4. **Bottom nav restructure for v4.0**
   - What we know: `base_mobile.html` has 4 tabs (Дайджест, Сайты, Позиции, Ещё). Adding "Ошибки" requires a 5th tab or replacing "Ещё".
   - What's unclear: Final nav structure for v4.0 with all Phase 28-30 features.
   - Recommendation: Replace "Ещё" button with "Ошибки" tab linking to `/m/errors`, since "Ещё" currently has no destination. Phase 32 (Telegram Bot) can revisit nav structure if needed.

---

## Sources

### Primary (HIGH confidence)
- Yandex Webmaster API v4 docs — broken internal links endpoint confirmed: `GET /user/{user_id}/hosts/{host_id}/links/internal/broken/samples`, response fields `count`, `links[]` with `source_url`, `destination_url`, `discovery_date` — https://yandex.com/dev/webmaster/doc/en/reference/host-links-internal-samples
- Yandex Webmaster API v4 docs — indexing samples endpoint confirmed: `GET /user/{user_id}/hosts/{host_id}/indexing/samples`, status enum `HTTP_2XX/3XX/4XX/5XX/OTHER` — https://yandex.com/dev/webmaster/doc/en/reference/hosts-indexing-samples
- CONTEXT.md (Phase 30) — all decisions D-01 through D-12, canonical_refs, code_context sections
- Existing codebase: `app/services/yandex_webmaster_service.py`, `app/models/task.py`, `app/tasks/suggest_tasks.py`, `alembic/versions/0030_add_priority_to_seo_tasks.py`, `app/templates/mobile/tools/partials/tool_progress.html`, `app/templates/base_mobile.html`

### Secondary (MEDIUM confidence)
- Yandex Webmaster API v4 — summary endpoint response structure with `site_problems` severity levels — https://yandex.com/dev/webmaster/doc/en/reference/host-id-summary
- Yandex Webmaster API v4 resources overview confirming no dedicated sanctions endpoint — https://yandex.com/dev/webmaster/doc/en/concepts/getting-started

### Tertiary (LOW confidence)
- PostgreSQL enum extension behavior (COMMIT/BEGIN wrapper) — from SQLAlchemy/Alembic community knowledge, not official Alembic docs page (docs confirm ALTER TYPE limitation exists; exact workaround pattern from prior project migrations in codebase at 0030)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed already installed in project
- Architecture patterns: HIGH — all patterns derived from existing codebase code
- Yandex API (indexing + crawl): MEDIUM — endpoint URLs and response shapes verified via official docs, not live-tested
- Yandex API (sanctions): MEDIUM — confirmed no dedicated endpoint exists; summary-based approach is research finding
- Alembic enum extension: HIGH — confirmed from existing migration 0030 pattern in codebase
- Client model Telegram field: HIGH — confirmed by reading Client model directly

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days — stable APIs)
