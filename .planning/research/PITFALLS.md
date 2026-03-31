# Pitfalls Research

**Domain:** SEO Management Platform — FastAPI + Celery + Playwright + PostgreSQL + WordPress REST API
**Researched:** 2026-03-31
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Playwright Browser Leaks in Long-Running Celery Workers

**What goes wrong:**
Each Celery task that uses Playwright launches a browser context. When tasks crash mid-execution, or when the worker process is recycled by Celery's `--max-tasks-per-child`, browser processes (Chromium) are left orphaned. Over hours, a VPS accumulates dozens of zombie Chromium processes consuming RAM. The worker appears alive but the VPS runs out of memory, killing other containers.

**Why it happens:**
Developers write `async with async_playwright() as p` inside the task but don't account for task hard-kills (SIGKILL from Celery time limits). When Celery hard-kills a task thread, the context manager's `__aexit__` never runs. Playwright's subprocess management is OS-level — Python garbage collection cannot clean up child processes.

**How to avoid:**
- Use a single `BrowserContext` pool per worker process, not per task. Initialize one browser in Celery worker `init` signal, share it across tasks via a module-level variable.
- Set `--max-tasks-per-child=50` on crawl workers so the worker process recycles, killing all child browser processes cleanly.
- Wrap every Playwright task in a `try/finally` that explicitly calls `context.close()` and `browser.close()`.
- Add a watchdog: a periodic Celery Beat task that counts `pgrep chromium` and alerts if it exceeds threshold.
- Set `soft_time_limit` (which raises `SoftTimeLimitExceeded`) in addition to `time_limit` — gives the task a chance to close the browser before hard kill.

**Warning signs:**
- `ps aux | grep chromium` shows 10+ processes on idle system
- VPS RAM climbing continuously without dropping
- Celery worker logs show tasks completing but memory never freed
- `docker stats` shows the celery-worker container's MEM constantly increasing

**Phase to address:**
Iteration 2 (Crawler implementation — first time Playwright runs in Celery)

---

### Pitfall 2: Running Multiple Playwright Instances Concurrently Without Limits

**What goes wrong:**
Celery workers default to `concurrency=number_of_CPUs`. On a 4-core VPS, 4 Playwright tasks run simultaneously, each spawning a Chromium instance. Chromium is RAM-heavy (~200MB each). 4 concurrent instances = ~800MB just for browsers, plus the crawled pages, plus everything else. The VPS OOM-killer fires and takes down the whole Docker stack. This happens silently — no Python exception, just a dead container.

**Why it happens:**
Celery concurrency is set globally. Developers don't separate compute-bound tasks from browser-bound tasks into different worker pools with different concurrency limits.

**How to avoid:**
- Dedicate a separate Celery worker for Playwright tasks with `concurrency=2` (or 1 on small VPS) using a dedicated queue (`crawler`, `serp`).
- Use `CELERYD_PREFETCH_MULTIPLIER=1` on Playwright workers to prevent a single worker from claiming more tasks than it can run.
- Set `worker_max_memory_per_child=512000` (512MB) to recycle workers that bloat.
- For a 2GB VPS: `concurrency=1` for Playwright workers; for 4GB: `concurrency=2`.

**Warning signs:**
- Container restart loops visible in `docker-compose logs`
- `dmesg | grep oom` shows OOM kill events
- Tasks disappear from queue without completing and without error logs

**Phase to address:**
Iteration 2 (first Playwright-in-Celery code) — set worker topology immediately

---

### Pitfall 3: Celery Task Granularity — Entire Site as One Task

**What goes wrong:**
Developer creates one Celery task `crawl_site(site_id)` that opens a browser, crawls all URLs, processes everything, writes to DB, and closes. If a site has 500 pages and the task fails at page 400, the entire crawl is lost. The task holds a browser open for 20+ minutes, hitting time limits. Progress is invisible until completion. One slow site blocks other crawl tasks from starting.

**Why it happens:**
It mirrors how you'd write a script. The leap to "each URL is a task" feels over-engineered until the first production failure.

**How to avoid:**
- Use a three-level task hierarchy:
  1. `schedule_site_crawl(site_id)` — discovers URLs, enqueues individual page tasks
  2. `crawl_page(url, crawl_run_id)` — crawls one URL, writes result immediately
  3. `finalize_crawl_run(crawl_run_id)` — aggregates results, triggers diff computation (use Celery `chord` or `group`)
- Each `crawl_page` task is idempotent: if it already ran for this `crawl_run_id`, skip it.
- Store `crawl_run_id` in DB on creation so progress is visible before completion.
- Set per-task time limits: `crawl_page` max 60s, `schedule_site_crawl` max 30s.

**Warning signs:**
- Tasks that run for >5 minutes
- "One site is slow, all others wait"
- Restarts lose all in-progress crawl data
- No ability to show "crawling: 45/200 pages"

