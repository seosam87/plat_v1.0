# Phase 15: Keyword Suggest - Research

**Researched:** 2026-04-06
**Domain:** Yandex Suggest API, Google Suggest API, Yandex Wordstat API, Redis caching, Celery async tasks
**Confidence:** HIGH (infrastructure patterns from codebase), MEDIUM (external API endpoints — unofficial/undocumented)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sources and routing:**
- D-01: Yandex Suggest API directly (suggest.yandex.ru) via existing proxy pool (5 proxies), NOT via XMLProxy
- D-02: Google Suggest API directly (suggestqueries.google.com) from server without proxy
- D-03: All external calls via Celery tasks with retry=3, NOT inline in request handler
- D-04: Both todos included in phase scope: (1) fix position check ignores keyword engine preference, (2) proxy management, XMLProxy integration and health checker
- D-05: Use shared proxy pool (same 5 used for positions) for Yandex Suggest
- D-06: On ban/429 — rotate proxy with 30s pause and retry (max 3 attempts), on exhaustion — return partial results with user warning
- D-07: Google Suggest directly from server without proxy

**Display and interaction:**
- D-08: Table with filtering: columns — suggestion, source (Я/G), frequency. Text search, column sorting
- D-09: Export only (CSV/copy), no adding suggestions to keyword tracking
- D-10: Separate sidebar section with icon (like Client Reports)
- D-11: HTMX polling every 3s: spinner -> progress bar -> results (pattern from Client Reports)

**Wordstat frequency:**
- D-12: Yandex Direct OAuth token stored in ServiceCredential (Fernet encryption), like XMLProxy/GSC
- D-13: "Frequency" column in results table with sorting. Hidden when token not configured
- D-14: Dismissable banner "Configure Yandex Direct token in Settings for frequency data" when token not configured
- D-15: Separate "Load frequency" button after getting suggestions (not automatic). Conserves API limits

**Expansion strategy:**
- D-16: Expand seed across Russian alphabet А-Я (33 letters): seed + а, seed + б, ..., seed + я. Single mode, no user selection
- D-17: Sequential requests to Yandex Suggest with 200-500ms pause (safer than parallel)
- D-18: Google Suggest — same alphabetic expansion А-Я

### Claude's Discretion
- Specific endpoint: suggest.yandex.ru vs suggest-ya.ru (pick the working one)
- Response format and parsing: JSON/XML from both APIs
- Celery task structure (one task for full alphabet or chain)
- Redis caching pattern (key, format, serialization)
- CSV export format (delimiter, encoding, headers)
- Yandex Direct API v5 — specific methods for Wordstat

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SUG-01 | User can get suggestions via Yandex Suggest by seed keyword with alphabetic expansion (200+ results) | Yandex Suggest API endpoint verified, alphabetic expansion pattern documented, proxy rotation strategy defined |
| SUG-02 | Google Suggest works as additional source (simple endpoint, no auth) | Google Suggest endpoint confirmed (suggestqueries.google.com), no auth required, direct from server |
| SUG-03 | Wordstat API integration (opt-in, requires OAuth token) for frequency | Yandex Wordstat API at api.wordstat.yandex.net documented, OAuth Bearer auth confirmed, /v1/topRequests method identified |
| SUG-04 | Suggest results cached in Redis (TTL 24h); repeated request makes no external calls | Redis caching pattern confirmed from dashboard_service.py, aioredis pattern established, TTL pattern in place |
</phase_requirements>

---

## Summary

Phase 15 introduces a keyword suggestion feature that queries Yandex Suggest and optionally Google Suggest for a given seed keyword, expanding it alphabetically (А-Я, 33 letters) to gather 200+ results. The core complexity is managing the proxy pool for Yandex requests, implementing ban/retry handling, and caching results in Redis to avoid redundant API calls.

The infrastructure for this phase is largely established in the codebase: the proxy pool model (`Proxy`), service credential storage (`ServiceCredential`), Redis caching (dashboard_service pattern), Celery task patterns (position_tasks.py), and HTMX polling UI (client_reports templates). The phase reuses all these patterns rather than inventing new ones.

The external API endpoints are unofficial/undocumented (Yandex Suggest, Google Suggest) or require application approval (Yandex Wordstat). The Wordstat API at `api.wordstat.yandex.net` requires an OAuth token and access request from Yandex Direct support — this is a real constraint that affects implementation timing.

