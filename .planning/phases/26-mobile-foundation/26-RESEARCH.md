# Phase 26: Mobile Foundation - Research

**Researched:** 2026-04-10
**Domain:** Mobile web UI (bottom nav + Jinja2), Telegram WebApp auth, PWA (manifest + service worker)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Separate `base_mobile.html` template — completely independent from `base.html`, no sidebar at all. Mobile pages inherit this template, desktop pages continue using `base.html`.
- **D-02:** Bottom navigation with 4 tabs: Дайджест, Сайты, Позиции, Ещё (overflow menu).
- **D-03:** Explicit links for version switching — desktop shows "Мобильная версия" link at bottom, mobile shows "Полная версия" link at top.
- **D-04:** Link Telegram ID via profile settings — user logs into desktop, goes to profile, clicks "Привязать Telegram" (Telegram Login Widget). This adds `telegram_id` field to User model.
- **D-05:** Unlinked Telegram ID behavior — show "Привяжите аккаунт" screen with instructions and link to desktop profile. No fallback login form inside WebApp.
- **D-06:** WebApp auth flow — validate `initData` with HMAC-SHA256 using bot token, extract `telegram_id`, look up User, issue standard JWT. After that, user works as a normal authenticated user.
- **D-07:** Shell-only service worker cache — HTML shell, CSS, JS, icons. All data fetched from server. Offline shows "Нет подключения" stub page.
- **D-08:** PWA branding — theme_color `#1e1b4b` (indigo), background `#ffffff`. Use existing favicon/logo as app icon. Splash screen matches these colors.

### Claude's Discretion

- **D-09:** Mobile routing organization — Claude decides whether to use a single `mobile.py` router, per-feature routers, or another pattern. Key constraint: mobile endpoints must call the same service layer as desktop.
- **D-10:** Mobile auth mechanism — Claude decides the optimal approach. Key constraint: after Telegram WebApp auth issues a token, the user should be indistinguishable from a desktop-authenticated user at the service layer.

### Deferred Ideas (OUT OF SCOPE)

- UI/branding redesign — user не доволен текущей цветовой схемой (indigo). Добавить в бэклог.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MOB-01 | Пользователь может открыть `/m/` на мобильном и видеть touch-friendly layout с bottom navigation (без sidebar) | `base_mobile.html` + `/m/` router + Tailwind CSS bottom nav pattern |
| MOB-02 | Пользователь может открыть приложение через Telegram WebApp и автоматически авторизоваться через Telegram ID (initData HMAC-SHA256 валидация) | Telegram WebApp JS SDK + Python HMAC-SHA256 stdlib + existing JWT/cookie auth |
| MOB-03 | Мобильное приложение можно установить на домашний экран как PWA (manifest.json + service worker) | W3C Web App Manifest + Cache API shell pattern |

</phase_requirements>

---

## Summary

Phase 26 builds three independent subsystems that together form the mobile foundation: (1) a standalone mobile template with bottom navigation, (2) Telegram WebApp authentication, and (3) PWA installation support. Each subsystem has a clear integration point with the existing codebase and requires no new third-party Python packages.

The mobile template (`base_mobile.html`) is a clean-room Jinja2 template that does NOT extend `base.html`. It uses the same Tailwind CSS CDN already loaded in `base.html` and has a fixed bottom nav bar with 4 tabs (D-02). The `/m/` router pattern follows the exact same `APIRouter` convention as all other 40+ existing routers and calls the same service layer. Authentication is unchanged: `get_current_user` from `app/auth/dependencies.py` works as-is since it already reads the JWT from the cookie.

Telegram WebApp authentication uses Python's stdlib `hmac` + `hashlib` modules (already available — no new dependencies). The `TELEGRAM_BOT_TOKEN` is already in `settings`. The flow validates `initData` server-side, looks up the user by `telegram_id` (new column on `users`), and issues a standard JWT cookie — making the Telegram-authenticated user identical to a password-authenticated user from the service layer's perspective.

PWA support requires two static files: `app/static/manifest.json` and `app/static/service-worker.js`. The manifest is served as a plain JSON static file; the service worker is registered via `<script>` in `base_mobile.html`. No new Python packages or Celery tasks are needed.