**Phase to address:**
Iteration 2 (design the crawl task hierarchy before writing first task)

---

### Pitfall 4: Result Backend Bloat with CELERY_RESULT_BACKEND = Redis

**What goes wrong:**
Celery stores task results in Redis by default without expiration, or with a very long TTL. An SEO platform running daily crawls on 50 sites generates thousands of task results per day. After a month, Redis holds gigabytes of serialized task results that are never read by any application code (the real data is already in PostgreSQL). Redis fills up, which blocks new task submission, which silently drops tasks.

**Why it happens:**
`result_expires` is not set by default in many tutorials. Developers assume Redis handles its own memory management, but Redis with `maxmemory-policy noeviction` (common default) just errors instead of evicting.

**How to avoid:**
- Set `result_expires=3600` (1 hour) — crawl results are either read immediately or never.
- For fire-and-forget tasks (background jobs that write to DB), disable result storage: `@app.task(ignore_result=True)`.
- Use `ignore_result=True` on all Playwright and crawl tasks — the result lives in PostgreSQL, not Redis.
- Only store results for tasks where the API endpoint polls for completion (e.g., on-demand position check).
- Configure Redis `maxmemory 512mb` and `maxmemory-policy allkeys-lru` in Docker Compose.
- Monitor Redis memory: add `GET /health` check that reports Redis `used_memory_human`.

**Warning signs:**
- `redis-cli info memory` shows `used_memory` growing daily
- Task submission suddenly starts failing with Redis connection errors
- `CELERY_RESULT_BACKEND` tasks never expire in `flower`

**Phase to address:**
Iteration 1 (Celery configuration baseline — set this from day one)

---

### Pitfall 5: keyword_positions Schema Without Partitioning

**What goes wrong:**
`keyword_positions` accumulates one row per (keyword, date, engine, geo, device). At 500 keywords × 2 engines × 365 days = 365,000 rows per year per site. At 50 sites = 18M rows in 2 years. Queries like "get 90-day history for keyword 1234" do a full table scan unless properly indexed. `GROUP BY keyword_id ORDER BY checked_at DESC` on 18M rows takes 10+ seconds. The positions chart in the UI times out.

**Why it happens:**
The schema works fine in development with 1,000 rows. The developer doesn't think about query patterns at schema design time. Indexes are added later as an afterthought, but `(keyword_id, checked_at)` composite indexes alone don't help if the query planner still scans old partitions.

**How to avoid:**
- Partition `keyword_positions` by range on `checked_at` from the start: monthly partitions in PostgreSQL 16 via declarative partitioning.
- Primary query pattern first: the most common query is `WHERE keyword_id = X AND checked_at >= NOW() - INTERVAL '90 days'` — create index on `(keyword_id, checked_at DESC)` within each partition.
- Add `(site_id, checked_at)` index for dashboard queries across all keywords for a site.
- Never query `keyword_positions` without a `WHERE checked_at >= ...` bound.
- Create partitions for the next 12 months in the initial migration; add a Celery Beat task to create new partitions monthly.
- Keep only 2 years of data; archive or drop older partitions via a maintenance task.

**Warning signs:**
- `EXPLAIN ANALYZE` shows `Seq Scan` on `keyword_positions`
- Position history chart takes >2s to load
- `pg_relation_size('keyword_positions')` exceeds 1GB

**Phase to address:**
Iteration 3 (before first position data is written — migration design is the prevention)

---

### Pitfall 6: Async SQLAlchemy Session Leaks in FastAPI

**What goes wrong:**
Developer creates an `AsyncSession` in a FastAPI dependency, but exception paths or background tasks hold references that prevent the session from closing. Over time, the PostgreSQL connection pool exhausts. New requests fail with `asyncpg.TooManyConnectionsError`. The error appears to be random because it depends on how many connections are currently leaked.

**Why it happens:**
`AsyncSession` with `async with` works, but FastAPI's dependency injection can be subtle. If a dependency yields a session and the endpoint raises before consuming the generator, SQLAlchemy's connection may not be returned to the pool. Background tasks started inside request scope that capture the session outlive the request lifecycle.

**How to avoid:**
- Always use `yield` in the session dependency combined with `try/finally`:
  ```python
  async def get_db():
      async with AsyncSessionLocal() as session:
          try:
              yield session
          finally:
              await session.close()
  ```
- Never pass a FastAPI-scoped `AsyncSession` to a `BackgroundTask` or Celery task. Background operations get their own session.
- Set `pool_size=10, max_overflow=5` and `pool_timeout=30` explicitly — don't rely on defaults.
- Set `pool_pre_ping=True` to detect dead connections before using them.
- Monitor `SELECT count(*) FROM pg_stat_activity WHERE state = 'idle'` — idle connections that never release are the tell.

