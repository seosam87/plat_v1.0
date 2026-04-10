# Technology Stack

**Project:** SEO Management Platform
**Researched:** 2026-04-10 (v4.0 update — Mobile & Telegram additions)
**Confidence:** HIGH (existing stack), HIGH (v4.0 additions — minimal new libraries required)

---

## Existing Stack (Validated — Do Not Re-Research)

Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, PostgreSQL 16, Redis 7, Celery 5.4,
Playwright 1.47+, Jinja2 3.1, HTMX 2.0, Tailwind CSS, WeasyPrint 62, authlib 1.3,
httpx 0.27, beautifulsoup4 4.12 + lxml 5, loguru 0.7, redbeat 2.2, openpyxl 3.1,
python-telegram-bot 21.x, aiosmtplib 3, slowapi 0.1.9, passlib[bcrypt], python-jose,
cryptography 42, pytest 8 + pytest-asyncio + respx, anthropic ≥0.89, pyotp 2.9,
sse-starlette ≥3.3.3, mammoth 1.6.

Full details in the v1.0–v3.0 STACK.md sections below.

---

## v4.0 New Additions

### New Libraries Required

Three additions. Everything else uses the existing stack.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| python-telegram-bot | **22.x** (upgrade from 21.x) | Bot handlers + WebApp buttons | v22 adds full Bot API 9.x support; `InlineKeyboardButton(web_app=WebAppInfo(url=...))` was available in v21 but v22 stabilises the `WebAppData` handler and fixes timedelta typing. Upgrade is low-risk: only breaking change is `datetime.timedelta` return types (opt-in via `PTB_TIMEDELTA=true`). Use keyword arguments everywhere and the migration is non-breaking. |
| tailwindcss-safe-area | **0.1.x** (CDN plugin or npm) | `env(safe-area-inset-*)` utilities for iOS notch/home-bar | Tailwind CSS does not ship `safe-area-inset` utilities by default. This tiny plugin adds `pb-safe`, `pt-safe`, `px-safe` utility classes. Required for correct PWA rendering on iPhone (notch, home indicator). If Tailwind is loaded via CDN Play (current pattern), add the env-based padding manually in `base_mobile.html` as CSS custom properties instead — see Integration Patterns below. |
| claude-code-sdk | **≥0.0.13** (PyPI) | Programmatic Claude Code CLI invocation from Telegram bot | Official Anthropic Python SDK for spawning `claude -p` as subprocess with structured JSON output. Wraps `asyncio.create_subprocess_exec` with proper stdin/stdout/stderr handling and retry logic. Used only in the bot's `/agent` command handler — not imported by the main FastAPI app. |

### No-Addition Rationale

| v4.0 Capability | Library Already in Stack | How It Covers the Need |
|-----------------|--------------------------|------------------------|
| Mobile-optimised Jinja2 templates (`base_mobile.html`) | Jinja2 3.1 + HTMX 2.0 + Tailwind CSS | New base template, new `/m/` router, mobile-specific CSS classes. No new library — pure HTML/CSS/HTMX patterns. |
| Telegram WebApp initData validation (Mini App auth) | `hmac` + `hashlib` (Python stdlib) | HMAC-SHA256 validation of `initData` is 20 lines of stdlib code. No third-party library required; see Integration Patterns below. |
| Telegram Bot `/deploy`, `/test`, `/logs`, `/status` commands | python-telegram-bot 22.x (existing, upgraded) | `CommandHandler` + async callbacks. Bot already in stack for push notifications — extend with command handlers in same Application instance. |
| PWA manifest + service worker | Static files served by FastAPI | `manifest.json` and `sw.js` are static file assets served at well-known paths. No Python library. Registered via `<link rel="manifest">` in `base_mobile.html`. |
| Push notifications (web push) | Celery 5.4 + Redis 7 (existing) | Web push via VAPID requires `pywebpush` if native browser push is needed. For this project, Telegram push is the notification channel — no separate web push library required. |
| Bot command security (restrict to admin Telegram IDs) | python-telegram-bot 22.x + Redis 7 | Allowlist of Telegram user IDs stored in Redis (or `settings.py`). A `filters.User(user_id=[...])` filter on `CommandHandler` enforces it natively. |