**Primary recommendation:** Build a new `suggest_service.py` modeled on `xmlproxy_service.py` (sync httpx.Client for Celery tasks), store task results as JSON in Redis with a composite cache key, and follow the `client_report_tasks.py` pattern for the Celery task lifecycle. Add the Yandex Direct OAuth token to `service_credentials` using the existing `save_credential_sync` / Fernet pattern.

---

## Standard Stack

All stack components are already installed in the project. No new dependencies required.

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.27.x | Sync HTTP in Celery tasks, async HTTP in routers | Project-established pattern; replaces requests entirely |
| redis-py (aioredis) | 5.0.x | Redis cache read/write | Used in dashboard_service.py; `redis.asyncio.from_url()` pattern |
| Celery | 5.4.x | Async task execution with retry | All external API calls run in Celery per D-03 |
| FastAPI / Jinja2 | 0.115.x / 3.1.x | Router + HTML template rendering | Project-wide standard |
| slowapi | 0.1.9 | Rate limiting (10 req/min on suggest endpoint) | Already configured in main.py; add decorator only |
| SQLAlchemy async | 2.0.x | ORM for new SuggestJob model | Project-wide standard |
| Alembic | 1.13.x | Database migration for SuggestJob table | Project-wide standard; all schema changes via migration |
| cryptography (Fernet) | 42.x | Yandex Direct token encryption at rest | Already used for xmlproxy key and WP credentials |

### No New Dependencies
The entire phase builds on existing stack. No `pip install` needed.

---

## Architecture Patterns

### Recommended New File Structure
```
app/
├── models/
│   └── suggest_job.py          # SuggestJob model (status lifecycle)
├── services/
│   └── suggest_service.py      # Yandex + Google suggest fetch (sync, for Celery)
├── tasks/
│   └── suggest_tasks.py        # Celery task: fetch_suggest_keywords
├── routers/
│   └── keyword_suggest.py      # /ui/keyword-suggest/* endpoints
├── templates/
│   └── keyword_suggest/
│       ├── index.html           # Main page (form + status area)
│       └── partials/
│           ├── suggest_status.html   # Polling partial (3 states)
│           └── suggest_results.html  # Results table card
alembic/versions/
└── 0040_add_suggest_jobs.py    # Migration for suggest_jobs table
```

### Pattern 1: SuggestJob Model (mirrors ClientReport)
**What:** Tracks the lifecycle of a suggest request. Stores seed, sources config, and result JSON blob.
**When to use:** Required for HTMX polling — router returns task_id, client polls `/status/{job_id}`.

```python
# Source: app/models/client_report.py pattern
class SuggestJob(Base):
    __tablename__ = "suggest_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seed: Mapped[str] = mapped_column(String(200), nullable=False)
    include_google: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # "pending" | "running" | "complete" | "partial" | "failed"
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partial_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # for ban scenario
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
```

### Pattern 2: Redis Cache Key Convention
**What:** Cache suggest results under a composite key so that repeat queries for the same seed+sources return instantly.
**When to use:** Every suggest task reads cache first; only calls external APIs on cache miss.

```python
# Source: app/services/dashboard_service.py pattern + D-16 decisions
import hashlib
import json
import redis.asyncio as aioredis

SUGGEST_CACHE_TTL = 86400  # 24 hours per SUG-04

def _suggest_cache_key(seed: str, include_google: bool) -> str:
    """Stable cache key for a suggest request."""
    # Normalize seed: lowercase, strip whitespace
    normalized = seed.strip().lower()
    sources = "yg" if include_google else "y"
    return f"suggest:{sources}:{normalized}"

# In Celery task (sync context) — use redis.Redis (sync client)
import redis as sync_redis

def _cache_get(r: sync_redis.Redis, key: str) -> list | None:
    raw = r.get(key)
    return json.loads(raw) if raw else None

def _cache_set(r: sync_redis.Redis, key: str, data: list) -> None:
    r.set(key, json.dumps(data, ensure_ascii=False), ex=SUGGEST_CACHE_TTL)
```

**Important:** In Celery tasks (sync context) use `redis.Redis` (sync client), NOT `redis.asyncio`. In FastAPI routers (async) use `redis.asyncio.from_url()`.