**Warning signs:**
- `pg_stat_activity` shows many connections in `idle in transaction` state
- `asyncpg: connection pool exhausted` errors in logs
- Error rate increases linearly with uptime and resets after worker restart

**Phase to address:**
Iteration 1 (establish the DB session pattern before any endpoints are built)

---

### Pitfall 7: N+1 Queries in FastAPI Endpoints via SQLAlchemy

**What goes wrong:**
Dashboard endpoint loads 50 sites, then for each site makes a separate query to get latest crawl status, another for position count, another for open tasks. What looks like one request is actually 150+ queries. The dashboard takes 8 seconds. Adding `selectinload` as an afterthought is painful because the models weren't designed with relationship loading strategy in mind.

**Why it happens:**
SQLAlchemy ORM lazy loading is disabled in async mode (raises `MissingGreenlet`), so developers replace it with explicit loops with individual queries — which is just manual N+1.

**How to avoid:**
- Design the data access layer (DAL) with query patterns in mind before writing models. Ask: "what are the top 5 most common read operations?"
- For the dashboard (N sites), use a single aggregation query with window functions or CTEs — never iterate over sites in Python.
- Use `selectinload` or `joinedload` in SQLAlchemy where relationships are always needed together.
- Write a `repositories/` layer with explicit query methods (no ad-hoc queries in route handlers).
- Add query logging in development: `echo=True` on the engine shows every SQL statement.
- The rule: if a route loops over a list and queries the DB inside the loop, it's broken.

**Warning signs:**
- `echo=True` shows 50+ queries for a single dashboard page load
- Dashboard page consistently >2s even with empty data
- SQLAlchemy `asyncio` deprecation warnings about lazy loading

**Phase to address:**
Iteration 1 (repository pattern), Iteration 6 (dashboard aggregation queries)

---

### Pitfall 8: SERP Parsing — Getting Banned by Google

**What goes wrong:**
Playwright opens a Chromium instance in headless mode, navigates to `google.com/search?q=keyword`, and scrapes results. Google detects headless Chrome within 5–10 requests via browser fingerprinting (navigator.webdriver, Chrome DevTools Protocol artifacts, missing browser plugins, predictable timing). IP gets a CAPTCHA after ~10 searches. After repeated violations, the VPS IP is soft-banned and receives empty SERPs or redirect loops.

**Why it happens:**
Developer tests with 2–3 keywords manually and it works. Production has 500+ keywords per site. Google's bot detection is statistical — it's fine at low volume, catastrophic at scale.

**How to avoid:**
- Use `playwright-stealth` or manual stealth patches: set `navigator.webdriver = undefined`, spoof plugins, canvas fingerprint, WebGL renderer.
- Use `--disable-blink-features=AutomationControlled` launch argument.
- Rotate User-Agent strings from a realistic pool (real Chrome versions, matching OS).
- Randomize delays: 3–8 seconds between requests, not fixed intervals.
- Use residential proxy rotation for SERP requests (not datacenter IPs — Google recognizes VPS subnets).
- **Primary strategy**: Use DataForSEO API as the default position-checking method. Playwright SERP parsing is the fallback for small volumes only.
- Keep Playwright SERP to <50 queries/day from any single IP without proxies.
- Never run Playwright SERP requests from the same IP that serves the web application.

**Warning signs:**
- Google returns CAPTCHA HTML instead of search results
- Results HTML has zero `.g` elements (classic CAPTCHA redirect)
- All keyword positions suddenly show as "not found"
- Playwright screenshot of SERP shows "unusual traffic" page

**Phase to address:**
Iteration 3 (SERP parser design — build stealth and DataForSEO fallback from the start)

---

### Pitfall 9: SERP Parsing — Yandex is More Aggressive Than Google

**What goes wrong:**
Yandex's SmartCaptcha fires earlier than Google's. A VPS IP from a non-Russian datacenter is flagged immediately because Yandex expects Russian users from Russian IPs. Yandex also has stricter rate limits per IP (sometimes blocks after 3–5 requests). Unlike Google, Yandex has no equivalent to DataForSEO as an easy fallback — Yandex.Webmaster API provides clicks/impressions data but not raw SERP positions.

**Why it happens:**
Developers test Yandex parsing locally (from a residential IP) where it works fine, then deploy to a VPS (datacenter IP) where it fails immediately.

**How to avoid:**
- Prioritize Yandex Webmaster API for position data: it's official, rate-limit-friendly, and provides historical data.
- For cases requiring SERP parsing, use Russian residential proxies specifically.
- Yandex XML API (`xmlsearch.yandex.ru`) is the official programmatic search API — has a free tier with 1,000 requests/day. Use this instead of scraping.
- Treat Yandex SERP scraping as last resort, not primary method.
- In `docker-compose.yml`, separate Yandex requests to a worker that routes traffic through a proxy.

