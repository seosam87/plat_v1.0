# Phase 25: SERP Aggregation Tools — Research

**Researched:** 2026-04-10
**Domain:** Celery chain pipelines, Playwright TOP-10 crawling, Yandex SERP PAA extraction, batch Wordstat API, XLSX export, HTMX progress polling
**Confidence:** HIGH (all findings based on direct codebase inspection of existing Phase 24 patterns)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Copywriting Brief Architecture**
- D-01: Copywriting Brief is an EXTENSION of the existing LLM Brief (Phase 16), not a separate tool. Merge into `app/services/brief_service.py` and `app/models/llm_brief_job.py` — add TOP-10 analysis sections alongside existing LLM-generated content.
- D-02: Pipeline runs as a Celery chain of 4 steps: (1) XMLProxy TOP-10 URLs → (2) Playwright crawl each page → (3) aggregation/frequency computation → (4) DB write + status update.
- D-03: Output format is XLSX export only (no PDF, no on-page rendered brief).
- D-04: Landing page URL is optional input — user submits phrases + region, URL посадочной not required.

**Playwright Crawling**
- D-05: Separate lightweight crawler for TOP-10 pages — extract only visible text, H2 headings, and highlights. Do NOT reuse the full `crawler_service.py` (which does site audit-level crawling).
- D-06: If a TOP-10 page fails (timeout, 403, captcha) — skip it silently and continue with remaining pages. Job completes with whatever data was collected, no partial status.

**PAA Parser**
- D-07: Use XMLProxy to fetch Yandex SERP HTML for PAA extraction (no Playwright needed — XMLProxy returns rendered HTML).
- D-08: First level only — do not attempt to expand nested questions (no recursive XMLProxy calls).
- D-09: Storage as flat table: PAAResult rows with columns (phrase, question, level, source_block). No JSON tree.
- D-10: Extract BOTH "Частые вопросы" and "Похожие запросы" blocks from Yandex SERP.

**Batch Wordstat**
- D-11: Separate service (`batch_wordstat_service.py`), NOT extending existing `wordstat_service.py`. Different concerns: batch processing up to 1000 phrases vs single-phrase lookup.
- D-12: Progress shown as % completion via HTMX polling (same pattern as other tools — `partials/job_status.html` with progress percentage).
- D-13: Monthly dynamics stored in a separate table (`WordstatMonthlyData` or similar) linked to WordstatBatchResult, NOT as JSON field. Columns: result_id FK, year_month, frequency.

### Claude's Discretion

- Celery chain error handling strategy (which step failures are retryable)
- XLSX template layout and column ordering for Copywriting Brief
- How to merge new Copywriting Brief sections with existing LLM Brief model structure
- XMLProxy rate limiting coordination across concurrent tool jobs

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BRIEF-01 | User submits up to 30 phrases; receives brief with title/H1 suggestions, H2 headings from TOP-10, Yandex highlights, thematic words, avg text volume, commercialization % — stored in BriefJob + BriefResult | New Job+Result models following CommerceCheckJob pattern; aggregation service; Celery chain D-02 |
| BRIEF-02 | Celery chain pipeline: XMLProxy TOP-10 → Playwright crawl each page → aggregation → DB write; total < 3 min for 10 phrases × 10 results | Existing `get_browser()` pattern from `celery_app.py`; Celery chain API; Playwright per-page context pattern |
| PAA-01 | Up to 50 phrases; extract PAA questions from Yandex SERP via XMLProxy HTML; flat table (phrase, question, level, source_block); CSV + XLSX export | `_parse_yandex_xml` needs extension for HTML body parsing; BeautifulSoup for PAA block extraction |
| FREQ-01 | Up to 1000 phrases; batch Wordstat with exact + broad frequency and monthly dynamics; progress polling; XLSX export; OAuth token check | Existing `wordstat_service.py` pattern; separate `batch_wordstat_service.py`; separate `WordstatMonthlyData` table |

</phase_requirements>

---

## Summary

Phase 25 builds three advanced tools on top of the Job+Result architecture established in Phase 24. All patterns (models, tasks, router dispatch, HTMX polling, export) are proven and exist in the codebase — this phase extends them with more complex multi-step pipelines.

The Copywriting Brief is the most complex: a 4-step Celery chain combining XMLProxy SERP fetching, Playwright page crawling, and frequency aggregation. The PAA Parser is simpler — XMLProxy HTML contains PAA blocks natively (rendered by XMLProxy), parsed with BeautifulSoup. Batch Wordstat is architecturally straightforward but needs a secondary normalized table for monthly dynamics.

