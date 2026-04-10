# Architecture Research

**Domain:** Mobile Focus Apps + Telegram Bot integration into existing FastAPI/Jinja2/HTMX platform
**Researched:** 2026-04-10
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Client Layer                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐   │
│  │  Desktop /    │  │  Mobile        │  │  Telegram WebApp      │   │
│  │  base.html    │  │  base_mobile   │  │  base_telegram.html   │   │
│  │  (sidebar)    │  │  (bottom tabs) │  │  (telegram-web-app.js)│   │
│  └──────┬────────┘  └──────┬─────────┘  └──────────┬────────────┘  │
│         │ /ui/             │ /m/                    │ /tg/           │
└─────────┼──────────────────┼────────────────────────┼───────────────┘
          │                  │                        │
┌─────────▼──────────────────▼────────────────────────▼───────────────┐
│                     FastAPI app (app/main.py)                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  Existing routers│  │  Mobile routers   │  │  Telegram routers  │ │
│  │  app/routers/    │  │  app/routers/m/   │  │  app/routers/tg/   │ │
│  │  (unchanged)     │  │  prefix=/m        │  │  prefix=/tg        │ │
│  └────────┬─────────┘  └────────┬──────────┘  └────────┬───────────┘ │
│           │                     │                       │             │
│  ┌────────▼─────────────────────▼───────────────────────▼───────────┐│
│  │                    Shared Service Layer                           ││
│  │  app/services/  (position_service, digest_service, wp_service,   ││
│  │  overview_service, site_service, task_service, etc.)             ││
│  └────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Auth Layer                                    ││
│  │  /m/  -> JWT cookie (same as desktop, no new auth system)       ││
│  │  /tg/ -> initData HMAC validation -> exchange for JWT           ││
│  └─────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────────────┐
│                     Telegram Bot Process                             │
│  ┌───────────────────────┐   ┌─────────────────────────────────────┐│
│  │  python-telegram-bot  │   │  Bot command handlers               ││
│  │  Application (polling │   │  /status /deploy /test /logs        ││
│  │  or webhook mode)     │   │  + Claude Code agent bridge         ││
│  └──────────┬────────────┘   └──────────────┬──────────────────────┘│
│             │ reads DB directly               │ Celery tasks          │
│             │ (SYNC_DATABASE_URL)             │ (celery_app.send_task)│
└─────────────┴────────────────────────────────┴────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────────────┐
│                     Data Layer (unchanged)                           │
│  PostgreSQL 16  |  Redis 7  |  Celery workers  |  Beat scheduler    │
└────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| `app/routers/m/` | Mobile-specific route handlers, return HTMLResponse with mobile templates | New router package, each focus app is a separate file |
| `app/routers/tg/` | Telegram WebApp route handlers, initData validation middleware | New router package, thin wrappers over existing services |
| `base_mobile.html` | Bottom-tab nav layout, touch-friendly CSS, no sidebar | New Jinja2 base template, inherits no CSS from base.html |
| `base_telegram.html` | Telegram WebApp JS integration, theme passthrough, viewport lock | New Jinja2 base template, loads telegram-web-app.js CDN |
| `app/services/telegram_bot_service.py` | Bot Application setup, command handlers, webhook registration | New service, wraps python-telegram-bot 21.x Application |
| `app/auth/tg_auth.py` | initData HMAC-SHA256 validation, user lookup by telegram_id | New auth module, pure Python crypto, no new library |
| Existing services (unchanged) | Business logic: positions, sites, tasks, digest, wp_service | All mobile/TG routes call existing services without modification |
| Telegram bot process | Long-running Application.run_polling() or webhook handler | Separate Docker Compose service, shares DB/Redis with api |

## Recommended Project Structure