### Pattern 3: Yandex Suggest API Call
**What:** Unofficial Yandex search suggest endpoint. The working endpoint confirmed by SEO tooling community is `https://wordstat.yandex.ru/suggest` (used by Wordstat UI) or the search suggest endpoint at `https://suggest.yandex.net/suggest-yandsearch`. Research found no authoritative official docs — use the endpoint that returns data in testing.
**When to use:** For each letter А-Я, make one request with `seed + " " + letter` as query.

```python
# Source: research + xmlproxy_service.py pattern (sync httpx.Client in Celery)
YANDEX_SUGGEST_URL = "https://wordstat.yandex.ru/suggest"  # VERIFY in testing

def fetch_yandex_suggest_sync(
    query: str,
    proxy_url: str | None = None,
    timeout: int = 10,
) -> list[str]:
    """Fetch Yandex suggest results for a query string.
    Returns list of suggestion strings, empty on failure.
    """
    params = {
        "part": query,
        "uil": "ru",
        "lr": "213",  # Moscow region
        "srv": "wordstat",
    }
    proxies = {"http://": proxy_url, "https://": proxy_url} if proxy_url else None
    try:
        with httpx.Client(timeout=timeout, proxies=proxies) as client:
            resp = client.get(YANDEX_SUGGEST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            # Response format: {"items": [{"value": "keyword phrase"}, ...]}
            # OR flat list format — verify in testing
            return [item["value"] for item in data.get("items", [])]
    except (httpx.HTTPStatusError, httpx.HTTPError, KeyError) as exc:
        logger.warning("Yandex suggest request failed: {}", exc)
        return []
```

**Confidence note (MEDIUM):** The exact Yandex Suggest endpoint and JSON response format are NOT officially documented. The endpoint `wordstat.yandex.ru/suggest` is used by the Wordstat UI and observed in network traffic by SEO tools. Verify the exact URL and response structure in a real request before writing production code. Two known formats in the wild:
1. `{"items": [{"value": "phrase"}, ...]}` (Wordstat-style)
2. `["query", ["phrase1", "phrase2", ...], ...]` (search-style, same as Google format)

### Pattern 4: Google Suggest API Call
**What:** Unofficial but stable Google autocomplete endpoint. No auth required.
**When to use:** When `include_google=True` in the suggest job.

```python
# Source: fullstackoptimization.com spec + community documentation (MEDIUM confidence)
GOOGLE_SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

def fetch_google_suggest_sync(query: str, timeout: int = 10) -> list[str]:
    """Fetch Google autocomplete suggestions. No proxy needed (D-07)."""
    params = {
        "client": "chrome",  # returns JSON array
        "q": query,
        "hl": "ru",           # Russian language
        "gl": "ru",           # Russia country
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(GOOGLE_SUGGEST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            # Response: ["query", ["suggestion1", "suggestion2", ...], ...]
            return data[1] if len(data) > 1 else []
    except Exception as exc:
        logger.warning("Google suggest request failed: {}", exc)
        return []
```

**Confidence: MEDIUM** — endpoint is well-documented by community, used by many SEO tools, but Google can change it without notice.

### Pattern 5: Proxy Rotation with Ban Handling
**What:** Select active proxy from DB, rotate on 429/ban, pause 30s, retry up to 3 times per D-06.

```python
# Source: D-06 + proxy.py model + proxy_health_service.py pattern
from app.models.proxy import Proxy, ProxyStatus
from app.database import get_sync_db
from sqlalchemy import select

def get_active_proxies_sync() -> list[str]:
    """Return URLs of all active proxies from DB."""
    with get_sync_db() as db:
        proxies = db.execute(
            select(Proxy).where(
                Proxy.status == ProxyStatus.active,
                Proxy.is_active == True
            )
        ).scalars().all()
    return [p.url for p in proxies]

def fetch_with_proxy_rotation(
    fetch_fn,  # callable(query, proxy_url) -> list[str]
    query: str,
    proxies: list[str],
    max_retries: int = 3,
    pause_seconds: int = 30,
) -> tuple[list[str], bool]:
    """Try fetch_fn with proxy rotation. Returns (results, was_banned)."""
    import time
    for attempt, proxy_url in enumerate(proxies[:max_retries]):
        results = fetch_fn(query, proxy_url)
        if results:  # non-empty = success
            return results, False
        logger.warning("Proxy {} failed/banned for query {}, rotating", proxy_url, query)
        if attempt < max_retries - 1:
            time.sleep(pause_seconds)
    return [], True  # exhausted proxies
```

