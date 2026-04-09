# Phase 24: Tools Infrastructure & Fast Tools - Research

**Researched:** 2026-04-10
**Domain:** FastAPI / SQLAlchemy async / Celery sync tasks / HTMX polling / XMLProxy / httpx
**Confidence:** HIGH — all findings verified against live codebase; no external API research needed

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Two-page flow: page 1 = input form + previous jobs list; page 2 = results for a specific job
- **D-02:** URL scheme: `/ui/tools/{slug}/` (list + form), `/ui/tools/{slug}/{job_id}` (results)
- **D-03:** HTMX polling every 10 seconds while job is pending/running
- **D-04:** Progress = plain text "Обработка... 45/200 фраз" + spinner. No progress bar widget.
- **D-05:** Export in both formats: CSV + XLSX (openpyxl already in stack)
- **D-06:** No job retention limit; manual deletion via UI; volume is negligible at <20 users
- **D-07:** Single "Инструменты" sidebar entry → `/ui/tools/`; no sub-items per tool
- **D-08:** Slugs: `commercialization`, `meta-parser`, `relevant-url`
- **D-09:** XMLProxy balance exhaustion → partial result (save what was collected, mark job as partial)
- **D-10:** Input limits — Commercialization: 200 phrases; Meta-parser: 500 URLs; Relevant URL: 100 phrases
- **D-11:** Rate limiting: 10 requests/minute per user (slowapi already integrated)

### Claude's Discretion

- Specific Job+Result model column structure (following SuggestJob as template)
- Which Celery worker queue to use (main `default` queue vs dedicated)
- Results table column layout for each tool
- Russian UI copy (within copywriting contract from UI-SPEC)

### Deferred Ideas (OUT OF SCOPE)

None — all ideas stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TOOL-INFRA-01 | "Tools" section in sidebar navigation, accessible to admin and manager roles; lists all tools with recent job status | Sidebar is data-driven via `app/navigation.py` NAV_SECTIONS list; adding one flat entry (no children, `url="/ui/tools/"`) is one edit. Active-state resolution is automatic via `_URL_TO_NAV` pattern matching. |
| TOOL-INFRA-02 | Each tool follows: input form → submit → HTMX polling → results table → CSV/XLSX download; no page reload | Pattern confirmed live in `keyword_suggest` router + `suggest_status.html` partial. Polling uses `hx-trigger="load delay:10s"` + `hx-swap="outerHTML"`. Export is a plain `<a href="...">` link, no HTMX. |
| COM-01 | Commercialization Check: up to 200 phrases → commercialization %, intent class, geo-dep flag, localization flag via XMLProxy; stored in CommerceCheckJob + CommerceCheckResult | `xmlproxy_service.search_yandex_sync()` already parses Yandex SERP; commercialization metrics require counting commercial vs informational results per phrase. Credentials loaded via `get_credential_sync(db, "xmlproxy")`. |
| META-01 | Meta Tag Parser: up to 500 URLs → HTTP status, title, H1, H2 list (up to 10), meta description, canonical via async httpx with 10s timeout and 5 concurrent workers; stored in MetaParseJob + MetaParseResult | `httpx.AsyncClient` is in the stack; inside Celery sync tasks must use `httpx.Client` (sync) with `asyncio.gather()` via `asyncio.run()` or use a thread pool. See Pitfall 3 below. |
| REL-01 | Relevant URL Finder: up to 100 phrases + domain → which URL from that domain appears in Yandex TOP-10, its position, top-3 competing domains; stored in RelevantUrlJob + RelevantUrlResult | `xmlproxy_service.search_yandex_sync()` returns `results` list with `url`, `position`, `domain` per result; filtering by target domain is trivial post-parse. Top-3 competitors = first 3 domains not equal to target domain. |

</phase_requirements>

---

## Summary

Phase 24 is an extension phase, not a greenfield build. Three-quarters of the required infrastructure already exists in the codebase: the Job lifecycle pattern (`SuggestJob`), the Celery task structure (`suggest_tasks.py`), the XMLProxy client (`xmlproxy_service.py`), the HTMX polling partial (`suggest_status.html`), the export pattern (`keyword_suggest.py export_csv`), the rate limiter (`app/rate_limit.py`), and the stub router + template (`app/routers/tools.py`, `app/templates/tools/index.html`).

