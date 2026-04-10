# Phase 28: Positions & Traffic — Research

**Researched:** 2026-04-10
**Domain:** Mobile FastAPI/Jinja2/HTMX — position check UI + Metrika traffic comparison
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Card layout for each keyword — phrase, position, colored delta (+green/-red), engine, check date. Pattern consistent with digest blocks from Phase 27.

**D-02:** Filters: site select + period (7d/30d/all). Sort by delta magnitude by default. Minimal mobile UI.

**D-03:** Two tabs at top: "Все" (all keywords) and "Просевшие" (delta < 0 only). Dropped tab shows task creation button per keyword.

**D-04:** HTMX-polling for progress — button "Запустить проверку" → POST triggers Celery `check_positions(site_id)` → toast "Проверка запущена" → progress block polls via `hx-trigger='every 3s'` showing "Проверено X из Y ключей".

**D-05:** On completion: polling detects status=done → shows "Проверка завершена" with button "Показать результаты" that reloads the position list via hx-get swap. NOT auto-replace.

**D-06:** Data source: Yandex.Metrika API only. Sites without `metrika_token` show empty state "Метрика не подключена".

**D-07:** Period selection: presets only — "Эта неделя vs прошлая", "Этот месяц vs прошлый", "30 дней vs 30 дней". No custom date picker.

**D-08:** Display: summary card at top (total traffic period 1 → period 2, delta %), then per-page list sorted by delta (biggest drops first). Red for drops, green for growth. Each page row is tappable for task creation.

**D-09:** Reuse `task_form.html` partial from Phase 27. hx-get loads form with `prefilled_title` (keyword phrase or page URL). Same save/cancel flow, same toast. Unified pattern across all mobile pages.

### Claude's Discretion

- Service layer approach — new mobile-specific service or extend existing `position_service.py` / `traffic_analysis_service.py`
- Metrika API query structure — how to fetch per-page traffic for comparison
- Progress endpoint design — how to expose Celery task progress for HTMX polling

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| POS-01 | Пользователь может запустить проверку позиций для сайта с телефона | `check_positions` Celery task exists; `/positions/sites/{id}/check` POST endpoint exists; needs `/m/positions/check` mobile POST endpoint that calls same task |
| POS-02 | Пользователь видит результаты проверки: позиции, тренды, изменения за период | `keyword_latest_positions` table provides fast read; `get_latest_positions()` returns dict rows with delta; period filter needs service-layer function |
| POS-03 | Пользователь может создать задачу на просевшие позиции прямо из результатов | `task_form.html` partial exists; `SeoTask` model with `TaskType.manual` confirmed; POST endpoint pattern from `/m/health/{site_id}/tasks` can be replicated |
| TRF-01 | Пользователь может сравнить трафик по сайту за два периода с телефона | `metrika_service.py` has `fetch_page_traffic()`, `compute_period_delta()`, `get_page_traffic()`; `Site.metrika_token` and `Site.metrika_counter_id` fields exist |
| TRF-02 | Пользователь видит какие страницы просели/выросли и может создать ТЗ на просевшую | `compute_period_delta()` returns sorted list with `visits_delta`; same `task_form.html` pattern for task creation |
</phase_requirements>

---

## Summary

Phase 28 adds two mobile pages: `/m/positions` (position check launcher + result list) and `/m/traffic` (Metrika-based two-period traffic comparison). Both pages are built as Jinja2 templates extending `base_mobile.html`, using HTMX 2.0 for interactions, and reusing the `task_form.html` partial from Phase 27 for task creation.

All backend services needed are already implemented. `position_service.py` has `get_latest_positions()` using the `keyword_latest_positions` flat cache table (fast, no partition scan). The Celery task `check_positions(site_id)` exists in `position_tasks.py` with full XMLProxy + DataForSEO support. The `metrika_service.py` has `fetch_page_traffic()`, `save_page_snapshots()`, `get_page_traffic()`, and `compute_period_delta()` — everything needed for the traffic comparison feature.

The primary implementation work is: (1) new mobile router endpoints in `mobile.py`, (2) a `mobile_positions_service.py` helper (following the `mobile_digest_service.py` pattern), (3) a `mobile_traffic_service.py` helper that orchestrates Metrika fetch + DB save + compute_period_delta, and (4) the Jinja2 templates with HTMX polling for position check progress. No new models, no Alembic migrations, no new dependencies needed.