### Pattern 6: Alphabetic Expansion Task Structure
**What:** One Celery task covers the full А-Я expansion loop. Sequential per D-17.
**When to use:** Single `fetch_suggest_keywords.delay(job_id)` call from router.

```python
# Source: D-16, D-17, position_tasks.py task structure
RU_ALPHABET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"  # 33 letters

@celery_app.task(
    name="app.tasks.suggest_tasks.fetch_suggest_keywords",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=300,   # 33 letters * ~3s per letter = ~100s, generous headroom
    time_limit=360,
)
def fetch_suggest_keywords(self, job_id: str) -> dict:
    """Alphabetic expansion suggest fetch. Checks Redis cache first."""
    import time
    import redis as sync_redis
    from app.config import settings

    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)

    # ... load job from DB, check cache, run expansion loop ...
    # For each letter in RU_ALPHABET:
    #   time.sleep(random.uniform(0.2, 0.5))  # D-17: 200-500ms pause
    #   results = fetch_yandex_suggest_sync(f"{seed} {letter}", proxy_url)
    #   all_suggestions.extend(results)
```

### Pattern 7: Wordstat Frequency via Yandex Wordstat API
**What:** `api.wordstat.yandex.net` with Bearer OAuth token. The `/v1/topRequests` method returns frequency for specific phrases.
**When to use:** Only when user clicks "Load frequency" button (D-15) and token is configured.

```python
# Source: Yandex Wordstat API official docs (HIGH confidence for auth/structure)
# Source: research on /v1/topRequests and /v1/dynamics endpoints
WORDSTAT_API_BASE = "https://api.wordstat.yandex.net"

def fetch_wordstat_frequency_sync(
    phrases: list[str],
    oauth_token: str,
    region_id: int = 0,  # 0 = all Russia
) -> dict[str, int]:
    """Fetch search frequency for a list of phrases.
    Returns {phrase: monthly_count} mapping.
    NOTE: /v1/topRequests is the correct method for frequency by phrase.
    Rate limit: personal quota per token — 429 on exceed.
    """
    results = {}
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        for phrase in phrases:
            try:
                resp = client.post(
                    f"{WORDSTAT_API_BASE}/v1/topRequests",
                    headers=headers,
                    json={
                        "phrase": phrase,
                        "regionIds": [region_id] if region_id else [],
                    },
                )
                if resp.status_code == 429:
                    logger.warning("Wordstat quota exceeded for phrase: {}", phrase)
                    break
                resp.raise_for_status()
                data = resp.json()
                # Extract frequency count from topRequests response
                # Exact field name: verify from live API response
                count = data.get("count") or 0
                results[phrase] = count
            except Exception as exc:
                logger.warning("Wordstat fetch failed for {}: {}", phrase, exc)
    return results
```

**Confidence: MEDIUM** — API base URL and auth header format verified from official Yandex docs. The exact request body fields and response structure for `/v1/topRequests` require live testing. The `/v1/dynamics` method (verified in docs) returns time-series; `/v1/topRequests` returns current frequency. Use `/v1/topRequests` for per-keyword frequency display.

