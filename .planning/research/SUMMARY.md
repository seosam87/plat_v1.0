# Project Research Summary

**Project:** SEO Management Platform
**Domain:** Self-hosted WordPress SEO agency tool (20–100 sites, Playwright + FastAPI + Celery)
**Researched:** 2026-03-31
**Confidence:** HIGH

## Executive Summary

This is a self-hosted, internal SEO management platform for an agency managing 20–100 WordPress sites. The closest analogues are SE Ranking and Screaming Frog combined with a WP-native content pipeline — but no SaaS competitor offers direct WP write-back (TOC injection, schema.org, internal linking) with diff preview and rollback. That WP content pipeline is the structural differentiator and should be treated as the primary value proposition driving adoption.

The recommended architecture is a FastAPI (HTMX + Jinja2) web layer backed by Celery workers for all long-running work (crawling, SERP parsing, WP pipeline), PostgreSQL as the primary store, and Redis as the broker and cache. The stack is well-understood, all version decisions are locked, and the main risks are operational — Playwright memory management, SERP ban avoidance, and `keyword_positions` table growth — all of which must be addressed at specific iterations, not deferred.

Three findings from research differ materially from PROJECT.md's current framing and must be acted on during roadmap planning: `redbeat` is required for UI-driven crawl scheduling (not mentioned in PROJECT.md), DataForSEO should be the primary SERP source (Playwright is the supplement, not vice versa), and `keyword_positions` partitioning must be created in iteration 3's first migration — it cannot be added retroactively to a populated table.

---

## Key Findings

### Recommended Stack

The stack is fully validated with no substitutions needed. Python 3.12 + FastAPI 0.115 + Pydantic v2 + SQLAlchemy 2.0 async is a coherent, compatible unit. Celery 5.4 (not 5.3) is required for Python 3.12 compatibility. HTMX 2.0 (not 1.x) must be used from the start — 2.0 has breaking changes that make a later migration painful.

**Core technologies:**
- Python 3.12 / FastAPI 0.115 / Pydantic 2.7+ — async-first web layer; Pydantic v2 is 3–5x faster; FastAPI 0.115 requires it
- PostgreSQL 16 / SQLAlchemy 2.0 / asyncpg 0.29 / Alembic 1.13 — primary persistent store; async engine for FastAPI, sync engine for Celery workers
- Celery 5.4 / Redis 7.2 / redbeat 2.2 — task queue, scheduling, broker; `redbeat` required for UI-driven schedule changes without worker restart
- Playwright 1.47+ — browser automation for crawling and SERP; one `Browser` per worker process, one `BrowserContext` per task
- Jinja2 3.1 + HTMX 2.0 — server-side rendering; eliminates SPA build toolchain entirely
- httpx 0.27 / authlib 1.3 — async HTTP client for all external APIs; authlib handles GSC OAuth 2.0
- WeasyPrint 62 — HTML-to-PDF for reports; renders existing Jinja2 templates, no extra tooling
- cryptography 42 (Fernet) — WP Application Password encryption at rest

**Key version constraints to enforce:**
- Celery must be 5.4.x — 5.3 has import errors on Python 3.12
- HTMX must be 2.0.x from day one — 1.x to 2.0 has breaking attribute changes
- Do not use psycopg2 — use asyncpg for FastAPI, psycopg3 sync for Celery
- Do not use FastAPI `on_event()` — deprecated; use `lifespan=` with `asynccontextmanager`

### Expected Features

The feature landscape is well-understood from competitor analysis (Semrush, Ahrefs, SE Ranking, Screaming Frog, Topvisor). PROJECT.md covers all table-stakes features. The WP content pipeline is the differentiator.

**Must have (table stakes — missing any of these makes the tool feel broken):**
- Keyword rank tracking with position history (geo + device dimensions)
- Google Search Console integration via OAuth 2.0
- Playwright-based site crawler (title, H1, meta, status, depth, schema detection)
- Page snapshot diffs with change feed UI
- Keyword → page mapping + cannibalization detection
- Dashboard aggregating positions, tasks, and crawl changes across all sites (<3s load)
- Report export (PDF + Excel) — client deliverable; without it, the tool has no external output
- Role-based access (admin / manager / client) — client data isolation is non-negotiable