```
app/
├── routers/
│   ├── m/                         # Mobile focus apps (NEW)
│   │   ├── __init__.py
│   │   ├── digest.py              # GET /m/digest
│   │   ├── positions.py           # GET /m/positions/{site_id}
│   │   ├── health.py              # GET /m/health/{site_id}
│   │   ├── pages.py               # GET /m/pages/{site_id} — approve queue + quick fix
│   │   ├── traffic.py             # GET /m/traffic/{site_id}
│   │   ├── report.py              # GET /m/report/{site_id}
│   │   ├── task.py                # GET /m/task — quick task create
│   │   └── tools.py               # GET /m/tools
│   ├── tg/                        # Telegram WebApp variants (NEW)
│   │   ├── __init__.py
│   │   ├── auth.py                # POST /tg/auth — initData -> JWT exchange
│   │   ├── digest.py              # GET /tg/digest
│   │   └── pages.py               # GET /tg/pages/{site_id}
│   └── (existing routers — unchanged)
├── auth/
│   ├── tg_auth.py                 # initData validation (NEW)
│   └── (existing auth files — unchanged)
├── templates/
│   ├── base_mobile.html           # Bottom-tab layout (NEW)
│   ├── base_telegram.html         # Telegram WebApp layout (NEW)
│   ├── mobile/                    # Mobile-specific templates (NEW)
│   │   ├── digest/
│   │   ├── positions/
│   │   ├── health/
│   │   ├── pages/
│   │   ├── traffic/
│   │   ├── report/
│   │   ├── task/
│   │   └── tools/
│   └── (existing templates — unchanged)
├── services/
│   └── (existing services — unchanged; mobile/tg routers call them directly)
└── main.py                        # Add include_router for m_* and tg_* packages (8-12 lines added)

bot/                               # Telegram bot entry point (NEW top-level package)
├── __init__.py
├── main.py                        # python bot/main.py — Application.run_polling()
├── commands/
│   ├── status.py                  # /status handler
│   ├── deploy.py                  # /deploy handler (calls Celery tasks)
│   ├── logs.py                    # /logs handler (reads loguru log tail)
│   └── agent.py                   # /claude handler — Claude Code agent bridge
└── middleware/
    └── auth_guard.py              # restrict to allowed telegram_user_ids from config
```

### Structure Rationale

- **`app/routers/m/` package vs flat files:** Keeps mobile routes isolated; the flat router list in main.py already has 40+ entries — a package prevents further clutter without obscuring the surface boundary.
- **`bot/` at project root:** The bot is a separate long-running process, not a FastAPI route. Keeping it at root alongside `app/` makes the process boundary explicit and simplifies the docker-compose.yml service definition.
- **Mobile templates in `app/templates/mobile/`:** Mirrors the existing per-domain template subdirectory pattern (`tools/`, `crm/`, `pipeline/`). No naming collision with desktop templates.
- **Existing services untouched:** The mobile and TG layers are presentation-only thin wrappers. All business logic stays in `app/services/`. This means mobile features inherit all existing service test coverage for free.

## Architectural Patterns

### Pattern 1: Prefix-Scoped Router with Shared Services

**What:** Each surface (`/m/`, `/tg/`) gets its own router package. Routers call existing services directly. No service duplication.

**When to use:** All mobile/TG routes. Services are already async and session-aware — mobile routes get identical data freshness as desktop.

**Trade-offs:** Mobile routes are thin (10-30 lines each); all complexity stays in services. If a mobile-specific aggregation emerges (combining digest + positions + tasks into one payload), create `app/services/mobile_aggregate_service.py` — a new service that calls existing services, not one that copies them.

**Example:**
```python
# app/routers/m/positions.py
router = APIRouter(prefix="/m", tags=["mobile"])

@router.get("/positions/{site_id}", response_class=HTMLResponse)
async def mobile_positions(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await position_service.get_top_movers(db, site_id, limit=20)
    return templates.TemplateResponse(
        "mobile/positions/index.html",
        {"request": request, "data": data, "user": current_user},
    )
```

### Pattern 2: Telegram initData Authentication

**What:** Telegram WebApp passes `initData` (URL-encoded string) in every request. The server validates the HMAC-SHA256 signature using `TELEGRAM_BOT_TOKEN` as the key. On valid initData, the server looks up the user by `telegram_user_id` in the users table and issues a standard JWT.

**When to use:** All `/tg/` routes. Never trust initData without HMAC validation — Telegram explicitly documents that unvalidated initData can be forged by any client.