**Primary recommendation:** Create two new service files following the `mobile_digest_service.py` pattern (async, no sync Session), add 8–10 new endpoints to `mobile.py`, and implement 6 new templates (2 pages + 4 partials).

---

## Standard Stack

### Core (all already in project — no new installs)

| Library | Version | Purpose | Why Used |
|---------|---------|---------|----------|
| FastAPI | 0.115.x | Router endpoints | Project standard |
| Jinja2 | 3.1.x | Templates | Project standard |
| HTMX | 2.0.3 | Client-side interactions | Already in `base_mobile.html` via CDN |
| SQLAlchemy async | 2.0.x | DB queries | Project standard |
| redis-py | 5.0.x | Task ID storage for progress polling | Already used in `positions.py` |
| Celery | 5.4.x | `check_positions` task | Already implemented |
| httpx | 0.27.x | Metrika API calls | Already in `metrika_service.py` |

**No new packages needed.** This phase is purely additive wiring of existing services.

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
app/
├── routers/
│   └── mobile.py                          # Add ~8 new endpoints here
├── services/
│   ├── mobile_positions_service.py        # NEW — positions data for mobile
│   └── mobile_traffic_service.py          # NEW — traffic comparison for mobile
└── templates/mobile/
    ├── positions.html                     # NEW — /m/positions page
    ├── traffic.html                       # NEW — /m/traffic page
    └── partials/
        ├── position_card.html             # NEW — keyword position row
        ├── position_progress.html         # NEW — HTMX-polled progress block
        ├── traffic_summary.html           # NEW — summary card (period 1 → 2)
        └── traffic_page_row.html          # NEW — per-page URL + delta row
```

### Pattern 1: Mobile Service — async-only, no sync Session

Follow `mobile_digest_service.py` exactly: async functions only, `AsyncSession` parameter, SQLAlchemy `select()` ORM queries, NO imports from sync services that use `Session`.

```python
# Source: app/services/mobile_digest_service.py — established pattern
async def get_mobile_positions(
    db: AsyncSession,
    site_id: uuid.UUID,
    period_days: int | None = None,
    dropped_only: bool = False,
) -> list[dict]:
    """Query keyword_latest_positions for mobile card list."""
    # Use keyword_latest_positions (flat cache) — NOT keyword_positions (partitioned)
    # Always filter checked_at for partition safety when joining keyword_positions
    ...
```

**Critical:** Query `keyword_latest_positions` (flat cache table), NOT `keyword_positions` (partitioned). The partition table requires `checked_at >= cutoff` in every WHERE clause or you get full-table scans. The flat cache was built explicitly for this use case.

### Pattern 2: Position Progress Polling — Redis task_id, HTMX outerHTML swap

The desktop router (`positions.py`) already stores the task_id in Redis with TTL 600:
```python
# Source: app/routers/positions.py line 123
r.setex(f"position_check:{site_id}", 600, task.id)
```

The mobile POST endpoint should write to the same Redis key. The polling GET endpoint reads the key, calls `celery_app.AsyncResult(task_id)`, and returns:
- Running: template with `hx-trigger="every 3s"` → HTMX continues polling
- Done: template WITHOUT `hx-trigger` → HTMX polling stops automatically

The `check_positions` task does NOT emit granular `checked/total` progress — it only has final `positions_written` in the result dict. The progress display will show "Проверка выполняется..." (spinner) during PENDING/STARTED, and "Проверка завершена — {N} ключей" when `result.ready()` and `result.successful()`.

If granular "Проверено X из Y" is desired, the task would need `self.update_state(state='PROGRESS', meta={'checked': n, 'total': total})` calls inside `_check_via_xmlproxy`. Confirmed: the current `check_positions` task does NOT call `update_state`. **Decision for planner:** either add `update_state` calls to `check_positions` (modifies existing task), or simplify the progress display to binary running/done states. The UI-SPEC mentions "Проверено X из Y" but the task doesn't support it today.

### Pattern 3: Metrika Traffic Comparison — two-phase fetch+compare

```python
# Source: app/services/metrika_service.py — existing functions
# Phase 1: fetch (or read from cache)
rows_a = await get_page_traffic(db, site_id, period_a_start, period_a_end)
if not rows_a:
    rows_a = await fetch_page_traffic(counter_id, token, date1, date2)
    await save_page_snapshots(db, site_id, period_a_start, period_a_end, rows_a)