The planner's primary task is to replicate and adapt the established SuggestJob pattern three times — once per tool — adding the specific logic each tool requires (SERP analysis for commercialization, httpx batch fetch for meta-parser, domain-filtering for relevant URL). The UI-SPEC provides complete visual and copywriting contracts. The navigation system requires one configuration edit (`app/navigation.py`). The smoke test system requires adding `tool_slug` and `tool_job_id` to `SMOKE_IDS` and seeding one row per tool job model.

The single novel technical element is the Meta Tag Parser's async-inside-sync challenge: Celery tasks run synchronously but httpx.AsyncClient works in asyncio. The established project resolution (used in `llm_tasks.py`) is `asyncio.run(async_fn())` wrapping within the sync task body. A thread pool approach with `httpx.Client` (sync) is equally valid and simpler — the planner should choose one and document it consistently.

**Primary recommendation:** Replicate SuggestJob/suggest_tasks.py/keyword_suggest.py patterns exactly; only deviate for tool-specific logic (SERP parsing formulas, httpx concurrency, result column schemas).

---

## Standard Stack

### Core (already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.x | ORM for Job+Result models | Established project standard; async engine in routers, sync session in Celery tasks |
| Alembic | 1.13.x | DB migrations for 6 new tables | Established migration pattern; use `--autogenerate` then review |
| Celery 5.4.x + Redis | bundled | Async task execution | Already configured; tool tasks go in `default` queue (no Playwright needed) |
| httpx | 0.27.x | Meta Tag Parser HTTP fetching | Already in stack; use `httpx.Client` (sync) inside Celery tasks |
| openpyxl | 3.1.x | XLSX export | Already in `requirements.txt`; used in keyword export |
| slowapi | 0.1.9 | Rate limiting (10 req/min) | Already in `app/rate_limit.py` as shared `limiter` instance |
| Jinja2 | 3.1.x | Templates | Already configured via `app/template_engine.py` |
| HTMX | 2.0.x | Polling + form submission | Loaded via CDN in `base.html` |
| beautifulsoup4 + lxml | 4.12.x | HTML parsing for meta tags | Already in stack (used by audit/crawl services) |

### No New Dependencies

All libraries required by Phase 24 are already installed. No `pip install` step is needed.

---

## Architecture Patterns

### Recommended Project Structure for Phase 24

```
app/
├── models/
│   ├── commerce_check_job.py        # CommerceCheckJob + CommerceCheckResult
│   ├── meta_parse_job.py            # MetaParseJob + MetaParseResult
│   └── relevant_url_job.py         # RelevantUrlJob + RelevantUrlResult
├── services/
│   ├── commerce_check_service.py    # SERP analysis logic (commercialization formula)
│   ├── meta_parse_service.py        # httpx batch fetcher + BeautifulSoup extractor
│   └── relevant_url_service.py     # XMLProxy + domain filtering logic
├── tasks/
│   ├── commerce_check_tasks.py      # Celery task: run_commerce_check
│   ├── meta_parse_tasks.py          # Celery task: run_meta_parse
│   └── relevant_url_tasks.py       # Celery task: run_relevant_url
├── routers/
│   └── tools.py                    # Replace stub — all 3 tools + index
└── templates/tools/
    ├── index.html                   # Replace stub — tool card grid
    ├── commercialization/
    │   ├── index.html               # Form + job list
    │   ├── results.html             # Results page (job detail)
    │   └── partials/
    │       └── job_status.html      # HTMX polling partial
    ├── meta-parser/
    │   ├── index.html
    │   ├── results.html
    │   └── partials/job_status.html
    └── relevant-url/
        ├── index.html
        ├── results.html
        └── partials/job_status.html
alembic/versions/
    └── 0047_add_tool_job_tables.py  # Single migration for all 6 tables
```

### Pattern 1: Job Model Pair (follow SuggestJob exactly)

**What:** Each tool has a `*Job` table (input + status) and a `*Result` table (one row per phrase/URL).
**When to use:** Always — this is the established pattern for all async tools.