**Trade-offs:** Adds one crypto operation per request (negligible). Requires `telegram_user_id` column on the users table (one migration). The exchange endpoint (`POST /tg/auth`) returns a short-lived JWT that the Telegram WebApp stores in `sessionStorage` and attaches as `Authorization: Bearer` header to subsequent HTMX requests.

**Example:**
```python
# app/auth/tg_auth.py
import hashlib, hmac, urllib.parse
from app.config import settings

def validate_init_data(init_data: str) -> dict:
    """Raises ValueError if signature invalid. Returns parsed fields dict."""
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", "")
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    expected = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise ValueError("Invalid initData signature")
    return parsed
```

### Pattern 3: Approve Queue with Mobile Quick-Fix

**What:** The existing `WpContentJob` model already has `pending_approval` / `approved` / `pushed` statuses and `POST /pipeline/jobs/{job_id}/approve`. The mobile Pages focus app renders a card list of `pending_approval` jobs for a site, with inline approve/reject buttons using HTMX `hx-post`.

**When to use:** The mobile approve queue reuses the existing pipeline service and job model without schema changes. The quick-fix flow (inline content edit → approve → push) adds only a `content_override` field to the HTMX form payload in new mobile-specific endpoints.

**Trade-offs:** No new Celery queue needed — approved jobs enter the existing `wp` queue via `push_to_wp.delay()`. The mobile UI is a filtered view of existing data. The quick-fix endpoints are new but call existing `pipeline_service` functions.

**Flow:**
```
Mobile /m/pages/{site_id}
    -> pipeline_service.get_pending_jobs(db, site_id)
    -> renders card list
    -> HTMX hx-post="/pipeline/jobs/{id}/approve"  (EXISTING endpoint)
    -> returns HX-Trigger: showToast
    -> HTMX hx-get="/m/pages/{site_id}/fragment" refreshes card list
```

### Pattern 4: Telegram Bot as Separate Docker Service

**What:** The bot runs `python bot/main.py` which calls `Application.run_polling()`. It is NOT mounted inside the FastAPI lifespan. It shares the same `.env`, PostgreSQL, and Redis as the api service.

**When to use:** Always. Mounting the bot inside FastAPI via lifespan creates coupling — API unavailability equals bot unavailability, and vice versa. A separate Docker service provides independent restart policies and log streams.

**Trade-offs:** Webhook mode (registering `setWebhook` with Telegram) is more production-appropriate than polling because it has no long-lived HTTP connection and misses no updates on restart. However, polling mode is simpler to develop and has no public URL requirement. Start with polling during development; migrate to webhook before production by adding `POST /tg/webhook` endpoint and calling `setWebhook`.

**Bot-to-platform integration:** Bot command handlers read from DB directly via `SYNC_DATABASE_URL` (synchronous SQLAlchemy session — simpler inside bot context) and dispatch Celery tasks via `celery_app.send_task("app.tasks.wp_tasks.run_health_check", args=[site_id])`.

### Pattern 5: base_mobile.html as Independent Layout

**What:** `base_mobile.html` inherits nothing from `base.html`. It is a standalone HTML template with bottom tab navigation, no sidebar, and mobile-optimized viewport meta tags.

**When to use:** All `/m/` routes. Do not attempt to CSS-hide the sidebar and reuse base.html.

**Why it must be independent:** base.html loads Shepherd.js, flatpickr, and the full CDN Tailwind CSS (collectively ~520kB). On 4G mobile this adds 1-2 seconds to TTI. The sidebar JavaScript is also initialized on load, causing JS errors when the sidebar DOM is hidden.

**Trade-offs:** Two base templates to maintain. Acceptable because the mobile layout has fundamentally different chrome (no sidebar, bottom tabs, no admin-tour JS). Shared fragments (e.g., a position table row) can be extracted to `templates/components/` and included by both desktop and mobile templates when a component appears in 3+ templates.

```html
<!-- base_mobile.html skeleton -->
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <script src="https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
  <title>{% block title %}SEO{% endblock %}</title>
</head>
<body class="bg-gray-50 pb-16">
  {% block content %}{% endblock %}
  <nav class="fixed bottom-0 w-full bg-white border-t flex justify-around py-2 z-50">
    <!-- 5 tab icons: Digest, Positions, Health, Pages, Tools -->
    {% block bottom_tabs %}{% endblock %}
  </nav>
</body>
</html>
```