**Should have (competitive differentiators — WP pipeline is the standout):**
- WP content pipeline: TOC injection, JSON-LD schema.org, internal linking — with mandatory diff preview + rollback (the safety layer is what converts sceptics)
- Yandex Webmaster integration — genuine niche advantage for RU-market agencies; no Western SaaS does this well
- Auto-task creation from crawl findings (404 → task, cannibalization → task, missing schema → task)
- SERP-intersection keyword clustering
- Content plan + one-click WP draft creation
- Template-based page brief generation (no LLM — deterministic output matters for client deliverables)
- Kanban task board tied to SEO findings

**Defer (v2+):**
- LLM-generated content enrichment — add as opt-in after template briefs are validated
- Competitor keyword gap analysis — requires third-party data index; scope tightly via DataForSEO on-demand
- Ad traffic API integrations — CSV upload covers 90% of use cases with zero maintenance burden
- SERP-intersection automated clustering — defer until keyword volumes exceed 500+ per site

### Architecture Approach

The system is a three-layer architecture: FastAPI handles all HTTP routing with Jinja2 + HTMX for server-side rendering; Celery workers handle all long-running operations (crawling, SERP parsing, WP pipeline, report delivery); PostgreSQL is the persistent store and Redis is the broker + cache. The critical boundary is the service layer — services are importable by both FastAPI routes (async) and Celery tasks (sync), with session lifecycle owned by the caller.

**Major components:**
1. FastAPI app — thin routers → service layer → async SQLAlchemy; never puts business logic in route handlers
2. Service layer (`app/services/`) — all business logic; accepts `db` session as parameter; shared between routes and tasks
3. Celery worker pool — three dedicated queues: `crawl` (Playwright-heavy, concurrency=2), `wp` (WP REST calls, concurrency=4), `default` (fast tasks, concurrency=8)
4. Celery Beat + redbeat — cron-style scheduling stored in Redis; UI-configurable without worker restart
5. Integration clients (`app/integrations/`) — thin wrappers for WP REST, GSC, DataForSEO, Telegram; isolated third-party breakage
6. PostgreSQL — `keyword_positions` partitioned by month from iteration 3 first write; async engine (FastAPI) + sync engine (Celery)

**Critical boundary rules:**
- Routes never import ORM models directly — only schemas and services
- Celery tasks use sync SQLAlchemy (psycopg3); no `asyncio.run()` inside tasks except for Playwright
- Pass IDs between FastAPI and Celery — never ORM objects
- Task results for background jobs go to PostgreSQL; only poll-able task results go to Redis result backend

### Critical Pitfalls

The top pitfalls are ranked by blast radius and phase criticality:

1. **`keyword_positions` table without partitioning** — at 50 sites × 500 keywords × 2 engines × 365 days = 18M rows/year; `EXPLAIN ANALYZE` will show full table scans; position charts will time out. Cannot add partitioning to an existing non-partitioned table without a full rebuild. Must be created in iteration 3's first Alembic migration before any position data is written. See PITFALLS.md §Pitfall 5.

2. **Playwright browser leaks in long-running Celery workers** — crashed tasks leave orphaned Chromium processes; VPS RAM climbs until OOM kills Docker stack. Use module-level `Browser` per worker (initialized via `worker_process_init` signal), one `BrowserContext` per task closed in `finally`, `--max-tasks-per-child=50`, and `soft_time_limit` to allow graceful cleanup. Address in iteration 2. See PITFALLS.md §Pitfall 1.

3. **Google SERP ban via Playwright** — headless Chrome is fingerprinted within 5–10 requests at scale; VPS IPs are recognized; production with 500+ keywords triggers CAPTCHAs. DataForSEO must be the primary position-checking method; Playwright SERP parsing is the low-volume supplement only (< 50 queries/day without proxy rotation). Design this correctly in iteration 3. See PITFALLS.md §Pitfall 8.

4. **Celery Beat schedule wiped on Redis flush** — `FLUSHALL` in dev or Redis restart without persistence silently stops all crawling and position checks; team notices weeks later. Configure Redis with `appendonly yes`; store schedule source-of-truth in PostgreSQL; reload from DB on Beat startup; add health check that asserts N active schedules exist. Address in iteration 2. See PITFALLS.md §Pitfall 13.