```python
# Source: app/models/suggest_job.py (reference)
# CommerceCheckJob — follows SuggestJob structure exactly
class CommerceCheckJob(Base):
    __tablename__ = "commerce_check_jobs"
    __table_args__ = (Index("ix_ccj_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Tool-specific: store raw input + counts
    input_phrases: Mapped[list] = mapped_column(JSONB, nullable=False)   # list of str
    phrase_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class CommerceCheckResult(Base):
    __tablename__ = "commerce_check_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("commerce_check_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    commercialization: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 0–100
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)            # commercial/informational/mixed
    geo_dependent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    localized: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
```

**Note on JSONB:** Use `sqlalchemy.dialects.postgresql.JSONB` for `input_phrases`. Alternative: store as newline-delimited text. JSONB is cleaner for Alembic autogenerate.

**Note on `completed_at`:** SuggestJob does not have this field but it is useful for tools (display "finished X minutes ago"). Add it to all three tool Job models.

### Pattern 2: Celery Task Structure (follow suggest_tasks.py exactly)

```python
# Source: app/tasks/suggest_tasks.py
@celery_app.task(
    name="app.tasks.commerce_check_tasks.run_commerce_check",
    bind=True,
    max_retries=3,
    queue="default",          # not crawl — no Playwright needed
    soft_time_limit=600,      # 200 phrases × ~2s each = ~400s max; give headroom
    time_limit=660,
)
def run_commerce_check(self, job_id: str) -> dict:
    from app.services.service_credential_service import get_credential_sync
    from app.services.xmlproxy_service import search_yandex_sync, XMLProxyError

    with get_sync_db() as db:
        job = db.get(CommerceCheckJob, uuid.UUID(job_id))
        job.status = "running"
        db.commit()
        phrases = job.input_phrases  # list[str]

    creds = None
    with get_sync_db() as db:
        creds = get_credential_sync(db, "xmlproxy")
    if not creds or not creds.get("user") or not creds.get("key"):
        with get_sync_db() as db:
            job = db.get(CommerceCheckJob, uuid.UUID(job_id))
            job.status = "failed"
            job.error_message = "XMLProxy не настроен"
            db.commit()
        return {"status": "failed"}

    results = []
    balance_exhausted = False
    for i, phrase in enumerate(phrases):
        # Update progress: job.result_count = i (so UI can show "N/total фраз")
        if i % 10 == 0:
            with get_sync_db() as db:
                j = db.get(CommerceCheckJob, uuid.UUID(job_id))
                if j:
                    j.result_count = i
                    db.commit()
        try:
            serp = search_yandex_sync(creds["user"], creds["key"], phrase, max_position=10)
            result_data = _analyze_commercialization(phrase, serp["results"])
            results.append(result_data)
        except XMLProxyError as e:
            if e.code in (32, 33):   # balance exhausted codes
                balance_exhausted = True
                break
            # Other XMLProxy errors: retry via Celery
            raise self.retry(exc=e, countdown=30)
        except Exception as e:
            raise self.retry(exc=e, countdown=30)

    # Write results + update status
    status = "partial" if balance_exhausted and results else ("failed" if not results else "complete")
    with get_sync_db() as db:
        for r in results:
            db.add(CommerceCheckResult(job_id=uuid.UUID(job_id), **r))
        job = db.get(CommerceCheckJob, uuid.UUID(job_id))
        job.status = status
        job.result_count = len(results)
        job.completed_at = datetime.now(timezone.utc)
        if balance_exhausted:
            job.error_message = "Баланс XMLProxy исчерпан — сохранены частичные данные"
        db.commit()
    return {"status": status, "count": len(results)}
```

### Pattern 3: Router Structure (follow keyword_suggest.py)

The tools router replaces the current stub. All three tools share the same router file. Each tool gets four endpoints:

```
GET  /ui/tools/                             # index (tool card grid)
GET  /ui/tools/{slug}/                      # tool landing (form + job list)
POST /ui/tools/{slug}/            @limiter.limit("10/minute")  # submit → dispatch task → redirect
GET  /ui/tools/{slug}/{job_id}              # results page (static shell + polling partial)
GET  /ui/tools/{slug}/{job_id}/status       # HTMX polling partial
GET  /ui/tools/{slug}/{job_id}/export       # CSV + XLSX download (?format=csv|xlsx)
DELETE /ui/tools/{slug}/{job_id}            # delete job (hx-delete)
```