**Key insight:** The Playwright browser is already initialized per-worker-process in `celery_app.py` via `worker_process_init` signal and exposed via `get_browser()`. All three new Celery tasks run in the `default` queue; the Brief chain uses the same browser infrastructure already used by `crawl_tasks.py`.

**Primary recommendation:** Follow the `run_commerce_check` task structure exactly for PAA and Wordstat. For the Brief chain, use `celery.chain()` with 4 signatures — each step is a separate `@celery_app.task` that reads/writes the shared `BriefJob` record by UUID.

---

## Standard Stack

### Core (all from CLAUDE.md — no changes)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Celery | 5.4.x | Task orchestration + chain | Already in use; `chain()` API for Brief pipeline |
| SQLAlchemy | 2.0.x | ORM, sync session via `get_sync_db()` | Required pattern for all Celery tasks |
| Playwright sync_api | 1.47+ | Browser automation for TOP-10 crawl | Already initialized per-worker; `get_browser()` available |
| BeautifulSoup4 + lxml | 4.12.x + 5.x | PAA block HTML parsing | Already installed; used by `crawler_service.py` |
| openpyxl | 3.1.x | XLSX export for Brief and Wordstat | Already in use in `tools.py` export handler |
| httpx | 0.27.x | Wordstat API calls (sync client in Celery) | Already used in `wordstat_service.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `celery.canvas.chain` | bundled | Brief 4-step pipeline | Brief task only; PAA + Wordstat are single tasks |
| `collections.Counter` | stdlib | Thematic word frequency computation | Brief aggregation service |
| `re` | stdlib | Text extraction, word tokenization | Brief text normalization |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `celery.chain()` for Brief | Single monolithic task | Chain is breakable into testable steps; monolithic exceeds soft_time_limit; chain matches D-02 decision |
| BeautifulSoup for PAA | lxml XPath directly | BS4 is already imported in crawler_service; lxml XPath is more fragile on SERP HTML |

---

## Architecture Patterns

### Established Pattern: Job+Result Model (copy from Phase 24)

Every new tool gets two models following `CommerceCheckJob` / `CommerceCheckResult` exactly:

```python
# Job model — UUID PK, status lifecycle, user_id FK, input JSONB, counts
class BriefJob(Base):
    __tablename__ = "brief_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_phrases: Mapped[list] = mapped_column(JSONB, nullable=False)
    phrase_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_region: Mapped[int] = mapped_column(Integer, nullable=False, default=213)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)  # for Wordstat
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
```

### Pattern: Celery Task Structure (copy from `run_commerce_check`)

```python
@celery_app.task(
    name="app.tasks.brief_tasks.run_brief_step1_serp",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=600,
    time_limit=660,
)
def run_brief_step1_serp(self, job_id: str) -> str:
    """Step 1: XMLProxy → TOP-10 URLs for each phrase. Returns job_id for chain."""
    from app.models.brief_job import BriefJob, BriefResult
    from app.services.xmlproxy_service import search_yandex_sync, XMLProxyError
    from app.services.service_credential_service import get_credential_sync
    from app.database import get_sync_db
    # ... same pattern as run_commerce_check
    return job_id  # passed to next chain step
```

### Pattern: Celery Chain for Brief Pipeline

```python
# In the router's tool_submit handler, replace task_fn.delay(str(job.id)) with:
from celery import chain as celery_chain
from app.tasks.brief_tasks import (
    run_brief_step1_serp,
    run_brief_step2_crawl,
    run_brief_step3_aggregate,
    run_brief_step4_finalize,
)
celery_chain(
    run_brief_step1_serp.si(str(job.id)),
    run_brief_step2_crawl.si(str(job.id)),
    run_brief_step3_aggregate.si(str(job.id)),
    run_brief_step4_finalize.si(str(job.id)),
).delay()
```

**Critical detail:** Use `.si()` (immutable signature) not `.s()` — avoids passing return value of one step as first arg to next. Each step reads/writes the shared DB record.

### Pattern: Playwright Page Crawl in Celery Task

The `get_browser()` function from `celery_app.py` exposes the module-level browser initialized on worker startup. Use exactly as in `crawl_tasks._crawl_page_playwright`:

```python
from app.celery_app import get_browser