**Warning signs:**
- All Yandex SERP tasks returning empty or CAPTCHA from day one of VPS deployment
- `SmartCaptcha` in Playwright page HTML
- Yandex position checks fail consistently while Google works

**Phase to address:**
Iteration 3 (design Yandex integration — choose API-first before implementing any scraping)

---

### Pitfall 10: WordPress REST API — Application Password Stored in Plaintext

**What goes wrong:**
WP Application Passwords are stored in the database as plaintext strings or base64-encoded (which is not encryption). If the database is compromised (SQL injection, backup leak, misconfigured pgAdmin), all managed WP sites are immediately compromised. With Application Passwords, an attacker has full WP REST API access — can delete all posts, create admin users, deface sites.

**Why it happens:**
Developers treat credentials as configuration, store them like other config values, and don't apply encryption because "it's internal."

**How to avoid:**
- Fernet-encrypt all Application Passwords before storing in DB (the PROJECT.md already mandates this — enforce it from the first WP model migration).
- The Fernet key lives in `.env` / Docker secret, never in source code or DB.
- Use a separate `credentials` table with `encrypted_value` column — never a plaintext `password` column.
- Rotate Fernet key procedure: decrypt all, re-encrypt with new key, update key. Document this procedure.
- Audit log every use of a WP credential: `used_for`, `task_id`, `timestamp`.
- Verify WP connection only stores the credential after successful test — never store unverified credentials.

**Warning signs:**
- `wpsites` table has a `password` or `app_password` column of type `text` without `_encrypted` suffix
- Fernet key is committed to git (check `.env.example` for accidentally real values)
- No audit log on credential access

**Phase to address:**
Iteration 1 (WP site model is created here — encrypt from the first migration)

---

### Pitfall 11: WordPress REST API — Rate Limiting and Large Sites

**What goes wrong:**
WP REST API has no built-in rate limiting but the hosting provider often does (shared hosting, Cloudflare, WP-specific security plugins like Wordfence). Fetching all posts for a 2,000-post site with `GET /wp-json/wp/v2/posts?per_page=100` in a loop makes 20 requests in rapid succession. Wordfence (common on client sites) flags this as a brute-force attack and blocks the platform's IP. The client's site becomes inaccessible from the platform permanently until manually whitelisted.

**Why it happens:**
Development tests on a clean WP install. Production client sites have security plugins the developer didn't account for.

**How to avoid:**
- Add mandatory delay between WP API pagination requests: minimum 0.5s, configurable per site.
- Implement exponential backoff on 429 and 403 responses from WP API.
- Detect Wordfence block responses (they return specific HTML, not JSON) and surface an alert in the UI: "Site X: IP blocked by security plugin — whitelist required."
- Cache the full post list in the platform DB; refresh only on explicit request or scheduled (not every crawl).
- For sites with 1,000+ posts, use incremental sync: fetch only `modified_after=last_sync_timestamp`.

**Warning signs:**
- WP API returns HTML instead of JSON (security plugin redirect)
- HTTP 403 or 429 from WP API
- `requests.exceptions.JSONDecodeError` when parsing WP API response
- WP API calls succeed in dev but fail immediately in production on client sites

**Phase to address:**
Iteration 1 (WP API client implementation — build throttling and error handling before any other WP feature)

---

### Pitfall 12: JWT Role Enforcement — Missing Authorization at Service Layer

**What goes wrong:**
Developer adds role checks in route decorators (`Depends(require_role("manager"))`), but the service layer functions are called directly in tests or by Celery tasks without going through the FastAPI route. A Celery task that runs with admin context can call `service.get_project(project_id)` for any project, bypassing the manager's "own projects only" restriction. The route-level check gives false confidence that data is isolated.

**Why it happens:**
FastAPI's dependency injection is route-level. Service functions don't know about the caller's role. This works until someone calls the service from a non-route context.

**How to avoid:**
- Pass `current_user: User` as an explicit parameter to all service functions that return user-scoped data.
- Service functions enforce scoping: `if current_user.role == "manager" and project.owner_id != current_user.id: raise 403`.
- Never use a "super user" context in Celery tasks that touches user-owned data — pass the originating user's ID and scope accordingly.
- Write tests that call service functions directly with different user roles, not just through the HTTP API.
- In Iteration 7 hardening: add integration tests that verify a manager cannot access another manager's project at both HTTP and service layer.

**Warning signs:**
- Authorization tests only use `httpx` / HTTP client — no direct service layer tests
- Service functions take `site_id` but not `current_user_id`
- Celery tasks call service functions without user context

**Phase to address:**
Iteration 1 (auth design) and Iteration 7 (enforcement audit — test every service function)

---

### Pitfall 13: Celery Beat Schedule Stored in Redis Gets Wiped