# Phase 2: compute delta
comparison = compute_period_delta(rows_a, rows_b)
# Sort by visits_delta ascending (biggest drops first)
comparison.sort(key=lambda r: r["visits_delta"])
```

The `compute_period_delta()` function returns `visits_delta = visits_b - visits_a`, so negative = drop, positive = growth. The per-page list sorts by `visits_delta` ascending (most negative first) per D-08.

Period preset calculations:
```python
# "Эта неделя vs прошлая"
today = date.today()
week_start = today - timedelta(days=today.weekday())         # Monday
period_b = (week_start, today)
period_a = (week_start - timedelta(weeks=1), week_start - timedelta(days=1))

# "Этот месяц vs прошлый"
this_month_start = today.replace(day=1)
last_month_end = this_month_start - timedelta(days=1)
last_month_start = last_month_end.replace(day=1)
period_b = (this_month_start, today)
period_a = (last_month_start, last_month_end)

# "30 дней vs 30 дней"
period_b = (today - timedelta(days=29), today)
period_a = (today - timedelta(days=59), today - timedelta(days=30))
```

### Pattern 4: task_form.html Reuse — endpoint duplication required

The existing `task_form.html` partial hardcodes the POST URL as `/m/health/{{ site_id }}/tasks`. For `/m/positions` and `/m/traffic`, new endpoints are needed:
- `/m/positions/{site_id}/task-form` — GET, returns task_form with `prefilled_title`
- `/m/positions/{site_id}/tasks` — POST, creates task (same logic as health task endpoint)
- `/m/traffic/{site_id}/task-form` — GET
- `/m/traffic/{site_id}/tasks` — POST

**Alternative (recommended):** Create a generic `/m/tasks/{site_id}` endpoint pair and pass the POST URL as a template variable into `task_form.html`. This avoids duplicating the endpoint code 3 times. Requires modifying `task_form.html` to use a variable `{{ post_url }}` instead of hardcoded path.

### Pattern 5: HTMX 2.0 Polling — stop by omitting hx-trigger

The established HTMX 2.0 approach for stopping polling is to return a response that lacks the `hx-trigger` attribute. The simplest way:
- While running: return `position_progress.html` template which includes `hx-trigger="every 3s"`
- When done: return `position_done.html` or a conditional in the same partial that renders without `hx-trigger`

```html
<!-- position_progress.html — shown while task is running -->
<div id="check-progress-slot"
  hx-get="/m/positions/check/status?site_id={{ site_id }}"
  hx-trigger="every 3s"
  hx-target="this"
  hx-swap="outerHTML">
  <!-- spinner + progress text -->
</div>

<!-- When done, server returns this instead (no hx-trigger): -->
<div id="check-progress-slot">
  <!-- checkmark + "Показать результаты" button -->