5. **Single Celery queue for all task types** — a 20-minute Playwright crawl blocks Telegram alerts and quick DB updates; one stuck browser starves all other work. Three queues must be configured in iteration 1 even before Playwright is used: `crawl`, `wp`, `default`. See PITFALLS.md §Pitfall 3 and §Anti-Pattern 3.

6. **Redis result backend bloat** — Celery stores task results indefinitely by default; 50 sites × daily crawls accumulates gigabytes in Redis; Redis OOM blocks new task submission. Set `result_expires=3600` and `ignore_result=True` on all background jobs in iteration 1 Celery config. See PITFALLS.md §Pitfall 4.

7. **Async session leaks in FastAPI** — exception paths can prevent `AsyncSession` from returning to the pool; connection pool exhausts under load; error rate increases with uptime. Always use `yield` with `try/finally` in the session dependency; never share a FastAPI session with a Celery task; set `pool_pre_ping=True`. Address in iteration 1. See PITFALLS.md §Pitfall 6.

---

## Gaps Found During Research (Differ from PROJECT.md)

These items are absent from or inconsistent with the current PROJECT.md framing. The roadmap agent must account for all of them:

| Gap | Severity | Action Required |
|-----|----------|-----------------|
| `redbeat` not mentioned in PROJECT.md | HIGH | Iteration 2 requirement: crawl schedule must be UI-configurable without worker restart. `redbeat` (Redis-backed Beat scheduler) is the only solution that works across multiple containers. The built-in file-based scheduler breaks in Docker. Add `redbeat` to iteration 1 stack setup. |
| DataForSEO is the fallback in PROJECT.md; research reverses this | HIGH | DataForSEO should be the primary SERP source. Playwright SERP parsing is too fragile at scale (ban risk, IP rotation cost). Architect iteration 3 with DataForSEO as primary; Playwright as supplement for low-volume or on-demand checks. |
| No keyword volume / difficulty data source specified | MEDIUM | PROJECT.md mentions "volume estimate" in brief generation but names no source. DataForSEO Keywords Data endpoint is the practical answer — cheap, on-demand, no separate crawled index needed. Add to iteration 3 scope. |
| GSC URL Inspection API not mentioned | MEDIUM | A page can be excluded from Google's index despite having no `noindex` tag (GSC coverage exclusions). The GSC URL Inspection API verifies actual indexation status. Worth adding as enrichment in iteration 3's GSC integration work. |
| No sitemap.xml parsing in crawler | LOW | Sitemaps give the crawler a faster, more complete URL seed list — especially for large sites with deep navigation where link-following alone misses pages. Add as a crawler enhancement in iteration 2. |
| `keyword_positions` partitioning must be iteration 3, migration 1 | CRITICAL | PROJECT.md doesn't specify when partitioning is created. Research is explicit: it must be in the first Alembic migration for this table. Retro-partitioning a populated 10M+ row table requires full table recreation and extended downtime. The roadmap must enforce this as a hard constraint, not an optional enhancement. |
| Yandex SERP scraping is harder than PROJECT.md implies | MEDIUM | Yandex SmartCaptcha fires on VPS datacenter IPs immediately. Priority order for Yandex positions: (1) Yandex Webmaster API (official, rate-limit-friendly), (2) Yandex XML API (1,000 req/day free tier), (3) Playwright with Russian residential proxy as last resort. Design iteration 3's Yandex integration around the API, not scraping. |
| Celery result backend + Redis broker should use separate DBs | LOW | Using the same Redis DB for both broker and result backend can cause key collisions. Use DB 0 for broker, DB 1 for results — configurable via `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` env vars. Wire up in iteration 1. |

---

## Implications for Roadmap

The dependency graph from FEATURES.md and build order from ARCHITECTURE.md align with PROJECT.md's iteration structure. The main adjustments are ensuring the pitfall-prevention steps land in the right iterations and the gap items are explicitly scheduled.

