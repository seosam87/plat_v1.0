# Pitfalls Research

**Domain:** SEO Management Platform v4.0 — Adding Mobile Focus Apps and Telegram Bot to a 45-phase, 137-plan FastAPI + Jinja2 + HTMX system
**Researched:** 2026-04-10
**Confidence:** HIGH

This document focuses exclusively on pitfalls that arise from *adding* a mobile UI layer and Telegram bot to the *existing* v3.1 system. Generic mobile or bot development mistakes are omitted. Every pitfall is grounded in the codebase's current state — the existing JWT auth, Jinja2 templates, HTMX patterns, WP pipeline, and Celery infrastructure already in place.

---

## Critical Pitfalls

### Pitfall 1: Telegram WebApp initData Is Not Validated Server-Side

**What goes wrong:**
When a Telegram Mini App opens, Telegram injects `window.Telegram.WebApp.initData` — a query string containing the user's Telegram ID, username, and an HMAC-SHA256 signature. Many developers read `initData.user.id` on the client side and POST it directly to the backend to get a JWT token. The backend trusts this POST without verifying the HMAC, meaning any attacker can POST `{"telegram_id": 12345}` to impersonate any user — including the admin. The platform controls WP credentials for 20–100 client sites; an impersonation attack has catastrophic consequences.

**Why it happens:**
`initData` looks like a trustworthy object because it comes from Telegram's JS SDK. Developers test in Telegram where the data is always valid and never test the unauthenticated API call directly. The signature verification requires HMAC-SHA256 with the bot token as the key material — it is a non-obvious, multi-step algorithm that is easy to skip when prototyping.

**How to avoid:**
- Implement server-side `initData` validation before issuing any JWT. The algorithm: extract `hash` from `initData`, sort remaining fields alphabetically into a `data_check_string`, compute `HMAC-SHA256(data_check_string, key=HMAC-SHA256("WebAppData", bot_token))`, compare with extracted `hash`.
- Reject `initData` where `auth_date` is older than 3600 seconds (prevents replay attacks with captured valid tokens).
- The Telegram auth endpoint must return a short-lived JWT (15–30 minutes) with `scope: "telegram_webapp"` so it cannot be reused outside the Mini App context.
- Use `python-telegram-bot 21.x` — already in the stack — which provides `telegram.helpers.check_webapp_signature()` utility for the HMAC verification.

**Warning signs:**
- Auth endpoint `POST /telegram/auth` accepts `{"telegram_id": N}` without any signature parameter.
- `initData` is logged anywhere (it contains the raw signature — leaking it enables replay attacks).
- JWT issued from Telegram auth has the same expiry (24h) as the standard web JWT.

**Phase to address:**
Mobile Foundation phase (base infrastructure) — before any Mini App feature routes are built, the `initData` validation middleware must exist and be covered by a unit test that sends a forged `telegram_id` and expects 401.

---

### Pitfall 2: Telegram Bot Has No Access Control — Any Telegram User Can Issue Commands

**What goes wrong:**
The bot is deployed publicly (all Telegram bots are public by default). Anyone who finds the bot's username can send `/deploy`, `/status`, `/logs` — commands that trigger Celery tasks, expose system status, or invoke Claude Code. Without an allowlist check, a random user who stumbles on the bot can run destructive operations against production sites.

**Why it happens:**
`python-telegram-bot` handlers are stateless — they process any incoming message from any `chat_id`. Developers add command handlers and test them with their own account. The bot works in testing. The access check is an afterthought that is never added because "who would find it?"