## Data Flow

### Mobile Quick-Fix Flow

```
User on /m/pages/{site_id}
    |
    v
GET /m/pages/{site_id}
    -> pipeline_service.get_pending_jobs(db, site_id)
    -> renders mobile/pages/index.html (card list)
    |
    v (tap "Approve")
HTMX hx-post="/pipeline/jobs/{job_id}/approve"   <- EXISTING ENDPOINT, unchanged
    -> job.status = approved
    -> push_to_wp.delay(job_id)                   <- EXISTING Celery task
    -> returns HX-Trigger: showToast + HX-Reswap: none
    |
    v (tap "Quick Fix" — open edit sheet)
HTMX hx-get="/m/pages/{site_id}/jobs/{job_id}/edit"   <- NEW mobile endpoint
    -> returns mobile/pages/_edit_sheet.html (inline textarea)
    |
    v (save)
HTMX hx-post="/m/pages/{site_id}/jobs/{job_id}/fix"   <- NEW mobile endpoint
    -> pipeline_service.update_job_content(db, job_id, content_override)
    -> pipeline_service.approve_and_push(db, job_id)
    -> returns updated card fragment
```

### Telegram WebApp Auth Flow

```
Telegram opens WebApp URL: https://seo.example.com/tg/digest
    |
    v
Telegram injects window.Telegram.WebApp.initData into the page
    |
    v
base_telegram.html onload JS:
    fetch("POST /tg/auth", body={init_data: Telegram.WebApp.initData})
    |
    v
/tg/auth handler:
    -> validate_init_data(init_data)          # HMAC-SHA256 check
    -> lookup user by telegram_user_id        # DB: users.telegram_user_id
    -> create_access_token(user_id, role)     # existing JWT function (unchanged)
    -> return {access_token: "..."}
    |
    v
JS stores token in sessionStorage
All subsequent HTMX requests include header:
    hx-headers='{"Authorization": "Bearer <token>"}'
    |
    v
/tg/* route handlers use get_current_user (existing dependency — unchanged)
    -> reads Authorization header (already supported in auth/dependencies.py)
```

### Bot-to-Platform Data Flow

```
Telegram user sends /status
    |
    v
bot/commands/status.py handler
    |
    +-> DB query (SYNC_DATABASE_URL, synchronous session)
    |       SELECT sites, last_crawl, open_tasks FROM ...
    |
    +-> Celery: celery_app.send_task("app.tasks.wp_tasks.check_site", args=[...])
    |       (fire-and-forget; bot sends "check queued" confirmation message)
    |
    +-> bot.send_message(chat_id, formatted_status_html)
```

### Mobile Auth Flow (JWT Cookie — no changes needed)

```
User visits /m/digest on mobile browser (not logged in — no access_token cookie)
    |
    v
get_current_user raises 401
    |
    v
FastAPI redirect -> 302 to /auth/login?next=/m/digest
    |
    v
User submits login form -> existing /auth/token endpoint
access_token cookie set (domain-wide, path="/")
    |
    v
Redirect to /m/digest — cookie present, get_current_user succeeds
```

The existing `auth/dependencies.py` already reads `request.cookies.get("access_token")` as a fallback after the Bearer header check. No modification needed.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current (5-20 internal users) | Single bot process polling; all services on one VPS; no changes needed |
| 50-100 users | Switch bot to webhook mode (one nginx route POST /tg/webhook → bot service); horizontal scaling of bot not needed at this count |
| 100+ users | Bot webhook on dedicated port; Redis pub/sub for bot-to-api event notifications instead of DB polling |

Mobile focus apps have no additional scaling concerns beyond the existing FastAPI app — they share the same worker pool and connection pool.

## Anti-Patterns

### Anti-Pattern 1: Mounting the Bot Inside FastAPI Lifespan

**What people do:** Start `Application.run_polling()` inside `@asynccontextmanager lifespan(app)` to avoid a second Docker service.