### Phase 1: Infrastructure & Auth Foundation
**Rationale:** Everything depends on auth, the DB session pattern, Celery queue topology, and encrypted WP credentials. Getting these wrong means rework across all subsequent iterations.
**Delivers:** Working Docker Compose stack; JWT auth with 3 roles; WP site CRUD with Fernet-encrypted credentials; 3-queue Celery topology (`crawl`, `wp`, `default`); Redis with `appendonly yes` + `maxmemory-policy allkeys-lru`; `result_expires=3600`; audit log; async session dependency with `try/finally`; `GET /health`.
**Addresses:** Table-stakes site management, auth/RBAC foundation.
**Avoids:** Session leaks (Pitfall 6), Redis bloat (Pitfall 4), plaintext credentials (Pitfall 10), single-queue anti-pattern (Anti-Pattern 3).
**Research flags:** Standard patterns — no additional research needed.

### Phase 2: Crawler & Change History
**Rationale:** The crawler is the highest-leverage early investment — it unblocks TOC/schema detection, change feed, content pipeline triggers, and auto-task creation. Must establish Playwright worker pattern before any task complexity is added.
**Delivers:** Playwright crawler with 3-level task hierarchy (schedule → per-page → finalize); page snapshots with JSON diffs; change feed UI; Celery Beat schedule configurable from UI (requires `redbeat`); sitemap.xml parsing as seed URL source; 404 → auto-task.
**Addresses:** Technical audit table stakes; change feed differentiator.
**Avoids:** Browser leaks (Pitfall 1), OOM from concurrent Playwright (Pitfall 2), Beat schedule wipe (Pitfall 13), monolithic task anti-pattern (Pitfall 3).
**Research flags:** Playwright worker lifecycle (Pattern 4 in ARCHITECTURE.md) is non-obvious — follow the `worker_process_init` signal pattern exactly.

### Phase 3: Semantics & Positions
**Rationale:** Keyword tracking is the primary reason users open the tool daily. The `keyword_positions` schema partitioning must be in this iteration's first migration — it cannot be deferred.
**Delivers:** Keyword import (CSV/XLSX/manual); `keyword_positions` table with monthly range partitioning (created before first write); DataForSEO as primary SERP source; Playwright SERP as low-volume supplement; GSC OAuth 2.0 integration + URL Inspection API; Yandex Webmaster API (not scraping); keyword volume data via DataForSEO Keywords Data endpoint; position history UI; SERP-intersection clustering; cannibalization detection; Telegram alerts.
**Addresses:** Position tracking (core table stakes); GSC integration; Yandex advantage.
**Avoids:** `keyword_positions` partitioning debt (Pitfall 5), Google SERP ban (Pitfall 8), Yandex ban (Pitfall 9).
**Research flags:** DataForSEO API batching and rate limits need validation; GSC pagination (`startRow`) for high-traffic sites.

### Phase 4: WP Content Pipeline
**Rationale:** The differentiator. Requires crawl data (page list, detected missing TOC/schema) and keyword DB (for internal linking relevance). Must not be built before those foundations exist.
**Delivers:** Celery pipeline per page (download → parse → generate TOC/schema/links → diff preview); mandatory diff preview UI before push; rollback history; Yoast/RankMath meta write-back; batch processing by category.
**Addresses:** WP content pipeline differentiator (TOC injection, schema.org, internal linking).
**Avoids:** WP rate-limiting (Pitfall 11); per-site semaphore with Redis token bucket; exponential backoff on 429/403.
**Research flags:** Yoast vs RankMath field name differences need per-site detection (`seo_plugin` stored on site model).

### Phase 5: Projects, Tasks & Content Plan
**Rationale:** Aggregates data from all prior subsystems. Can only be built once crawl, positions, and WP pipeline exist. Kanban + auto-task creation closes the loop from data → action.
**Delivers:** Kanban board with drag-and-drop; auto-task creation from crawl findings; content plan with keyword → title → status → WP post link; one-click WP draft creation; template-based page brief (PDF/HTML download).
**Addresses:** Task board differentiator; content plan workflow.
**Research flags:** Standard patterns; brief template design is a product decision, not a technical research question.

### Phase 6: Reports & Ad Traffic
**Rationale:** Terminal consumer — reads from all prior subsystems but writes to none. Dashboard aggregation queries must be designed carefully to hit the < 3s target at 50 sites.
**Delivers:** Dashboard with Redis-cached aggregates (5-min TTL); project reports (PDF + Excel); scheduled delivery via Celery Beat (Telegram + SMTP); ad traffic CSV upload + period comparison.
**Addresses:** Report export (table stakes); ad traffic module.
**Avoids:** N+1 dashboard queries (Pitfall 7); use CTEs/window functions for aggregation, not Python loops over sites.
**Research flags:** Dashboard query design for 50 sites × 500 keywords — run `EXPLAIN ANALYZE` during development.

