# Architecture Research

**Domain:** SEO Management Platform — FastAPI + Celery + PostgreSQL + Playwright + WordPress REST API
**Researched:** 2026-03-31
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HTTP Layer                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI  (Jinja2 + HTMX + REST JSON API)                    │   │
│  │  Routes → Dependencies → Service Layer → Async SQLAlchemy    │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────────────┘
                          │ enqueue tasks (Redis)
┌─────────────────────────▼───────────────────────────────────────────┐
│                      Task Layer                                      │
│  ┌──────────────────┐  ┌───────────────┐  ┌───────────────────────┐ │
│  │  Celery Worker   │  │  Celery Beat  │  │  Celery Flower (UI)   │ │
│  │  (crawl/SERP/WP) │  │  (schedules)  │  │  (monitoring)         │ │
│  └────────┬─────────┘  └───────────────┘  └───────────────────────┘ │
│           │ uses sync SQLAlchemy + httpx + Playwright                │
└───────────┼─────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────────┐
│                      Data Layer                                      │
│  ┌──────────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   PostgreSQL 16   │  │   Redis 7    │  │  File Storage (local)  │ │
│  │  (primary store) │  │  (broker +   │  │  (snapshots, exports)  │ │
│  │                  │  │   cache)     │  │                        │ │
│  └──────────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────────┐
│                   External Integrations                              │
│  ┌───────────┐ ┌───────────┐ ┌──────────────┐ ┌─────────────────┐  │
│  │  WP REST  │ │   GSC     │ │ DataForSEO   │ │  Telegram/SMTP  │  │
│  │  API      │ │  OAuth2   │ │  API         │ │  Notifications  │  │
│  └───────────┘ └───────────┘ └──────────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| FastAPI app | HTTP routing, auth, request validation, response rendering, task dispatch | `app/` with routers, depends, schemas |
| Service layer | Business logic, orchestration, no HTTP concerns | `app/services/` — called from routes AND tasks |
| Celery Worker | Long-running async work: crawling, SERP parsing, WP pipeline | `app/tasks/` — separate process, sync SQLAlchemy |
| Celery Beat | Cron-style scheduling: periodic crawls, position checks, reports | Beat schedule stored in DB (django-celery-beat pattern) or Redis |
| PostgreSQL | Persistent state: all domain data, audit log, position history | asyncpg driver for FastAPI, psycopg2/psycopg3 for Celery |
| Redis | Celery broker + result backend + optional caching layer | Single Redis instance sufficient at this scale |
| Playwright (in worker) | Crawling pages, SERP parsing — browser automation in worker process | One browser instance per worker, managed via context |

## Recommended Project Structure

```
app/
├── main.py                  # FastAPI app factory, middleware, lifespan
├── config.py                # Pydantic Settings — reads from env
├── database.py              # Async engine, session factory, Base
├── celery_app.py            # Celery app factory, config
│
├── models/                  # SQLAlchemy ORM models (one file per domain)
│   ├── site.py
│   ├── keyword.py
│   ├── crawl.py
│   ├── position.py
│   ├── task.py
│   └── user.py
│
├── schemas/                 # Pydantic v2 request/response schemas
│   ├── site.py
│   ├── keyword.py
│   └── ...
│
├── routers/                 # FastAPI routers (thin — delegate to services)
│   ├── auth.py
│   ├── sites.py
│   ├── keywords.py
│   ├── crawl.py
│   └── ...
│
├── services/                # Business logic — importable from routes AND tasks
│   ├── site_service.py
│   ├── crawl_service.py
│   ├── keyword_service.py
│   ├── wp_service.py        # WP REST API calls + credential decrypt
│   ├── position_service.py
│   └── report_service.py
│
├── tasks/                   # Celery task modules
│   ├── crawl_tasks.py
│   ├── position_tasks.py
│   ├── wp_tasks.py
│   └── report_tasks.py
│
├── integrations/            # Thin clients for external APIs
│   ├── wordpress.py         # httpx client + retry + rate limit
│   ├── gsc.py               # Google Search Console
│   ├── dataforseo.py
│   └── telegram.py
│
├── auth/                    # JWT, bcrypt, role enforcement
│   ├── jwt.py
│   ├── dependencies.py      # get_current_user, require_role
│   └── encryption.py        # Fernet helpers
│
├── templates/               # Jinja2 HTML templates
│   ├── base.html
│   ├── sites/
│   ├── keywords/
│   └── ...
│
└── static/                  # CSS, JS (HTMX, Chart.js)

alembic/                     # Migrations
tests/
docker-compose.yml
Dockerfile
```