**What goes wrong:**
Celery Beat with `redbeat` scheduler (or even default file-based scheduler) stores its schedule state. When Redis is flushed (for any reason: debug session, `FLUSHALL`, data migration, Redis restart with `--save ""`) all scheduled tasks disappear. The system silently stops crawling and checking positions. The team notices weeks later when clients ask why position charts stopped updating.

**Why it happens:**
Developers `FLUSHALL` Redis in development to clear test data, not realizing it also wipes the Beat schedule. In production, Redis restarts without persistence configured, losing state.

**How to avoid:**
- Use `redbeat` with Redis persistence: configure Redis with `appendonly yes` in `docker-compose.yml` for the Redis service.
- Store the crawl schedule definition in PostgreSQL (the PROJECT.md requires "configurable from UI with no restart"). Redis is cache, Postgres is source of truth. On Beat startup, reload schedules from Postgres.
- Add to `GET /health`: check that at least N active Beat schedules exist in Redis; alert if zero.
- In development, never use `FLUSHALL` — use `FLUSHDB` on a test-only Redis DB (use DB 1 for tests, DB 0 for app).

**Warning signs:**
- No crawl tasks in Celery queues for >24 hours without explanation
- `redbeat` or `celery inspect scheduled` returns empty
- Position last_checked timestamps stop advancing

**Phase to address:**
Iteration 2 (first crawl schedule) — design schedule persistence before implementing

---

### Pitfall 14: Docker Compose Volume Management — Data Loss on Rebuild

**What goes wrong:**
Developer runs `docker-compose down -v` to reset the environment (common during development). `-v` removes named volumes, destroying all PostgreSQL data. In a production scenario where the developer runs this to "fix" a stuck service, all production data is gone with no backup.

**Why it happens:**
`-v` flag is in muscle memory from development. The difference between `docker-compose down` and `docker-compose down -v` is a single character.

**How to avoid:**
- Use named volumes with explicit external declarations for production data:
  ```yaml
  volumes:
    postgres_data:
      external: true
  ```
  Marking a volume as `external: true` requires it to be created manually (`docker volume create`) and prevents `docker-compose down -v` from deleting it.
- Document this in README and deployment runbook.
- Automated daily backup: `pg_dump` piped to a timestamped file outside the container, retained for 7 days.
- Add a pre-commit hook or Makefile target that warns before running `down -v`.

**Warning signs:**
- Production `docker-compose.yml` uses anonymous volumes or inline volume definitions
- No `pg_dump` cron job exists
- Developers have direct access to run `docker-compose down -v` in production

**Phase to address:**
Iteration 1 (infrastructure setup — volume strategy before any data is stored)

---

### Pitfall 15: Async SQLAlchemy + Celery — "Detached Instance" Errors

**What goes wrong:**
A FastAPI route loads an ORM object, passes its `id` to a Celery task. Inside the Celery task (sync context), the developer tries to use an `AsyncSession` from the FastAPI session factory — which doesn't work because Celery runs in a different event loop (or no event loop). Alternatively: an ORM object created in one `AsyncSession` is accessed after the session closes, raising `DetachedInstanceError` when accessing a lazy relationship.

**Why it happens:**
SQLAlchemy 2.0 async is subtly different from sync. Celery workers run in threads or processes with their own event loops. Sharing sessions or ORM objects across async/sync boundaries is a common mistake.

**How to avoid:**
- Celery tasks always create their own `AsyncSession` using `asyncio.run()` or a dedicated sync session factory:
  ```python
  def my_celery_task(site_id: int):
      with SyncSessionLocal() as session:  # sync session for Celery
          site = session.get(Site, site_id)
  ```
- Never pass ORM objects between FastAPI and Celery — pass IDs only.
- For Celery tasks that need async (Playwright), use `asyncio.run()` as the task's entry point.
- Disable lazy loading entirely (`lazy="raise"`) on all relationships to catch accidental lazy loads at development time.

**Warning signs:**
- `DetachedInstanceError` in Celery task logs
- `MissingGreenlet: greenlet_spawn has not been called` errors
- Tasks that work in pytest but fail in Celery worker