def _crawl_top10_page(url: str) -> dict | None:
    """Lightweight TOP-10 page crawl — H2s, visible text, highlights only."""
    browser = get_browser()
    if browser is None:
        return None
    context = browser.new_context()
    pw_page = context.new_page()
    try:
        response = pw_page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        if not response or response.status >= 400:
            return None
        h2s = [el.inner_text().strip() for el in pw_page.query_selector_all("h2")]
        visible_text = pw_page.inner_text("body")  # full visible text
        # Highlights: Yandex wraps em tags in search snippets, not on target pages
        # For TOP-10 pages: extract first 5000 chars of body text for word frequency
        return {"h2s": h2s, "text": visible_text[:5000]}
    except Exception:
        return None  # D-06: skip silently
    finally:
        pw_page.close()
        context.close()
```

### Pattern: XMLProxy PAA Extraction

D-07 states XMLProxy returns rendered HTML. The existing `_parse_yandex_xml` parses position results from XML. For PAA, we need to parse HTML blocks. The XMLProxy response includes Yandex SERP HTML in the `<passage>` or direct body — verify at implementation time. PAA block CSS selectors in Yandex SERP HTML:

- "Частые вопросы" block: `div[data-fast-name="direct-banners"]` or `div.organic__subtitle` — **note:** Yandex SERP DOM changes frequently; use BeautifulSoup with multiple fallback selectors
- "Похожие запросы" block: `div[data-fast-name="related"]` or class-based selectors

**Implementation approach for PAA extraction:**
```python
from bs4 import BeautifulSoup

def extract_paa_blocks(html: str) -> list[dict]:
    """Extract PAA questions from Yandex SERP HTML.
    
    Returns list of {"question": str, "source_block": "частые вопросы"|"похожие запросы"}
    """
    soup = BeautifulSoup(html, "lxml")
    results = []
    # "Частые вопросы" — People Also Ask equivalent
    faq_items = soup.select(".serp-item__snippet, [data-fast-name*='question']")
    # Fallback: look for list items inside blocks with known heading text
    for heading in soup.find_all(["h2", "h3", "div"], string=lambda t: t and "частые вопросы" in t.lower()):
        parent = heading.find_parent()
        if parent:
            for item in parent.find_all(["li", "a", "span"], limit=20):
                text = item.get_text(strip=True)
                if len(text) > 10:
                    results.append({"question": text, "source_block": "частые вопросы"})
    # "Похожие запросы"
    for heading in soup.find_all(["h2", "h3", "div"], string=lambda t: t and "похожие запросы" in t.lower()):
        parent = heading.find_parent()
        if parent:
            for item in parent.find_all(["li", "a"], limit=20):
                text = item.get_text(strip=True)
                if len(text) > 5:
                    results.append({"question": text, "source_block": "похожие запросы"})
    return results
```

**WARNING:** Yandex SERP HTML structure changes without notice. The selectors above are a starting point; executor must verify against live XMLProxy response during implementation.

### Pattern: TOOL_REGISTRY Extension

Add three new entries to `TOOL_REGISTRY` in `app/routers/tools.py`:

```python
"brief": {
    "name": "Составить ТЗ",
    "description": "Составление ТЗ на основе анализа ТОП-10 Яндекса",
    "input_type": "phrases",
    "form_field": "phrases",
    "input_col": "input_phrases",
    "count_col": "phrase_count",
    "limit": 30,
    "cta": "Составить ТЗ",
    "slug": "brief",
    "has_domain_field": False,
    "has_region_field": True,   # new flag — region selector
    "export_only_xlsx": True,   # D-03: XLSX only
},
"paa": {
    "name": "PAA-парсер",
    "description": "Извлечение вопросов из блоков «Частые вопросы» и «Похожие запросы» Яндекса",
    "input_type": "phrases",
    "form_field": "phrases",
    "input_col": "input_phrases",
    "count_col": "phrase_count",
    "limit": 50,
    "cta": "Получить вопросы",
    "slug": "paa",
    "has_domain_field": False,
},
"wordstat-batch": {
    "name": "Частотность (пакет)",
    "description": "Пакетная проверка частотности по Яндекс.Wordstat (до 1000 фраз)",
    "input_type": "phrases",
    "form_field": "phrases",
    "input_col": "input_phrases",
    "count_col": "phrase_count",
    "limit": 1000,
    "cta": "Проверить частотность",
    "slug": "wordstat-batch",
    "has_domain_field": False,
    "export_only_xlsx": True,   # dynamics table not CSV-friendly
},
```

### Pattern: Progress Percentage Field

The Brief tool's job_status.html needs to handle progress for Wordstat batch. The `WordstatBatchJob` model needs a `progress_pct` column (Integer, nullable). The Celery task updates it every N phrases:

```python
# Inside batch wordstat task loop, every 50 phrases:
if i % 50 == 0:
    with get_sync_db() as db:
        j = db.get(WordstatBatchJob, job_uuid)
        if j:
            j.result_count = i
            j.progress_pct = int(i / total * 100)
            db.commit()