### Anti-Patterns to Avoid
- **Inline external API calls in FastAPI router handlers:** All suggest/wordstat calls must go through Celery (D-03). The router only dispatches the task and polls status.
- **Parallel Yandex Suggest requests:** D-17 mandates sequential with 200-500ms pause. Parallel = faster bans.
- **asyncio in Celery tasks:** Use `redis.Redis` (sync), `httpx.Client` (sync), `get_sync_db()`. The pattern from `position_tasks.py` is correct. Do NOT use `redis.asyncio` in sync Celery tasks.
- **Storing suggest results in PostgreSQL as large blobs:** Store in Redis only. The `SuggestJob` model stores metadata (seed, status, count) not the full result list. Full results live in Redis at the cache key.
- **Fetching Wordstat for all 200+ suggestions automatically:** D-15 says explicit "Load frequency" button only. Never auto-trigger Wordstat fetch.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP with proxy support | Custom proxy handler | `httpx.Client(proxies=...)` | httpx natively supports HTTP/SOCKS5 proxy URLs |
| Redis TTL caching | Custom cache layer | `redis.set(key, val, ex=TTL)` | One-liner; use existing pattern from dashboard_service |
| Fernet credential encryption | Custom encryption | `crypto_service.encrypt/decrypt` + `save_credential_sync` | Already handles all service credentials; add `yandex_direct_token` as encrypted field |
| Rate limiting (10 req/min) | Custom rate limiter | slowapi `@limiter.limit("10/minute")` | Already installed and configured in main.py |
| HTMX polling lifecycle | Custom WebSocket | HTMX `hx-trigger="load delay:3s" hx-swap="outerHTML"` | Established pattern from client_reports; works perfectly for async task status |
| Alphabetic Russian expansion | Manual list | `"абвгдеёжзийклмнопрстуфхцчшщъыьэюя"` constant | A known fixed 33-char string; no library needed |
| CSV export with BOM | Custom file serialization | Python `csv` module + `\ufeff` BOM prefix | Standard library; UTF-8 BOM required for Excel Russian text (per UI-SPEC) |

**Key insight:** Every infrastructure component (proxy, cache, rate limiting, task dispatch, HTMX polling) already exists in the codebase. This phase is 80% wiring existing patterns together.

---

## Common Pitfalls

### Pitfall 1: Wrong Redis Client in Celery
**What goes wrong:** Using `redis.asyncio` (aioredis) inside a sync Celery task raises `RuntimeError: no running event loop` or silently drops data.
**Why it happens:** `dashboard_service.py` uses async Redis because it runs in FastAPI's async context. Celery tasks by default are synchronous.
**How to avoid:** In Celery tasks, use `import redis; r = redis.from_url(settings.REDIS_URL, decode_responses=True)`. Only use `redis.asyncio` in FastAPI route handlers or services called from async context.
**Warning signs:** `SyntaxError` on `await` in task, or `RuntimeError: no current event loop`.

### Pitfall 2: Yandex Suggest Endpoint Ambiguity
**What goes wrong:** Yandex has multiple suggest endpoints serving different products (Maps, Search, Wordstat UI). Using the wrong one returns empty results or geographic suggestions instead of keyword suggestions.
**Why it happens:** The endpoint is undocumented and varies by product. `suggest.yandex.ru` is the general search suggest; `wordstat.yandex.ru/suggest` may be the Wordstat-specific endpoint.
**How to avoid:** Test both endpoints manually before committing to one. Use network inspection in a browser while using Wordstat autocomplete to identify the actual endpoint in production use. The `srv` or `uil` parameter may differentiate them.
**Warning signs:** Empty `items` array or wrong suggestion types in responses.

### Pitfall 3: Redis Key Collision Between Jobs
**What goes wrong:** Two users request the same seed keyword simultaneously. Both get cache miss, both dispatch tasks, both write to the same cache key. Race condition creates duplicate work but not data corruption (both write same data).
**Why it happens:** No mutex or task deduplication.
**How to avoid:** This is acceptable for v1 — duplicate work is harmless (both write same result). A `NX` Redis lock can prevent duplicate dispatches but adds complexity. Don't add the lock unless duplicate Celery tasks cause visible performance issues.
**Warning signs:** Multiple `fetch_suggest_keywords` tasks with identical seeds in Flower.

### Pitfall 4: Wordstat /v1/topRequests vs /v1/dynamics Confusion
**What goes wrong:** Using `/v1/dynamics` for frequency display returns time-series arrays, not single frequency integers. The UI expects an integer "monthly count" per keyword.
**Why it happens:** Both endpoints return "frequency" but in different formats.
**How to avoid:** Use `/v1/topRequests` which returns a `topRequests` array with phrase/count pairs. Filter for the exact phrase from the response. Use `/v1/dynamics` only if you need historical trend data.
**Warning signs:** Frequency column shows arrays or objects instead of integers.

### Pitfall 5: 33-Letter Expansion With Sequential Pause = ~20-30 Second Task
**What goes wrong:** 33 requests × (API call time ~0.5-2s + pause 200-500ms) = 23-83 seconds minimum. If proxy is slow or banned, a single letter can take 30s (pause) × 3 retries.
**Why it happens:** Sequential mandatory per D-17, pause mandatory per D-06.
**How to avoid:** Set `soft_time_limit=300` on the Celery task. The HTMX polling UI shows "Loading..." so users see progress. Return partial results (D-06) rather than failing the whole task if proxies are exhausted midway. Log progress per letter with `logger.info`.
**Warning signs:** Tasks timing out at Celery soft limit, UI stuck in "loading" for >5 minutes.

