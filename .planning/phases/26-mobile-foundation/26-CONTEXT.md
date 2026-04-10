# Phase 26: Mobile Foundation - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Touch-friendly mobile interface at `/m/` with bottom navigation, Telegram WebApp authentication, and PWA installation support. This is the foundation layer — all subsequent mobile phases (27–33) depend on it.

**Delivers:**
- `base_mobile.html` — standalone mobile base template (no sidebar)
- `/m/` routing — dedicated mobile endpoints
- Telegram WebApp auth — initData HMAC-SHA256 validation, JWT issuance
- PWA — manifest.json + service worker (shell-only cache)

**Out of scope:**
- Individual mobile apps (digest, positions, traffic) — Phases 27–31
- Telegram Bot as Docker service — Phase 32
- Claude Code Agent — Phase 33
- UI/branding redesign — backlog

</domain>

<decisions>
## Implementation Decisions

### Mobile Layout
- **D-01:** Separate `base_mobile.html` template — completely independent from `base.html`, no sidebar at all. Mobile pages inherit this template, desktop pages continue using `base.html`.
- **D-02:** Bottom navigation with 4 tabs: Дайджест, Сайты, Позиции, Ещё (overflow menu).
- **D-03:** Explicit links for version switching — desktop shows "Мобильная версия" link at bottom, mobile shows "Полная версия" link at top.

### Telegram WebApp Authentication
- **D-04:** Link Telegram ID via profile settings — user logs into desktop, goes to profile, clicks "Привязать Telegram" (Telegram Login Widget). This adds `telegram_id` field to User model.
- **D-05:** Unlinked Telegram ID behavior — show "Привяжите аккаунт" screen with instructions and link to desktop profile. No fallback login form inside WebApp.
- **D-06:** WebApp auth flow — validate `initData` with HMAC-SHA256 using bot token, extract `telegram_id`, look up User, issue standard JWT. After that, user works as a normal authenticated user.

### PWA Configuration
- **D-07:** Shell-only service worker cache — HTML shell, CSS, JS, icons. All data fetched from server. Offline shows "Нет подключения" stub page.
- **D-08:** PWA branding — current platform colors: theme_color `#1e1b4b` (indigo), background `#ffffff`. Use existing favicon/logo as app icon. Splash screen matches these colors.

### Claude's Discretion
- **D-09:** Mobile routing organization — Claude decides whether to use a single `mobile.py` router, per-feature routers, or another pattern. Key constraint: mobile endpoints must call the same service layer as desktop.
- **D-10:** Mobile auth mechanism — Claude decides the optimal approach (shared JWT via cookie, header-based, session, or hybrid). Key constraint: after Telegram WebApp auth issues a token, the user should be indistinguishable from a desktop-authenticated user at the service layer.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Templates & Layout
- `app/templates/base.html` — current desktop base template with sidebar, responsive CSS breakpoints at 1023px and 767px
- `app/templates/login.html` — current login page

### Authentication
- `app/routers/auth.py` — JWT login flow, `create_access_token`, `get_current_user`
- `app/auth/dependencies.py` — `get_current_user` dependency
- `app/auth/jwt.py` — JWT token creation

### Telegram Integration
- `app/services/telegram_service.py` — existing push-only Telegram service (send_message, no WebApp auth)
- `app/models/client.py:63` — `Client.telegram_username` field (reference for naming conventions)

### Project Context
- `.planning/REQUIREMENTS.md` — MOB-01, MOB-02, MOB-03 acceptance criteria
- `.planning/ROADMAP.md` §Phase 26 — success criteria and dependencies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/auth/jwt.py` — JWT creation, can be reused for Telegram WebApp token issuance
- `app/auth/dependencies.py` — `get_current_user` dependency, mobile routes can use as-is after auth
- `app/services/telegram_service.py` — bot token already in settings, reuse for HMAC validation
- `app/config.py` — `settings.TELEGRAM_BOT_TOKEN` already configured

### Established Patterns
- All routers in `app/routers/` use `APIRouter` with prefix, `Depends(get_current_user)`
- Templates use Jinja2 inheritance from `base.html`
- HTMX 2.0 for partial updates (CDN loaded)
- Tailwind CSS via CDN

### Integration Points
- New `telegram_id` column needed on User model (Alembic migration)
- New profile section for Telegram linking (extends existing `app/routers/profile.py`)
- New `/m/` router(s) registered in `app/main.py`
- `manifest.json` + `service-worker.js` in `app/static/`
- `base_mobile.html` in `app/templates/`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

- **UI/branding redesign** — user не доволен текущей цветовой схемой (indigo). Нужно исследовать варианты улучшения внешнего вида. Добавить в бэклог.

</deferred>

---

*Phase: 26-mobile-foundation*
*Context gathered: 2026-04-10*