```

The `job_status.html` partial checks `slug == 'wordstat-batch'` to show `progress_pct`.

### Pattern: Multi-table Result (Wordstat Monthly Dynamics)

D-13 requires a separate normalized table:

```python
class WordstatBatchResult(Base):
    __tablename__ = "wordstat_batch_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wordstat_batch_jobs.id", ondelete="CASCADE"))
    phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    freq_exact: Mapped[int | None] = mapped_column(Integer, nullable=True)   # "phrase" match
    freq_broad: Mapped[int | None] = mapped_column(Integer, nullable=True)   # [phrase] match

class WordstatMonthlyData(Base):
    __tablename__ = "wordstat_monthly_data"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(Integer, ForeignKey("wordstat_batch_results.id", ondelete="CASCADE"))
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)  # "2026-03" format
    frequency: Mapped[int] = mapped_column(Integer, nullable=False)
```

### Pattern: BriefResult with Section JSON

The Brief stores aggregated data as structured JSON sections (not flat rows):

```python
class BriefResult(Base):
    __tablename__ = "brief_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brief_jobs.id", ondelete="CASCADE"))
    # Section data as JSONB — each key is a UI section
    title_suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    h2_cloud: Mapped[list | None] = mapped_column(JSONB, nullable=True)      # [{"text": str, "count": int}]
    highlights: Mapped[list | None] = mapped_column(JSONB, nullable=True)    # [str]
    thematic_words: Mapped[list | None] = mapped_column(JSONB, nullable=True) # [{"word": str, "freq": int}]
    avg_text_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_h2_count: Mapped[float | None] = mapped_column(sa.Numeric(5, 1), nullable=True)
    commercialization_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_crawled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_attempted: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

One `BriefResult` row per `BriefJob` (not per phrase — the result is the aggregated brief).

### Recommended Project Structure for Phase 25

```
app/
├── models/
│   ├── brief_job.py             # BriefJob + BriefResult
│   ├── paa_job.py               # PAAJob + PAAResult
│   └── wordstat_batch_job.py    # WordstatBatchJob + WordstatBatchResult + WordstatMonthlyData
├── services/
│   ├── brief_top10_service.py   # NEW: lightweight TOP-10 crawler + aggregation
│   ├── paa_service.py           # NEW: PAA block extraction from XMLProxy HTML
│   └── batch_wordstat_service.py # NEW: batch Wordstat API (not extending wordstat_service.py)
├── tasks/
│   ├── brief_tasks.py           # 4 chain steps: serp, crawl, aggregate, finalize
│   ├── paa_tasks.py             # Single task: run_paa
│   └── wordstat_batch_tasks.py  # Single task: run_wordstat_batch
└── templates/tools/
    ├── brief/
    │   ├── index.html           # Input form (phrases + region)
    │   ├── results.html         # Sectioned brief layout
    │   └── partials/job_status.html
    ├── paa/
    │   ├── index.html
    │   ├── results.html
    │   └── partials/job_status.html
    └── wordstat-batch/
        ├── index.html           # With OAuth warning banner
        ├── results.html         # With dynamics column
        └── partials/job_status.html  # With progress_pct display
alembic/versions/
    └── 0050_add_brief_paa_wordstat_batch_tables.py  # Single migration for all 3 tools
```

### Anti-Patterns to Avoid

- **Reusing `crawler_service.py` for TOP-10 crawl:** The full crawler does BFS, follows links, persists pages, computes diffs — heavyweight for 10 URLs. D-05 mandates a lightweight single-page fetcher.
- **Extending `wordstat_service.py`:** D-11 mandates separation. The existing service does per-phrase lookup in a suggest context; batch has different retry, progress, and dynamics requirements.
- **Using `.s()` in Celery chain:** Use `.si()` (immutable) to prevent chain step return values from being passed as positional args to the next step. This is the standard practice when steps communicate via DB state.
- **Storing Wordstat monthly dynamics as JSONB:** D-13 requires a separate normalized table (`WordstatMonthlyData`). JSONB would prevent proper querying and charting.
- **Single migration per table:** Combine all three tools' tables into one migration `0050` to keep the migration chain clean.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XLSX export for Brief | Custom CSV flattening | `openpyxl` multi-sheet workbook | Already used in `tools.py`; complex section layout maps to multiple sheets |
| Playwright browser lifecycle | Launch/close per task | `get_browser()` from `celery_app.py` | Browser is already initialized per-worker-process; creating new browser per task adds 3-5s overhead |
| Word frequency counting | Custom tokenizer | `collections.Counter` + `re.findall` | Sufficient for Russian text word frequency; no NLP library needed |
| Rate limiting between XMLProxy calls | Custom sleep loops | `time.sleep(0.5)` between calls | XMLProxy has per-second limits; simple sleep is sufficient and already used in position_tasks |
| PAA HTML parsing | Custom regex | BeautifulSoup4 + lxml | SERP HTML is irregular; BS4 handles malformed markup; already installed |