### Structure Rationale

- **models/ vs schemas/:** SQLAlchemy models own the DB shape; Pydantic schemas own the API contract. Never return ORM objects directly from routes.
- **services/:** Shared between routers and tasks. Services take a `db` session as a parameter — they do not own session lifecycle. This is the critical boundary.
- **tasks/:** Celery tasks are thin wrappers: validate inputs, call service layer, handle retries. Business logic stays in services, not in task functions.
- **integrations/:** Each external API gets its own module with its own retry/rate-limit logic. This isolates third-party breakage.
- **celery_app.py separate from main.py:** Celery workers import `celery_app` without loading the full FastAPI app, avoiding startup cost and circular imports.

## Architectural Patterns

### Pattern 1: Async SQLAlchemy Session via FastAPI Dependency

**What:** Each request gets its own async session via a FastAPI dependency. Session commits/rollbacks are managed by the dependency, not by route handlers.

**When to use:** All FastAPI route handlers that need DB access.

**Trade-offs:** Clean isolation; slight overhead per request. Do not reuse sessions across requests — each request is independent.

**Example:**
```python
# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(settings.DATABASE_URL, pool_size=10, max_overflow=5)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# app/dependencies.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# app/routers/sites.py
@router.get("/sites/{site_id}")
async def get_site(site_id: int, db: AsyncSession = Depends(get_db)):
    return await site_service.get_by_id(db, site_id)
```

### Pattern 2: Celery Tasks Use Sync SQLAlchemy (Not Async)

**What:** Celery workers run in their own process. They use synchronous SQLAlchemy with psycopg2/psycopg3, not asyncpg. Do not try to run asyncio event loops inside Celery tasks — it creates complexity with no benefit.

**When to use:** All Celery task code that needs DB access.

**Trade-offs:** Two session factories (async for FastAPI, sync for Celery). This is the standard pattern — do not fight it. The service layer absorbs this by accepting a generic `Session` type.

**Example:**
```python
# app/celery_db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sync_engine = create_engine(settings.SYNC_DATABASE_URL, pool_size=5)
SyncSessionLocal = sessionmaker(sync_engine)

# app/tasks/crawl_tasks.py
@celery_app.task(bind=True, max_retries=3)
def crawl_site(self, site_id: int):
    with SyncSessionLocal() as db:
        try:
            crawl_service.run_crawl(db, site_id)  # service is sync-compatible
        except Exception as exc:
            raise self.retry(exc=exc, countdown=60)
```

### Pattern 3: Fan-Out Task Pattern for Multi-Site Operations

**What:** A coordinator task reads all active sites and dispatches one task per site. Each site task is independent — failure of one does not affect others. Use Celery canvas `group()` for parallel dispatch.

**When to use:** Any operation that runs across all sites (nightly crawl, position check, scheduled reports).

**Trade-offs:** Coordinator can be lightweight. Workers process sites in parallel up to concurrency limit. Add site_id to task routing key to prevent one slow site from blocking others.