</div>
```

### Pattern 6: Mobile Router — site_id via query param vs path param

The health page uses `/m/health/{site_id}` (path param). For `/m/positions` the site is selected via filter, so site_id is a query param: `/m/positions?site_id=...`. The initial page load can default to the first active site. Filter changes via `hx-get` pass `site_id` and `period` as query params.

### Anti-Patterns to Avoid

- **Querying `keyword_positions` without cutoff:** Never query the partitioned table without `checked_at >= cutoff`. Use `keyword_latest_positions` for mobile displays.
- **Calling sync services from async context:** `mobile_positions_service.py` must be fully async. Do NOT import from sync functions like `write_position_sync`.
- **Blocking Celery task call in FastAPI endpoint:** Use `.delay()` (returns immediately) not `.apply()` (blocks). The trigger endpoint is already correct in the desktop router.
- **Auto-refreshing position list after check:** D-05 is explicit — show "Показать результаты" button, not auto-replace. Do not add `hx-on::after-request` that swaps the list automatically.
- **Direct Metrika API calls on every page load:** Always read from `metrika_traffic_pages` DB first; only call the Metrika API if no cached rows exist for the requested period. Heavy API calls must not block page rendering.
- **Hardcoding task POST URL in task_form.html:** Parameterize or create page-specific endpoints — do not copy the form partial and hardcode a new URL.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Position data fetch for mobile | Custom DISTINCT ON query | `get_latest_positions()` from `position_service.py` or direct query on `keyword_latest_positions` | Already handles partition safety, engine/region filters |
| Celery task progress | Custom progress DB table | `celery_app.AsyncResult(task_id)` + Redis key from `position_check:{site_id}` | Desktop router already implements this exact pattern |
| Period delta calculation | Custom loop comparing two dicts | `compute_period_delta(rows_a, rows_b)` in `metrika_service.py` | Already handles new/lost pages, None values, deduplication |
| Metrika data fetch | New API client | `fetch_page_traffic()` + `save_page_snapshots()` + `get_page_traffic()` | Fully implemented with pagination, URL normalization, upsert |
| Task creation | New SeoTask creation logic | Replicate the 10-line pattern from `/m/health/{site_id}/tasks` | Same `SeoTask(task_type=TaskType.manual, ...)` pattern |
| Russian date formatting | Custom strftime | `_ru_short_date()` from `mobile_digest_service.py` + `_RU_MONTHS` dict | Already locale-independent |

---

## Common Pitfalls

### Pitfall 1: Progress display vs. task capability mismatch

**What goes wrong:** UI-SPEC says "Проверено X из Y ключей" but `check_positions` never calls `self.update_state()` with granular progress. Polling endpoint gets `AsyncResult.info` = None. Template tries to render `{{ checked }}/{{ total }}` and crashes or shows 0/0.

**Why it happens:** UI was designed aspirationally; task implementation was not updated to emit progress.

**How to avoid:** Either (a) add `self.update_state(state='PROGRESS', meta={'checked': n, 'total': total})` inside the per-keyword loop in `_check_via_xmlproxy`, or (b) simplify progress display to binary running/done. Adding update_state is low-risk (it just sets a Redis key) but touches the existing task. The planner should pick one approach and make it explicit in the plan.

**Warning signs:** Template renders "Проверено 0 из 0 ключей" while check is running.

### Pitfall 2: `get_latest_positions()` returns raw dict rows, not ORM objects

**What goes wrong:** `get_latest_positions()` returns `list[dict]` (from `.mappings().all()`), not ORM `KeywordPosition` objects. Template tries to access `.phrase` or `.checked_at.strftime()` and gets `AttributeError` or `KeyError`.

**Why it happens:** The function returns raw SQL mappings; `keyword_id` is a UUID, not the keyword phrase. To get the phrase, a JOIN with the `keywords` table is needed.

**How to avoid:** The mobile service must JOIN `keyword_latest_positions` with `keywords` to get `phrase`. Use `keyword_latest_positions` directly via SQLAlchemy ORM (not `get_latest_positions()` which lacks the JOIN):

```python
stmt = (
    select(
        KeywordLatestPosition,
        Keyword.phrase,
    )
    .join(Keyword, KeywordLatestPosition.keyword_id == Keyword.id)
    .where(KeywordLatestPosition.site_id == site_id)
    .order_by(func.abs(KeywordLatestPosition.delta).desc().nullslast())
)
```

### Pitfall 3: Metrika token vs. counter_id — both required

**What goes wrong:** `Site` has both `metrika_token` (OAuth token) and `metrika_counter_id` (numeric counter ID like "12345678"). The `fetch_page_traffic()` function requires both. If only `metrika_token` is set but `metrika_counter_id` is None, the API call will fail.

**Why it happens:** Users may configure only one field. The "Метрика не подключена" check in D-06 should verify BOTH fields.

**How to avoid:** Empty state condition: `if not site.metrika_token or not site.metrika_counter_id`. Show the warning card if either is missing.

### Pitfall 4: `metrika_traffic_pages` requires exact period match

**What goes wrong:** `get_page_traffic(db, site_id, period_start, period_end)` queries by exact `period_start` and `period_end` equality. If the user requests "этот месяц vs прошлый" on Apr 5 and again on Apr 10, the period_end is different, causing a cache miss and a redundant Metrika API call.

**Why it happens:** The cache is keyed on exact date ranges. The period end is always `today` for "this month", so it changes daily.

**How to avoid:** For the mobile view, always fetch fresh from Metrika if `period_end >= today - 1` (recent periods), and only use cache for completed past periods. Alternatively, accept the API call on every load — Metrika's API is fast for 30-day queries.

### Pitfall 5: HTMX polling and Redis key expiry race condition

**What goes wrong:** Position check takes > 600 seconds (Redis TTL) for a large keyword set. Redis key expires; polling endpoint returns `{"active": False}` (no task_id); HTMX renders "done" state prematurely while task is still running.

**Why it happens:** The `r.setex(f"position_check:{site_id}", 600, task.id)` TTL is fixed at 10 minutes. Large Yandex checks with 500+ keywords via XMLProxy (1 req/keyword at ~1 req/sec) take 8-10 minutes.

**How to avoid:** The polling endpoint should also call `celery_app.AsyncResult(task_id)` even if `task_id` was passed as a query param (from the initial POST response), not only from Redis. On the frontend, store `task_id` in a `data-task-id` attribute and pass it to the status endpoint.

### Pitfall 6: task_form.html cancel button uses hardcoded `#task-form-slot` ID