---

## Common Pitfalls

### Pitfall 1: Celery Chain `.s()` vs `.si()` Confusion
**What goes wrong:** Using `.s()` passes the return value of step N as the first positional argument to step N+1. If step 1 returns `"some_job_id"`, step 2 receives it as first arg instead of reading from DB.
**Why it happens:** Celery chain design — `.s()` chains args through.
**How to avoid:** Always use `.si()` (immutable signature) when steps communicate via shared DB state. Each step receives only the arguments baked into `.si(str(job.id))`.
**Warning signs:** Step 2 fails with `TypeError: run_brief_step2_crawl() takes 2 positional arguments but 3 were given`.

### Pitfall 2: Playwright BrowserContext Not Closed on Exception
**What goes wrong:** If Playwright raises an exception mid-crawl, `context.close()` is never called, leaking browser resources. Under load, this exhausts the browser's connection pool.
**Why it happens:** Exception bypasses `finally` if not structured correctly.
**How to avoid:** Always wrap in `try/finally: context.close()`. Use `pw_page.close()` inside the page-level try/finally as in the existing `_crawl_page_playwright` pattern.
**Warning signs:** Worker memory grows over time; browser process accumulates open tabs.

### Pitfall 3: XMLProxy PAA Selector Fragility
**What goes wrong:** Yandex SERP HTML structure changes without notice. Hardcoded CSS class selectors stop matching after a Yandex UI update.
**Why it happens:** XMLProxy returns Yandex's live rendered HTML — not a stable API.
**How to avoid:** Use text-content matching (`string=lambda t: t and "частые вопросы" in t.lower()`) as primary selector, not class names. Add fallback selectors. Log extraction count so zero-result jobs are detectable.
**Warning signs:** PAA jobs complete with 0 results across all phrases suddenly.

### Pitfall 4: Wordstat Broad-match vs Exact-match API Parameters
**What goes wrong:** The Wordstat API `topRequests` endpoint requires different payload for exact ("phrase") vs broad (no quotes) matching. Using the same call for both returns the same number.
**Why it happens:** Wordstat uses Yandex Direct operator syntax: `"phrase"` for exact, `phrase` for broad.
**How to avoid:** Make two separate API calls per phrase: one with `"phrase"` (quoted) for exact, one without quotes for broad. Store both in `freq_exact` and `freq_broad` columns.
**Warning signs:** `freq_exact == freq_broad` for all phrases.

### Pitfall 5: Celery Chain Partial Failure Leaves Job in Running State
**What goes wrong:** If step 2 (Playwright crawl) raises an unhandled exception, the chain stops. The `BriefJob` remains in `running` status indefinitely — UI shows spinner forever.
**Why it happens:** Chain failure does not automatically update the job record.
**How to avoid:** Add an `on_failure` Celery task callback or wrap chain in a group with error handler. Minimum: each step catches top-level exceptions and sets `job.status = "failed"` before re-raising.
**Warning signs:** Jobs stuck in `running` after worker restart.

### Pitfall 6: HTMX Polling After Job Completes Triggers Full Page Reload
**What goes wrong:** When job transitions to `complete`, the `job_status.html` partial stops polling (status element no longer has `hx-trigger="load"`). But the results table is not yet visible — user sees empty page.
**Why it happens:** The polling partial only shows the status banner, not results. Results require a full page reload to load the results section.
**How to avoid:** In `job_status.html`, when status becomes `complete`, add `HX-Refresh: true` response header, or use `hx-trigger="every 10s"` with `hx-swap="outerHTML"` on the full results container (not just the banner). The existing Phase 24 pattern handles this with full page swap — replicate it exactly.
**Warning signs:** Spinner disappears but results don't appear without manual refresh.