**Example:**
```python
# app/tasks/crawl_tasks.py
from celery import group

@celery_app.task
def schedule_all_crawls():
    """Coordinator: dispatches one crawl task per active site."""
    with SyncSessionLocal() as db:
        site_ids = site_service.get_active_site_ids(db)
    job = group(crawl_site.s(site_id) for site_id in site_ids)
    job.apply_async()

@celery_app.task(bind=True, max_retries=3, queue="crawl")
def crawl_site(self, site_id: int):
    ...
```

### Pattern 4: Playwright Process Management in Celery Workers

**What:** Playwright browser instances are expensive to start. Use a module-level browser instance per worker process, initialized at worker startup via Celery signals. Use a new `BrowserContext` per crawl task, then close it. Never share a context across tasks.

**When to use:** Any Celery task that uses Playwright for crawling or SERP parsing.

**Trade-offs:** Module-level browser reuse avoids per-task startup cost (~1–2s). Contexts are cheap and provide isolation. Set `CELERY_WORKER_MAX_TASKS_PER_CHILD` (e.g., 50–100) to periodically restart workers and reclaim leaked memory.

**Example:**
```python
# app/tasks/browser.py
from celery.signals import worker_process_init, worker_process_shutdown
from playwright.sync_api import sync_playwright

_playwright = None
_browser = None

@worker_process_init.connect
def init_browser(**kwargs):
    global _playwright, _browser
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(headless=True)

@worker_process_shutdown.connect
def close_browser(**kwargs):
    global _playwright, _browser
    if _browser:
        _browser.close()
    if _playwright:
        _playwright.stop()

def get_browser():
    return _browser

# app/tasks/crawl_tasks.py
@celery_app.task(bind=True, max_retries=3, queue="crawl")
def crawl_site(self, site_id: int):
    browser = get_browser()
    context = browser.new_context(user_agent=random_ua())
    page = context.new_page()
    try:
        # ... crawl logic
    finally:
        context.close()  # always close context
```

### Pattern 5: Time-Series Position Data with Partitioning-Ready Schema

**What:** Store one row per (keyword_id, date, engine, geo, device). Index on (keyword_id, date DESC). At 100 sites × 500 keywords × 2 engines × 2 devices × 365 days = ~73M rows/year. Use PostgreSQL range partitioning by month on `checked_at` to keep query times fast without immediate complexity.

**When to use:** `keyword_positions` table design from iteration 3 onward.

**Trade-offs:** Partitioning by month means old data is cheap to archive/drop. Without partitioning, a simple index on (keyword_id, checked_at) handles the load up to ~10M rows before needing attention.

**Example:**
```sql
CREATE TABLE keyword_positions (
    id          BIGSERIAL,
    keyword_id  INT NOT NULL REFERENCES keywords(id),
    checked_at  TIMESTAMPTZ NOT NULL,
    engine      VARCHAR(20) NOT NULL,  -- 'google', 'yandex'
    geo         VARCHAR(10) NOT NULL,  -- 'RU', 'US', etc.
    device      VARCHAR(10) NOT NULL,  -- 'desktop', 'mobile'
    position    SMALLINT,              -- NULL = not in top 100
    url         TEXT,
    PRIMARY KEY (id, checked_at)
) PARTITION BY RANGE (checked_at);

CREATE INDEX idx_kp_keyword_date
    ON keyword_positions (keyword_id, checked_at DESC);
```

### Pattern 6: WordPress Integration with Per-Site Rate Limiting

**What:** Each WP site gets its own httpx `AsyncClient` (or sync `httpx.Client` in tasks) with a per-site semaphore. Store rate limit state in Redis so multiple workers respect the same limit. Use exponential backoff on 429/503.

**When to use:** All WP REST API calls (CRUD, meta updates, health checks).

**Trade-offs:** Redis-based rate limiting adds a Redis round-trip but prevents WP site bans. Simple token bucket per site_id stored in Redis as a counter with TTL is sufficient.