**How to avoid:**
- Store `TELEGRAM_OWNER_ID` as an environment variable (the owner's numeric Telegram user ID, not username — usernames can be changed).
- Add a `require_telegram_owner` decorator applied to every command handler. Implementation: check `update.effective_user.id == int(settings.TELEGRAM_OWNER_ID)`. If not match, silently ignore (do not reply — replying confirms the bot exists to an attacker) or reply with a generic error.
- For a team scenario (small team, 2–3 people), store allowed IDs in a `TELEGRAM_ALLOWED_IDS` comma-separated env var and check membership.
- Log every received command with `user_id`, `username`, and `command` in loguru — even rejected ones — so unauthorized probe attempts are visible.

**Warning signs:**
- A command handler that processes messages without any `if update.effective_user.id != OWNER_ID: return` guard.
- The bot is tested with `@BotFather`'s `/mybots` link shared publicly.
- `TELEGRAM_OWNER_ID` is not in `.env.example` or the Compose env spec.

**Phase to address:**
Telegram Bot phase — the `require_telegram_owner` decorator must be the first piece of code written for the bot, before any commands. Its unit test (send command from unauthorized user_id, expect no response) must be green before any feature work begins.

---

### Pitfall 3: Claude Code Bot Integration Has No Command Injection Guard

**What goes wrong:**
The `/claude` or `/task` bot command accepts natural-language text from the Telegram message and passes it to Claude Code as a task description. If the user message contains shell metacharacters or prompt injection (e.g., "fix the login bug; also run `rm -rf /`"), the Claude Code invocation may execute unintended shell commands. Published CVEs (February 2026) document that Claude Code CLI has command injection vulnerabilities via untrusted project hooks and environment variable injection.

**Why it happens:**
Claude Code is trusted as "safe AI" — developers do not treat its input the same way they would treat `subprocess.run(user_input, shell=True)`. The trust boundary between the Telegram message (external, untrusted) and the Claude Code invocation (trusted system) is not explicitly maintained.

**How to avoid:**
- Never pass raw Telegram message text directly as a shell argument to Claude Code. Always pass it as structured input through a controlled API call (`anthropic.Anthropic().messages.create()`), not as a CLI argument.
- If using `subprocess` to invoke Claude Code CLI, always use `shell=False` with an explicit argument list: `subprocess.run(["claude", "--task", sanitized_input], shell=False)`.
- Strip shell metacharacters from the task description before use: reject messages containing `` ` ``, `$()`, `&&`, `||`, `;`, `|`, `>`, `<`.
- Run Claude Code invocations in a Docker container with limited filesystem mounts (no access to `.env`, credentials, or SSH keys) and no outbound network except the Anthropic API endpoint.
- Claude Code's own permission system requires interactive approval for file writes and shell commands — on a remote bot, this approval channel does not exist. Therefore, limit bot-triggered Claude Code to read-only analysis tasks (code review, explain, audit), not write tasks (edit files, run tests, deploy).

**Warning signs:**
- Bot command handler does `subprocess.run(f"claude --task '{message.text}'", shell=True)`.
- Claude Code invoked with `DISABLE_SECURITY_PATTERNS=true` because "it's only internal."
- Bot responds to `/claude rm -rf /` with "I'll take care of that" rather than an error.

**Phase to address:**
Telegram Bot phase (Claude Code integration sub-feature) — this is the highest-risk feature in v4.0. Treat as a security-sensitive integration requiring explicit threat modeling before implementation. If the risk cannot be mitigated adequately, scope the bot to read-only Claude Code queries only.

---

### Pitfall 4: Mobile Templates Duplicate Desktop Template Logic Instead of Extending It

**What goes wrong:**
A developer creates `base_mobile.html` by copying `base.html` and modifying it. Then each mobile focus app template (`digest_mobile.html`) is copied from its desktop equivalent and modified. Over time, a bug fix or design change in the desktop template requires a parallel fix in the mobile template — which is often missed. After 8 focus apps, there are 8+ pairs of diverged templates. Service layer changes that update template variable names break the mobile templates invisibly (no error at startup, only at runtime).

**Why it happens:**
Copy-paste is the path of least resistance when the mobile layout is structurally different from the desktop layout. "It would take too long to factor out the shared parts into macros" — which is true initially, but the debt compounds.

**How to avoid:**
- `base_mobile.html` should `{% extends "base.html" %}` and override only the blocks that differ (nav, sidebar, footer structure). It must NOT be a full copy of `base.html`.
- Shared data display components (position badge, site health indicator, keyword count) must be Jinja2 macros in `components/macros.html`, imported by both desktop and mobile templates: `{% from "components/macros.html" import position_badge, site_health_badge %}`.
- Mobile focus apps should define new layouts but reuse existing data display macros. The "mobile" part is layout and interaction, not data presentation logic.
- Use Tailwind's responsive prefix (`sm:`, `md:`) to handle minor layout variations without separate templates. Only create a separate mobile template when the layout is fundamentally different (e.g., a full-screen card swipe UI vs. a table).

**Warning signs:**
- `grep -r "{% extends" templates/mobile/` returns templates that extend `base_mobile.html` but `base_mobile.html` does not extend `base.html`.
- A desktop template bug is fixed but the corresponding mobile template still has the old broken code.
- `templates/mobile/` directory has more than 2x the number of templates that have a desktop equivalent.

**Phase to address:**
Mobile Foundation phase — `base_mobile.html` template architecture must be settled before any focus app templates are written. Define which blocks are overridden and which macros are shared. This decision cannot be retrofitted cheaply.

---

### Pitfall 5: Telegram WebApp Auth and Web JWT Auth Create Two Parallel Session Systems

**What goes wrong:**
The platform issues JWTs at `POST /auth/login` with `exp=24h`. The Telegram Mini App gets its own JWT from `POST /telegram/auth` after `initData` validation. If these are not unified, the platform has two session systems: web sessions and Telegram sessions. An admin user has two separate JWTs with different expiries, different scopes, and potentially different permissions. API endpoints must check both token types. The existing `get_current_user` dependency only validates web JWTs — Mini App calls fail with 401 until the dependency is patched.

**Why it happens:**
Telegram auth is added as a new endpoint without auditing how the existing `get_current_user` JWT dependency works. The new token type works for new endpoints but the existing endpoints (position data, site health) still require the web JWT format, so the Mini App cannot reuse existing API endpoints.

**How to avoid:**
- Issue a standard platform JWT from the Telegram auth endpoint. The token payload adds a `source: "telegram"` claim but the token is otherwise identical in format to the web JWT.
- The existing `get_current_user` dependency validates the JWT signature — it does not care about the `source` claim. No changes to existing endpoints are needed.
- Store the platform `user.id` in the JWT payload, resolved by matching `telegram_id` to a `users.telegram_id` column (add this nullable column in the migration). If no match, the bot/Mini App user has no platform account and gets a `403 Not Found` with a setup message.
- Short-lived Telegram JWTs (15–30 min) are refreshed silently by the Mini App using `Telegram.WebApp.initData` (re-validate and re-issue) rather than a refresh token flow.

**Warning signs:**
- `app/auth/dependencies.py` has two different `get_current_user` variants — one for web, one for Telegram.
- Mini App API calls go to a separate `/m/api/` prefix with duplicated route handlers that bypass the existing auth middleware.
- A `telegram_id` field appears in the JWT payload of standard web login tokens.

**Phase to address:**
Mobile Foundation phase — the `users.telegram_id` column migration and the Telegram auth endpoint must be built in the same phase as `base_mobile.html`, before any focus app touches the auth flow.

---

### Pitfall 6: HTMX `hx-push-url` Navigation Breaks the Mobile Back Button

**What goes wrong:**
The existing desktop UI uses `hx-push-url` for navigation — it updates the browser URL and HTMX history cache when navigating between pages. On desktop, this works acceptably. On mobile (especially Android Chrome), pressing the device back button after HTMX navigation produces inconsistent behavior: sometimes the URL updates but the content does not refresh, sometimes the full-page snapshot is restored but scroll position is lost, and in some cases HTMX history cache is empty (first visit from a Telegram Mini App WebView) causing the restored page to be blank.

**Why it happens:**
HTMX history restoration relies on a localStorage snapshot of the DOM taken at navigation time. In Telegram Mini App WebView, localStorage behavior may differ from Chrome. The `hx-push-url` issue on mobile back button is a known open bug in HTMX (GitHub issue #854, open as of 2025).

**How to avoid:**
- In the mobile `/m/` routes, avoid `hx-push-url` entirely. Mobile focus apps are designed as single-purpose screens — full-page navigation is triggered by links, not HTMX history. Use `hx-target` and `hx-swap` for in-page partial updates without URL manipulation.
- When navigation between focus apps is needed (e.g., from Digest to Positions), use standard `<a href="/m/positions/">` links that perform a full page load, not HTMX navigation.
- If the Mini App has internal screens (e.g., a site-detail drill-down from the Health focus app), manage that state with Telegram Mini App's own `BackButton` API (`window.Telegram.WebApp.BackButton.show()` / `.hide()`) instead of browser history.

**Warning signs:**
- Mobile templates use `hx-push-url` on navigation links.
- A user taps the Android back button and lands on a blank white page.
- `hx-history="false"` is applied globally to work around the issue rather than avoiding `hx-push-url` on mobile.

**Phase to address:**
Mobile Foundation phase — establish a routing convention: `/m/*` routes never use `hx-push-url`. Document this in the phase PLAN.md as a hard constraint, not a recommendation.

---

### Pitfall 7: WP Pipeline Approve Action Has No Accidental-Tap Protection on Mobile

**What goes wrong:**
The "Pages" mobile focus app allows approving and pushing content changes to live WordPress sites. On desktop, the approve button is a deliberate click in a form context with visual separation from cancel. On mobile, touch targets are tightly packed and fat-finger taps are common. A user scrolling through the approve queue accidentally taps "Approve & Push" on the wrong page — the change goes live on the client's site immediately. There is no undo. The existing `POST /pipeline/pages/{id}/approve` endpoint is immediate and irreversible.

**Why it happens:**
The desktop pipeline UI was built assuming deliberate, precise mouse clicks. The mobile UI copies the action buttons without adapting the confirmation flow for touch. Destructive actions on mobile require a fundamentally different UX pattern — not just a smaller button.

**How to avoid:**
- Every irreversible action on the mobile UI (approve, push, publish) requires a two-step confirmation: first tap shows a confirmation sheet (`Telegram.WebApp.showConfirm()` or an HTMX-rendered bottom sheet), second tap executes the action.
- Touch targets for destructive actions must be a minimum 48×48px (Android Material) / 44×44pt (iOS HIG). Approve and Reject buttons must have at least 16px spacing between them to prevent simultaneous activation.
- Add a 3-second cooldown after the confirmation sheet appears before the confirm button becomes tappable (prevents double-tap from blowing past the confirmation).
- For approvals specifically: show the diff of what will be changed (title, content excerpt) in the confirmation sheet so the user sees exactly what they are approving.
- Consider a swipe-to-confirm pattern for approve (swipe right = approve, swipe left = reject) which requires deliberate directional intent and is harder to trigger accidentally.

**Warning signs:**
- Approve and Reject buttons are adjacent (less than 16px apart) in the mobile template.
- `POST /pipeline/pages/{id}/approve` is called directly from an `hx-post` on a button with no intermediate confirmation step.
- Audit log shows approval timestamps clustering at the same second as a list-scroll event for the same user.

**Phase to address:**
Pages focus app phase — the confirmation flow must be designed before the approve action is wired up. Never ship a destructive mobile action without a tested confirmation gate. Add to acceptance criteria: "Approve action requires exactly 2 taps to execute; 1 tap shows confirmation only."

---

### Pitfall 8: Telegram Bot Webhook and FastAPI Share Port — Webhook Secret Is Not Validated

**What goes wrong:**
The recommended deployment for a single-VPS system is to register a Telegram webhook at a secret URL path (e.g., `POST /telegram/webhook/RANDOM_SECRET`) and mount the handler inside the existing FastAPI app. If the secret path is too simple or if there is no `X-Telegram-Bot-Api-Secret-Token` header validation, any attacker who discovers the endpoint can POST forged updates that trigger bot command handlers. On this platform, those handlers include `/deploy` and `/logs` commands that expose production system state.

**Why it happens:**
Developers register the webhook with a token in the URL and assume "nobody will guess it." They forget that Telegram can optionally send a secret token header, and they do not validate it. Path-based secrets are sufficient if the path is truly random, but header validation adds defense-in-depth.

**How to avoid:**
- Use polling instead of webhooks for this deployment scenario. The single-VPS + Docker Compose setup has no benefit from webhooks (latency is irrelevant for an internal admin bot). Polling requires no public endpoint, no SSL webhook registration, no secret path management. Run `python-telegram-bot`'s `Application.run_polling()` in a dedicated Celery worker or a separate Docker service.
- If webhooks are chosen: set `secret_token` in `setWebhook` API call; validate `X-Telegram-Bot-Api-Secret-Token` header in the FastAPI handler before processing any update; return `200 OK` even for rejected requests (do not reveal validation failure to the caller).
- Never run `Application.run_polling()` inside the FastAPI event loop — it blocks the loop. Use a separate container: `docker-compose.yml` service `telegram-bot` that runs `python bot.py` independently.

**Warning signs:**
- Telegram webhook URL uses a short, guessable path (`/telegram/webhook/bot123`).
- `X-Telegram-Bot-Api-Secret-Token` header validation is absent from the webhook handler.
- `Application.run_polling()` is called inside FastAPI's `lifespan` context manager on the same event loop as the HTTP server.

**Phase to address:**
Telegram Bot phase — decide polling vs. webhook in the PLAN.md before writing any code. For this project: use polling in a dedicated Docker service. This decision eliminates the webhook secret validation pitfall entirely and simplifies the architecture.

---

### Pitfall 9: `python-telegram-bot` Event Loop Conflicts With FastAPI's asyncio Loop

**What goes wrong:**
FastAPI runs on an asyncio event loop managed by uvicorn. `python-telegram-bot 21.x`'s `Application` also requires an asyncio event loop. When a developer tries to run both in the same process (to "share state" between the web app and the bot), they encounter: `RuntimeError: This event loop is already running` or the bot's `run_polling()` blocks uvicorn's loop, causing HTTP requests to time out. Even using `asyncio.create_task()` to run the bot alongside FastAPI results in subtle task cancellation issues during shutdown.

**Why it happens:**
Python-telegram-bot's `Application.run_polling()` is designed to own the event loop — it is not designed for embedding. FastAPI + uvicorn also owns the event loop. Two frameworks fighting for loop ownership in one process is a well-documented Python asyncio antipattern.

**How to avoid:**
- Run the Telegram bot as a separate Docker service with its own process and its own event loop. The `docker-compose.yml` service `telegram-bot` runs `python -m app.bot` which calls `Application.run_polling()` — completely isolated from the FastAPI process.
- Communication between bot and web app goes through the database (bot writes a `bot_commands` row, Celery worker picks it up) or through a Redis pub/sub channel. Never through shared in-process state.
- If the bot needs to call the platform's own API (to fetch site health data), it uses `httpx.AsyncClient` to call `http://web:8000/api/...` internally — the same API the mobile frontend uses.

**Warning signs:**
- `app/main.py` imports anything from the bot module during FastAPI startup.
- `Application.initialize()` is called in a FastAPI `@asynccontextmanager lifespan` block.
- `asyncio.get_event_loop().run_until_complete(bot_app.run_polling())` appears anywhere in the codebase.

**Phase to address:**
Telegram Bot phase — the Docker service separation must be designed in the phase PLAN.md before any bot code is written. The `docker-compose.yml` update (new `telegram-bot` service) is the first task, not an afterthought.

---

### Pitfall 10: PWA Service Worker Intercepts HTMX Requests and Serves Stale Cached Partials

**What goes wrong:**
Adding a PWA manifest and service worker to enable "Add to Home Screen" on mobile seems harmless. But HTMX works by making HTTP requests to fetch HTML partials (`hx-get="/m/digest/data"`). If the service worker caches these partial responses and serves them on subsequent requests, the user sees stale data: yesterday's position data showing as "current," outdated site health scores. Unlike a full-page response where stale HTML is obvious, a stale HTMX partial is indistinguishable from a fresh one to the user.

**Why it happens:**
Service workers cache by URL pattern. HTMX partial endpoints have the same URL as their data-returning counterparts — there is no structural difference between a "cacheable asset" URL and a "dynamic data" URL unless explicitly configured. A developer configures the service worker to cache `/m/*` for offline support and inadvertently caches dynamic data endpoints.

**How to avoid:**
- If PWA/service worker is added, explicitly exclude all HTMX partial endpoints from caching. Use a network-first or network-only strategy for all paths under `/m/api/` and any URL that returns HTMX partials.
- Distinguish static assets (`/static/`, `/favicon.ico`) from dynamic endpoints by URL structure. Only cache static assets.
- Add `Cache-Control: no-store` response header to all HTMX partial responses (server-side, not just service worker configuration) as defense-in-depth.
- Consider: for this deployment (single VPS, always-online internal tool), a PWA manifest without a service worker is sufficient for "Add to Home Screen." The offline caching benefit does not justify the cache invalidation complexity for a data-heavy SEO platform.

**Warning signs:**
- Position data on the mobile digest page shows the same numbers for 24+ hours without refreshing.
- DevTools Application → Cache Storage shows HTMX partial responses (`/m/digest/data`, `/m/positions/data`) listed in the service worker cache.
- Users report stale data after the server was updated with new position data.

**Phase to address:**
Mobile Foundation phase — if PWA is included, the service worker cache strategy must be explicitly defined with HTMX-aware exclusion rules. The default "cache everything" PWA template is not safe for this application.

---

### Pitfall 11: Telegram Mini App Viewport Height Is Wrong on iOS — Bottom Buttons Are Clipped

**What goes wrong:**
The mobile focus apps use `height: 100vh` for full-screen layouts. In Telegram Mini App on iOS, `100vh` is calculated based on the maximum viewport height (keyboard hidden, navigation bars collapsed). When the on-screen keyboard appears, or when Telegram's bottom navigation bar is visible, content overflows the actual visible area and fixed-position bottom buttons (Approve, Submit, Back) are clipped behind the system UI. This is a known documented bug in Telegram iOS (GitHub issue #1296, open as of 2025 per official Telegram iOS repo).

**Why it happens:**
CSS `100vh` does not equal "the currently visible area" on mobile — it equals the maximum possible viewport height. Mobile browsers (and Telegram's WebView) use this definition, which differs from desktop. Developers test in desktop Telegram (where this bug doesn't appear) and miss the mobile-specific clipping.

**How to avoid:**
- Use `100dvh` (dynamic viewport height) instead of `100vh` for full-screen container heights. `dvh` updates when the keyboard appears or system UI changes.
- For bottom-fixed elements (action buttons, navigation bars), apply `padding-bottom: env(safe-area-inset-bottom)` as a fallback for notched iPhones.
- Listen to Telegram Mini App's `viewportChanged` event: `window.Telegram.WebApp.onEvent('viewportChanged', handler)` — the handler receives the new `viewportHeight` value. Apply this height to the main container via JS: `document.documentElement.style.setProperty('--tg-viewport-height', height + 'px')`. Use `var(--tg-viewport-height)` as the container height.
- Test in actual Telegram mobile app (iOS and Android), not only in desktop Telegram or browser DevTools mobile simulation.

**Warning signs:**
- Mobile templates use `h-screen` (Tailwind's `100vh`) for full-screen layouts.
- The "Approve" button on the Pages focus app is not visible on an iPhone 14 test.
- CSS contains `height: 100vh` without a `dvh` fallback in any mobile template.

**Phase to address:**
Mobile Foundation phase — define the CSS viewport strategy for all mobile templates before any focus app template is built. Add `--tg-viewport-height` CSS variable setup to `base_mobile.html` once, and all focus apps inherit it.

---

## Technical Debt Patterns

Shortcuts that seem reasonable for v4.0 but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Copying desktop templates for mobile instead of using Jinja2 macros | Faster to prototype | Every shared component fix requires 2 edits; templates diverge silently | Never — build macros in Mobile Foundation phase |
| Issuing separate JWT types for Telegram vs web auth | Isolated token systems | Two parallel session systems; existing endpoints inaccessible from Mini App | Never — unify on one JWT format with `source` claim |
| Skipping `initData` HMAC validation in development | Faster local testing | Validation gap gets deployed to production; impersonation attacks become possible | Never — validate in all environments; mock with test bot token in tests |
| Running the Telegram bot inside FastAPI's event loop | Single process, no extra Docker service | asyncio event loop contention; bot or HTTP server starves the other | Never — separate Docker service always |
| Using `100vh` for mobile layouts | Standard CSS, works in desktop tests | Bottom content clipped in Telegram iOS WebView; not caught until device testing | Never for mobile templates — use `dvh` + `env(safe-area-inset-bottom)` |
| Implementing WP pipeline approve without 2-step confirmation | Simpler mobile UI code | Accidental approvals on production client sites; irreversible | Never for destructive actions |
| PWA service worker with default cache-all strategy | Easy offline support | Stale HTMX partials; users see outdated SEO data | Acceptable only with explicit HTMX endpoint exclusion rules |
| Bot with no allowlist during initial testing | Easier to test with any account | Publicly accessible bot with destructive commands; discoverable by bots | Never — allowlist from line 1 of code |

---

## Integration Gotchas

Common mistakes when connecting the new v4.0 layers to the existing system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Telegram auth + existing JWT | Creating a new `/m/api/` prefix with duplicated route handlers | Issue a standard platform JWT from `/telegram/auth`; use existing route handlers with `HX-Request` detection for response format |
| Mobile routes + existing HTMX patterns | Using `hx-push-url` on mobile navigation | Mobile `/m/*` routes never use `hx-push-url`; navigation is full-page `<a href>` links |
| WP pipeline + mobile approve | Copying desktop approve button HTML without confirmation flow | Every destructive mobile action requires `Telegram.WebApp.showConfirm()` or HTMX bottom sheet before execution |
| Bot service + FastAPI app | Importing bot module in `app/main.py` to share DB session | Bot gets its own `AsyncSession` via its own database dependency; communicates via Redis pub/sub or DB rows |
| Telegram bot polling + Celery worker | Running `run_polling()` inside a Celery task | Dedicated `telegram-bot` Docker service; Celery handles tasks triggered by bot commands, not the bot loop itself |
| Mobile templates + existing macros | Re-implementing data display components in mobile-specific HTML | Import existing macros (`position_badge`, `site_health_badge`) in mobile templates; only override layout, not data presentation |
| Mini App viewport + Tailwind `h-screen` | Using `h-screen` class on full-height mobile containers | Replace with `style="height: var(--tg-viewport-height, 100dvh)"` set by `viewportChanged` listener in `base_mobile.html` |
| Bot commands + Celery tasks | Bot handler directly calls service functions synchronously | Bot handler writes a `bot_command_queue` Redis key or DB row; Celery worker reads and executes; bot polls for result with a task ID |
| Claude Code integration + bot | Passing raw `message.text` as shell argument | Structured input only; `shell=False`; metacharacter strip; read-only scope; isolated container |

---

## Performance Traps

Patterns that work in development but fail at production data volumes.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Mobile Digest fetches all 20–100 sites eagerly | Digest page takes > 3s to load on mobile (violates `<3s` constraint) | Paginate digest: load first 10 sites, infinite scroll with `hx-trigger="revealed"` | At 20+ sites with full position data |
| Bot command `/status` queries all sites in a synchronous loop | Bot response takes 30+ seconds for 100-site platform | Celery task for status aggregation; bot receives task ID, polls result endpoint; bot replies with "Checking..." then edits message with result | At 10+ sites |
| Mobile position chart loads full 90-day history for all keywords | Mobile chart is slow to render; large JSON payload over mobile network | Limit to 14-day history by default on mobile; add "Load 90 days" toggle | At 100+ keywords per site |
| HTMX polling on mobile (hx-trigger="every 5s") drains mobile battery | User reports battery drain when mobile app is open; background radio keeps active | Use `visibilitychange` event to pause HTMX polling when the tab is not visible; resume on focus | Always — any constant HTMX polling on mobile |
| Telegram bot sends a message per line of log output | Bot Flood Control limit (30 messages per second per bot); API returns 429 | Buffer log lines; send a single multi-line message up to 4096 characters; rate-limit bot messages to 1 per 3 seconds | At 5+ lines per log event |

---

## Security Mistakes

Domain-specific security issues for v4.0 features.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `initData` not validated server-side | Any attacker can impersonate any platform user, including admin, by POSTing a fake `telegram_id` | Server-side HMAC-SHA256 validation required before any JWT is issued; `auth_date` expiry check (3600s) required |
| Bot has no `user_id` allowlist | Any Telegram user who finds the bot can trigger `/deploy`, `/logs`, `/status` against production | `require_telegram_owner` decorator on every handler; `TELEGRAM_ALLOWED_IDS` env var checked before processing any message |
| Claude Code bot integration with `shell=True` | Command injection; arbitrary code execution on the VPS | Always `shell=False`; explicit argument list; metacharacter filtering; isolated Docker container with limited mounts |
| Telegram webhook without `X-Telegram-Bot-Api-Secret-Token` validation | Forged Telegram updates trigger bot handlers | Use polling (no webhook security surface) or validate secret token header if webhooks chosen |
| Mobile API endpoints accessible without auth | An unauthenticated user who discovers `/m/api/positions` can read SEO data | All `/m/*` routes must go through the same `get_current_user` dependency as desktop routes; mobile JWT is same format as web JWT |
| `initData` logged in debug mode | Raw `initData` contains the HMAC signature; a log with `initData` enables replay attacks | Never log `initData` raw; log only `user_id` and `auth_date` after validation |
| Bot token stored in codebase | Anyone with repo access can impersonate the bot | `TELEGRAM_BOT_TOKEN` in `.env` only; never in `docker-compose.yml` inline; never committed to git |

---

## UX Pitfalls

Common user experience mistakes specific to the mobile + Telegram context.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Desktop table layout shrunk to mobile screen | Position tables with 6 columns are unreadable at 375px width | Mobile focus apps show only the 2–3 most important columns; full table accessible via "See all" link to desktop |
| No loading state for HTMX requests on mobile (slow 4G) | User taps button; nothing happens for 2 seconds; taps again (double submit) | Add `htmx:beforeRequest` / `htmx:afterRequest` handlers to show/hide a full-screen loading overlay on mobile; disable buttons during request |
| All 8 focus apps accessible from a flat bottom nav | Bottom nav with 8 items is unusable; icons too small; labels cut off | Group focus apps: primary (Digest, Positions, Health) in bottom nav; secondary (Traffic, Report, Tools, Tasks, Pages) in a "More" sheet |
| Telegram bot sends wall-of-text responses | Bot messages are unreadable; user scrolls past them | Format bot responses with Markdown (bold headers, emoji status indicators); limit to 5 key data points per message; add "Details" inline keyboard button |
| Mobile approve queue shows no context for what is being approved | User cannot evaluate the change without knowing what it is | Always show: site name, page URL, change type (title/content/schema), and a diff excerpt in the approve card — never just "Page ID 4521" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces for v4.0.

- [ ] **Telegram auth:** `initData` HMAC validation implemented server-side — verify by POSTing a fake `{"telegram_id": 1}` without a valid signature and confirming 401 response.
- [ ] **Telegram auth:** `auth_date` replay protection — verify that an `initData` with `auth_date` older than 3600 seconds is rejected with 401.
- [ ] **Bot access control:** Every command handler has `require_telegram_owner` check — verify that a message from `user_id=99999` (not in allowlist) produces no bot response.
- [ ] **Bot Docker service:** Telegram bot runs as a separate Docker service, not embedded in FastAPI — verify `docker-compose.yml` has a `telegram-bot` service and the FastAPI service has no bot imports.
- [ ] **Mobile foundation:** `base_mobile.html` extends `base.html` (not a copy) — verify with `grep "extends" templates/mobile/base_mobile.html`.
- [ ] **Mobile foundation:** Viewport height uses `dvh` + `--tg-viewport-height` CSS variable — verify by opening the app in Telegram iOS and tapping in a text field (keyboard appears); confirm no bottom button clipping.
- [ ] **Mobile navigation:** No `hx-push-url` on `/m/*` routes — verify with `grep -r "hx-push-url" templates/mobile/`.
- [ ] **WP pipeline (mobile):** Approve action requires 2 taps — verify by tapping "Approve" once and confirming that execution does NOT happen (only confirmation sheet appears).
- [ ] **JWT unification:** Telegram-issued JWT works on existing API endpoints (e.g., `GET /api/sites/`) — verify by using a Telegram-issued token to call a desktop-mode endpoint and expecting 200 (not 401).
- [ ] **Claude Code integration:** Bot does not execute write operations — verify that `/claude edit app/main.py` returns a "read-only scope" error from the bot.
- [ ] **Service worker (if added):** HTMX partial endpoints are not cached — verify in DevTools → Application → Cache Storage that `/m/digest/data` is absent.
- [ ] **Bot flood control:** Bot does not send more than 1 message per 3 seconds — verify by triggering a log command and confirming that multi-line output is batched into a single message.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| `initData` validation bypass discovered in production | HIGH | Immediate: revoke all Telegram-issued JWTs by rotating JWT secret (instant logout for all users); hotfix validation; audit logs for any suspicious `telegram_id` POSTs; notify affected users |
| Bot accessible without allowlist in production | MEDIUM | Add `require_telegram_owner` decorator and redeploy bot service (2-minute fix); review bot message logs for unauthorized usage; rotate bot token if commands were received from unknown users |
| Template duplication divergence (8 focus app pairs) | HIGH | Audit diff between desktop and mobile versions of each template; extract shared parts to macros; refactor takes 2–4 hours per focus app; test each |
| Mobile approve sent accidentally | MEDIUM | Check WP REST API logs for the pushed content; if still within WP revision history, revert via WP admin; add confirmation gate and redeploy mobile; notify client if change was visible |
| asyncio event loop deadlock (bot + FastAPI in same process) | MEDIUM | Restart the affected container; separate bot into its own Docker service (1-2 hours); no data loss |
| PWA service worker serving stale HTMX partials | LOW | Force service worker update: increment cache version, deploy; add `Cache-Control: no-store` to HTMX partial responses server-side as permanent fix |
| Claude Code bot executes unexpected file modification | HIGH | Inspect git diff in the working directory immediately; revert changes with `git checkout`; remove Claude Code write access from bot scope; audit all bot-triggered Claude Code calls in logs |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| `initData` not validated server-side | Mobile Foundation (auth integration) | Unit test: forged `telegram_id` POST returns 401 |
| Bot has no `user_id` allowlist | Telegram Bot (first task) | Test: unknown `user_id` sends command → no response logged |
| Claude Code integration command injection | Telegram Bot (Claude Code sub-feature) | `shell=False` audit; metacharacter test input rejected |
| Mobile template duplication | Mobile Foundation | `grep "extends" base_mobile.html` returns `base.html` |
| Dual JWT session systems | Mobile Foundation (auth integration) | Telegram JWT works on existing `GET /api/sites/` endpoint |
| HTMX back-button navigation broken on mobile | Mobile Foundation | `grep -r "hx-push-url" templates/mobile/` returns empty |
| WP approve without confirmation on mobile | Pages focus app | Approve requires 2 taps; 1-tap test does not execute approve |
| Webhook secret not validated | Telegram Bot (infra setup) | Separate Docker service using polling — webhook surface eliminated |
| python-telegram-bot event loop conflict | Telegram Bot (infra setup) | Bot runs in `telegram-bot` service; FastAPI imports no bot modules |
| PWA service worker caches HTMX partials | Mobile Foundation (if PWA added) | DevTools cache storage shows no dynamic endpoints; `Cache-Control: no-store` on partials |
| Viewport `100vh` clips bottom content on iOS | Mobile Foundation | iPhone device test: no bottom button clipping with keyboard open |
| Bot flood control | Telegram Bot (logging commands) | Log command produces 1 batched message, not N individual messages |

---

## Sources

- Telegram Mini Apps official documentation — `initData` validation algorithm: https://core.telegram.org/bots/webapps
- Telegram Mini Apps community docs — init data HMAC validation: https://docs.telegram-mini-apps.com/platform/init-data
- Security risks in Telegram Mini Apps — nadcab.com blog, 2025
- Claude Code security documentation — command injection CVEs, February 2026: https://code.claude.com/docs/en/security
- Claude Code CLI command injection flaw writeup: https://phoenix.security/critical-ci-cd-nightmare-3-command-injection-flaws-in-claude-code-cli-allow-credential-exfiltration/
- python-telegram-bot event loop pitfalls: https://github.com/python-telegram-bot/python-telegram-bot/discussions/3516
- HTMX `hx-push-url` back button bug on mobile: https://github.com/bigskysoftware/htmx/issues/854
- Telegram iOS viewport height bug (keyboard): https://github.com/TelegramMessenger/Telegram-iOS/issues/1296
- Telegram iOS safe-area-inset support request: https://github.com/TelegramMessenger/Telegram-iOS/issues/1377
- Telegram Mini App deep linking issues across platforms: https://x.com/rickyoffline/status/1837083491927769536
- grammY deployment guide — polling vs webhooks: https://grammy.dev/guide/deployment-types
- Smashing Magazine — managing dangerous actions in UIs: https://www.smashingmagazine.com/2024/09/how-manage-dangerous-actions-user-interfaces/
- Apple HIG touch target minimum: 44×44pt
- Android Material touch target minimum: 48×48dp
- PWA service worker offline pitfalls: https://markaicode.com/progressive-web-app-tutorial-2025-service-worker-offline/
- HTMX offline + service worker: https://github.com/mvolkmann/htmx-offline
- Existing codebase: `app/auth/dependencies.py`, `app/services/subprocess_pdf.py`, `app/routers/sites.py`
- Project constraints: `CLAUDE.md` — JWT exp=24h, Jinja2+HTMX fixed stack, FastAPI 0.115+

---
*Pitfalls research for: SEO Management Platform v4.0 (Mobile Focus Apps + Telegram Bot)*
*Researched: 2026-04-10*