**Primary recommendation:** Single `app/routers/mobile.py` router with prefix `/m/`, one Alembic migration for `telegram_id` on `users`, two static files for PWA, and one new template `base_mobile.html`. Total new Python code under 200 lines.

---

## Standard Stack

### Core (no new packages required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `hashlib` + `hmac` | stdlib | Telegram initData HMAC-SHA256 validation | Already available; Telegram docs use exactly HMAC_SHA256 with stdlib |
| `app/auth/jwt.py` | existing | JWT issuance for Telegram WebApp auth | `create_access_token(user_id, role)` already handles token creation |
| `app/auth/dependencies.py` | existing | `get_current_user` dependency | Already reads JWT from cookie OR Authorization header — mobile works as-is |
| Tailwind CSS 3.x (CDN) | CDN (same as `base.html`) | Mobile layout + bottom nav styling | Already loaded project-wide; no new CSS framework |
| HTMX 2.0.3 (CDN) | CDN (same as `base.html`) | Partial updates in mobile pages | Already loaded; use `hx-boost` and `hx-get` patterns as in desktop |
| Jinja2 3.1.x | existing | `base_mobile.html` templating | Same `templates` engine from `app/template_engine.py` |

### Supporting (new static files only)

| Asset | Location | Purpose |
|-------|----------|---------|
| `manifest.json` | `app/static/manifest.json` | PWA installability — served as static file |
| `service-worker.js` | `app/static/service-worker.js` | Shell caching + offline stub |
| PWA icons | `app/static/icons/` | 192x192 + 512x512 PNG icons for PWA |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `hmac`/`hashlib` | `telegram-init-data` PyPI package | Package adds a dependency for 15 lines of stdlib code — not worth it |
| Single `mobile.py` router | Per-feature mobile routers | Per-feature makes sense for phases 27–31 when content grows; Phase 26 only needs `/m/` index + telegram-auth endpoint |
| Cookie-based JWT (same as desktop) | Header-based JWT | Cookie approach means the same `UIAuthMiddleware` and `get_current_user` work unchanged; header requires mobile-specific auth middleware |

**Installation:** No new packages needed. The existing `requirements.txt` (or equivalent) already has all dependencies for this phase.

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
app/
├── routers/
│   └── mobile.py              # NEW: /m/ prefix router, all mobile endpoints
├── templates/
│   ├── base_mobile.html       # NEW: standalone mobile base template
│   └── mobile/
│       ├── index.html         # NEW: /m/ homepage (bottom nav, placeholder content)
│       └── tg_link_required.html  # NEW: "Привяжите аккаунт" screen
├── static/
│   ├── manifest.json          # NEW: PWA manifest
│   ├── service-worker.js      # NEW: shell cache service worker
│   └── icons/
│       ├── icon-192.png       # NEW: PWA icon
│       └── icon-512.png       # NEW: PWA icon

alembic/versions/
└── 0051_add_telegram_id_to_users.py  # NEW: migration
```

### Pattern 1: `base_mobile.html` — Standalone Mobile Template

**What:** A complete HTML document (NOT extending `base.html`) with bottom navigation. Defines `{% block content %}` for page content and `{% block title %}`.

**When to use:** Every `/m/` endpoint renders a template that does `{% extends "base_mobile.html" %}`.

**Critical requirement:** `base_mobile.html` must include `<link rel="manifest" href="/static/manifest.json">` and the service worker registration script. It must NOT include the sidebar, hamburger button, or server log panel from `base.html`.

**Example:**
```html
{# Source: W3C Web App Manifest spec + existing base.html patterns #}
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="theme-color" content="#1e1b4b">
  <link rel="manifest" href="/static/manifest.json">
  <title>{% block title %}SEO Platform{% endblock %}</title>
  <script src="https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; padding: 0;
           padding-bottom: 64px; /* space for bottom nav */ }
    .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0;
                  height: 64px; background: #1e1b4b; z-index: 50;
                  display: flex; justify-content: space-around; align-items: center;
                  padding-bottom: env(safe-area-inset-bottom); }
  </style>