**Example:**
```python
# app/integrations/wordpress.py
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class WordPressClient:
    def __init__(self, base_url: str, username: str, app_password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, app_password)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    def get(self, path: str, **kwargs):
        with httpx.Client(auth=self.auth, timeout=30) as client:
            r = client.get(f"{self.base_url}/wp-json/wp/v2{path}", **kwargs)
            r.raise_for_status()
            return r.json()
```

## Data Flow

### Synchronous Request Flow (UI pages)

```
Browser (HTMX request)
    ↓
FastAPI Router (validate, auth check)
    ↓
Service Layer (business logic, async DB reads)
    ↓
Async SQLAlchemy → PostgreSQL
    ↓
Jinja2 Template → HTML fragment
    ↓
Browser (HTMX swaps fragment into DOM)
```

### Async Task Flow (crawl, position check, WP pipeline)

```
User triggers action (UI button / Celery Beat schedule)
    ↓
FastAPI Route → enqueue task → Redis broker
    ↓ (returns task_id immediately; UI polls /tasks/{id}/status)
Celery Worker picks up task
    ↓
Task → Service Layer (sync) → Sync SQLAlchemy → PostgreSQL
    ↓                       → Playwright (if crawl/SERP)
    ↓                       → WP REST API (if WP pipeline)
    ↓
Task result → Redis result backend
    ↓
HTMX polling endpoint → FastAPI reads task status → updates UI
```

### Key Data Flows

1. **Site onboarding:** User submits WP URL + credentials → FastAPI encrypts credentials (Fernet) → stores in DB → triggers verification task → Celery calls WP REST `/users/me` → marks site active or error.

2. **Scheduled crawl:** Celery Beat fires `schedule_all_crawls` → fan-out `group()` dispatches one `crawl_site` task per active site → each worker fetches site pages via Playwright → writes `page_snapshots` + diff vs. previous → auto-creates tasks for 404s → updates `last_crawled_at`.

3. **Position check:** `schedule_position_checks` → one task per (site, engine) → SERP parser (Playwright or DataForSEO) → writes rows to `keyword_positions` → Telegram alert if position drop > threshold.

4. **WP content pipeline:** User selects pages → FastAPI enqueues pipeline tasks → each task: fetch page via Playwright → parse HTML → generate TOC/schema/links → store diff preview → UI shows before/after → user approves → push update via WP REST API.

5. **Dashboard load:** FastAPI route aggregates: top positions (last 24h from `keyword_positions`), open tasks count, recent crawl changes (last 48h from `page_snapshots`) — all via indexed reads, no joins across all sites, returns < 3s.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1–20 sites | Single worker with concurrency=4, all queues on one worker process |
| 20–50 sites | Separate `crawl` and `default` queues; 2 worker processes; Beat on its own process |
| 50–100 sites | Dedicated crawl workers (concurrency=2, Playwright-heavy); dedicated default workers (concurrency=8, I/O tasks); `WORKER_MAX_TASKS_PER_CHILD=50` |
| 100+ sites | Add worker replicas (Docker Compose `scale`); consider Redis Sentinel; partition `keyword_positions` by month |

### Scaling Priorities

1. **First bottleneck — Playwright concurrency:** Each Playwright browser context uses ~100–200 MB RAM. At concurrency=4 with Playwright, a worker needs ~1 GB RAM. Separate crawl workers (low concurrency, high RAM) from API workers (high concurrency, low RAM) early.

2. **Second bottleneck — `keyword_positions` table size:** At 100 sites × 500 keywords this grows fast. Add monthly partitioning in the Alembic migration for this table at iteration 3, before data accumulates. Retro-partitioning is painful.

3. **Third bottleneck — Redis memory:** Task result backend accumulates results. Set `CELERY_RESULT_EXPIRES=3600` (1h) from day one. Use `redis.conf maxmemory-policy allkeys-lru` to prevent Redis OOM.

## Anti-Patterns

### Anti-Pattern 1: Running asyncio inside Celery Tasks