---

## Integration Patterns for v4.0

### 1. Telegram WebApp — initData Validation (No Library)

The `initData` query string is signed with HMAC-SHA256 using the bot token. Validate in a FastAPI dependency:

```python
import hashlib, hmac, urllib.parse
from fastapi import Header, HTTPException

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN

def _build_check_string(init_data: str) -> tuple[str, str]:
    params = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
    received_hash = params.pop("hash", "")
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    return data_check_string, received_hash

async def verify_telegram_webapp(
    x_telegram_init_data: str = Header(...)
) -> dict:
    """FastAPI dependency — validates Telegram Mini App initData."""
    data_check_string, received_hash = _build_check_string(x_telegram_init_data)
    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=403, detail="Invalid Telegram initData")
    return dict(urllib.parse.parse_qsl(x_telegram_init_data))
```

Apply as `Depends(verify_telegram_webapp)` on all `/m/` endpoints that receive Telegram WebApp requests.

**Why no library:** `init-data-py` and `telegram_init_data` packages exist but add a dependency for 20 lines of stdlib code. The algorithm is stable (documented since Bot API 6.0). Use stdlib.

### 2. Telegram WebApp Button — Open Mini App from Bot

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

def make_webapp_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Открыть дайджест", web_app=WebAppInfo(url=url))
    ]])
```

`WebAppInfo(url=...)` requires HTTPS. In development, use ngrok or Cloudflare Tunnel. In production, the existing HTTPS VPS satisfies this.

### 3. Telegram Bot — Single Application, Multiple Handler Types

The existing `python-telegram-bot` push-notification code runs as a fire-and-forget sender. For v4.0, upgrade to a persistent `Application` that handles both push (outbound) and commands (inbound):

```python
# app/telegram_bot.py
from telegram.ext import Application, CommandHandler, filters

application = (
    Application.builder()
    .token(settings.TELEGRAM_BOT_TOKEN)
    .build()
)

# DevOps commands — restricted to admin Telegram IDs
ADMIN_IDS = settings.TELEGRAM_ADMIN_IDS  # List[int] from settings

application.add_handler(CommandHandler(
    "deploy", handle_deploy,
    filters=filters.User(user_id=ADMIN_IDS)
))
application.add_handler(CommandHandler(
    "status", handle_status,
    filters=filters.User(user_id=ADMIN_IDS)
))
# ... /test, /logs, /agent
```

Start the Application via FastAPI lifespan (not a separate process):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await application.initialize()
    await application.start()
    # Set webhook — do not use polling in production (blocks event loop)
    await application.bot.set_webhook(url=f"{settings.BASE_URL}/telegram/webhook")
    yield
    await application.stop()
    await application.shutdown()
```

**Webhook over polling:** Production runs on a VPS with HTTPS — webhook mode is mandatory. Polling blocks the async event loop and cannot coexist with FastAPI. Register a `/telegram/webhook` POST endpoint that calls `application.process_update()`.

### 4. Claude Code CLI Agent — Subprocess via SDK

```python
# app/services/claude_agent.py
import asyncio, json
from claude_code_sdk import ClaudeCodeOptions, claude_code

async def run_claude_task(prompt: str, work_dir: str) -> str:
    """Run Claude Code headlessly and return text result."""
    options = ClaudeCodeOptions(
        cwd=work_dir,
        allowed_tools=["Read", "Edit", "Bash"],
        permission_mode="acceptEdits",
    )
    result_text = []
    async with claude_code(prompt, options=options) as agent:
        async for message in agent:
            if message.type == "result":
                result_text.append(message.result)
    return "\n".join(result_text)
```

Invoke from a Celery task triggered by the `/agent` bot command. Never invoke directly in a FastAPI endpoint — Claude Code tasks can take minutes and will block the web worker.