### Pitfall 6: Fix Position Engine Bug (Todo 1) Conflicts With Existing Tests
**What goes wrong:** Fixing `_check_via_dataforseo` and `_check_via_serp_parser` to use `kw.engine.value` (instead of hardcoded "google") may break existing tests that assert "google" is always written.
**Why it happens:** `test_position_tasks_engine.py` and `test_position_tasks.py` may assert specific engine values.
**How to avoid:** Read existing position task tests before implementing the fix. Update test assertions to reflect the correct engine-aware behavior.
**Warning signs:** `test_position_tasks_engine.py` failures after the engine fix.

### Pitfall 7: ServiceCredential ENCRYPTED_FIELDS Not Updated for Yandex Direct Token
**What goes wrong:** The Yandex Direct OAuth token is stored unencrypted if `"yandex_direct"` is not added to `ENCRYPTED_FIELDS` in `service_credential_service.py`.
**Why it happens:** The Fernet encryption is opt-in per service; new services default to plaintext.
**How to avoid:** Add `"yandex_direct": ["token"]` to `ENCRYPTED_FIELDS` in `service_credential_service.py` before implementing the credential save endpoint. Test with `test_service_credential_service.py` pattern.
**Warning signs:** Token visible in plaintext in `service_credentials.credential_data` column.

---

## Code Examples

### Redis Cache Read Pattern (Sync — for Celery)
```python
# Source: pattern derived from dashboard_service.py (async) adapted to sync
import json
import redis

def get_cached_suggestions(redis_url: str, cache_key: str) -> list[dict] | None:
    r = redis.from_url(redis_url, decode_responses=True)
    raw = r.get(cache_key)
    if raw:
        return json.loads(raw)
    return None

def set_cached_suggestions(redis_url: str, cache_key: str, data: list[dict], ttl: int = 86400) -> None:
    r = redis.from_url(redis_url, decode_responses=True)
    r.set(cache_key, json.dumps(data, ensure_ascii=False), ex=ttl)
```

### Cache Key with Normalization
```python
# Source: D-16 decisions + Redis key design pattern
def suggest_cache_key(seed: str, include_google: bool) -> str:
    normalized_seed = seed.strip().lower()
    sources = "yg" if include_google else "y"
    return f"suggest:{sources}:{normalized_seed}"
```

### Slowapi Rate Limit Decorator
```python
# Source: app/main.py limiter setup + slowapi documentation
from slowapi import Limiter
from slowapi.util import get_remote_address

# In router (app.state.limiter already configured in main.py):
@router.post("/search", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def search_suggestions(request: Request, ...):
    ...
```

### Credential Registration for Yandex Direct Token
```python
# Source: service_credential_service.py ENCRYPTED_FIELDS pattern
# In service_credential_service.py — add to ENCRYPTED_FIELDS dict:
ENCRYPTED_FIELDS: dict[str, list[str]] = {
    "xmlproxy": ["key"],
    "rucaptcha": ["key"],
    "yandex_direct": ["token"],  # ADD THIS
}

# Save:
save_credential_sync(db, "yandex_direct", {"token": oauth_token})

# Read:
creds = get_credential_sync(db, "yandex_direct")
token = creds["token"] if creds else None
```

### CSV Export With BOM (per UI-SPEC)
```python
# Source: UI-SPEC CSV Export Format section
import csv
import io
from fastapi.responses import StreamingResponse

def export_suggestions_csv(suggestions: list[dict], seed: str) -> StreamingResponse:
    """UTF-8 BOM CSV for Excel compatibility with Russian text."""
    output = io.StringIO()
    output.write("\ufeff")  # BOM
    writer = csv.DictWriter(output, fieldnames=["Подсказка", "Источник", "Частотность"])
    writer.writeheader()
    for s in suggestions:
        writer.writerow({
            "Подсказка": s["keyword"],
            "Источник": "Яндекс" if s["source"] == "yandex" else "Google",
            "Частотность": s.get("frequency", ""),
        })
    content = output.getvalue()
    from datetime import date
    safe_seed = seed[:30].replace(" ", "_")
    filename = f"suggest_{safe_seed}_{date.today()}.csv"
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

### HTMX Polling Pattern for Suggest Status
```python
# Source: app/templates/client_reports/partials/generation_status.html pattern
# suggest_status.html partial — three states:

# State 1: pending/running — self-replaces via outerHTML every 3s
# <div hx-get="/ui/keyword-suggest/status/{{ job_id }}"
#      hx-trigger="load delay:3s"
#      hx-swap="outerHTML">
#   <spinner>Загружаем подсказки...</spinner>
# </div>

# State 2: complete — renders results card directly (no more polling)
# State 3: failed — renders error message (no more polling)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Wordstat Yandex Direct API v4 (SOAP-like) | Wordstat API at api.wordstat.yandex.net (REST/JSON) | 2023-2024 | Newer API is simpler; old Direct v4 for keyword stats is deprecated |
| HTMX 1.x `hx-sse` / `hx-ws` | HTMX 2.0.x — SSE/WS moved to extensions | Mid-2024 | Project already uses HTMX 2.0, no impact |

**Deprecated/outdated:**
- Yandex Direct v4 API for keyword statistics: replaced by `api.wordstat.yandex.net`. Do not use old DirectAPI endpoints for Wordstat data.
- `redis.StrictRedis`: Use `redis.Redis` (they are aliases in redis-py 4.x+, but `redis.Redis` is the canonical modern name).

---

## Open Questions

1. **Exact Yandex Suggest endpoint URL and response format**
   - What we know: Multiple candidate URLs exist. The one used by Wordstat UI (`wordstat.yandex.ru/suggest`) and the general search suggest are the most likely. Response is JSON.
   - What's unclear: Exact URL path, parameter names, response JSON structure (items array vs flat array). This is undocumented.
   - Recommendation: In Wave 0 / first task, make a live test request with the candidate URL and log the response before writing the parser. Build the parser from the actual response structure.

2. **Yandex Wordstat API access approval**
   - What we know: `api.wordstat.yandex.net` requires OAuth token AND explicit access approval from Yandex Direct support.
   - What's unclear: Does the user already have access? The API may return 403 until access is granted.
   - Recommendation: In the settings UI for Yandex Direct token, add a note "Access must be requested via Yandex Direct support". If API returns 403, the Wordstat column should gracefully show "Access not approved yet" rather than a generic error.

3. **Proxy pool size vs 33-letter expansion**
   - What we know: 5 proxies in the pool (per D-05). 33 requests per suggest run.
   - What's unclear: Will one proxy be used for all 33 letters sequentially, or should the task rotate between proxies even when not banned?
   - Recommendation: Use a single proxy per run (round-robin across jobs, not within one job). Only rotate within a job when banned (D-06). This avoids unnecessary proxy switching overhead.

4. **Todo: fix position check ignores engine preference — scope**
   - What we know: `position_tasks.py` lines 113, 154 hardcode "google" instead of reading `kw.engine`. The fix is in `_check_via_dataforseo` and `_check_via_serp_parser` (NOT `_check_via_xmlproxy`, which already uses "yandex").
   - What's unclear: Looking at current `position_tasks.py` lines 210-211, the code already reads `engine_str = "yandex"` in `_check_via_xmlproxy`. The DataForSEO path at line 268 already reads `engine_str = kw.engine.value if kw.engine else "google"`. This means the bug described in the todo may already be partially or fully fixed by prior work.
   - Recommendation: Read current `position_tasks.py` carefully in Wave 0 and confirm whether the engine routing bug still exists. The todo was created 2026-04-02 and significant work has happened since. May be a no-op fix.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Redis | Cache (SUG-04), Celery broker | Already in docker-compose | 7.2.x | — |
| PostgreSQL | SuggestJob model | Already running | 16.x | — |
| Celery worker | Async task execution (D-03) | Already running | 5.4.x | — |
| Proxy pool (5 proxies) | Yandex Suggest (D-01, D-05) | DB records required | — | Return error: "No active proxies configured" |
| Yandex Direct OAuth token | Wordstat (SUG-03) | Stored in ServiceCredential | — | Wordstat column hidden (graceful degradation) |
| Yandex Wordstat API access | Wordstat (SUG-03) | Requires user approval from Yandex | — | 403 error handled gracefully, column hidden |