**What people do:** Use `asyncio.run()` or `async def` task functions to call async SQLAlchemy from Celery workers.

**Why it's wrong:** Celery workers are synchronous by default. Running `asyncio.run()` per task creates and destroys an event loop per task, which is slow and causes subtle bugs with Playwright (which has its own async event loop). The `celery[gevent]` + async combination creates difficult-to-debug deadlocks.

**Do this instead:** Use sync SQLAlchemy (psycopg2/psycopg3 sync driver) in Celery tasks. Keep the async/sync boundary at the FastAPI edge. Services can be written in a sync-compatible style with separate async wrappers for the FastAPI layer if needed.

### Anti-Pattern 2: Putting Business Logic in Celery Task Functions

**What people do:** Write all the crawl logic, DB writes, and API calls directly inside the `@celery_app.task` decorated function.

**Why it's wrong:** Task functions become untestable without a running Celery broker. Business logic is buried in the task layer. Can't reuse logic from FastAPI routes (e.g., manual trigger via API calls the same logic as the scheduled task).

**Do this instead:** Task functions are thin — they validate inputs, call a service function, and handle retry logic. Service functions contain all business logic and accept a `db` session parameter. Service functions are tested directly with pytest without Celery.

### Anti-Pattern 3: One Celery Queue for Everything

**What people do:** All tasks go to the default queue, processed by all workers.

**Why it's wrong:** A 20-minute SERP crawl task blocks the queue for quick tasks (e.g., sending a Telegram alert, updating a post meta field). One stuck Playwright browser can starve all other work.

**Do this instead:** Define at least three queues from day one:
- `crawl` — Playwright-heavy, long-running (concurrency=2)
- `wp` — WP REST API calls, medium duration (concurrency=4)
- `default` — fast tasks: notifications, DB updates, report generation (concurrency=8)

### Anti-Pattern 4: Sharing a Playwright Browser Context Across Tasks

**What people do:** Create one global `BrowserContext` shared across all tasks in a worker to save memory.

**Why it's wrong:** Contexts share cookies, storage, and network state. A SERP parse that gets a CAPTCHA challenge corrupts the context for all subsequent tasks in the same worker. Memory leaks accumulate across task calls.

**Do this instead:** Share the `Browser` instance (expensive to create), create a new `BrowserContext` per task call, and always close it in a `finally` block. Set `WORKER_MAX_TASKS_PER_CHILD=50` to restart workers periodically and reclaim any leaked browser memory.

### Anti-Pattern 5: Storing WP Credentials in Plain Text

**What people do:** Store Application Passwords directly in the `sites` table as plaintext or base64.

**Why it's wrong:** DB dump or misconfigured backup exposes all client WP credentials immediately.

**Do this instead:** Encrypt with Fernet (symmetric, authenticated encryption) using a key from environment variable `FERNET_KEY`. Decrypt only when needed for an API call, never log the decrypted value. Rotate `FERNET_KEY` by re-encrypting all credentials in a migration script.

### Anti-Pattern 6: Polling for Task Status via DB

**What people do:** Write task status to PostgreSQL and have the UI poll a DB-backed endpoint every second.

**Why it's wrong:** High-frequency polling at 50+ concurrent users generates significant unnecessary DB load for what is essentially a pub/sub problem.