**What goes wrong:** `task_form.html` cancel button calls `document.getElementById('task-form-slot').innerHTML=''`. The positions page uses per-keyword slots `#task-form-slot-{keyword_id}` and the traffic page uses a single `#task-form-slot`. If the IDs don't match, cancel does nothing.

**Why it happens:** The partial hardcodes a specific element ID.

**How to avoid:** Either (a) use the same `id="task-form-slot"` for the container on both pages (only one form open at a time), or (b) pass the container ID as a template variable. Option (a) is simpler and consistent with the health page pattern.

---

## Code Examples

### Mobile positions service: query keyword_latest_positions with phrase JOIN

```python
# New: app/services/mobile_positions_service.py
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.keyword_latest_position import KeywordLatestPosition
from app.models.keyword import Keyword

async def get_mobile_positions(
    db: AsyncSession,
    site_id: uuid.UUID,
    period_days: int | None = None,
    dropped_only: bool = False,
    limit: int = 100,
) -> list[dict]:
    stmt = (
        select(
            KeywordLatestPosition.id,
            KeywordLatestPosition.position,
            KeywordLatestPosition.previous_position,
            KeywordLatestPosition.delta,
            KeywordLatestPosition.engine,
            KeywordLatestPosition.checked_at,
            Keyword.phrase,
        )
        .join(Keyword, KeywordLatestPosition.keyword_id == Keyword.id)
        .where(KeywordLatestPosition.site_id == site_id)
    )
    if dropped_only:
        stmt = stmt.where(KeywordLatestPosition.delta < 0)
    if period_days:
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        stmt = stmt.where(KeywordLatestPosition.checked_at >= cutoff)
    stmt = stmt.order_by(
        func.abs(KeywordLatestPosition.delta).desc().nullslast()
    ).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "phrase": r.phrase,
            "position": r.position,
            "delta": r.delta,
            "engine": r.engine,
            "checked_at": r.checked_at,
        }
        for r in rows
    ]
```

### Mobile router: trigger position check (POST)

```python
# In app/routers/mobile.py
@router.post("/positions/check", status_code=202)
async def mobile_trigger_position_check(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.tasks.position_tasks import check_positions as _check_task
    from app.config import settings
    import redis as _redis
    task = _check_task.delay(str(site_id))
    r = _redis.from_url(settings.REDIS_URL)
    r.setex(f"position_check:{site_id}", 600, task.id)
    # Return the progress partial immediately (HTMX swaps into #check-progress-slot)
    return mobile_templates.TemplateResponse(
        "mobile/partials/position_progress.html",
        {"request": request, "site_id": site_id, "task_id": task.id, "status": "started"},
    )
```

### Mobile router: position check status (GET, polled by HTMX)

