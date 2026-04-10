# Phase 27: Digest & Site Health - Research

**Researched:** 2026-04-10
**Domain:** FastAPI + HTMX mobile pages, async service layer, Celery task dispatch, SQLAlchemy async queries
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Block order in digest: Позиции → Ошибки краулера → Алерты → Просроченные задачи.
- **D-02:** TOP-5 items per block.
- **D-05:** Health card has 6 metric blocks: (1) Доступность сайта (HTTP-статус), (2) Свежие ошибки краулера (количество), (3) Статус последнего краулинга (дата + результат), (4) Резкие изменения позиций (дельта за 7 дней), (5) Просроченные задачи (количество), (6) Статус индексации (данные GSC/Yandex если есть).
- **D-06:** Visual: вертикальный список с иконками статуса (зелёный/жёлтый/красный).
- **D-08:** Task creation inline: нажатие раскрывает 2-3 поля (текст предзаполнен из ошибки, приоритет, проект). Кнопка «Сохранить» отправляет и показывает тост.

### Claude's Discretion
- **D-03:** Digest data source architecture — choose between new `mobile_digest_service.py`, extending `morning_digest_service.py`, or another approach.
- **D-04:** Deep link strategy — `/m/` if page exists, `/ui/` desktop fallback until Phases 28–31.
- **D-07:** API approach for health card actions (HTMX inline vs fetch API vs hybrid).

### Deferred Ideas (OUT OF SCOPE)
- Push notifications / Telegram digest replacement
- Dedicated mobile pages for positions, errors, tasks (Phases 28–31)
- Weekly digest UI
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIG-01 | Пользователь видит утреннюю сводку: ТОП изменения позиций, новые ошибки краулера, сработавшие алерты, просроченные задачи | `mobile_digest_service.py` (new) aggregates data from `KeywordPosition`, `Page`, `ChangeAlert`, `SeoTask` models |
| DIG-02 | Из дайджеста можно перейти к проблеме одним тапом | Deep link pattern: `/ui/` desktop URLs as fallback until Phase 28–31 mobile pages exist |
| HLT-01 | Пользователь видит карточку здоровья сайта: доступность, свежие ошибки, статус краулинга, резкие изменения позиций | New `MobileHealthService` with 6 async queries; extends approach from `compute_site_health()` |
| HLT-02 | Пользователь может запустить краулинг или поставить задачу на ошибку с этой карточки | HTMX POST to `/m/health/{site_id}/crawl` + inline task form with `hx-swap="outerHTML"` on the button |
</phase_requirements>

---

## Summary

Phase 27 builds two mobile read-mostly pages on top of the Phase 26 foundation (`base_mobile.html`, `/m/` router, HTMX 2.0.3, Tailwind CDN). The digest page aggregates cross-site data from four existing data sources into a single compact screen. The health card is per-site and adds two write actions (trigger crawl, create task inline).

The key architectural challenge is that `morning_digest_service.py` uses a sync SQLAlchemy session (for Celery), but FastAPI mobile routes require async. The correct approach is a new `app/services/mobile_digest_service.py` with async methods that re-implement the queries using `AsyncSession`. This avoids a sync/async session mixing bug that would silently block the event loop.

For health card actions, HTMX is the right choice over raw fetch because the toast infrastructure in `base_mobile.html` already wires `htmx:responseError` to `showToast()`, and the OOB swap pattern (`hx-swap-oob`) is the established pattern for server-driven toasts in this stack.

**Primary recommendation:** New `mobile_digest_service.py` (async-only), new endpoints in `mobile.py` router, HTMX for both actions on health card using existing toast infrastructure.

---

## Standard Stack

