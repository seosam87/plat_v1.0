# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

This repository contains **GSD (get-shit-done) v1.30.0** — a project management and AI-assisted development framework for Claude Code. It is not a traditional software application but a workflow orchestration system that lives inside `.claude/` and provides structured commands, agents, and tooling for managing multi-phase software projects.

## Invoking the Framework

GSD commands are invoked as Claude Code slash commands with the `gsd:` prefix:

```
/gsd:new-project          # Initialize a new project with roadmap
/gsd:discuss-phase        # Gather decisions before planning a phase
/gsd:plan-phase [N]       # Generate a PLAN.md for a phase
/gsd:execute-phase        # Run tasks from the current PLAN.md
/gsd:review               # Verify/QA the current phase
/gsd:complete-milestone   # Mark a phase complete and advance
/gsd:research-phase       # Deep ecosystem research for a phase
/gsd:debug                # Troubleshoot failures
/gsd:health               # Project health report
/gsd:stats                # Execution metrics
/gsd:map-codebase         # Analyze project structure
```

The underlying Node.js CLI can be called directly:
```bash
node .claude/get-shit-done/bin/gsd-tools.cjs <command> [args]
```

## Architecture

```
.claude/
├── settings.json              # Claude Code harness config (hooks, statusline)
├── package.json               # {"type":"commonjs"}
├── commands/gsd/              # 57 workflow orchestrators (markdown)
├── agents/                    # 18 specialized AI agents (markdown definitions)
├── hooks/                     # 4 automated gates (JS)
│   ├── gsd-check-update.js    # SessionStart: check for updates
│   ├── gsd-context-monitor.js # PostToolUse: track context usage
│   ├── gsd-prompt-guard.js    # PreToolUse: validate edits
│   └── gsd-statusline.js      # Status bar display
└── get-shit-done/
    ├── bin/
    │   ├── gsd-tools.cjs      # Central CLI utility (state, git, phase ops)
    │   └── lib/               # 14 CJS modules (core, state, phase, roadmap, etc.)
    ├── templates/             # 40+ markdown templates for project artifacts
    ├── references/            # 16 reference guides (config schema, model profiles, etc.)
    └── workflows/             # Additional workflow documentation
```

### Data Flow

Slash commands invoke orchestrators in `commands/gsd/`, which spawn specialized agents and call `gsd-tools.cjs` for file I/O, state updates, and git commits. Project state is persisted in markdown files: `STATE.md`, `ROADMAP.md`, `PLAN.md`, `SUMMARY.md`.

### Key Agents

| Agent | Role |
|-------|------|
| `gsd-planner` | Generates PLAN.md task breakdowns |
| `gsd-executor` | Executes tasks from plans |
| `gsd-verifier` | QA and acceptance validation |
| `gsd-debugger` | Troubleshooting and recovery |
| `gsd-phase-researcher` | Deep technical research |
| `gsd-roadmapper` | Creates project roadmaps |
| `gsd-plan-checker` | Validates plan quality |

### Configuration

`gsd-file-manifest.json` tracks all framework files with SHA256 hashes. The config schema (in `templates/config.json`) controls workflow behavior: research gates, plan checks, auto-advance, concurrent agent limits, and confirmation gates.

## Modifying the Framework

- **Commands** live in `.claude/commands/gsd/` as markdown files describing orchestration logic
- **Agent definitions** live in `.claude/agents/` as markdown files
- **Core logic** lives in `.claude/get-shit-done/bin/gsd-tools.cjs` and `bin/lib/`
- **Templates** for project artifacts live in `.claude/get-shit-done/templates/`
- After modifying files tracked in `gsd-file-manifest.json`, update the manifest hashes accordingly

<!-- GSD:project-start source:PROJECT.md -->
## Project

**SEO Management Platform**

An internal SEO management platform for a team managing 20–100 WordPress sites for clients. It centralises keyword tracking, site crawling, content optimisation (TOC, schema.org, internal linking), SEO project management, and reporting — all in one self-hosted web application. Built for a solo developer + Claude workflow, deployed via Docker Compose on a single VPS.