**Routing note:** The slug is a string path parameter, not a path converter. FastAPI will match all three slugs to the same route handler via a single `slug: str` parameter. The handler dispatches to the appropriate model/service based on slug value with a dict lookup:

```python
TOOL_REGISTRY = {
    "commercialization": {"model": CommerceCheckJob, "result_model": CommerceCheckResult, "task": run_commerce_check, "limit": 200},
    "meta-parser":       {"model": MetaParseJob,     "result_model": MetaParseResult,     "task": run_meta_parse,    "limit": 500},
    "relevant-url":      {"model": RelevantUrlJob,   "result_model": RelevantUrlResult,   "task": run_relevant_url,  "limit": 100},
}
```

This avoids duplicating 7 endpoints × 3 tools = 21 route handlers. One set of handlers covers all tools.

### Pattern 4: HTMX Polling Partial

**What:** Per D-03, polling every 10 seconds. Reuse `suggest_status.html` pattern exactly.
**Key detail:** `hx-trigger="load delay:10s"` not `every 10s` — the partial self-replaces after each poll, so `load delay:10s` fires once per render, achieving 10s interval.

```html
{# Source: app/templates/keyword_suggest/partials/suggest_status.html #}
{% if status in ('pending', 'running') %}
<div
  hx-get="/ui/tools/{{ slug }}/{{ job.id }}/status"
  hx-trigger="load delay:10s"
  hx-swap="outerHTML"
  class="flex items-center gap-3 p-4 bg-blue-50 rounded-lg border border-blue-100"
>
  <svg class="animate-spin text-blue-600" ...></svg>
  <div>
    <div class="text-sm font-medium text-blue-700">
      {% if job.result_count is not none %}
        Обработка... {{ job.result_count }}/{{ job.phrase_count }} фраз
      {% else %}
        Обработка...
      {% endif %}
    </div>
    <div class="text-xs text-blue-500">Обычно занимает менее минуты</div>
  </div>
</div>
{% elif status == 'complete' %}
...
{% endif %}
```

### Pattern 5: Sidebar Navigation Entry

Edit `app/navigation.py` — add one flat (no-children) entry to `NAV_SECTIONS`:

```python
# Source: app/navigation.py — add after keyword-suggest section
{
    "id": "tools",
    "label": "Инструменты",
    "icon": "wrench",          # New icon — add SVG case to sidebar.html
    "url": "/ui/tools/",
    "admin_only": False,
    "children": [],
},
```

The sidebar component `components/sidebar.html` handles flat entries via the `{% else %}` branch (top-level link without children). Adding `wrench` icon requires adding one `{% elif section.icon == 'wrench' %}` block in `sidebar.html`.

### Pattern 6: Export (CSV + XLSX)

```python
# Source: app/routers/keyword_suggest.py export_csv (adapted)
@router.get("/{slug}/{job_id}/export")
async def export_tool_results(
    slug: str,
    job_id: uuid.UUID,
    format: str = "csv",   # query param: ?format=csv or ?format=xlsx
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> StreamingResponse:
    tool = TOOL_REGISTRY.get(slug)
    if not tool:
        raise HTTPException(404)
    result = await db.execute(
        select(tool["result_model"]).where(tool["result_model"].job_id == job_id)
    )
    rows = result.scalars().all()

    if format == "xlsx":
        return _export_xlsx(rows, slug)
    return _export_csv(rows, slug)
```

For XLSX: use `openpyxl.Workbook()`, write header row + data rows, save to `io.BytesIO`, return `StreamingResponse` with `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` media type.

For CSV: use `csv.writer` with UTF-8 BOM (`"\ufeff"`), return `StreamingResponse` with `text/csv; charset=utf-8`.

### Pattern 7: Meta Tag Parser — Sync httpx in Celery

Meta Tag Parser must fetch 500 URLs with 5 concurrent workers. Celery tasks are synchronous. The established project pattern (from `llm_tasks.py`) for async-in-sync is:

```python
import asyncio
import httpx
from bs4 import BeautifulSoup

async def _fetch_url(client: httpx.AsyncClient, url: str) -> dict:
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")
        return {
            "url": url,
            "status_code": resp.status_code,
            "title": (soup.find("title") or {}).get_text(strip=True)[:500],
            "h1": (soup.find("h1") or {}).get_text(strip=True)[:500],
            "h2_list": [h.get_text(strip=True) for h in soup.find_all("h2")][:10],
            "meta_description": (soup.find("meta", attrs={"name": "description"}) or {}).get("content", "")[:500],
            "canonical": (soup.find("link", attrs={"rel": "canonical"}) or {}).get("href", ""),
            "error": None,
        }
    except Exception as e:
        return {"url": url, "status_code": None, "error": str(e)[:200],
                "title": None, "h1": None, "h2_list": [], "meta_description": None, "canonical": None}

async def _fetch_all(urls: list[str]) -> list[dict]:
    sem = asyncio.Semaphore(5)   # 5 concurrent workers per D-META-01
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        async def bounded(url):
            async with sem:
                return await _fetch_url(client, url)
        return await asyncio.gather(*[bounded(u) for u in urls])

# Inside Celery task (sync):
results = asyncio.run(_fetch_all(urls))
```

`asyncio.run()` is safe inside Celery workers that use the default prefork pool (no existing event loop in subprocess).

### Pattern 8: Smoke Test Integration

New routes require:
1. Add `tool_slug` and `tool_job_id` to `SMOKE_IDS` in `tests/fixtures/smoke_seed.py`
2. Seed one `CommerceCheckJob` row (status="complete") with `id = SMOKE_IDS["tool_job_id"]`
3. Add `"tool_slug": "commercialization"` to `SMOKE_IDS` (string param, not UUID)
4. The `/ui/tools/{slug}/` and `/ui/tools/{slug}/{job_id}` routes will be auto-discovered by `discover_routes()` because they start with `/ui/` and return `HTMLResponse`
5. `/ui/tools/{slug}/{job_id}/status` is a partial — add it to `is_partial()` check in `_smoke_helpers.py`

**Note:** `tool_job_id` must be a UUID that resolves to an existing `CommerceCheckJob` row in seed. Since all three tool job models have the same URL pattern `/ui/tools/{slug}/{job_id}`, one seeded job (commercialization) is sufficient — the smoke test only resolves one slug×job_id combination.

### Anti-Patterns to Avoid

- **Separate routers per tool:** Creates 21 route handlers instead of 7. Use TOOL_REGISTRY dispatch instead.
- **Inline HTTP calls in request handlers:** All XMLProxy and httpx calls must be in Celery tasks. The POST handler creates a Job row and dispatches the task; it never fetches external data.
- **AsyncSession in Celery tasks:** Celery uses the sync DB session pattern (`get_sync_db()` context manager). Never import `AsyncSession` or `get_db` inside task files.
- **Separate migration per tool:** One migration file for all 6 tables is cleaner and atomic.
- **Cache layer for tool results:** Unlike SuggestJob, tool results are stored in DB rows (not Redis cache). No Redis read/write in tool task handlers.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTMX polling | Custom JS polling timer | `hx-trigger="load delay:10s"` pattern from suggest_status.html | Already proven in production; self-contained |
| CSV with BOM | Custom CSV writer | stdlib `csv.writer` + `"\ufeff"` BOM prefix | Existing pattern in `export_csv`; Excel compatibility |
| XLSX export | Custom spreadsheet writer | `openpyxl.Workbook()` + `io.BytesIO` | Already in stack; used in other export flows |
| Rate limiting | Custom counter in Redis | `@limiter.limit("10/minute")` decorator from `app.rate_limit` | Already middleware-wired; slowapi handles key=IP by default |
| XMLProxy credentials | Custom credential store | `get_credential_sync(db, "xmlproxy")` | Already encrypted at rest; UI for managing in proxy admin |
| Job status rendering | Custom status widget | Reuse `suggest_status.html` color/structure patterns | Status badge colors, spinner SVG, text patterns are established |
| Concurrency for Meta Parser | threading.Thread pool | `asyncio.Semaphore(5)` + `asyncio.run()` | Cleaner than threads; established project pattern in llm_tasks.py |
| Input validation | Manual len() checks | Pydantic `max_length` in Form or textarea `maxlength` attr + JS counter | Double-layer: JS counter (UX) + server-side check (security) |