### Core (fixed by CLAUDE.md — no substitutions)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.x | Route handlers for `/m/digest`, `/m/health/{site_id}` | Fixed stack |
| SQLAlchemy | 2.0.x async | `AsyncSession` queries for digest and health data | Fixed stack |
| Jinja2 | 3.1.x | `mobile_templates.TemplateResponse()` — same pattern as existing mobile routes | Fixed stack |
| HTMX | 2.0.3 | Inline form expansion, crawl trigger, OOB toast swap | Already loaded in `base_mobile.html` |
| Tailwind CSS | CDN | Styling — already loaded in `base_mobile.html` | Fixed stack |
| Celery | 5.4.x | `crawl_site.delay()` for triggering crawl from health card | Fixed stack |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| loguru | 0.7.x | Structured logging in new service | Always — project-wide |
| python-jose | 3.3.x | JWT auth — inherited from existing `Depends(get_current_user)` | Already wired |

---

## Architecture Patterns

### Recommended Project Structure (new files only)
```
app/
├── services/
│   └── mobile_digest_service.py   # NEW — async digest + health queries
├── routers/
│   └── mobile.py                   # EXTEND — add /digest, /health/{id} routes + action endpoints
└── templates/mobile/
    ├── digest.html                 # NEW — extends base_mobile.html
    └── health.html                 # NEW — extends base_mobile.html
```

No new models. No Alembic migration needed. No new Celery tasks — reuse `crawl_site`.

### Pattern 1: Async Digest Service (D-03 resolution)

**Recommendation:** Create `app/services/mobile_digest_service.py` as a standalone async service.

**Why not extend `morning_digest_service.py`:** It uses `Session` (sync), runs inside Celery, and returns Telegram HTML. Adding async methods to it would create a confusing dual-session contract. SQLAlchemy async and sync sessions must never be mixed in the same call stack.

**Why not extend `digest_service.py`:** It is site-scoped (single `site_id` per call), while the digest page needs cross-site aggregation.

**Data queries needed:**
```python
# Source: SQLAlchemy 2.0 async docs — AsyncSession pattern
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timezone, timedelta

async def get_top_position_changes(db: AsyncSession, limit: int = 5) -> list[dict]:
    """TOP-5 keywords with largest absolute delta in last 7 days, across all sites."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    # KeywordPosition.delta = previous_position - current_position (positive = improved)
    # keyword_positions is range-partitioned on checked_at — always filter by checked_at
    result = await db.execute(
        select(KeywordPosition)
        .where(
            KeywordPosition.checked_at >= cutoff,
            KeywordPosition.delta.isnot(None),
        )
        .order_by(desc(func.abs(KeywordPosition.delta)))
        .limit(limit)
    )
    return result.scalars().all()

async def get_recent_crawl_errors(db: AsyncSession, limit: int = 5) -> list[dict]:
    """TOP-5 most recent crawler error pages (http_status=404 or has_noindex)."""
    # Page.site_id + Page.crawled_at indexed
    result = await db.execute(
        select(Page)
        .where(
            (Page.http_status == 404) | (Page.has_noindex.is_(True))
        )
        .order_by(desc(Page.crawled_at))
        .limit(limit)
    )
    return result.scalars().all()

async def get_recent_alerts(db: AsyncSession, limit: int = 5) -> list[dict]:
    """TOP-5 most recent ChangeAlerts (error severity first)."""
    result = await db.execute(
        select(ChangeAlert)
        .order_by(desc(ChangeAlert.created_at))
        .limit(limit)
    )
    return result.scalars().all()

async def get_overdue_tasks(db: AsyncSession, limit: int = 5) -> list[dict]:
    """TOP-5 overdue SeoTasks (due_date < today, status != resolved)."""
    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(SeoTask)
        .where(
            SeoTask.due_date < today,
            SeoTask.status != TaskStatus.resolved,
        )
        .order_by(SeoTask.due_date)
        .limit(limit)
    )
    return result.scalars().all()
```

**Critical gotcha — partitioned table:** `keyword_positions` is range-partitioned on `checked_at`. ALL queries against this table MUST include a `checked_at` filter or PostgreSQL will scan every partition. Always use `checked_at >= cutoff`.

### Pattern 2: Health Card Async Queries (D-05)

The existing `compute_site_health()` in `site_service.py` measures *setup completeness* (7 boolean flags). The mobile health card needs *operational status* (6 metrics). These are distinct — do not extend the existing function, create new async queries:

```python
async def get_mobile_site_health(db: AsyncSession, site_id: uuid.UUID) -> dict:
    """6 operational health metrics for mobile health card."""
    # (1) Last HTTP status — latest CrawlJob's status + finished_at
    # (2) Fresh crawl error count — Pages with 404/noindex from latest CrawlJob
    # (3) Last crawl status — latest CrawlJob.status + finished_at + pages_crawled
    # (4) Sharp position changes — KeywordPosition delta > threshold in last 7 days
    # (5) Overdue task count — SeoTask where due_date < today and status != resolved
    # (6) Indexation status — Site.metrika_token presence as proxy; null if no GSC/Yandex data
```

**Status thresholds for color indicators (D-06):**
- Green: site reachable (last crawl done), 0 errors, 0 overdue tasks, no sharp drops
- Yellow: 1-5 crawl errors, crawl >7 days old, 1-3 overdue tasks
- Red: site unreachable (crawl failed), >5 errors, >3 overdue tasks, position drop >10

### Pattern 3: Deep Link Strategy (D-04 resolution)

**Recommendation:** Smart fallback — mobile URL if page exists in Phase 27, desktop `/ui/` otherwise.

```
Digest item type → Link target
─────────────────────────────────────────────────────
Position change   → /ui/sites/{site_id}/positions     (desktop, Phase 28 will add /m/positions)
Crawl error       → /ui/crawls/{crawl_job_id}         (desktop)
Alert             → /ui/sites/{site_id}/monitoring    (desktop)
Overdue task      → /ui/tasks?site_id={site_id}       (desktop)
Health card link  → /m/health/{site_id}               (mobile — exists after this phase)
```

All these desktop links work today. When Phase 28–31 add mobile equivalents, their specific digest items can be updated. This avoids dead links on tap.

### Pattern 4: Health Card Actions (D-07 resolution)

**Recommendation:** HTMX for both actions. Rationale:
- `base_mobile.html` already wires `htmx:responseError` → `showToast()` globally
- Toast via `HX-Trigger` response header is the clean server-driven pattern (no JS needed)
- Fetch API would require manual error handling and duplicate the existing toast wiring

**Crawl trigger pattern (reuse existing endpoint):**
```html
<!-- In health.html -->
<button
  hx-post="/sites/{{ site.id }}/crawl"
  hx-swap="none"
  hx-on::after-request="if(event.detail.successful) showToast('Краулинг запущен', 'success')"
>
  Запустить краулинг
</button>
```

Note: `/sites/{site_id}/crawl` (existing desktop endpoint) requires `require_admin` — mobile user must be admin or a new mobile-only endpoint must relax this to `get_current_user`. **Decision for planner:** create `/m/health/{site_id}/crawl` (POST) that calls `crawl_site.delay()` with `get_current_user` instead of `require_admin`.

**Inline task creation (D-08):**
```html
<!-- Collapsed state — single button -->
<button
  hx-get="/m/health/{{ site.id }}/task-form?url={{ error.url|urlencode }}"
  hx-target="#task-form-slot"
  hx-swap="innerHTML"
>
  Создать задачу
</button>
<div id="task-form-slot"></div>

<!-- Expanded form returned by /m/health/{site_id}/task-form (HTML fragment) -->
<form
  hx-post="/m/health/{{ site.id }}/tasks"
  hx-swap="outerHTML"
  hx-target="closest form"
>
  <input name="title" value="{{ prefilled_title }}">
  <select name="priority">...</select>
  <button type="submit">Сохранить</button>
</form>
```

POST handler returns empty string + `HX-Trigger: {"showToastSuccess": "Задача создана"}` header, or alternatively the button calls `showToast()` via `hx-on::after-request`.

### Pattern 5: Toast via HTMX (established in codebase)

`base_mobile.html` defines `showToast(msg, type)` in global JS. The `htmx:responseError` event auto-calls it on server errors. For success confirmation from HTMX actions, use `hx-on::after-request`:

```html
hx-on::after-request="if(event.detail.successful) showToast('Готово', 'success')"
```

This is consistent with `analytics/dead_content.html` which uses `HX-Trigger` header + JS listener. The `hx-on::after-request` inline approach is simpler for mobile (no separate JS listener needed).

### Anti-Patterns to Avoid

- **Using sync `morning_digest_service.build_morning_digest()` directly in FastAPI route:** It takes `Session` (sync), will block the async event loop. Must use async queries.
- **Querying `keyword_positions` without `checked_at` filter:** Partitioned table — full scan = all partitions. Always add `WHERE checked_at >= {cutoff}`.
- **Reusing `compute_site_health()` for the mobile health card:** It measures setup completeness (7 boolean steps), not operational status. Repurposing it will produce wrong data for the 6 operational metrics.
- **Adding `require_admin` to new mobile action endpoints:** Mobile users are regular users. Use `get_current_user` for all `/m/` endpoints, consistent with existing mobile routes.
- **Loading all sites' data without pagination:** Digest queries must use `LIMIT 5` on every block to avoid slow page loads.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toast notifications | Custom JS notification system | `showToast()` in `base_mobile.html` + `hx-on::after-request` | Already implemented and tested in Phase 26 |
| Crawl task dispatch | New Celery task | `crawl_site.delay(str(site_id))` from `app.tasks.crawl_tasks` | Existing task has retry=3, soft_time_limit, site guards |
| Task creation | New service class | Direct `SeoTask(...)` insert via AsyncSession + `db.flush()` | `SeoTask` model is simple; task_service.py pattern is clear |
| Auth check on mobile endpoints | Custom middleware | `Depends(get_current_user)` — same as all other `/m/` routes | UIAuthMiddleware + JWT cookie already handles redirect to login |
| Position delta calculation | Custom SQL window functions | `KeywordPosition.delta` column — already stores `previous_position - current_position` | Delta is pre-computed at write time |

---

## Common Pitfalls

### Pitfall 1: Sync Session in Async Route
**What goes wrong:** Calling `build_morning_digest(db: Session)` or `build_digest(db: Session)` from a FastAPI async handler causes the sync SQLAlchemy session to block the asyncio event loop — silent performance degradation, no error raised.
**Why it happens:** Python's asyncio does not detect sync blocking calls in coroutines.
**How to avoid:** Write new async functions in `mobile_digest_service.py` using `AsyncSession`. Never import or call sync service functions from async route handlers.
**Warning signs:** Response time > 1s for simple queries on small data sets.

### Pitfall 2: Partitioned Table Without Date Filter
**What goes wrong:** `SELECT * FROM keyword_positions WHERE site_id = X ORDER BY delta DESC LIMIT 5` scans ALL monthly partitions — becomes slow as data grows.
**Why it happens:** PostgreSQL's partition pruning only activates when the partition key (`checked_at`) appears in the WHERE clause.
**How to avoid:** Always add `WHERE checked_at >= NOW() - INTERVAL '7 days'` (or equivalent timedelta) to every `keyword_positions` query.
**Warning signs:** EXPLAIN ANALYZE shows "Seq Scan" on multiple partitions.

### Pitfall 3: HTMX 2.0 Event Name Syntax
**What goes wrong:** Using `hx-on:htmx:after-request` (HTMX 1.x syntax) instead of `hx-on::after-request` (HTMX 2.0 syntax with double colon).
**Why it happens:** HTMX 2.0 changed the event attribute naming convention.
**How to avoid:** `base_mobile.html` already loads HTMX 2.0.3. Use `hx-on::after-request`, `hx-on::before-request` (double colon prefix for internal events).
**Warning signs:** Toast never fires after successful request.