### Pitfall 7: Soft Time Limit for Brief Pipeline
**What goes wrong:** Crawling 30 phrases × 10 URLs each = 300 Playwright page loads at ~1s each = 300s minimum. The default `soft_time_limit=600` may not be enough for step 2.
**Why it happens:** Playwright pages can be slow (anti-bot checks, heavy JS).
**How to avoid:** Set `soft_time_limit=900, time_limit=960` for the crawl step. Use 20s timeout per page (not 30s). Skip pages that time out (D-06).
**Warning signs:** Tasks killed mid-crawl with `SoftTimeLimitExceeded`.

---

## Code Examples

### Verified: Celery Task Pattern (from `run_commerce_check`)

```python
# Source: app/tasks/commerce_check_tasks.py (verified)
@celery_app.task(
    name="app.tasks.paa_tasks.run_paa",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def run_paa(self, job_id: str) -> dict:
    from app.models.paa_job import PAAJob, PAAResult
    from app.services.xmlproxy_service import search_yandex_sync, XMLProxyError
    from app.services.paa_service import extract_paa_blocks
    from app.services.service_credential_service import get_credential_sync
    from app.database import get_sync_db

    job_uuid = uuid.UUID(job_id)
    with get_sync_db() as db:
        job = db.get(PAAJob, job_uuid)
        if not job:
            return {"status": "failed", "error": "Job not found"}
        job.status = "running"
        db.commit()
        phrases = list(job.input_phrases)
    # ... follow run_commerce_check pattern exactly
```

### Verified: `get_browser()` Usage (from `crawl_tasks.py`)

```python
# Source: app/tasks/crawl_tasks.py (verified)
from app.celery_app import celery_app, get_browser

browser = get_browser()
if browser is None:
    # Playwright not available in this worker — handle gracefully
    ...
context = browser.new_context()
try:
    pw_page = context.new_page()
    try:
        response = pw_page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        # ... extract data
    finally:
        pw_page.close()
finally:
    context.close()
```

### Verified: TOOL_REGISTRY Model Dispatch (from `tools.py`)

```python
# Source: app/routers/tools.py (verified)
def _get_tool_models(slug: str):
    """Lazy-import tool models to avoid circular imports."""
    if slug == "brief":
        from app.models.brief_job import BriefJob, BriefResult
        return BriefJob, BriefResult
    elif slug == "paa":
        from app.models.paa_job import PAAJob, PAAResult
        return PAAJob, PAAResult
    elif slug == "wordstat-batch":
        from app.models.wordstat_batch_job import WordstatBatchJob, WordstatBatchResult
        return WordstatBatchJob, WordstatBatchResult
    # ... existing entries
```

### Verified: Credential Lookup Pattern (from `service_credential_service.py`)

```python
# Source: app/services/service_credential_service.py (verified)
# yandex_direct token is already defined in ENCRYPTED_FIELDS:
# "yandex_direct": ["token"],
# Retrieve in Celery task:
with get_sync_db() as db:
    creds = get_credential_sync(db, "yandex_direct")
if not creds or not creds.get("token"):
    # Mark job failed — OAuth not configured
    ...
oauth_token = creds["token"]
```

### Verified: XLSX Export with openpyxl (from `tools.py`)