### Phase 7: Client Access & Hardening
**Rationale:** Role enforcement audit, rate limiting, and observability. Adding this last ensures the full feature surface is known before hardening.
**Delivers:** Full RBAC enforcement at service layer (not just route decorators); client invite links; `slowapi` rate limiting; Celery Flower or custom task status UI; structured JSON logging (loguru); OpenAPI docs; `GET /health` with DB + Redis + Celery + Beat schedule checks; deploy README.
**Addresses:** Client access; production hardening.
**Avoids:** Role bypass at service layer (Pitfall 12); Flower exposed without auth.
**Research flags:** Standard patterns.

### Phase Ordering Rationale

- Auth and DB session patterns must be iteration 1 — every subsequent phase depends on them, and retrofitting correct session management is painful.
- Crawler before positions — positions require keywords and crawl infrastructure; the Playwright worker pattern established in iteration 2 is reused by SERP parsing in iteration 3.
- WP pipeline after crawl + keywords — the pipeline needs to know which pages exist (crawl) and which keywords are relevant (keyword DB) to generate meaningful internal links.
- Reporting last — reads from everything; premature reporting wastes effort if upstream schemas change.
- `keyword_positions` partitioning is a hard constraint, not an ordering preference — it must be iteration 3's first migration.

### Research Flags

Phases needing additional research during planning:
- **Phase 3 (Positions):** DataForSEO API rate limits and batch sizes; GSC `startRow` pagination behaviour at scale — validate against API docs before writing integration code.
- **Phase 4 (WP Pipeline):** Yoast vs RankMath detection and field name mapping — test against real sites with both plugins before finalising the `wp_service` interface.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Infrastructure):** All patterns are well-documented in ARCHITECTURE.md and STACK.md.
- **Phase 5 (Projects/Tasks):** Standard CRUD + Kanban; no novel integration challenges.
- **Phase 7 (Hardening):** Standard middleware and logging patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified for Python 3.12 compatibility; version compatibility matrix in STACK.md |
| Features | HIGH | Based on direct knowledge of 6+ competing tools; competitor feature analysis in FEATURES.md |
| Architecture | HIGH | Patterns are standard FastAPI + Celery; code examples in ARCHITECTURE.md are production-tested patterns |
| Pitfalls | HIGH | All 15 pitfalls are grounded in specific failure modes with observable warning signs |

**Overall confidence:** HIGH

### Gaps to Address During Implementation

- **DataForSEO Keywords Data endpoint pricing/limits:** Validate credits consumption per keyword before wiring up volume lookups in iteration 3.
- **GSC URL Inspection API quotas:** 2,000 queries/day per project; plan batch scheduling strategy for sites with 2,000+ pages.
- **Yandex XML API availability:** Confirm the free tier (1,000 req/day) is accessible from a non-RU VPS; may require account-level configuration.
- **WeasyPrint Docker image size:** If image size is a concern, the `apt-get install -y libpango-1.0-0 libcairo2` pattern in STACK.md handles it; decide at iteration 6 when PDF is implemented.

---

## Sources

### Primary (HIGH confidence)
- STACK.md — full version compatibility matrix, installation commands, alternatives considered
- FEATURES.md — competitor feature analysis (Semrush, Ahrefs, SE Ranking, Serpstat, Screaming Frog, Topvisor); gap analysis vs PROJECT.md
- ARCHITECTURE.md — 6 implementation patterns with code examples; anti-patterns; data flow diagrams; build order implications
- PITFALLS.md — 15 pitfalls with root cause analysis, prevention steps, warning signs, and phase assignments
- PROJECT.md — authoritative requirements, constraints, and iteration structure

### Secondary (MEDIUM confidence)
- DataForSEO API documentation — SERP, Keywords Data, Backlinks endpoints
- Google Search Console API — Search Analytics, URL Inspection quotas
- Yandex Webmaster API + Yandex XML API — position data and programmatic search

---
*Research completed: 2026-03-31*
*Ready for roadmap: yes*