**Security boundary:** The `/agent` command must be restricted to `TELEGRAM_ADMIN_IDS` and must run with an explicit `--allowedTools` whitelist. Never pass `--dangerouslySkipPermissions` from a bot handler.

### 5. PWA manifest.json + Service Worker — Pure Static Files

Add to `app/static/`:

```
app/static/
  manifest.json          # PWA manifest
  sw.js                  # Service worker (offline shell cache)
  icons/
    icon-192.png
    icon-512.png
```

`manifest.json` minimum required fields:

```json
{
  "name": "SEO Platform",
  "short_name": "SEO",
  "start_url": "/m/digest",
  "display": "standalone",
  "theme_color": "#1e293b",
  "background_color": "#0f172a",
  "icons": [
    { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

`sw.js` — app-shell caching strategy (cache `/m/*` HTML shells, network-first for data):

```javascript
const SHELL_CACHE = "seo-shell-v1";
const SHELL_URLS = ["/m/digest", "/m/positions", "/static/css/mobile.css"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL_CACHE).then(c => c.addAll(SHELL_URLS)));
});

self.addEventListener("fetch", e => {
  if (SHELL_URLS.includes(new URL(e.request.url).pathname)) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
  // All other requests: network pass-through (no cache for API data)
});
```

Register in `base_mobile.html`:

```html
<link rel="manifest" href="/static/manifest.json" />
<script>
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js");
  }
</script>
```

### 6. Safe Area Insets — Without npm Build Step

Since Tailwind is loaded via CDN Play (no build step), add safe-area padding as CSS custom properties in `base_mobile.html` rather than a Tailwind plugin:

```html
<style>
  :root {
    --sat: env(safe-area-inset-top, 0px);
    --sab: env(safe-area-inset-bottom, 0px);
    --sal: env(safe-area-inset-left, 0px);
    --sar: env(safe-area-inset-right, 0px);
  }
  .pb-safe  { padding-bottom: var(--sab); }
  .pt-safe  { padding-top: var(--sat); }
  .px-safe  { padding-left: var(--sal); padding-right: var(--sar); }
</style>
```

Viewport meta tag (required for `env()` to work on iOS):

```html
<meta name="viewport" content="width=device-width, initial-scale=1,
      maximum-scale=1, user-scalable=no, viewport-fit=cover" />
```

Apply `.pb-safe` to bottom navigation bars and `.pt-safe` to fixed headers.

**If Tailwind is moved to a build step later:** Add `tailwindcss-safe-area` plugin (`npm i -D tailwindcss-safe-area`) and replace the manual CSS with `pb-safe`, `pt-safe` utility classes from the plugin.

### 7. Mobile HTMX Patterns

HTMX 2.0 works identically on mobile — no mobile-specific version or plugin. Key patterns for mobile focus apps:

- **Pull-to-refresh:** `hx-trigger="revealed"` on a sentinel div at top of scroll container fires position/data refresh
- **Infinite scroll:** `hx-trigger="intersect once"` on bottom sentinel loads next page chunk
- **Touch-friendly targets:** Use Tailwind `min-h-[44px] min-w-[44px]` for all interactive elements (Apple HIG minimum)
- **Swipe gestures:** HTMX does not handle swipe natively. Use `touchstart`/`touchend` listeners that call `htmx.trigger(el, 'swipeleft')` — keep in a 30-line `mobile-gestures.js` static file
- **No `hx-boost` on `/m/` routes:** `hx-boost` intercepts navigation globally; mobile SPA-like routing works better with explicit `hx-push-url` on link clicks

---

## Upgrade: python-telegram-bot 21.x → 22.x

**Why upgrade now:** v21 is still maintained but v22 is the stable branch as of early 2026 (latest stable: v22.x). v21 is already in the installed stack so the upgrade happens in a single requirements change.

**Breaking changes from v21 to v22:**

| Change | Impact | Fix |
|--------|--------|-----|
| Duration attributes return `datetime.timedelta` (opt-in via `PTB_TIMEDELTA=true`) | Low — not used in current push-only integration | Use keyword args everywhere; set `PTB_TIMEDELTA=false` initially, migrate gradually |
| `v22.4`: one parameter added non-backward-compatibly for positional args | Low | Already using keyword arguments per project convention |
| Removed deprecated v20 functionality | Minimal — not using deprecated APIs | Check: `BotCommand`, `ChatAction`, `ParseMode` usages unchanged |

**Migration steps:**

```bash
uv pip install "python-telegram-bot>=22.0,<23.0"
# Verify: python -c "import telegram; print(telegram.__version__)"
# Run existing notification tests
```

**If upgrade blocked:** v21.11+ (latest v21 release) works for all v4.0 features — `WebAppInfo`, `CommandHandler`, webhook mode all available. Upgrade is recommended but not blocking.

---

## What NOT to Add (v4.0 Scope)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| aiogram 3.x | Better framework for complex bots with conversation state, but adds a second bot library alongside python-telegram-bot; split brain for telegram code | python-telegram-bot 22.x — already in stack, sufficient for command handling + webhook |
| React / Vue / Svelte for Telegram Mini App frontend | SPA framework is explicitly out of scope per PROJECT.md; adds build toolchain; the Telegram WebApp wrapper around Jinja2 HTMX pages is the architecture | Jinja2 + HTMX 2.0 rendered pages, opened in Telegram via `WebAppInfo(url=...)` |
| `pywebpush` / `web-push` (browser push notifications) | Browser VAPID push requires key management and service worker subscription flow; Telegram is the notification channel for this team | python-telegram-bot send_message from Celery tasks (already shipping) |
| `init-data-py` / `telegram_init_data` (third-party initData validators) | 20 lines of stdlib `hmac` + `hashlib` cover the entire algorithm; extra dependency for no gain | stdlib `hmac.new(b"WebAppData", ...)` — see Integration Patterns |
| ngrok / cloudflare-tunnel as a dependency | Tunnel tools are dev environment concerns, not application dependencies | Document in CONTRIBUTING.md; production uses native HTTPS VPS |
| Separate bot process / separate Docker service | Adds IPC complexity; the bot Application integrates cleanly into FastAPI lifespan; webhook mode removes polling-vs-event-loop conflict | FastAPI lifespan-managed `Application` + webhook endpoint |
| `flask-pwa` / `django-pwa` | Flask/Django libraries; incompatible with FastAPI | `manifest.json` + `sw.js` as static files — no library needed |
| Starlette WebSocket for bot commands | Telegram uses webhooks (POST), not WebSocket; introducing WebSocket for this creates unnecessary complexity | FastAPI POST endpoint → `application.process_update()` |
| `claude-code-headless` (npm package) | Node.js package; running Node.js inside the Python application is an unnecessary runtime dependency | `claude-code-sdk` (PyPI) — same capability, Python-native |

---

## Installation (v4.0 Additions)

```bash
# Upgrade python-telegram-bot
uv pip install "python-telegram-bot>=22.0,<23.0"

# Claude Code agent SDK (only if /agent bot command is in scope for this phase)
uv pip install "claude-code-sdk>=0.0.13"

# No other new packages.
# Mobile templates, PWA files (manifest.json, sw.js, icons/) are static assets.
# Telegram initData validation uses stdlib hmac + hashlib.
# Safe-area CSS is inline in base_mobile.html.
```

---

## Version Compatibility (v4.0)

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| python-telegram-bot 22.x | Python 3.12 | Fully compatible; v22 requires Python ≥3.9 |
| python-telegram-bot 22.x | Bot API 9.x | v22 tracks current Bot API; `WebAppInfo`, `WebAppData` stable since Bot API 6.0 |
| claude-code-sdk ≥0.0.13 | Python 3.12 | asyncio-based; spawns `claude` CLI as subprocess; requires `claude` CLI installed in container PATH |
| telegram-web-app.js v62 | HTMX 2.0 | No conflict; telegram-web-app.js operates on `window.Telegram.WebApp` namespace; HTMX operates on DOM attributes; no overlap |
| FastAPI 0.115 + webhook endpoint | python-telegram-bot 22.x Application | `application.process_update(Update.de_json(data, bot))` is the integration point; fully async-compatible |

---

## Alternatives Considered (v4.0 Scope)

| Category | Decision | Alternative | Why Not |
|----------|----------|-------------|---------|
| Bot framework | python-telegram-bot 22.x (upgrade) | aiogram 3.x | aiogram is architecturally superior for complex bots; this project needs command handling bolted onto an existing notification sender — upgrading the existing library is less churn |
| Bot runtime | FastAPI lifespan + webhook | Standalone bot process (separate Docker service) | Webhook mode inside FastAPI eliminates polling, reduces Docker complexity (one fewer service), and shares the app's settings/DB session factory |
| Telegram Mini App frontend | Jinja2 + HTMX pages opened via WebAppInfo URL | Full SPA (React) compiled to static files served as Mini App | SPA is out of scope per PROJECT.md decision record; Jinja2 pages render fine inside the Telegram WebView; the existing HTMX pattern works for all 8 focus apps |
| initData validation | stdlib hmac + hashlib | `init-data-py` library | Zero-dependency stdlib implementation; algorithm is 20 lines; well-documented by Telegram since Bot API 6.0 |
| PWA push | Telegram bot push (existing) | VAPID web push via `pywebpush` | The team uses Telegram; adding browser push would duplicate the channel; Telegram push is richer (inline keyboards, Mini App buttons) |
| Safe-area CSS | Manual CSS custom properties in `base_mobile.html` | `tailwindcss-safe-area` npm plugin | Project uses Tailwind CDN Play (no build step); the plugin requires npm; manual CSS variables achieve identical result with no toolchain change |
| Claude agent invocation | `claude-code-sdk` Python package | Raw `asyncio.create_subprocess_exec("claude", "-p", ...)` | SDK handles JSON output parsing, session management, retry on `api_retry` events, and structured result extraction; ~50 lines saved vs. raw subprocess |

---

## v3.0 New Additions (Preserved Reference)

See previous STACK.md version — no new libraries added in v3.0.

---

## v2.0 New Additions (Preserved Reference)

| Library | Version | Feature | Why |
|---------|---------|---------|-----|
| anthropic | ≥0.89.0 | LLM Briefs (opt-in AI content) | Official Anthropic Python SDK; `AsyncAnthropic` client |
| pyotp | 2.9.0 | 2FA TOTP | RFC 6238 compliant; works with Google Authenticator |
| qrcode[pil] | ≥8.2 | 2FA QR code display | Provisioning URI QR codes for authenticator app setup |
| sse-starlette | ≥3.3.3 | In-app real-time notifications | `EventSourceResponse` for HTMX `hx-ext="sse"` |

---

## v1.0 Stack (Preserved Reference)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | Runtime | 3.12 is the stable LTS-track release with best async performance |
| FastAPI | 0.115.x | ASGI web framework | 0.115 stable branch; lifespan-only startup (no deprecated `on_event`) |
| Pydantic | 2.7+ | Data validation | Rust-core; 3–5x faster than v1; FastAPI 0.111+ requires v2 |
| PostgreSQL | 16.x | Primary database | PG16 parallel query gains; battle-tested Docker images |
| asyncpg | 0.29.x | Async PostgreSQL driver | Required by SQLAlchemy async engine; fastest pure-async PG driver |
| SQLAlchemy | 2.0.x (≥2.0.30) | ORM + query builder | Only version with proper async support; `AsyncSession` + `async_sessionmaker` |
| Alembic | 1.13.x | Database migrations | Explicit SQLAlchemy 2.0 async engine support in `env.py` |
| Redis | 7.2.x | Message broker + cache | LTS branch; Redis 8 in preview — not for production |
| Celery | 5.4.x | Distributed task queue | 5.4 fixes Python 3.12 compatibility; `task_acks_late=True` for reliability |
| Playwright | 1.47+ | Browser automation | Async-native; stealth context options; `playwright[chromium]` only |
| Jinja2 | 3.1.x | Server-side HTML templating | Pairs natively with FastAPI; stable; `SandboxedEnvironment` for DB templates |
| HTMX | 2.0.x | Partial page updates | 2.0 from the start; `hx-ws`/`hx-sse` moved to extensions |

### Supporting Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| python-jose[cryptography] | 3.3.x | JWT encode/decode |
| passlib[bcrypt] | 1.7.x | Password hashing (cost factor 12) |
| cryptography | 42.x | Fernet encryption for WP credentials and TOTP secrets |
| python-multipart | 0.0.9+ | Form/file upload parsing |
| slowapi | 0.1.9 | Rate limiting (Redis storage backend) |
| greenlet | 3.x | SQLAlchemy async bridge |
| httpx | 0.27.x | Async HTTP client (WP REST, GSC, DataForSEO) |
| redis-py | 5.0.x | Redis client (cache, pub/sub, rate counters) |
| flower | 2.0.x | Celery task monitoring UI (secure with Basic Auth) |
| redbeat | 2.2.x | DB-backed Celery Beat schedule (survives Redis flush) |
| openpyxl | 3.1.x | Excel read/write (.xlsx) |
| weasyprint | 62.x | HTML→PDF (subprocess-isolated for memory leak mitigation) |
| mammoth | 1.6.x | DOCX→HTML conversion (brief uploads) |
| authlib | 1.3.x | OAuth 2.0 (GSC integration; `AsyncOAuth2Client` on httpx) |
| python-telegram-bot | 22.x | Bot commands + Mini App buttons + push alerts (async webhook mode) |
| aiosmtplib | 3.x | Async SMTP email dispatch |
| beautifulsoup4 | 4.12.x | HTML parsing (TOC, schema detection, GEO checks) |
| lxml | 5.x | Fast XML/HTML parser (bs4 backend) |
| loguru | 0.7.x | Structured JSON logging (10 MB rotation, 30-day retention) |
| pydantic-settings | 2.x | Type-validated settings from `.env` |
| pytest | 8.x | Test runner |
| pytest-asyncio | 0.23.x | Async test support (`asyncio_mode = "auto"`) |
| pytest-cov | 5.x | Coverage reporting (`--cov-fail-under=60`) |
| respx | 0.21.x | Mock httpx calls in tests |

---

## Sources

- python-telegram-bot changelog (v22.0–v22.6): https://docs.python-telegram-bot.org/en/stable/changelog.html — HIGH confidence (official docs)
- Telegram Mini Apps / WebApps official docs: https://core.telegram.org/bots/webapps — HIGH confidence (official); telegram-web-app.js current version: 62
- Telegram initData validation algorithm: https://docs.telegram-mini-apps.com/platform/init-data — HIGH confidence (official Telegram Mini Apps docs)
- Claude Code headless / Agent SDK: https://code.claude.com/docs/en/headless — HIGH confidence (official Anthropic docs); `--print` / `-p` flag, `--bare`, `--output-format json`
- claude-code-sdk PyPI: https://pypi.org/project/claude-code-sdk/ — HIGH confidence (official package)
- PWA manifest + service worker: https://almanac.httparchive.org/en/2025/pwa — MEDIUM confidence (2025 almanac data)
- safe-area-inset CSS: https://medium.com/@developerr.ayush/understanding-env-safe-area-insets-in-css-from-basics-to-react-and-tailwind-a0b65811a8ab — MEDIUM confidence (verified against MDN env() spec)
- HTMX 2.0 documentation: https://htmx.org/docs/ — HIGH confidence (official docs); no mobile-specific additions needed

---

*Stack research updated for v4.0 milestone: Mobile focus apps + Telegram WebApp + Telegram Bot commander + Claude Code agent*
*Original research: 2026-03-31 | v2.0 update: 2026-04-06 | v3.0 update: 2026-04-09 | v4.0 update: 2026-04-10*