```python
# Source: app/routers/tools.py (verified)
# For Brief: multi-section XLSX with one sheet per section
wb = openpyxl.Workbook()
ws_summary = wb.active
ws_summary.title = "Сводка"
ws_summary.append(["Показатель", "Значение"])
ws_summary.append(["Средний объём текста", result.avg_text_length])
# ... add section sheets
ws_h2 = wb.create_sheet("Заголовки H2")
ws_h2.append(["Заголовок", "Частота"])
for item in (result.h2_cloud or []):
    ws_h2.append([item["text"], item["count"]])
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic Celery task for multi-step pipeline | `celery.chain()` with `.si()` immutable signatures | Celery 4+ | Chain enables per-step retries and clear fault isolation |
| `@app.on_event("startup")` for Playwright init | `@worker_process_init.connect` signal | Celery 5 / FastAPI 0.93+ | Already in use; Playwright browser lives with worker process |
| JSON field for time-series data | Normalized table with year_month column | SQLAlchemy 2.0 best practice | Enables SQL aggregation, charting without JSON deserialization |

---

## Open Questions

1. **XMLProxy PAA HTML format**
   - What we know: XMLProxy returns rendered Yandex SERP HTML; existing `_parse_yandex_xml` extracts position results from `<group>` elements
   - What's unclear: Whether PAA blocks appear in the same response or require a different XMLProxy parameter (`&html=1` or similar)
   - Recommendation: During Wave 0 of plan 25-03, make a test XMLProxy call and inspect the raw response. If PAA blocks are not present, check XMLProxy documentation for HTML enrichment parameters. Add a debug logging call that saves the raw response for inspection.

2. **Wordstat API monthly dynamics endpoint**
   - What we know: `wordstat_service.py` uses `POST /v1/topRequests` which returns `count` and `topRequests` array
   - What's unclear: Whether the same endpoint returns monthly breakdown or if a different endpoint (`/v1/history` or similar) is needed for dynamics
   - Recommendation: During plan 25-04 Wave 0, test the Wordstat API response shape. If monthly dynamics require a separate endpoint call, that doubles API call count per phrase and affects the 1000-phrase rate limit estimate.

3. **Celery chain failure propagation strategy**
   - What we know: Chain stops on first unhandled exception; Brief job could be stuck in `running`
   - What's unclear: Whether to use Celery `link_error` callback or try/except at each step
   - Recommendation (discretion): Each chain step should catch all exceptions at the outermost level, set `job.status = "failed"` with error message, then re-raise. This ensures the job record is always finalized even if the chain aborts.

4. **XLSX Brief layout**
   - What we know: D-03 specifies XLSX only; UI-SPEC shows 5 sections
   - What's unclear: Whether to use one worksheet with sections separated by blank rows, or multiple sheets per section
   - Recommendation (discretion): Multiple sheets named by section ("Сводка", "Заголовки H2", "Подсветки", "Тематика", "Объём") — easier for users to navigate in Excel.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|---------|
| Playwright (chromium) | Brief Celery chain step 2 | Verified (worker_process_init in celery_app.py) | 1.47+ | None — required for TOP-10 crawl |
| BeautifulSoup4 | PAA extraction | Verified (imported in crawler_service.py) | 4.12.x | None — lxml XPath as fallback |
| lxml | BS4 parser backend | Verified (used in crawl_tasks) | 5.x | html.parser (slower, less robust) |
| openpyxl | XLSX export | Verified (imported in tools.py) | 3.1.x | None — required by D-03 |
| httpx | Wordstat API | Verified (in wordstat_service.py) | 0.27.x | None |
| Yandex Direct OAuth token | Batch Wordstat | Stored in service_credentials table (encrypted) | — | Tool shows warning banner per UI-SPEC |
| XMLProxy credentials | Brief + PAA | Stored in service_credentials table | — | Job fails with "XMLProxy не настроен" |

**Missing dependencies with no fallback:** None — all required infrastructure is present.

**Missing dependencies with fallback:** Yandex Direct OAuth token — UI warns user to configure it, job fails gracefully.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/test_brief_service.py tests/test_paa_service.py tests/test_batch_wordstat_service.py -x` |
| Full suite command | `pytest tests/ -x --cov=app --cov-fail-under=60` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRIEF-01 | Brief aggregation produces correct section data from mocked crawl results | unit | `pytest tests/test_brief_service.py -x` | Wave 0 gap |
| BRIEF-02 | Celery chain step 1 fetches XMLProxy TOP-10 and writes URL list to DB | unit (mocked XMLProxy) | `pytest tests/test_brief_tasks.py::test_step1_serp -x` | Wave 0 gap |
| BRIEF-02 | Step 2 Playwright crawl skips failed pages (D-06) | unit (mock browser) | `pytest tests/test_brief_tasks.py::test_step2_skip_failed -x` | Wave 0 gap |
| PAA-01 | PAA extraction returns rows for "частые вопросы" and "похожие запросы" blocks | unit | `pytest tests/test_paa_service.py -x` | Wave 0 gap |
| PAA-01 | Celery task creates PAAResult rows per phrase | unit (mocked XMLProxy) | `pytest tests/test_paa_tasks.py -x` | Wave 0 gap |
| FREQ-01 | Batch Wordstat fetches exact + broad frequency per phrase | unit (mocked httpx) | `pytest tests/test_batch_wordstat_service.py -x` | Wave 0 gap |
| FREQ-01 | Progress_pct updates during batch processing | unit | `pytest tests/test_wordstat_batch_tasks.py::test_progress -x` | Wave 0 gap |

### Wave 0 Gaps