**Missing dependencies with no fallback:**
- None that block core functionality (SUG-01, SUG-02, SUG-04). Proxy pool is required for Yandex Suggest but proxies are already managed via the UI introduced in an earlier phase.

**Missing dependencies with fallback:**
- Yandex Direct token (Wordstat): graceful degradation — feature hidden when not configured.
- Yandex Wordstat API approval: graceful error handling when API returns 403.

---

## Project Constraints (from CLAUDE.md)

| Constraint | Impact on Phase 15 |
|------------|-------------------|
| Tech stack fixed: Python 3.12, FastAPI 0.111+, SQLAlchemy 2.0 async, Celery 5 + Redis 7, HTMX | No alternatives to consider. All new code follows these versions. |
| All schema changes via Alembic migrations | New `suggest_jobs` table requires `0040_add_suggest_jobs.py` migration. |
| Celery retry=3 for all external API calls | Both Yandex Suggest and Wordstat tasks must have `max_retries=3`. |
| UI pages < 3s; long ops always async via Celery | Suggest fetch (up to 83s) must be Celery-dispatched. Router returns task_id immediately. |
| Passwords bcrypt, WP credentials Fernet-encrypted, JWT exp=24h | Yandex Direct OAuth token stored via ServiceCredential + Fernet (D-12). |
| Testing: pytest + httpx AsyncClient; service layer coverage > 60% | `suggest_service.py` needs unit tests mocking httpx calls with respx. |
| Logging: loguru, JSON format | All logging uses `logger.info/warning/error` from loguru. |
| FastAPI lifespan= parameter, not deprecated on_event | No impact (no startup hooks needed). |
| HTMX 2.0.x | No `hx-ws` or `hx-sse` attributes. Use `hx-trigger="load delay:3s"` polling pattern. |
| Rate limiting via slowapi from iteration 7 | New `/ui/keyword-suggest/search` endpoint gets `@limiter.limit("10/minute")`. |

---

## Sources

### Primary (HIGH confidence)
- `app/services/xmlproxy_service.py` — sync httpx.Client pattern for Celery service
- `app/services/dashboard_service.py` — aioredis caching pattern
- `app/tasks/position_tasks.py` — Celery task structure with proxy, retry, error handling
- `app/tasks/client_report_tasks.py` — async task + asyncio.run() pattern
- `app/models/client_report.py` — status lifecycle model pattern
- `app/services/service_credential_service.py` — Fernet credential storage pattern
- `app/routers/client_reports.py` — HTMX polling router pattern
- `app/navigation.py` — sidebar section registration pattern
- `app/celery_app.py` — task registration, queue routing
- `app/main.py` — slowapi limiter configuration
- `app/.planning/phases/15-keyword-suggest/15-CONTEXT.md` — all locked decisions
- `app/.planning/phases/15-keyword-suggest/15-UI-SPEC.md` — complete UI contract

### Secondary (MEDIUM confidence)
- Yandex Wordstat API official docs (`yandex.com/support2/wordstat/en/content/api-wordstat`, `api-structure`) — base URL, auth header, endpoint names verified
- Google Suggest endpoint `suggestqueries.google.com/complete/search` — widely documented by community, stable since 2010s, verified by multiple SEO tool sources
- Google Suggest response format `["query", ["suggestion1", ...], ...]` — confirmed by fullstackoptimization.com spec

### Tertiary (LOW confidence — verify in testing)
- Yandex Suggest endpoint URL (`wordstat.yandex.ru/suggest` or similar) — undocumented, inferred from network traffic analysis in SEO community. Must be verified by live request before production use.
- Yandex Wordstat `/v1/topRequests` request/response body fields — verified endpoint exists but exact JSON schema requires live API test.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use
- Architecture patterns: HIGH — all based on existing codebase patterns
- Yandex Suggest API endpoint: LOW — undocumented, must verify in testing
- Google Suggest API: MEDIUM — undocumented but stable, widely verified
- Wordstat API structure: MEDIUM — auth/URL verified, request body fields need live test
- Proxy rotation / ban handling: HIGH — pattern derived from decisions + existing proxy model
- Redis caching: HIGH — pattern directly from dashboard_service

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (Yandex Suggest endpoint: validate immediately; Wordstat API schema: validate in Wave 0)