**Phase to address:**
Iteration 2 (first Celery task that touches the DB)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single Celery queue for all task types | Simpler config, works immediately | Playwright crawls block quick position checks; priority inversion; impossible to scale workers independently | Never — set up queues in Iteration 1 |
| `ignore_result=False` on all tasks | Can inspect any task result | Redis fills with gigabytes of stale serialized data; Redis OOM blocks new submissions | Only for tasks where the API polls for result; use `ignore_result=True` as default |
| One `concurrency=8` Celery worker for everything | Simple deployment | OOM kill from 8 concurrent Chromium instances; no isolation between fast API tasks and slow crawls | Never — always separate Playwright workers |
| Skip `keyword_positions` partitioning until "later" | Faster initial implementation | Schema migration on a 10M+ row table requires extended downtime; cannot add partitions to existing table (must recreate) | Never — partition before first write |
| Storing Fernet key in `docker-compose.yml` `environment:` | Easy to configure | Key visible in `docker inspect`, process list, and Docker logs | Never — use Docker secrets or `.env` file excluded from git |
| Application Password in plaintext for "internal tool" | No encryption setup needed | Full WP admin access for all clients if DB is leaked | Never — PROJECT.md mandates Fernet from Iteration 1 |
| Synchronous `requests` in Celery tasks instead of `httpx` async | Simpler code | Blocks Celery thread; reduces effective concurrency; no async support for WP API | Only in truly sync task code where async adds no benefit; use `httpx` consistently |
| Single `AsyncSession` shared across request handlers | Avoids dependency boilerplate | Session state corruption; connection leaks; impossible to debug | Never — one session per request via dependency injection |
| Daily position checks for all 500 keywords at 09:00 | Simple schedule | Thundering herd: 500 SERP requests simultaneously, instant IP ban | Never — stagger with random offset per keyword or batch with delays |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| WordPress REST API | Assume `/wp-json/wp/v2/` is always enabled and accessible | Verify WP REST API, Application Passwords, and permalink structure during site connection; store `connection_verified_at` |
| WordPress REST API | Fetch all posts with `per_page=100` in tight loop | Paginate with 0.5s delay; use `modified_after` for incremental sync; detect and handle security plugin blocks |
| WordPress REST API | Use Basic Auth with admin password | Use Application Passwords only — they are revocable, scoped, and don't require the main admin password |
| Yoast/RankMath meta | Assume both plugins are always present | Detect which SEO plugin is active per site via `GET /wp-json/yoast/v1/` or `GET /wp-json/rank-math/v1/` probe; store `seo_plugin` per site |
| Google Search Console | Store OAuth refresh token in code/config | Store refresh token encrypted in DB; handle token expiry with automatic refresh; handle revocation gracefully |
| Google Search Console | Query full date range without pagination | GSC API returns max 1,000 rows per request; use `startRow` pagination for sites with many queries |
| DataForSEO | Send all keywords in one API call | DataForSEO has per-call limits; batch keywords in groups of 100; handle partial failures per keyword |
| Celery + Redis | Use Redis as both broker and result backend on same DB | Separate Redis DBs (DB 0 broker, DB 1 results) or use different Redis instances to prevent key collisions |
| Telegram Bot API | Send alert for every position change | Will spam on large crawls; implement threshold (drop > N positions), deduplication (one alert per keyword per day), and quiet hours |
| GSC OAuth | Redirect URI hardcoded to localhost | Parameterize redirect URI via env var; ensure it matches what's registered in Google Cloud Console |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `keyword_positions` full table scan | Position history chart >5s; dashboard timeout | Partition by month + index `(keyword_id, checked_at DESC)` | ~500K rows (~6 months at 50 sites, 500 keywords) |
| No DB connection pooling tuning | "Too many connections" errors; random 500s under load | Set `pool_size`, `max_overflow`, `pool_timeout` explicitly; set `pool_pre_ping=True` | When total connections across workers exceeds PostgreSQL `max_connections` (default 100) |
| Loading all crawl snapshots for diff comparison | Memory spike during diff computation; worker OOM | Stream snapshot JSON; compute diff server-side in chunks; never load all snapshots of a site in memory | Sites with >200 pages, snapshots >1MB each |
| Uncached dashboard aggregation queries | Dashboard >3s at 20 sites | Use materialized views or Redis cache (5-minute TTL) for dashboard aggregates | ~20 sites with 500+ keywords each |
| Playwright page.goto() without timeout | Task hangs forever on unresponsive sites | Always set `timeout=30000` on `goto()`, `wait_for_selector()`, `wait_for_load_state()` | Any site that times out (CDN issues, slow servers) |
| Celery `chord` for large groups | `chord` result tracking floods Redis | For groups >100 tasks, use DB-based tracking instead of Celery chord | `chord` with >100 tasks causes Redis memory spike |
| Synchronous `pg_dump` backup during peak hours | DB locks; slow queries during backup window | Schedule `pg_dump` at off-peak hours; use `--no-lock-wait` and replication for zero-lock backup | Sites being crawled while backup runs |
| Storing page HTML in PostgreSQL JSONB snapshots | DB size grows unbounded; slow JSON queries | Store only structured diff data (changed fields + old/new values), not full HTML; HTML goes to filesystem or object storage | After ~6 months of daily crawls on 50 sites (hundreds of GB) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| WP Application Passwords in plaintext DB column | Full WP admin access to all client sites if DB leaked | Fernet encryption from first migration; key in Docker secret / `.env` |
| JWT `exp` too long (7 days+) | Compromised token cannot be revoked; admin access persists after team member leaves | `exp=24h` as per PROJECT.md; implement token blacklist in Redis for immediate revocation on role change or user deletion |
| Fernet key committed to git | All historical DB backups decryptable forever | `.env` in `.gitignore`; `pre-commit` hook that rejects commits containing `FERNET_KEY=` |
| Client users can guess other project IDs | Data leakage between clients | Never expose sequential integer IDs to clients; use UUIDs for `project_id`, `site_id` in URLs; enforce ownership at service layer |
| SERP parsing credentials (proxy, DataForSEO) in logs | Credential exposure in log aggregators | Sanitize headers and auth in loguru; use structured logging with explicit field exclusion |
| Missing rate limiting on auth endpoints | Brute-force password attacks | `slowapi` rate limit on `/auth/login`: 5 requests/minute per IP; lock account after 10 failures |
| Application Password used for read + write operations | Leaked credential allows content modification | Create separate WP Application Passwords per platform feature if WP supports it; use minimal scope |
| Telegram bot token in Docker Compose `environment:` | Token visible in container inspection | Store in `.env` file; use Docker secrets in production |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Long-running operations block UI (position check, crawl) | User clicks button, page spins, gives up | All operations >2s go through Celery; UI shows "job queued" immediately with a task ID; HTMX polls `/tasks/{id}/status` |
| Position changes shown as raw numbers without delta indicators | Manager cannot tell if position improved or dropped without mental math | Always show delta vs previous check with color (green up, red down) and arrow icons; this is table-stakes for an SEO tool |
| Crawl errors shown only in logs | Team doesn't know a site is broken for days | Surface crawl errors in UI dashboard; auto-create a task on consecutive crawl failures; Telegram alert on site-level failure |
| All 500 keywords in one flat table | Manager cannot find relevant keywords; table lags | Paginate server-side (50 per page); filter by cluster/page/status; search by keyword text; lazy-load history charts |
| Position history chart loads for every keyword row | Dashboard freeze with 500 keywords | Load charts on-demand (click to expand); or only for keywords in current viewport (intersection observer) |
| No confirmation before pushing WP content changes | Accidental mass content modification on production sites | Mandatory diff preview with explicit "Confirm and Push" button; batch operations require re-authentication (password prompt) |
| Scheduled tasks with no visible last-run/next-run info | Team cannot tell if automation is working | Show `last_run_at`, `next_run_at`, `last_status` for every scheduled task in the UI settings page |