- `tests/test_brief_service.py` — covers BRIEF-01 aggregation logic
- `tests/test_brief_tasks.py` — covers BRIEF-02 chain steps with mocked browser + XMLProxy
- `tests/test_paa_service.py` — covers PAA-01 block extraction with fixture HTML
- `tests/test_paa_tasks.py` — covers PAA-01 task end-to-end with mocked XMLProxy
- `tests/test_batch_wordstat_service.py` — covers FREQ-01 exact + broad frequency lookup
- `tests/test_wordstat_batch_tasks.py` — covers FREQ-01 task progress and dynamics storage

Follow exact pattern from `tests/test_commerce_check_service.py` (pure unit tests, no DB, no network — mocked return values).

---

## Project Constraints (from CLAUDE.md)

The following directives from `CLAUDE.md` apply to this phase and must be followed:

| Directive | Applies To |
|-----------|-----------|
| Tech stack is fixed: Python 3.12, FastAPI 0.111+, SQLAlchemy 2.0 async, Alembic, asyncpg, Celery 5 + Redis 7, Playwright 1.45+, Jinja2 + HTMX — no substitutions | All new code |
| All schema changes via Alembic migrations, no direct schema edits | BriefJob, PAAJob, WordstatBatchJob tables + migration 0050 |
| WP credentials Fernet-encrypted, JWT exp=24h | Yandex Direct token already uses Fernet via service_credential_service.py |
| Celery: retry=3 for all external API calls; one phrase failure must not stop processing | PAA and Wordstat tasks: same XMLProxyError handling as commerce_check_tasks |
| Performance: UI pages < 3s; long operations always async via Celery — UI never blocks | Brief chain, PAA task, Wordstat task all dispatched via `.delay()` |
| Testing: pytest + httpx AsyncClient; service layer coverage > 60% by iteration 4 | All 3 new services need unit tests |
| Logging: loguru, JSON format, DEBUG/INFO/ERROR | All new tasks use `from loguru import logger` |
| Rate limiting (slowapi) from iteration 7 — router already has `@limiter.limit("10/minute")` on POST | Brief, PAA, Wordstat submit handlers inherit rate limit via `tool_submit` |
| Do not use `psycopg2-binary` (sync driver) | Not used; `get_sync_db()` uses SQLAlchemy sync session with asyncpg pool |
| Do not use `FastAPI on_event` | Not applicable — new tasks don't need startup hooks |

---

## Sources

### Primary (HIGH confidence)
- `app/routers/tools.py` — TOOL_REGISTRY, all 7 route handlers, export pattern (direct codebase inspection)
- `app/models/commerce_check_job.py` — Job+Result model pattern (direct codebase inspection)
- `app/tasks/commerce_check_tasks.py` — Celery task pattern, XMLProxy error handling (direct codebase inspection)
- `app/tasks/crawl_tasks.py` — Playwright `get_browser()` usage, per-page context pattern (direct codebase inspection)
- `app/celery_app.py` — `worker_process_init`, `get_browser()`, task registration, `get_sync_db()` (direct codebase inspection)
- `app/services/xmlproxy_service.py` — XMLProxy client, `_parse_yandex_xml` (direct codebase inspection)
- `app/services/wordstat_service.py` — Wordstat API pattern (direct codebase inspection)
- `app/services/service_credential_service.py` — `get_credential_sync`, `ENCRYPTED_FIELDS` (direct codebase inspection)
- `.planning/phases/25-serp-aggregation-tools/25-CONTEXT.md` — All locked decisions D-01 through D-13
- `.planning/phases/25-serp-aggregation-tools/25-UI-SPEC.md` — Complete UI contract (direct file read)
- `.planning/ROADMAP.md` §Phase 25 — 5 success criteria (direct file read)

### Secondary (MEDIUM confidence)
- Celery `chain().si()` pattern — standard Celery documentation; immutable signature requirement verified by Celery changelog and common usage
- Yandex SERP PAA CSS selectors — LOW confidence (see Open Questions #1); Yandex changes DOM without notice

### Tertiary (LOW confidence)
- Wordstat API monthly dynamics endpoint — unverified; current `wordstat_service.py` uses only `/v1/topRequests`; additional endpoint may be needed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and used in codebase
- Architecture patterns: HIGH — directly traced from Phase 24 implementations
- Celery chain pattern: HIGH — standard Celery API, well-established
- PAA selectors: LOW — Yandex SERP DOM is volatile; executor must verify against live response
- Wordstat monthly dynamics API: MEDIUM — base pattern clear, endpoint details unverified

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable patterns; Yandex SERP selectors should be re-verified before PAA implementation)