**Why it's wrong:** `Application.run_polling()` blocks or competes for the event loop. A bot crash or network disconnect stops the event loop and kills the FastAPI worker. Deploying a new API version with rolling restart kills the bot mid-conversation.

**Do this instead:** Separate Docker Compose service `bot:` with `command: python bot/main.py`. Share `.env`. Both services restart independently with independent health checks.

### Anti-Pattern 2: Duplicating Service Logic for Mobile Routes

**What people do:** Copy `position_service.get_positions()` into a new `mobile_position_service.py` and add mobile-specific filters there.

**Why it's wrong:** Service duplication breaks the single-source principle. When the positions schema changes, both copies need updating. Bug fixes in the original won't apply to mobile.

**Do this instead:** Add optional parameters to existing services (`limit=20`, `top_n_only=True`) or compose existing service calls in a thin router function. If a genuinely mobile-specific aggregation is needed, create `app/services/mobile_aggregate_service.py` — a new service that calls existing services, not one that copies them.

### Anti-Pattern 3: Trusting initData Without HMAC Validation

**What people do:** Parse `initData` and trust the `user.id` field directly.

**Why it's wrong:** Telegram's own documentation states that initData can be forged by any client. The HMAC-SHA256 signature is the only way to verify the data came from Telegram.

**Do this instead:** Always call `validate_init_data(init_data)` before using any field. Raise HTTP 401 on signature failure. This is a 10-line function with no new library dependencies — pure `hashlib` + `hmac` from stdlib.

### Anti-Pattern 4: Storing telegram_user_id in Redis Instead of DB

**What people do:** Store `telegram_user_id -> platform_user_id` mapping in Redis or in-memory to avoid a migration.

**Why it's wrong:** Redis flush (maintenance, upgrades) loses all associations permanently. In-memory state is lost on every worker restart.

**Do this instead:** Add `telegram_user_id BIGINT UNIQUE NULL` column to the `users` table via a single Alembic migration. Admin sets it in the user profile or during bot `/start` registration. One migration, permanent, indexed.

### Anti-Pattern 5: CSS-hiding base.html Sidebar for Mobile Routes

**What people do:** Reuse `base.html` and add `class="hidden md:block"` to the sidebar, `class="block md:hidden"` to bottom tabs.

**Why it's wrong:** base.html loads Shepherd.js, flatpickr, and Tailwind CDN (~520kB total). On 4G mobile this adds 1-2 seconds to TTI. The sidebar JavaScript initializes on load regardless of visibility, causing JS errors when sidebar DOM nodes are hidden.

**Do this instead:** `base_mobile.html` is a standalone ~60-line template. HTMX + Tailwind CDN only (no flatpickr, no Shepherd, no tour.js). Total head weight: ~120kB.

## Integration Points

### Existing System Touch Points

| Boundary | Integration Method | Change Type |
|----------|--------------------|-------------|
| `app/main.py` | Add 8-12 `include_router()` calls for `/m/` and `/tg/` packages | Append-only |
| `app/auth/dependencies.py` | No change — already reads both `Authorization` header and cookie | Unchanged |
| `app/models/user.py` | Add `telegram_user_id: BigInteger, nullable, unique` column | New column via migration 0046 |
| `app/config.py` | Add `TELEGRAM_WEBHOOK_SECRET: str = ""` for webhook mode (optional) | Additive |
| `docker-compose.yml` | Add `bot:` service entry pointing to `python bot/main.py` | New service, no existing services modified |
| `app/services/*` | No changes — mobile/TG routers are consumers only | Unchanged |
| `app/routers/wp_pipeline.py` | No changes — approve endpoint at `POST /pipeline/jobs/{job_id}/approve` already exists | Unchanged |
| `requirements.txt` | Add `python-telegram-bot[all]>=21.0,<22.0` | New dependency |

### New Components (greenfield)