### Pitfall 4: Missing `site_id` Join for Cross-Site Digest
**What goes wrong:** Digest shows errors/alerts without `Site.name` labels — user can't tell which site the item belongs to.
**Why it happens:** `ChangeAlert`, `Page`, `SeoTask` have `site_id` FK but no `site_name` denormalized column.
**How to avoid:** JOIN with `Site` table in digest queries, or eager load via `selectinload`, to have `site.name` available in template context.
**Warning signs:** Template renders `{{ item.site_id }}` UUID instead of a human-readable name.

### Pitfall 5: No Empty-State Handling
**What goes wrong:** New user with no crawl data opens `/m/digest` and sees a blank page or Python exception from empty list iteration.
**Why it happens:** Digest queries return empty lists when no data exists yet.
**How to avoid:** Each block template must handle `{% if items %}...{% else %}<p>Нет данных</p>{% endif %}`.
**Warning signs:** 500 error or blank blocks on fresh install.

### Pitfall 6: Health Card Crawl Endpoint Auth Level
**What goes wrong:** If new `/m/health/{site_id}/crawl` reuses the desktop `trigger_crawl` handler (which uses `require_admin`), regular mobile users get 403.
**Why it happens:** Desktop endpoints use `require_admin`; mobile endpoints use `get_current_user`.
**How to avoid:** Create a new POST endpoint `/m/health/{site_id}/crawl` in `mobile.py` with `Depends(get_current_user)` that calls `crawl_site.delay()` directly.

---

## Code Examples

### Async Position Delta Query (partitioned table safe)
```python
# mobile_digest_service.py
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.position import KeywordPosition
from app.models.site import Site

async def get_top_position_changes(db: AsyncSession, limit: int = 5) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = (
        select(KeywordPosition, Site.name.label("site_name"))
        .join(Site, KeywordPosition.site_id == Site.id)
        .where(
            KeywordPosition.checked_at >= cutoff,
            KeywordPosition.delta.isnot(None),
        )
        .order_by(desc(func.abs(KeywordPosition.delta)))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.all()
```

### Mobile Route Handler Pattern
```python
# app/routers/mobile.py — new endpoint
@router.get("/digest")
async def mobile_digest(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.mobile_digest_service import build_mobile_digest
    data = await build_mobile_digest(db)
    return mobile_templates.TemplateResponse(
        "mobile/digest.html",
        {"request": request, "user": user, "active_tab": "digest", **data},
    )
```

### Health Card Action — Crawl Trigger
```python
@router.post("/health/{site_id}/crawl", status_code=202)
async def mobile_trigger_crawl(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.tasks.crawl_tasks import crawl_site as crawl_site_task
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Сайт не найден")
    crawl_site_task.delay(str(site_id))
    return Response(status_code=202)
```

### Inline Task Form Fragment Endpoint
```python
@router.get("/health/{site_id}/task-form", response_class=HTMLResponse)
async def mobile_task_form(
    site_id: uuid.UUID,
    url: str = "",
    request: Request = None,
    user: User = Depends(get_current_user),
):
    """Return HTML fragment for inline task creation form."""
    prefilled_title = f"Ошибка: {url}" if url else ""
    return mobile_templates.TemplateResponse(
        "mobile/partials/task_form.html",
        {"request": request, "site_id": site_id, "prefilled_title": prefilled_title},
    )

@router.post("/health/{site_id}/tasks", response_class=HTMLResponse)
async def mobile_create_task(
    site_id: uuid.UUID,
    title: str = Form(...),
    priority: str = Form("p3"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.task import SeoTask, TaskPriority
    task = SeoTask(
        site_id=site_id,
        task_type="manual",
        url="",
        title=title,
        priority=TaskPriority(priority),
    )
    db.add(task)
    await db.flush()
    await db.commit()
    # Return empty fragment — toast triggered via hx-on::after-request in template
    return HTMLResponse(content="", status_code=201)
```