</head>
<body>
  {# "Full version" link at top per D-03 #}
  <div class="text-xs text-center py-1 bg-gray-100 text-gray-500">
    <a href="/ui/dashboard" class="underline">Полная версия</a>
  </div>

  <main class="p-4">
    {% block content %}{% endblock %}
  </main>

  <nav class="bottom-nav">
    <a href="/m/" class="flex flex-col items-center text-white text-xs gap-1">
      <!-- Дайджест icon + label -->
    </a>
    <a href="/m/sites" class="flex flex-col items-center text-white text-xs gap-1">
      <!-- Сайты -->
    </a>
    <a href="/m/positions" class="flex flex-col items-center text-white text-xs gap-1">
      <!-- Позиции -->
    </a>
    <button class="flex flex-col items-center text-white text-xs gap-1">
      <!-- Ещё (overflow) -->
    </button>
  </nav>

  <script>
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/static/service-worker.js');
    }
  </script>
</body>
</html>
```

### Pattern 2: `/m/` Router (`app/routers/mobile.py`)

**What:** Single `APIRouter(prefix="/m", tags=["mobile"])` with all Phase 26 endpoints. Calls same service layer as desktop routers.

**When to use:** All mobile-specific UI routes.

**Key endpoints for Phase 26:**
- `GET /m/` — mobile homepage (renders `mobile/index.html` with `base_mobile.html`)
- `POST /auth/telegram-webapp` — initData validation, returns JWT (no `/m/` prefix, lives in `auth.py` or new `app/routers/mobile_auth.py`)
- `GET /m/auth/telegram-callback` — Telegram Login Widget callback for profile linking
- `POST /profile/link-telegram` — saves `telegram_id` to User record

**Note on D-09 (Claude's discretion):** Use a single `mobile.py` for Phase 26. Phases 27–31 will each add their own mobile router (e.g., `mobile_digest.py`, `mobile_positions.py`) following the same per-feature pattern as desktop.

**Note on D-10 (Claude's discretion):** Use cookie-based JWT (same as desktop). After `POST /auth/telegram-webapp` validates initData and issues a JWT, set `access_token` cookie (same name as desktop). The existing `UIAuthMiddleware` in `main.py` only guards `/ui/*` paths — `/m/*` paths are NOT under `/ui/`, so they need their own guard. Two options:

Option A (recommended): Add `/m/` prefix to `UIAuthMiddleware` check. The existing middleware already handles cookie JWT validation — extending `PUBLIC_PATHS` check to also handle `/m/` redirect logic keeps auth in one place.

Option B: Add `Depends(get_current_user)` on every mobile endpoint directly. More explicit, less coupling to middleware. Fine for Phase 26's small surface.

**Recommendation:** Option B for Phase 26 — explicit `Depends(get_current_user)` per endpoint. Matches ALL existing router patterns. The `/m/auth/` endpoints are explicitly excluded from auth requirement.

### Pattern 3: Telegram WebApp Authentication

**Two separate flows exist (both required by D-04 and D-06):**

**Flow A — Telegram Login Widget (for profile page, desktop, D-04):**
- Desktop profile page embeds Telegram Login Widget script
- On click, widget sends user back to `data-auth-url` with query params: `id`, `first_name`, `last_name`, `username`, `photo_url`, `auth_date`, `hash`
- Backend validates using **SHA256(bot_token)** as HMAC key (NOT "WebAppData")
- Saves `telegram_id` to `User.telegram_id`

**Flow B — Telegram WebApp initData (for Mini App, D-06):**
- JavaScript: `window.Telegram.WebApp.initData` string is POSTed to backend
- Backend validates using **HMAC_SHA256(bot_token, "WebAppData")** as secret key
- Extracts `telegram_id` from `user` JSON field in initData
- Looks up User by `telegram_id`, issues JWT cookie

**Critical distinction:** Flow A (Login Widget) uses `secret_key = SHA256(bot_token)`. Flow B (Mini App) uses `secret_key = HMAC_SHA256(bot_token, key="WebAppData")`. Different algorithms for different Telegram auth methods.

**Python implementation (no new packages, stdlib only):**

```python
# Source: https://core.telegram.org/bots/webapps (official Telegram docs)
import hashlib
import hmac
import urllib.parse
import json
import time

def validate_telegram_webapp_initdata(init_data: str, bot_token: str) -> dict | None:
    """Validate Telegram WebApp initData. Returns parsed user dict or None if invalid."""
    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

    # Build data-check-string: all fields sorted alphabetically, key=value\n
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # Secret key: HMAC_SHA256(bot_token, "WebAppData")
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    # Check auth_date is recent (prevent replay attacks — 1 hour window)
    auth_date = int(params.get("auth_date", 0))
    if time.time() - auth_date > 3600:
        return None

    user_json = params.get("user", "{}")
    return json.loads(user_json)


def validate_telegram_login_widget(data: dict, bot_token: str) -> bool:
    """Validate Telegram Login Widget callback data."""
    received_hash = data.pop("hash", None)
    if not received_hash:
        return False

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )

    # Secret key: SHA256(bot_token)  — NOTE: different from WebApp flow
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(computed_hash, received_hash)
```

### Pattern 4: PWA Manifest and Service Worker

**`app/static/manifest.json`:**
```json
{
  "name": "SEO Platform",
  "short_name": "SEO",
  "start_url": "/m/",
  "display": "standalone",
  "theme_color": "#1e1b4b",
  "background_color": "#ffffff",
  "icons": [
    { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

**`app/static/service-worker.js` (shell-only cache, D-07):**
```javascript
// Source: MDN Service Worker API + W3C Cache API spec
const CACHE_NAME = 'seo-shell-v1';
const SHELL_ASSETS = [
  '/m/',
  '/static/manifest.json',
  '/static/service-worker.js',
  // Tailwind and HTMX are CDN — not cached in shell (they have their own CDN cache)
  // Add /static/icons/icon-192.png, /static/icons/icon-512.png
];

// Install: cache shell assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: cache-first for shell, network-first for everything else
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (SHELL_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then(r => r || fetch(event.request))
    );
    return;
  }
  // For data requests (API, /m/ pages): network first, offline fallback
  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match('/m/offline') || new Response('Нет подключения', {status: 503})
    )
  );
});
```

### Pattern 5: Alembic Migration for `telegram_id`

```python
# 0051_add_telegram_id_to_users.py
# Source: existing migration pattern in alembic/versions/
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    op.add_column('users',
        sa.Column('telegram_id', sa.BigInteger(), nullable=True, unique=True, index=True)
    )

def downgrade() -> None:
    op.drop_column('users', 'telegram_id')
```

**Why `BigInteger`:** Telegram user IDs are 64-bit integers. Python `int` handles them, but the DB column must be BIGINT not INT.

### Anti-Patterns to Avoid

- **Extending `base.html` for mobile:** Would inherit sidebar CSS, log panel, navigation context injection from `_NavAwareTemplates`. Use completely separate template.
- **Using `template_engine.templates` (the nav-injecting wrapper) for mobile pages:** `_NavAwareTemplates.TemplateResponse` injects sidebar sections and nav context that mobile templates don't need. For mobile routes, create a separate plain `Jinja2Templates("app/templates")` instance or call `_jinja_templates` directly.
- **Storing Telegram token in form state or localStorage:** JWT must be in `httpOnly` cookie (same as desktop). Do NOT use localStorage — XSS risk.
- **Skipping `hmac.compare_digest`:** Use timing-safe comparison. Plain `==` is vulnerable to timing attacks on hash comparison.
- **Using `initDataUnsafe` instead of `initData`:** `window.Telegram.WebApp.initDataUnsafe` is a pre-parsed JS object. Send the raw `initData` string to the backend for validation — that's what the hash covers.
- **Forgetting `auth_date` replay check:** An old but valid `initData` can be replayed. Always check `time.time() - auth_date < threshold`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC-SHA256 | Custom crypto | Python `hmac` + `hashlib` stdlib | Timing-safe `compare_digest` included; no deps |
| JWT for Telegram user | New token system | Existing `create_access_token(user_id, role)` in `app/auth/jwt.py` | Identical token, same expiry, same middleware |
| Offline detection | Custom network monitor | Service worker `fetch` event `.catch()` | Browser handles this natively via SW |
| Icon generation | Manual PNG creation | Generate from existing favicon/logo | Two sizes needed: 192x192, 512x512 |
| Cookie auth for `/m/` | Custom mobile session | Existing `get_current_user` + same cookie name | `dependencies.py` already reads from cookie |

**Key insight:** The existing auth infrastructure (JWT, cookie, `get_current_user`) is generic enough that mobile gets it for free. The only new code needed is the `telegram_id` lookup path.

---

## Common Pitfalls

### Pitfall 1: Wrong HMAC Key for Telegram Auth Methods
**What goes wrong:** Using `HMAC_SHA256(bot_token, "WebAppData")` for Login Widget validation (which requires `SHA256(bot_token)`), or vice versa. Silent validation failure — every auth attempt returns 401.
**Why it happens:** Two different Telegram auth methods have different key derivation. Easy to confuse.
**How to avoid:** Implement as two separate functions with explicit names: `validate_telegram_webapp_initdata()` and `validate_telegram_login_widget()`.
**Warning signs:** Validation always fails even with correct bot token.

### Pitfall 2: `telegram_id` Not in User Model at Alembic Time
**What goes wrong:** `mobile.py` imports `User.telegram_id` but migration hasn't run. Runtime `AttributeError` or SQLAlchemy query failure.
**Why it happens:** `alembic/env.py` must import `User` from `app/models/user.py` — if the column is added to the ORM class before the migration is applied, the app starts fine but DB has no column.
**How to avoid:** Add migration as Wave 0 task. Gate all `telegram_id` queries behind a Wave 1+ task.

### Pitfall 3: `UIAuthMiddleware` Does Not Protect `/m/` Routes
**What goes wrong:** Mobile pages at `/m/` are accessible without authentication because the middleware only checks `if not path.startswith("/ui")`.
**Why it happens:** Mobile path prefix is `/m/`, not `/ui/`.
**How to avoid:** Use `Depends(get_current_user)` on every mobile endpoint (Pattern 2, Option B). The explicit dependency is simpler than middleware extension for Phase 26's small surface.
**Warning signs:** Hitting `/m/` without a cookie returns 200 instead of redirect to login.

### Pitfall 4: CDN Resources Not Cached by Service Worker
**What goes wrong:** Service worker tries to cache CDN URLs for Tailwind/HTMX, fails due to CORS or opaque responses.
**Why it happens:** Cross-origin requests from service workers return opaque responses; `cache.addAll()` on opaque responses fails silently or stores bad data.
**How to avoid:** Do NOT include CDN URLs in `SHELL_ASSETS`. Tailwind CDN and HTMX CDN have their own HTTP cache. Only cache same-origin static files.

### Pitfall 5: iOS Safari PWA Requires `apple-touch-icon` Meta Tag
**What goes wrong:** On iOS, "Add to Home Screen" shows a blank icon or screenshot instead of the PWA icon.
**Why it happens:** iOS Safari ignores `manifest.json` icons for home screen thumbnails; requires `<link rel="apple-touch-icon">` in `<head>`.
**How to avoid:** Add `<link rel="apple-touch-icon" href="/static/icons/icon-192.png">` to `base_mobile.html`. This is the iOS-specific workaround.

### Pitfall 6: Telegram WebApp Requires HTTPS in Production
**What goes wrong:** `window.Telegram.WebApp.initData` is empty string on non-HTTPS origins.
**Why it happens:** Telegram WebApp JS SDK is served only to pages loaded inside Telegram's WebView, which only allows HTTPS mini apps in production.
**How to avoid:** For local dev, use Telegram's test environment or ngrok. Document this in Wave 0 setup notes.

### Pitfall 7: `safe-area-inset-bottom` for iPhone Notch
**What goes wrong:** Bottom navigation bar on iPhone X+ is obscured by the home indicator gesture area.
**Why it happens:** `position: fixed; bottom: 0` does not account for iPhone's safe area.
**How to avoid:** Add `padding-bottom: env(safe-area-inset-bottom)` to `.bottom-nav` and `viewport-fit=cover` to the viewport meta tag. Example is already in Pattern 1 above.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service worker required for PWA install prompt | Manifest alone triggers install prompt (Chrome/Edge) | 2023+ | Service worker still needed for offline; no longer mandatory for install prompt |
| `window.Telegram.WebApp.sendData()` for auth | POST `initData` to backend endpoint | Always was this way | `sendData` is for bots, not auth flows |
| `APScheduler` for periodic tasks | Celery Beat + redbeat | Project standard | Not relevant here; no periodic tasks in Phase 26 |

**No deprecated patterns in Phase 26 scope.**

---

## Open Questions

1. **Telegram Bot username for Login Widget**
   - What we know: `settings.TELEGRAM_BOT_TOKEN` is configured; the token encodes the bot ID but not the username.
   - What's unclear: The Login Widget `<script>` tag requires `data-telegram-login="bot_username"`. The username must be known at template render time.
   - Recommendation: Add `TELEGRAM_BOT_USERNAME: str = ""` to `app/config.py` as a new settings field. The planner should include a Wave 0 task to add this setting and document it.

2. **Icon assets: convert existing favicon or create new ones?**
   - What we know: `app/static/` has no existing `icons/` directory. The platform uses favicon from `base.html` (not explicitly listed in static files).
   - What's unclear: Whether a 192x192 and 512x512 PNG already exists.
   - Recommendation: The planner should include a task to create/verify PWA icons. If existing favicon is SVG/ICO, convert to PNG at required sizes.

3. **`_NavAwareTemplates` wrapper for mobile templates**
   - What we know: All existing routers use `from app.template_engine import templates` which injects sidebar/nav context. Mobile templates don't need sidebar sections.
   - What's unclear: Whether injecting unused sidebar context has any harmful side effects.
   - Recommendation: For `/m/` routes, use a separate plain `Jinja2Templates(directory="app/templates")` instance to avoid nav context injection overhead. This avoids a subtle bug where `nav_sections` cookie logic (which reads `selected_site_id`) could interfere with mobile page rendering. Create `app/template_engine.py` addition: `mobile_templates = Jinja2Templates(directory="app/templates")` as a plain instance.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib `hmac`/`hashlib` | Telegram HMAC validation | Yes | stdlib | — |
| `python-jose` | JWT issuance | Yes | (installed) | — |
| Tailwind CSS | Mobile layout | Yes (CDN) | 3.x via CDN | — |
| HTMX 2.0.3 | Partial updates | Yes (CDN) | 2.0.3 via CDN | — |
| Alembic | DB migration for `telegram_id` | Yes | (installed) | — |
| `settings.TELEGRAM_BOT_TOKEN` | Telegram WebApp auth | Configured (empty string fallback) | — | Feature-flag: if empty, disable TG auth endpoint |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- `TELEGRAM_BOT_USERNAME` not in settings yet — add as new optional config field. Without it, Login Widget cannot render.

---

## Sources

### Primary (HIGH confidence)
- [Telegram Mini Apps official docs](https://core.telegram.org/bots/webapps) — initData validation algorithm, user object structure, HMAC-SHA256 with "WebAppData" key
- [Telegram Login Widget official docs](https://core.telegram.org/widgets/login) — Login Widget HTML integration, SHA256(bot_token) validation algorithm
- Existing codebase — `app/auth/dependencies.py`, `app/auth/jwt.py`, `app/config.py`, `app/main.py` (all read directly)

### Secondary (MEDIUM confidence)
- [W3C Web App Manifest](https://web.dev/learn/pwa/web-app-manifest) — manifest.json field requirements, icon sizes
- [Flowbite Tailwind Bottom Navigation](https://flowbite.com/docs/components/bottom-navigation/) — bottom nav CSS pattern with Tailwind
- [PWA best practices 2025](https://blog.madrigan.com/en/blog/202601041306/) — service worker caching strategies, app shell architecture

### Tertiary (LOW confidence — needs implementation validation)
- iOS Safari `apple-touch-icon` requirement for home screen icons — widely documented but should be tested on actual iOS device

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing libraries confirmed
- Architecture: HIGH — based on direct codebase reading and official Telegram docs
- Pitfalls: HIGH for auth (official docs), MEDIUM for iOS Safari workaround (widely known but not officially tested in this setup)

**Research date:** 2026-04-10
**Valid until:** 2026-07-10 (Telegram WebApp API is stable; PWA specs are stable)