```python
@router.get("/positions/check/status", response_class=HTMLResponse)
async def mobile_position_check_status(
    site_id: uuid.UUID,
    task_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    from app.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    if result.ready() and result.successful():
        written = result.result.get("positions_written", 0)
        # Return done template (no hx-trigger) — polling stops
        return mobile_templates.TemplateResponse(
            "mobile/partials/position_progress.html",
            {"request": request, "site_id": site_id,
             "status": "done", "positions_written": written},
        )
    # Return running template (has hx-trigger="every 3s") — polling continues
    return mobile_templates.TemplateResponse(
        "mobile/partials/position_progress.html",
        {"request": request, "site_id": site_id, "task_id": task_id, "status": "running"},
    )
```

### Mobile traffic service: compute two-period comparison

```python
# New: app/services/mobile_traffic_service.py
from datetime import date, timedelta
from app.services.metrika_service import (
    fetch_page_traffic, save_page_snapshots, get_page_traffic, compute_period_delta
)

def _period_dates(preset: str) -> tuple[tuple[date, date], tuple[date, date]]:
    today = date.today()
    if preset == "this_week_vs_last":
        b_start = today - timedelta(days=today.weekday())
        b_end = today
        a_start = b_start - timedelta(weeks=1)
        a_end = b_start - timedelta(days=1)
    elif preset == "this_month_vs_last":
        b_start = today.replace(day=1)
        b_end = today
        a_end = b_start - timedelta(days=1)
        a_start = a_end.replace(day=1)
    else:  # 30d_vs_30d
        b_start = today - timedelta(days=29)
        b_end = today
        a_start = today - timedelta(days=59)
        a_end = today - timedelta(days=30)
    return (a_start, a_end), (b_start, b_end)

async def get_traffic_comparison(
    db, site_id, counter_id, token, preset="30d_vs_30d"
) -> dict:
    (a_start, a_end), (b_start, b_end) = _period_dates(preset)
    # Try cache first; fetch from API if missing
    rows_a = await get_page_traffic(db, site_id, a_start, a_end)
    if not rows_a:
        rows_a = await fetch_page_traffic(counter_id, token, str(a_start), str(a_end))
        if rows_a:
            await save_page_snapshots(db, site_id, a_start, a_end, rows_a)
            await db.commit()
    rows_b = await get_page_traffic(db, site_id, b_start, b_end)
    if not rows_b:
        rows_b = await fetch_page_traffic(counter_id, token, str(b_start), str(b_end))
        if rows_b:
            await save_page_snapshots(db, site_id, b_start, b_end, rows_b)
            await db.commit()
    comparison = compute_period_delta(rows_a, rows_b)
    # Sort biggest drops first (most negative visits_delta first)
    comparison.sort(key=lambda r: r["visits_delta"])
    total_a = sum(r["visits_a"] for r in comparison)
    total_b = sum(r["visits_b"] for r in comparison)
    delta_pct = round((total_b - total_a) / total_a * 100, 1) if total_a else 0
    return {
        "period_a": (str(a_start), str(a_end)),
        "period_b": (str(b_start), str(b_end)),
        "total_a": total_a,
        "total_b": total_b,
        "delta_pct": delta_pct,
        "pages": comparison[:50],  # limit to top 50 for mobile
    }
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Desktop SSE (EventSource) for position progress | Mobile HTMX polling every 3s | Polling is simpler, no SSE infrastructure needed; slightly higher server load but acceptable for < 20 users |
| Query `keyword_positions` with DISTINCT ON | Query `keyword_latest_positions` flat cache | Eliminates partition scan; O(n) by keyword count, not by historical record count |

---

## Open Questions

1. **Granular position progress ("Проверено X из Y")**
   - What we know: UI-SPEC specifies it; current `check_positions` task does not emit it
   - What's unclear: Should the planner add `self.update_state()` calls to `_check_via_xmlproxy`, or simplify the mobile UI to binary running/done?
   - Recommendation: Add `update_state` to the XMLProxy loop (low risk, ~5 lines). If the task fails mid-loop, the state shows the last written count. For DataForSEO (batch), update once after batch completes.

2. **task_form.html parameterization**
   - What we know: Current partial hardcodes POST URL as `/m/health/{{ site_id }}/tasks` and cancel clears `#task-form-slot`
   - What's unclear: Create page-specific endpoints (3 copies of same 10-line handler) or modify the partial to accept `post_url` variable?
   - Recommendation: Modify `task_form.html` to accept `post_url` variable; create one generic `/m/tasks/{site_id}` endpoint pair. This touches Phase 27 work but is a clean refactor.