**Do this instead:** Store task status in Redis result backend (Celery already does this). The `/tasks/{task_id}/status` endpoint reads from Redis, not PostgreSQL. HTMX polling interval of 2–3 seconds is sufficient for UX; longer for background jobs.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| WordPress REST API | httpx sync client in tasks, async client in routes; Basic Auth with Application Password | Decrypt Fernet credentials on each call; never cache decrypted value in memory beyond request scope |
| Google Search Console | OAuth 2.0; store refresh_token encrypted per site; use `google-auth` library | Token refresh is automatic; store access token in Redis with TTL matching expiry |
| Yandex Webmaster | Static token from `.env`; simple Bearer auth | Single token for all sites if agency account; per-site token if individual |
| DataForSEO | HTTP Basic Auth (login:password from `.env`); synchronous batch requests | Rate limit: 2000 requests/min on standard plan; use as fallback when Playwright SERP parsing is blocked |
| Telegram Bot API | Fire-and-forget POST to `sendMessage`; no webhook needed | Send from `default` queue task; never block main flow on Telegram failure |
| SMTP | `smtplib` or `aiosmtplib`; credentials from `.env` | Send from Celery task, not from FastAPI request handler |
| Yoast/RankMath REST | Part of WP REST API; update `post_meta` via `POST /wp/v2/posts/{id}` with `meta` field | Test with both plugins; field names differ (`_yoast_wpseo_title` vs `rank_math_title`) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| FastAPI route ↔ Service | Direct Python function call (async) | Routes never import models directly — only schemas and services |
| FastAPI route ↔ Celery | `.delay()` / `.apply_async()` via celery_app | Routes return task_id; never await task result in request handler |
| Celery task ↔ Service | Direct Python function call (sync) | Same service module, different session type (sync vs async) |
| Service ↔ Integration | Direct Python function call | Services call integration clients; integrations do not know about DB |
| Service ↔ DB | SQLAlchemy session passed as parameter | Session lifecycle owned by caller (route dependency or task context manager) |
| Beat schedule ↔ DB | `django-celery-beat` pattern or custom `PeriodicTask` model | Allows UI to update crawl schedule without worker restart |

## Build Order Implications

The dependency graph drives a natural build order:

**Phase 1 foundation (must be first):**
- `database.py`, `config.py`, `celery_app.py` — everything imports these
- `models/user.py`, `auth/` — all routes depend on auth
- `models/site.py`, `services/site_service.py`, `integrations/wordpress.py` — WP integration is the core value

**Phase 2 (unblocks crawler and positions):**
- Celery task infrastructure (queues, worker signals, Playwright init)
- `models/crawl.py`, `tasks/crawl_tasks.py`
- `integrations/` clients (WP, GSC, DataForSEO) — needed before tasks can run

**Phase 3 (depends on crawl data existing):**
- `models/keyword.py`, `models/position.py` with partitioned schema
- `tasks/position_tasks.py` — needs Playwright infrastructure from Phase 2
- Clustering, cannibalization detection — needs position history rows to exist

**Phase 4 (depends on keywords + crawl data):**
- WP content pipeline — depends on crawled page data + keyword mapping
- Diff preview UI — depends on content pipeline output

**Phase 5–6 (depends on all prior data):**
- Projects/tasks board — aggregates data from all prior models
- Dashboard + reports — reads from all tables; fast only if indexes are correct from day one

**Key constraint:** The `keyword_positions` partition scheme must be created in iteration 3's first migration, not retrofitted later. Getting the index strategy right at model definition time (iteration 3) prevents a painful backfill migration at iteration 5+.

## Sources

- SQLAlchemy 2.0 async documentation: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Celery 5 best practices: https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices
- Playwright Python: process/browser/context lifecycle: https://playwright.dev/python/docs/library
- FastAPI dependency injection patterns: https://fastapi.tiangolo.com/tutorial/dependencies/
- PostgreSQL table partitioning: https://www.postgresql.org/docs/16/ddl-partitioning.html
- Tenacity retry library: https://tenacity.readthedocs.io/en/latest/
- Celery canvas primitives (group, chain, chord): https://docs.celeryq.dev/en/stable/userguide/canvas.html
- FastAPI + SQLAlchemy async session management (standard community pattern): SQLAlchemy async session per request via dependency
- WordPress Application Passwords: https://make.wordpress.org/core/2020/11/05/application-passwords-integration-guide/

---
*Architecture research for: SEO Management Platform — FastAPI + Celery + PostgreSQL + Playwright*
*Researched: 2026-03-31*