---

## Common Pitfalls

### Pitfall 1: Job ID Collision in Smoke Tests

**What goes wrong:** The smoke test resolver uses `job_id` as a generic alias for `suggest_job_id` (line 63 in `smoke_seed.py`). Adding a new tool job model seeded with the same `job_id` UUID will collide if the new model has a different table than `suggest_jobs`.

**Why it happens:** `SMOKE_IDS["job_id"]` is shared across multiple routes by convention.

**How to avoid:** Add a dedicated `tool_job_id` key to `SMOKE_IDS` (distinct UUID) and seed `CommerceCheckJob` with that UUID. Update `_smoke_helpers.py` `PARAM_MAP` lookup to use `tool_job_id` for `/ui/tools/{slug}/{tool_job_id}` routes.

**Warning signs:** `KeyError: 'tool_job_id'` in `resolve_path()` at test collection time.

### Pitfall 2: Sidebar Icon Missing

**What goes wrong:** `components/sidebar.html` renders icons via a chain of `{% if section.icon == '...' %}` conditions. If `"wrench"` is added to NAV_SECTIONS but not to the icon chain in `sidebar.html`, the icon renders as empty space with no error.

**Why it happens:** The icon rendering is purely template logic with no validation.

**How to avoid:** Add the `{% elif section.icon == 'wrench' %}` block with an inline wrench SVG (24x24 viewBox, stroke-width 1.5, stroke currentColor) to match existing icon style.

**Heroicons wrench path:** `M21.75 6.75a4.5 4.5 0 0 1-4.884 4.484c-1.076-.091-2.264.071-2.95.904l-7.152 8.684a2.548 2.548 0 1 1-3.586-3.586l8.684-7.152c.833-.686.995-1.874.904-2.95a4.5 4.5 0 0 1 6.336-4.486l-3.276 3.276a3.004 3.004 0 0 0 2.25 2.25l3.276-3.276c.256.565.398 1.192.398 1.852Z` + `M4.867 19.125h.008v.008h-.008v-.008Z`

### Pitfall 3: asyncio.run() Inside Celery

**What goes wrong:** `asyncio.run()` raises `RuntimeError: This event loop is already running` if called inside an already-running event loop.

**Why it happens:** Celery uses prefork workers (subprocess per worker) — each subprocess has no running event loop, so `asyncio.run()` is safe. However, if a test mocks the Celery task inline (not via `.delay()`), it may run in an async test context that has an active loop.

**How to avoid:** In production Celery tasks, `asyncio.run()` is safe. In tests, mock the external HTTP calls using `respx` so the async path is not exercised directly.

**Warning signs:** `RuntimeError: This event loop is already running` in task unit tests.

### Pitfall 4: XMLProxy Error Code for Balance Exhaustion

**What goes wrong:** XMLProxy returns specific error codes when balance is exhausted. If the task catches all `XMLProxyError` as retryable, it will retry 3 times and then fail instead of saving partial results.

**Why it happens:** `XMLProxyError` is raised for all error codes; balance exhaustion (code 32 = "Daily limit exceeded", code 33 = "Insufficient funds") must be detected and treated as "stop and save partial" not "retry".

**How to avoid:** Check `e.code` before deciding to retry:
```python
except XMLProxyError as e:
    if e.code in (32, 33):
        balance_exhausted = True
        break   # stop processing, save what we have
    raise self.retry(exc=e, countdown=30)
```

**Warning signs:** All 3 retry attempts fail with the same XMLProxy error code 32/33.

### Pitfall 5: Route Order — Slug Conflict

**What goes wrong:** FastAPI matches routes in registration order. If `/ui/tools/{slug}/{job_id}` is registered before `/ui/tools/{slug}/`, FastAPI may try to interpret `export` or `status` in the last segment as a `job_id` UUID and fail validation.

**Why it happens:** FastAPI's path matching is first-match with the router's registered order.

**How to avoid:** Register more-specific routes (with literal path segments like `/status` or `/export`) before the generic `/{job_id}` route. In FastAPI, within one `router.add_api_route()` sequence, more-specific routes registered first win.