### Jinja2 Template Block Structure (digest.html)
```html
{% extends "base_mobile.html" %}
{% set active_tab = 'digest' %}

{% block content %}
<h1>Дайджест — {{ today }}</h1>

{# Block 1: Позиции #}
<section>
  <h2>Изменения позиций</h2>
  {% if position_changes %}
    {% for item in position_changes %}
    <a href="/ui/sites/{{ item.KeywordPosition.site_id }}/positions">
      <span class="{% if item.KeywordPosition.delta > 0 %}text-green{% else %}text-red{% endif %}">
        {{ item.KeywordPosition.delta|abs }}
      </span>
      {{ item.site_name }}
    </a>
    {% endfor %}
  {% else %}
    <p>Нет данных за последние 7 дней</p>
  {% endif %}
</section>

{# Blocks 2–4 follow same pattern #}
{% endblock %}
```

---

## Environment Availability

Step 2.6: SKIPPED — phase is pure code/config changes within the existing Docker Compose stack. All dependencies (PostgreSQL, Redis, Celery, FastAPI) are already running in the project environment.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Telegram-only morning digest | Web mobile `/m/digest` page | No Telegram dependency — browser-based |
| Sync `Session` in Celery | `AsyncSession` in FastAPI routes | Cannot mix — new service needed |
| Desktop `require_admin` actions | Mobile `get_current_user` actions | Mobile users not necessarily admin |

---

## Open Questions

1. **SeoTask.task_type for manually created tasks**
   - What we know: `TaskType` enum has `manual` — correct value for health card task creation.
   - What's unclear: `SeoTask.url` is `NOT NULL String(2000)`. For tasks created from an alert (no page URL), should `url` be empty string `""` or the alert's `page_url`?
   - Recommendation: Use the error's `page_url` as `url` when available; `""` when creating from a non-URL context. Empty string is valid per the schema (not nullable but no min-length constraint).

2. **Position changes: per-site or cross-site in digest?**
   - What we know: CONTEXT.md says "TOP изменения позиций" without specifying scope.
   - What's unclear: Does the user want TOP-5 across ALL sites, or TOP-5 per site?
   - Recommendation: Cross-site TOP-5 by absolute delta — simplest, fits one screen. Per-site breakdown is for the dedicated positions page (Phase 28).

3. **Health card metric 6 (indexation status)**
   - What we know: CONTEXT.md says "данные GSC/Yandex если есть". `Site.metrika_token` exists; no dedicated indexation count column visible in models.
   - What's unclear: Is there a stored indexation count from Yandex Webmaster or GSC in the current schema?
   - Recommendation: Display "Нет данных" / grey indicator if `site.metrika_token` is null. If token exists, show "Подключено" (green) as a proxy. True indexation data is Phase 30 (ERR-01). This keeps the metric useful without requiring new API calls.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase read: `app/services/morning_digest_service.py` — sync Session pattern, data queries
- Direct codebase read: `app/services/digest_service.py` — async/sync split, redbeat integration
- Direct codebase read: `app/services/site_service.py:compute_site_health()` — existing health pattern
- Direct codebase read: `app/services/change_monitoring_service.py` — `ChangeAlert` model
- Direct codebase read: `app/routers/mobile.py` — established mobile route pattern
- Direct codebase read: `app/routers/tasks.py` — `SeoTask` create/update pattern
- Direct codebase read: `app/routers/sites.py:trigger_crawl` — `crawl_site.delay()` invocation
- Direct codebase read: `app/templates/base_mobile.html` — HTMX 2.0.3, toast infrastructure
- Direct codebase read: `app/models/position.py`, `crawl.py`, `task.py`, `change_monitoring.py`
- CLAUDE.md: fixed tech stack constraints

### Secondary (MEDIUM confidence)
- HTMX 2.0 event syntax (`hx-on::after-request` double colon) — verified from `base_mobile.html` HTMX version (2.0.3) and HTMX 2.0 changelog knowledge
- SQLAlchemy async partition pruning behavior — from PostgreSQL partition documentation pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — fixed by CLAUDE.md, verified against existing codebase
- Architecture: HIGH — all patterns derived from actual code in the repository
- Pitfalls: HIGH — sync/async split, partition filter, HTMX 2.0 syntax verified from code
- Open questions: LOW — indexation data availability needs planner to verify via schema grep

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable stack, 30-day window)