## "Looks Done But Isn't" Checklist

- [ ] **Playwright Crawler:** Shows "crawl complete" in UI — verify Chromium processes are actually terminated (`pgrep chromium` should return empty after task finishes)
- [ ] **Position Tracking:** Positions populate in DB — verify partition is created for the current month before writing, or INSERTs silently fail in partitioned tables
- [ ] **WP Credentials:** Site connection test passes — verify the Application Password is stored Fernet-encrypted, not plaintext (check column value directly in DB)
- [ ] **Celery Beat Schedules:** Schedule visible in UI — verify schedule survives a Redis restart (Redis persistence must be enabled, or schedules reload from Postgres on startup)
- [ ] **JWT Auth:** Login endpoint returns a token — verify role enforcement at service layer, not just route decorator (test manager accessing another manager's project ID directly)
- [ ] **SERP Parser:** Returns positions for 10 test keywords — verify behavior at 100+ keywords (rate limiting, delays, IP ban detection)
- [ ] **Diff Preview:** Before/after diff renders in UI — verify rollback actually reverts WP content via API, not just marks the job as rolled back in DB
- [ ] **Celery Task Retry:** Retry logic present in code — verify one failing site's tasks do NOT block processing of other sites (use separate task IDs, not shared state)
- [ ] **Docker Compose Stack:** Starts with `docker-compose up --build` — verify it starts from zero on a clean system with no cached volumes or images
- [ ] **Audit Log:** Actions appear in `audit_log` table — verify WP credential access, role changes, and bulk operations are all logged (not just auth events)
- [ ] **Telegram Alerts:** Alert fires for test drop — verify duplicate suppression (same keyword doesn't alert twice in 24h even with multiple checks)
- [ ] **Report Generation:** PDF report generates — verify it works at scale (50 sites, 500 keywords — memory usage, not just correctness)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Playwright browser leak filling VPS RAM | MEDIUM | Restart celery-worker container; add `--max-tasks-per-child=50` to worker command; add `try/finally` browser cleanup in all tasks |
| Redis flushed, Beat schedule lost | LOW (if schedules in Postgres) / HIGH (if only in Redis) | If Postgres-backed: restart Beat, schedules reload automatically. If Redis-only: manually re-enter all schedules via UI; add Postgres persistence going forward |
| `keyword_positions` too slow, needs partitioning | HIGH | Create new partitioned table; migrate data in batches with zero-downtime migration (write to both, backfill, swap); requires maintenance window at 10M+ rows |
| Docker volume deleted with `-v` | HIGH (data loss) | Restore from last `pg_dump` backup; re-import keyword CSV files; re-add WP credentials; accept data loss for period since last backup |
| VPS IP banned by Google for SERP parsing | LOW-MEDIUM | Switch to DataForSEO API immediately; wait 48–72h before retrying direct scraping; add proxy rotation before resuming |
| WP credentials leaked (DB compromised) | HIGH | Immediately revoke all Application Passwords from WP admin on each site; generate new credentials; rotate Fernet key; notify clients |
| N+1 queries causing dashboard timeout | MEDIUM | Add caching layer (Redis, 5-min TTL) as immediate fix; then fix queries with proper joins/CTEs in next sprint |
| `keyword_positions` INSERT failures (missing partition) | LOW | Create missing partition manually (`CREATE TABLE keyword_positions_2026_04 PARTITION OF keyword_positions FOR VALUES FROM ('2026-04-01') TO ('2026-05-01')`); add Beat task to pre-create partitions |
| Session pool exhaustion | LOW-MEDIUM | Restart FastAPI workers to clear leaked sessions; identify leaking endpoint via `pg_stat_activity`; fix session lifecycle in code |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Playwright browser leaks | Iteration 2 | `pgrep chromium` returns 0 after crawl task completes; worker RAM stable over 24h |
| Concurrent Playwright OOM | Iteration 2 | Worker topology configured: dedicated queue, `concurrency=2`, `max_memory_per_child` set |
| Task granularity (whole site as one task) | Iteration 2 | `crawl_page` is a separate task; `crawl_run` table tracks per-page progress |
| Result backend Redis bloat | Iteration 1 | All crawl/SERP tasks have `ignore_result=True`; `result_expires=3600` set in Celery config |
| `keyword_positions` schema without partitioning | Iteration 3 | Alembic migration creates partitioned table; `EXPLAIN ANALYZE` on 90-day query shows index scan |
| SQLAlchemy session leaks | Iteration 1 | `pg_stat_activity` idle connections stay flat over 100 requests; `pool_pre_ping=True` configured |
| N+1 query patterns | Iteration 1 (pattern), Iteration 6 (dashboard) | `echo=True` shows ≤5 queries for dashboard load; response <3s at 50 sites |
| Google SERP bot detection | Iteration 3 | Stealth patches applied; DataForSEO as primary; Playwright SERP limited to <50/day without proxy |
| Yandex SERP detection | Iteration 3 | Yandex Webmaster API used as primary; XML API as secondary; scraping only with proxy |
| WP credentials plaintext | Iteration 1 | DB column contains `gAAA...` Fernet ciphertext, not readable password |
| WP REST API rate limiting | Iteration 1 | `WPClient` has configurable delay and 429 backoff; test against Wordfence-protected site |
| JWT role enforcement gaps | Iteration 1 (design), Iteration 7 (audit) | Service layer tests verify manager cannot access other manager's data without HTTP layer |
| Celery Beat schedule wiped | Iteration 2 | Schedules stored in Postgres; Beat survives `docker-compose restart redis` |
| Docker volume data loss | Iteration 1 | `postgres_data` volume marked `external: true`; `pg_dump` cron job configured |
| Async/sync session boundary errors | Iteration 2 | Celery tasks use sync session factory; no ORM objects passed across task boundaries |

## Sources

- Playwright official docs: "Browser and context lifecycle" — context-per-task is explicitly discouraged for high-frequency use
- Celery docs: `worker_max_tasks_per_child`, `worker_max_memory_per_child`, `CELERYD_PREFETCH_MULTIPLIER` — all relevant to Playwright worker management
- SQLAlchemy 2.0 async docs: "Session Lifecycle Patterns" — explicit guidance on FastAPI dependency injection pattern
- PostgreSQL docs: Declarative Table Partitioning — `keyword_positions` partitioning strategy
- `playwright-stealth` project (GitHub: `playwright-stealth`) — stealth patches for headless Chrome detection
- Yandex XML API docs (`xmlsearch.yandex.ru`) — official programmatic search, avoids scraping
- DataForSEO API docs — position tracking API, rate limits, batch sizes
- WordPress REST API handbook: "Authentication" — Application Passwords scope and security model
- FastAPI docs: "SQL (Relational) Databases" with async — session dependency pattern
- Known production issues with `redbeat`: schedule loss on Redis flush (GitHub issues #89, #134)
- Docker docs: "Use volumes" — `external: true` volumes and `docker-compose down -v` behavior

---
*Pitfalls research for: SEO Management Platform — FastAPI + Celery + Playwright + PostgreSQL + WordPress REST API*
*Researched: 2026-03-31*