**Correct registration order:**
1. `GET /ui/tools/` — index
2. `GET /ui/tools/{slug}/` — tool landing
3. `POST /ui/tools/{slug}/` — submit
4. `GET /ui/tools/{slug}/{job_id}/status` — polling partial (BEFORE /{job_id})
5. `GET /ui/tools/{slug}/{job_id}/export` — export (BEFORE /{job_id})
6. `DELETE /ui/tools/{slug}/{job_id}` — delete
7. `GET /ui/tools/{slug}/{job_id}` — results page (LAST)

### Pitfall 6: Commercialization Formula

**What goes wrong:** The XMLProxy SERP response for a phrase returns the TOP-10 results. Commercialization % is derived from how many results are commercial (ads, marketplaces, online stores) vs informational (Wikipedia, forums, blogs). This classification logic must be explicitly implemented — XMLProxy does not provide it directly.

**Why it happens:** `search_yandex_sync()` returns raw URLs + titles. Domain-based heuristics must classify intent.

**How to avoid:** Implement a domain classifier in `commerce_check_service.py`:
- Commercial signals: domains containing shop, market, купить, price, цена, store, магазин; Yandex Market, Ozon, Wildberries, AliExpress domains
- Geo-dependency signal: presence of regional terms in titles or SERP snippets; or check if results vary significantly by `lr` parameter
- Intent classification: >60% commercial = "commercial"; <20% = "informational"; else "mixed"
- Localized flag: presence of `<domain>.ru` regional subdomains or city-specific terms