**Core Value:** A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.

### Constraints

- **Tech Stack**: Python 3.12, FastAPI 0.111+, SQLAlchemy 2.0 async, Alembic, asyncpg, Celery 5 + Redis 7, Playwright 1.45+, Jinja2 + HTMX — fixed, no substitutions.
- **Database**: PostgreSQL 16 only; all schema changes via Alembic migrations, no direct schema edits in production.
- **Security**: Passwords bcrypt, WP credentials Fernet-encrypted, JWT exp=24h, HTTPS in production, rate limiting (slowapi) from iteration 7.
- **Celery**: retry=3 for all external API calls; one site failure must not stop processing of others.
- **Performance**: UI pages < 3s; long operations (position checks, crawling) are always async via Celery — UI never blocks.
- **Testing**: pytest + httpx AsyncClient; service layer coverage > 60% by iteration 4.
- **Logging**: loguru, JSON format, DEBUG/INFO/ERROR levels, 10 MB rotation, 30-day retention.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | Runtime | 3.12 is the stable LTS-track release with best async performance; 3.13 exists but ecosystem adoption lags — stay on 3.12 for 2025 builds |
| FastAPI | 0.115.x | ASGI web framework | 0.115 (released late 2024) is the stable branch for 2025; 0.111 is fine but 0.115 adds Pydantic v2 perf wins and lifespan-only startup (no deprecated `on_event`) |
| Pydantic | 2.7+ | Data validation (FastAPI dependency) | Pydantic v2 is Rust-core; 3–5x faster than v1; FastAPI 0.111+ requires v2 — do not mix with v1 |
| PostgreSQL | 16.x | Primary database | PG16 adds logical replication improvements and parallel query gains; PG17 exists (Oct 2024) but Docker images are less battle-tested — 16 is the safe 2025 production choice |
| asyncpg | 0.29.x | Async PostgreSQL driver | Required by SQLAlchemy async engine; fastest pure-async PG driver; no sync fallback needed |
| SQLAlchemy | 2.0.x (≥2.0.30) | ORM + query builder | 2.0 is the only version with proper async support; use `AsyncSession` + `async_sessionmaker` pattern; never use 1.4 legacy style |
| Alembic | 1.13.x | Database migrations | Tight SQLAlchemy coupling means staying on latest 1.13.x; use `--autogenerate` but always review generated migrations before applying |
| Redis | 7.2.x | Message broker + cache | Redis 7.2 is the LTS branch for 2025; Redis 8 is in preview — don't use it in production yet |
| Celery | 5.4.x | Distributed task queue | 5.4 fixes several Python 3.12 compatibility issues present in 5.3; use `celery[redis]` extra; configure `task_acks_late=True` for reliability |
| Celery Beat | 5.4.x (bundled) | Periodic task scheduler | Use `django-celery-beat`-style DB backend via `celery-beat-scheduler` or the built-in `redbeat` for DB-driven schedule changes without worker restart |
| Playwright | 1.45+ (≥1.47) | Browser automation / SERP parsing | 1.47+ adds better stealth context options; use `playwright[chromium]` only to keep Docker image small; async API throughout |
| Jinja2 | 3.1.x | Server-side HTML templating | Pairs natively with FastAPI via `Jinja2Templates`; 3.1.x is stable; no breaking changes expected |
| HTMX | 2.0.x | Partial page updates without SPA | HTMX 2.0 (released mid-2024) removed some legacy attributes (`hx-ws`, `hx-sse` moved to extensions) — use 2.0 from the start to avoid later migration |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Auth & Security** | | | |
| python-jose[cryptography] | 3.3.x | JWT encode/decode | Use for `access_token` + `refresh_token`; set `algorithm="HS256"` minimum, `RS256` if you need public key verification |
| passlib[bcrypt] | 1.7.x | Password hashing | `CryptContext(schemes=["bcrypt"])` — bcrypt cost factor 12 recommended for 2025 hardware |
| cryptography | 42.x | Fernet symmetric encryption | WP Application Password encryption at rest; `Fernet` is in this package; pin to 42.x (43 has minor API changes) |
| python-multipart | 0.0.9+ | Form/file upload parsing | Required for FastAPI form bodies and CSV/XLSX uploads; FastAPI does not auto-install it |
| slowapi | 0.1.9 | Rate limiting for FastAPI | Wraps `limits` library; integrates with FastAPI middleware; attach to `app.state.limiter`; use Redis storage backend in production |
| **Database Utilities** | | | |
| greenlet | 3.x | SQLAlchemy async bridge | Required by SQLAlchemy async; installed automatically but pin it to avoid breakage on Python 3.12 |
| psycopg2-binary | — | **Do NOT use** | See "What NOT to Use" — asyncpg replaces this for async workloads |
| **HTTP Client** | | | |
| httpx | 0.27.x | Async HTTP client | Use for WP REST API, GSC OAuth, DataForSEO calls; `httpx.AsyncClient` with connection pooling; replaces `requests` entirely |
| **Task Queue Extras** | | | |
| redis-py | 5.0.x | Redis client (Celery uses it internally) | Also use directly for manual cache writes, rate-limit counters, and pub/sub |
| flower | 2.0.x | Celery task monitoring UI | Web UI at port 5555; shows worker status, task history, failure rates; secure behind HTTP Basic Auth in production |
| redbeat | 2.2.x | DB-backed Celery Beat schedule | Stores periodic task schedule in Redis; enables UI-driven schedule changes without restarting Beat worker; replaces file-based `celerybeat-schedule` |
| **Data Import/Export** | | | |
| openpyxl | 3.1.x | Excel read/write (.xlsx) | Keyword import from Topvisor XLSX format + report export; pure Python, no LibreOffice dependency |
| python-docx | — | Word export | Not needed per PROJECT.md scope — skip |
| **PDF Generation** | | | |
| weasyprint | 62.x | HTML→PDF conversion | Renders Jinja2 templates to PDF; no headless Chrome dependency; best choice for server-side PDF in Python 2025; produces clean print-quality output |
| **OR** | | | |
| xhtml2pdf | 0.2.x | Lightweight HTML→PDF | Simpler than WeasyPrint but less CSS support; use only if WeasyPrint's system dependencies (Pango, Cairo) are a Docker image size concern |
| **OAuth** | | | |
| authlib | 1.3.x | OAuth 2.0 client flows | GSC OAuth 2.0 integration; `AsyncOAuth2Client` wraps `httpx`; handles token refresh automatically; better than `requests-oauthlib` for async |
| **Notifications** | | | |
| python-telegram-bot | 21.x | Telegram Bot API | Async-native in v21; use `Bot.send_message()` directly inside Celery tasks; no need for polling — push-only for alerts |
| aiosmtplib | 3.x | Async SMTP email | Non-blocking email dispatch from Celery tasks; replaces smtplib for async contexts |
| **Parsing & Content** | | | |
| beautifulsoup4 | 4.12.x | HTML parsing | TOC generation, schema detection, internal link analysis; use `lxml` parser for speed |
| lxml | 5.x | Fast XML/HTML parser | BS4 backend; also useful for direct XPath queries on crawled pages |
| html5lib | — | Alternative BS4 parser | Slower than lxml; only use if lxml fails on malformed HTML |
| **Monitoring & Logging** | | | |
| loguru | 0.7.x | Structured logging | JSON sink config: `logger.add("logs/app.log", serialize=True, rotation="10 MB", retention="30 days")`; replaces stdlib logging entirely |
| **Config & Environment** | | | |
| pydantic-settings | 2.x | Settings from .env files | `BaseSettings` moved here in Pydantic v2; reads `.env` + environment variables; type-validated config |
| python-dotenv | 1.0.x | .env file loader | Used by pydantic-settings under the hood; also useful in `docker-compose.yml` env loading |
| **Testing** | | | |
| pytest | 8.x | Test runner | 2025 standard; use with `pytest-asyncio` for async test functions |
| pytest-asyncio | 0.23.x | Async test support | Set `asyncio_mode = "auto"` in `pyproject.toml` to avoid decorating every async test |
| httpx | 0.27.x | Test HTTP client | `AsyncClient(app=app, base_url="http://test")` replaces `TestClient` for async FastAPI |
| factory-boy | 3.3.x | Test fixtures/factories | SQLAlchemy factories for seeding test DB; cleaner than raw fixture dicts |
| pytest-cov | 5.x | Coverage reporting | `--cov=app --cov-fail-under=60` per PROJECT.md constraint |
| respx | 0.21.x | Mock httpx calls in tests | Mock WP REST API, GSC, DataForSEO calls without real network; pairs naturally with httpx |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| Docker + Docker Compose v2 | Container orchestration | Use `docker compose` (v2, plugin) not `docker-compose` (v1, deprecated); Compose v2 is built-in to Docker Desktop and Docker Engine 20.10+ |
| uv | Python package manager | Replaces pip + pip-tools in 2025; `uv pip compile` for lockfile, `uv pip sync` for reproducible installs; 10–100x faster than pip |
| ruff | Linter + formatter | Replaces flake8 + isort + black in one tool; `ruff check` + `ruff format`; configure in `pyproject.toml` |
| mypy | Static type checker | Use with `--strict` incrementally; SQLAlchemy 2.0 has full type stubs; FastAPI is fully typed |
| pre-commit | Git hook manager | Run ruff + mypy on commit; `.pre-commit-config.yaml` in repo root |
| pgAdmin 4 / psql | PostgreSQL admin | pgAdmin as optional Compose service for dev; psql for quick inspections |
| Redis Insight (or redis-cli) | Redis inspection | `redis-cli monitor` for debugging Celery task queues during development |
## Installation
# Core framework
# Database
# Task queue
# Browser automation
# Auth & security
# HTTP client + OAuth
# Templating
# HTMX: load via CDN in base template or pin to local static file
# Data processing
# PDF generation (pick one)
# uv pip install xhtml2pdf>=0.2  # lightweight fallback
# Notifications
# Logging + config
# Dev dependencies
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastAPI 0.115 | Litestar (formerly Starlette-based) | Litestar has better OpenAPI customisation and built-in DI; choose it for API-only products. For HTMX+Jinja2 hybrid, FastAPI's ecosystem is larger |
| asyncpg + SQLAlchemy async | Tortoise ORM | Tortoise is simpler for small projects but its migration tooling (aerich) is immature vs. Alembic; SQLAlchemy 2.0 is the enterprise choice |
| Celery 5 + Redis | ARQ (async task queue) | ARQ is fully async and simpler; choose it for greenfield projects with < 10 task types. Celery is better here because the project needs Beat scheduling, Flower monitoring, and retry policies |
| Celery 5 + Redis | Dramatiq | Dramatiq is cleaner API than Celery but lacks Beat scheduling; not appropriate here |
| redbeat | django-celery-beat | django-celery-beat stores schedule in PostgreSQL (better for audit trail); redbeat stores in Redis (faster, simpler); use django-celery-beat if you need schedule history in your DB |
| WeasyPrint | ReportLab | ReportLab requires learning a proprietary drawing API; WeasyPrint renders your existing Jinja2 HTML — zero extra template work |
| WeasyPrint | Playwright PDF | Playwright can `page.pdf()` to generate PDFs; viable but adds browser launch overhead per report; WeasyPrint is lighter for batch reports |
| authlib | google-auth + google-api-python-client | google-auth is Google-specific; authlib handles GSC OAuth + any future OAuth provider in one library |
| python-telegram-bot 21 | aiogram 3 | aiogram is more feature-complete for bots with conversation handlers; python-telegram-bot 21 is simpler for push-only alert use case |
| httpx | aiohttp | Both are capable; httpx has better API ergonomics, built-in retries, and integrates with respx for mocking in tests |
| uv | pip + pip-tools | pip-tools is stable and widely understood; uv is strictly faster and produces compatible lockfiles; no reason to use pip-tools for new projects in 2025 |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Celery 5.3.x or earlier | 5.3 has multiple Python 3.12 incompatibilities (import errors, kombu serialisation bugs); always use 5.4+ | Celery 5.4.x |
| psycopg2 / psycopg2-binary | Synchronous driver; blocks the event loop when used with SQLAlchemy async; causes silent performance degradation | asyncpg (for async) or psycopg3 async (alternative) |
| SQLAlchemy 1.4 "future" mode | 1.4 async support is a preview shim; its `AsyncSession` has subtle differences from 2.0; running 2.0 from the start avoids a painful migration | SQLAlchemy 2.0 |
| FastAPI `on_event("startup")` / `on_event("shutdown")` | Deprecated in FastAPI 0.93+; removed path in 0.115; use `@asynccontextmanager` lifespan | FastAPI `lifespan=` parameter with `asynccontextmanager` |
| Pydantic v1 | FastAPI 0.111+ requires Pydantic v2; mixing v1 validators or using `from pydantic import validator` (v1 API) causes runtime errors | Pydantic v2 (`@field_validator`, `model_validator`) |
| APScheduler | Doesn't scale to multiple workers; no task state persistence; PROJECT.md explicitly ruled it out | Celery Beat + redbeat |
| Selenium / selenium-wire | Synchronous, heavier than Playwright, no native async; Playwright is strictly better for this use case | Playwright async API |
| Flask / Django | Flask lacks native async; Django has async views but its ORM is sync-first — incompatible with the chosen SQLAlchemy async architecture | FastAPI |
| `requests` library | Synchronous; blocks the event loop inside FastAPI async handlers and Celery async tasks | httpx.AsyncClient |
| python-docx for reports | Not in PROJECT.md scope; adds maintenance burden | openpyxl (Excel) + WeasyPrint (PDF) |
| HTMX 1.x | HTMX 2.0 made breaking changes (`hx-ws`, `hx-sse` moved to extensions; `hx-boost` default changed); starting on 1.x means a mandatory migration later | HTMX 2.0.x |
| redis-py < 4.6 | Pre-4.6 lacks async support (`redis.asyncio`); Celery 5.4 requires ≥4.6 | redis-py 5.0.x |
| PyJWT (standalone) | `python-jose` is already in the stack and covers JWT; having two JWT libraries creates confusion and potential signing inconsistencies | python-jose[cryptography] |
| Flower without auth | Flower exposes full task history and worker details; deploying it without Basic Auth or behind a reverse proxy auth layer leaks internal job data | `--basic_auth=user:pass` flag or Traefik/Nginx auth middleware |
## Stack Patterns by Variant
- Use `redbeat` as the Celery Beat scheduler backend
- Set `CELERY_BEAT_SCHEDULER = "redbeat.schedulers.RedBeatScheduler"` in Celery config
- Store `RedBeatSchedulerEntry` objects from FastAPI endpoint handlers
- Because: the built-in `PersistentScheduler` writes to a local file — it breaks when Beat runs in a separate container
- Use the `python:3.12-slim` base and install WeasyPrint system deps explicitly:
- Add ~80 MB to the image; acceptable for a single VPS deployment
- Because: WeasyPrint's Pango/Cairo deps are not included in slim images
- Use Microsoft's official `mcr.microsoft.com/playwright/python:v1.47.0-jammy` base image for the crawler worker
- It pre-installs Chromium + all system deps (~1.5 GB but fully cached after first pull)
- Because: manually installing Playwright browser deps in a custom image is error-prone
- Store `access_token`, `refresh_token`, `expires_at` in the DB per-site
- Use authlib's `OAuth2Session.ensure_active_token()` before every GSC API call
- Because: GSC tokens expire after 1 hour; silent failures cause phantom "no data" bugs
- Set `task_track_started=True`, `task_acks_late=True`, and a global `on_failure` handler that writes to the `audit_log` table
- Because: default Celery config acknowledges tasks on receipt, not on completion — a worker crash silently drops tasks
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI 0.115.x | Pydantic 2.7+ only | Do not install pydantic 1.x alongside; FastAPI 0.115 hard-requires v2 |
| FastAPI 0.115.x | Starlette 0.40.x | FastAPI pins a specific Starlette range; let FastAPI's dependency resolver pick it — never pin Starlette independently |
| SQLAlchemy 2.0.30+ | asyncpg 0.29.x | asyncpg 0.29 supports PostgreSQL 16 protocol features; earlier asyncpg versions may silently fall back to older protocol |
| Celery 5.4.x | Redis 7.2.x (redis-py 5.0.x) | Celery 5.4 uses kombu ≥5.3.4 which supports Redis 7's LMPOP command for better queue efficiency |
| Celery 5.4.x | Python 3.12 | 5.3 had import-time errors on 3.12 due to removed `distutils`; 5.4 patches this |
| Playwright 1.47.x | Python 3.12 | Fully compatible; async API uses asyncio natively |
| Alembic 1.13.x | SQLAlchemy 2.0.x | Alembic 1.13 added explicit support for SQLAlchemy 2.0 async engine in `env.py`; earlier Alembic versions require manual async env.py workarounds |
| authlib 1.3.x | httpx 0.27.x | authlib's `AsyncOAuth2Client` is built on httpx; version pairing is maintained by authlib; don't downgrade httpx independently |
| pydantic-settings 2.x | Pydantic 2.x | Same major version required; pydantic-settings 2.x will not work with pydantic 1.x |
| WeasyPrint 62.x | Python 3.12 | WeasyPrint 62 explicitly supports Python 3.12; versions < 60 have known issues on 3.12 |
| slowapi 0.1.9 | FastAPI 0.115.x | slowapi wraps `limits` and hooks into Starlette middleware; compatible with all FastAPI 0.10x releases |
| redbeat 2.2.x | Celery 5.4.x + Redis 7.x | redbeat 2.x requires Celery 5.x; Redis 7 RESP3 protocol is handled transparently by redis-py 5.x |
## Gaps Identified in Original TZ
| Gap | Recommended Library | Iteration Needed |
|-----|-------------------|-----------------|
| PDF report generation | WeasyPrint 62.x | Iteration 5 (briefs) + Iteration 6 (reports) |
| Excel export (.xlsx) | openpyxl 3.1.x | Iteration 3 (keyword import) + Iteration 6 (reports) |
| OAuth 2.0 for GSC | authlib 1.3.x | Iteration 3 |
| Rate limiting | slowapi 0.1.9 | Iteration 7 (but install from Iteration 1) |
| Celery task monitoring UI | flower 2.0.x | Iteration 7 |
| DB-driven Beat schedule | redbeat 2.2.x | Iteration 2 (crawl schedule from UI) |
| Telegram alerts | python-telegram-bot 21.x | Iteration 3 |
| SMTP reports | aiosmtplib 3.x | Iteration 6 |
| Test HTTP mocking | respx 0.21.x | Iteration 1 onward |
| HTML parsing (TOC, schema detection) | beautifulsoup4 + lxml | Iteration 2 |
## Sources
- Python 3.12 release notes and asyncio improvements — knowledge base through Aug 2025
- FastAPI changelog 0.111–0.115, Pydantic v2 migration guide — knowledge base
- SQLAlchemy 2.0 async documentation patterns — knowledge base
- Celery 5.4 changelog (Python 3.12 compatibility fixes) — knowledge base
- Playwright Python async API documentation — knowledge base
- HTMX 2.0 migration guide (breaking changes from 1.x) — knowledge base
- WeasyPrint 60+ Python 3.12 support notes — knowledge base
- authlib async OAuth2 client documentation — knowledge base
- redbeat documentation (Redis-backed Beat scheduler) — knowledge base
- python-telegram-bot v21 async migration notes — knowledge base
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