| Component | File(s) | Depends On |
|-----------|---------|------------|
| Mobile router package | `app/routers/m/*.py` (8 files) | existing services, get_current_user |
| Telegram WebApp router package | `app/routers/tg/*.py` (3 files) | tg_auth.py, existing services |
| initData auth | `app/auth/tg_auth.py` | stdlib hashlib/hmac, app.config.TELEGRAM_BOT_TOKEN |
| Mobile base layout | `app/templates/base_mobile.html` | none |
| Telegram base layout | `app/templates/base_telegram.html` | Telegram WebApp CDN |
| Mobile templates | `app/templates/mobile/**` (~16 files) | base_mobile.html |
| Alembic migration 0046 | `alembic/versions/0046_*.py` | users table (migration 0045 head) |
| Bot entry point | `bot/main.py` | python-telegram-bot 21.x |
| Bot command handlers | `bot/commands/*.py` (4-5 files) | SYNC_DATABASE_URL, celery_app.send_task |

### Build Order (Dependency-Driven)

**Wave 1 — Foundation (must complete before any mobile/bot work):**
1. Alembic migration 0046 — `users.telegram_user_id BIGINT UNIQUE NULL`. Gates all Telegram auth.
2. `base_mobile.html` — standalone layout, bottom-tab nav. Gates all mobile template work.
3. `app/auth/tg_auth.py` — initData HMAC validation. Gates all `/tg/` routes. Pure stdlib.
4. `requirements.txt` — add python-telegram-bot 21.x. Gates bot development.

**Wave 2 — Mobile Focus Apps (parallel after Wave 1):**
5. `/m/digest` — calls existing `morning_digest_service`. Simplest app, good integration smoke test.
6. `/m/positions/{site_id}`, `/m/health/{site_id}`, `/m/traffic/{site_id}` — read-only, no new write paths.
7. `/m/pages/{site_id}` — approve queue + quick-fix. Has the only new write path; build after read-only apps are validated.
8. `/m/report/{site_id}`, `/m/task`, `/m/tools` — thin wrappers, build in parallel with 6-7.

**Wave 3 — Telegram WebApp (parallel with Wave 2, after Wave 1):**
9. `POST /tg/auth` — initData validation -> JWT exchange. Requires migration 0046 + tg_auth.py.
10. `/tg/digest`, `/tg/pages/{site_id}` — thin wrappers over mobile router logic with base_telegram.html.

**Wave 4 — Telegram Bot (independent after Wave 1):**
11. Bot foundation — `bot/main.py`, Application setup, auth guard (allowed user IDs from config), `/start` command that registers `telegram_user_id`.
12. Bot commands — `/status`, `/deploy`, `/test`, `/logs`. Each as a separate handler; build and test individually.
13. Claude Code agent bridge — `/claude` command. Build last; most complex, no other component depends on it.
14. docker-compose.yml `bot:` service — add after bot runs locally.

**Critical path:** migration 0046 -> base_mobile.html + tg_auth.py -> /m/digest (smoke test) -> /m/pages (write path) -> /tg/auth -> /tg/pages -> bot foundation -> bot commands

## Sources

- Direct codebase inspection (2026-04-10): `app/auth/dependencies.py` — cookie + Bearer dual-path already implemented (lines 24-26); `app/routers/wp_pipeline.py` — existing approve endpoints at lines 66-85 and 193-213; `docker-compose.yml` — 5 existing services, confirmed bot service does not yet exist; `app/config.py` — `TELEGRAM_BOT_TOKEN` present (line 51), no webhook secret yet; `app/services/telegram_service.py` — push-only httpx calls, no Application object, confirms bot is not yet a running process
- Telegram Bot API initData validation algorithm — https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app (HMAC-SHA256 with "WebAppData" key derivation)
- Telegram WebApp JS SDK — `window.Telegram.WebApp.initData` availability confirmed; CDN `https://telegram.org/js/telegram-web-app.js`
- python-telegram-bot 21.x `Application.run_polling()` pattern — HIGH confidence; async Application API stable since v20; v21 added async-native handlers throughout
- FastAPI prefix-per-surface pattern — verified from existing codebase (`/ui/tools`, `/ui/crm`, `/ui/client-reports` prefixes all in use as separate router packages)
- base.html CDN payload analysis — direct inspection: Shepherd.js + flatpickr + Tailwind CDN loaded unconditionally (lines 7-18 of base.html)

---
*Architecture research for: Mobile Focus Apps + Telegram Bot (v4.0 milestone)*
*Researched: 2026-04-10*