Document the exact formula in `commerce_check_service.py` as constants (thresholds are Claude's discretion per the context).

### Pitfall 7: Delete Job While on Results Page

**What goes wrong:** Per the UI-SPEC, if a user deletes a job from the job list while currently viewing that job's results page, they should be redirected to `/ui/tools/{slug}/`. The `hx-delete` approach on the results page itself has no surrounding table row to swap out.

**Why it happens:** The delete button on the results page is not inside a table row — `hx-target="closest tr"` does not apply.

**How to avoid:** On the results page, the delete button uses `hx-delete` + `hx-on::after-request="window.location='/ui/tools/{slug}'"` or returns an `HX-Redirect` header from the DELETE endpoint.

---

## Code Examples

### XMLProxy Credential Retrieval (established pattern)

```python
# Source: app/tasks/position_tasks.py _check_via_xmlproxy
from app.services.service_credential_service import get_credential_sync
from app.services.xmlproxy_service import search_yandex_sync, XMLProxyError

with get_sync_db() as db:
    creds = get_credential_sync(db, "xmlproxy")
if not creds or not creds.get("user") or not creds.get("key"):
    # fail job, return
    ...
# creds["user"] and creds["key"] are decrypted automatically
```

### XLSX Export (openpyxl pattern)

```python
import io
import openpyxl
from fastapi.responses import StreamingResponse

def _build_xlsx(headers: list[str], rows: list[list]) -> StreamingResponse:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="results.xlsx"'},
    )
```

### Navigation Entry — Flat Sidebar Item

```python
# Source: app/navigation.py NAV_SECTIONS — add after keyword-suggest
{
    "id": "tools",
    "label": "Инструменты",
    "icon": "wrench",
    "url": "/ui/tools/",
    "admin_only": False,
    "children": [],
},
```

Active-state detection is automatic: `_URL_TO_NAV` pattern for `/ui/tools/` will match any path starting with `/ui/tools/`.

### Celery App Registration

```python
# Source: app/celery_app.py — add to include list
include=[
    ...
    "app.tasks.commerce_check_tasks",
    "app.tasks.meta_parse_tasks",
    "app.tasks.relevant_url_tasks",
],
```

No new task routes needed — all tool tasks use `queue="default"`.

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| SuggestJob stores results in Redis cache | Tool jobs store results in DB Result tables | DB rows allow rich queries, pagination, and no TTL concern |
| HTMX 1.x `hx-trigger="every Ns"` | HTMX 2.0 `hx-trigger="load delay:Ns"` on partial (self-replacing) | Both work; `load delay:` is the established project pattern |

---

## Environment Availability

Step 2.6: No new external dependencies. All services needed by Phase 24 are either already running (PostgreSQL, Redis, Celery) or in-process (httpx, openpyxl, beautifulsoup4). XMLProxy is a pre-configured external API with credentials stored in the database.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | All job models | Already running | 16.x | — |
| Redis | Celery broker | Already running | 7.2.x | — |
| Celery default worker | Task dispatch | Already running | 5.4.x | — |
| openpyxl | XLSX export | In requirements.txt | 3.1.x | CSV-only if missing |
| beautifulsoup4 + lxml | Meta tag parsing | In requirements.txt | 4.12.x / 5.x | — |
| XMLProxy API | Commercialization + Relevant URL | Pre-configured external | n/a | Partial/failed result if unconfigured |

---

## Open Questions

1. **Commercialization formula thresholds**
   - What we know: Domain heuristics are needed; commercial/informational/mixed classification
   - What's unclear: Exact threshold percentages (60%/20% are arbitrary starting points)
   - Recommendation: Claude's discretion per CONTEXT.md; document constants in service file so they can be tuned

2. **Meta-parser: handle 301/302 redirects**
   - What we know: `httpx.AsyncClient(follow_redirects=True)` handles redirects
   - What's unclear: Whether to record the final URL or the submitted URL in MetaParseResult
   - Recommendation: Record both `input_url` (submitted) and `final_url` (after redirect) in the Result model

3. **Relevant URL: handling of "not found" case**
   - What we know: If no URL from the target domain appears in TOP-10, result is "not found"
   - What's unclear: Whether to store a Result row for "not found" phrases or skip them
   - Recommendation: Store a Result row with `url=None`, `position=None` so the results table is complete

---

## Sources

### Primary (HIGH confidence — live codebase inspection)

| File | Topics Verified |
|------|----------------|
| `app/models/suggest_job.py` | Job model columns, UUID PK, status lifecycle, index pattern |
| `app/tasks/suggest_tasks.py` | Celery task structure, sync DB pattern, partial result handling, retry pattern |
| `app/services/xmlproxy_service.py` | `search_yandex_sync()` API, `XMLProxyError` with `.code`, `_parse_yandex_xml()` return shape |
| `app/routers/keyword_suggest.py` | HTMX polling endpoints, rate limit decorator, export_csv pattern, job dispatch |
| `app/routers/tools.py` | Current stub — router prefix `/ui/tools`, registered in main.py |
| `app/templates/tools/index.html` | Current stub template — replace in Phase 24 |
| `app/templates/keyword_suggest/partials/suggest_status.html` | `hx-trigger="load delay:3s"` pattern, status badge structure |
| `app/navigation.py` | `NAV_SECTIONS` structure, flat vs collapsible entries, `build_sidebar_sections()` |
| `app/templates/components/sidebar.html` | Icon dispatch (`{% if section.icon == '...' %}`), flat entry rendering |
| `app/template_engine.py` | `_NavAwareTemplates.TemplateResponse()` — auto-injects nav context |
| `app/celery_app.py` | `include=` list, queue routing, `task_acks_late=True`, `task_track_started=True` |
| `app/rate_limit.py` | Shared `limiter` instance, `key_func=get_remote_address` |
| `tests/fixtures/smoke_seed.py` | `SMOKE_IDS` dict, seed pattern, `job_id` alias convention |
| `tests/_smoke_helpers.py` | `is_partial()` heuristics, `SMOKE_SKIP`, `discover_routes()` logic |
| `.planning/phases/24-tools-infrastructure-fast-tools/24-UI-SPEC.md` | Complete visual and copywriting contract |
| `.planning/phases/24-tools-infrastructure-fast-tools/24-CONTEXT.md` | Locked decisions D-01 through D-11 |
| `.planning/config.json` | `nyquist_validation: false` (validation section omitted per instructions) |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified present in codebase
- Architecture patterns: HIGH — copied from live reference files with line-level verification
- Common pitfalls: HIGH — derived from code inspection of the exact patterns being reused
- XMLProxy error codes: MEDIUM — codes 32/33 from XMLProxy documentation referenced in codebase; verify against live API on first run

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable stack, no external API changes expected)