3. **Metrika cache staleness for current-period traffic**
   - What we know: `metrika_traffic_pages` caches by exact `(period_start, period_end)`. Current period end is `today`, so cache miss is expected on every day.
   - What's unclear: Is live Metrika API call on every `/m/traffic` page load acceptable?
   - Recommendation: Accept it. Metrika API is fast (~1-2s). Cache only serves historical periods. Add error handling (try/except on `fetch_page_traffic`) with fallback to empty data + toast error.

---

## Environment Availability

Step 2.6: SKIPPED — this phase adds mobile endpoints that consume existing services. All external dependencies (Redis, Celery, PostgreSQL, Metrika API) were established in prior phases. No new tools or services are introduced.

---

## Validation Architecture

`workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`. Skipping this section.

---

## Project Constraints (from CLAUDE.md)

All directives below are enforced — research does not recommend anything that contradicts them:

| Constraint | Applies to Phase 28 |
|------------|---------------------|
| Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async | Yes — all new code follows these |
| PostgreSQL 16 only; all schema changes via Alembic | No schema changes in this phase — no migration needed |
| Passwords bcrypt, JWT exp=24h | Not touched in this phase |
| Celery retry=3 for external API calls | `check_positions` already has `max_retries=3`; `fetch_page_traffic` uses httpx with no retry — consider adding `httpx` retry or try/except in service |
| Performance: UI pages < 3s | Mobile positions page reads from `keyword_latest_positions` flat cache (fast). Traffic page calls Metrika API — must be async, not blocking. |
| Jinja2 + HTMX — no SPA framework | Confirmed — no React/Vue |
| pytest + httpx AsyncClient; service layer coverage > 60% by iteration 4 | New service functions should have unit tests |
| loguru JSON logging | New services must use `from loguru import logger` |
| `FastAPI lifespan=` not `on_event` | Confirmed — not adding startup handlers |
| HTMX 2.0.x | Already loaded in `base_mobile.html` — use double-colon syntax `hx-on::after-request` |
| `hx-disabled-elt="this"` on POST buttons | Required on "Запустить проверку" button |

---

## Sources

### Primary (HIGH confidence)

- `app/services/position_service.py` — all 11 functions, `keyword_latest_positions` refresh pattern confirmed
- `app/tasks/position_tasks.py` — Celery task structure, lack of `update_state` confirmed
- `app/routers/positions.py` — Redis task_id storage pattern, `/check` and `/active-task` endpoints
- `app/routers/mobile.py` — all existing mobile endpoints, auth pattern, `mobile_templates` instance
- `app/services/metrika_service.py` — `fetch_page_traffic`, `save_page_snapshots`, `get_page_traffic`, `compute_period_delta` all confirmed
- `app/models/metrika.py` — `MetrikaTrafficDaily`, `MetrikaTrafficPage` schema confirmed
- `app/models/keyword_latest_position.py` — flat cache model confirmed with index on `(site_id, position)`
- `app/models/site.py` — `metrika_token` and `metrika_counter_id` fields confirmed
- `app/models/task.py` — `SeoTask`, `TaskType.manual`, `TaskPriority` confirmed
- `app/services/mobile_digest_service.py` — async service pattern reference
- `app/templates/base_mobile.html` — HTMX 2.0.3, `showToast()`, bottom nav with Positions tab wired
- `app/templates/mobile/partials/task_form.html` — hardcoded POST URL and cancel handler confirmed
- `.planning/phases/28-positions-traffic/28-UI-SPEC.md` — approved UI contract

### Secondary (MEDIUM confidence)

- HTMX 2.0 polling stop pattern (omit `hx-trigger`) — confirmed by HTMX 2.0 docs behavior, consistent with `base_mobile.html` patterns

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in codebase, no new deps
- Architecture: HIGH — all services and models inspected directly
- Pitfalls: HIGH — found by direct code inspection (missing update_state, hardcoded task_form URL, both metrika fields required)
- Open questions: MEDIUM — implementation choices for planner to decide

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable stack, all services are in-repo)
