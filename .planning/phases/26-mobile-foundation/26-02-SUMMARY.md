---
phase: 26-mobile-foundation
plan: "02"
subsystem: auth
tags: [telegram, hmac, jwt, webapp, login-widget, mobile]

requires:
  - phase: 26-mobile-foundation-01
    provides: base_mobile.html template, /m/ router skeleton, telegram_id column on User model, TELEGRAM_BOT_TOKEN/TELEGRAM_BOT_USERNAME in settings

provides:
  - HMAC-SHA256 Telegram WebApp initData validation (app/services/telegram_auth.py)
  - HMAC-SHA256 Telegram Login Widget validation (same module)
  - POST /m/auth/telegram-webapp — public endpoint that issues JWT cookie for Telegram users
  - GET /m/auth/link-required — instruction page for unlinked users
  - GET /profile/link-telegram — Login Widget callback that links telegram_id to user
  - POST /profile/unlink-telegram — removes telegram_id from user
  - Telegram section on desktop profile page with Login Widget embed
  - Auto-auth JS in base_mobile.html that fires on every mobile page load inside Telegram

affects: [26-03, 27-positions-app, 28-digest-app, 29-tasks-app, 30-err-app, 31-pages-app]

tech-stack:
  added: []
  patterns:
    - "Two distinct HMAC-SHA256 key derivation flows: WebApp uses hmac.new(b'WebAppData', bot_token) while Login Widget uses sha256(bot_token).digest()"
    - "Public /m/auth/ prefix excluded from UIAuthMiddleware via startswith check"
    - "Telegram JS auto-auth: fetch initData -> set cookie -> reload; on 404 redirect to /m/auth/link-required"

key-files:
  created:
    - app/services/telegram_auth.py
    - app/templates/mobile/tg_link_required.html
  modified:
    - app/routers/mobile.py
    - app/routers/profile.py
    - app/templates/profile/index.html
    - app/templates/base_mobile.html
    - app/main.py

key-decisions:
  - "On 404 from telegram-webapp endpoint, JS redirects to /m/auth/link-required (not JSON error) for better UX"
  - "Profile template at profile/index.html (not profile.html as plan stated) — adapted to actual file structure"
  - "UIAuthMiddleware skips /m/auth/ via startswith, not by adding each path to PUBLIC_PATHS set"

patterns-established:
  - "Telegram WebApp auth: validate initData -> query User by telegram_id -> issue JWT cookie -> reload page"
  - "Profile template receives telegram_bot_username from settings to control widget visibility"

requirements-completed: [MOB-02]

duration: 5min
completed: 2026-04-10
---

# Phase 26 Plan 02: Telegram WebApp Auth + Login Widget Profile Linking Summary

**HMAC-SHA256 Telegram auth: WebApp initData validation issues JWT cookies for Mini App users; Login Widget on desktop profile links telegram_id to user accounts**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-10T15:17:00Z
- **Completed:** 2026-04-10T15:22:21Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Created `app/services/telegram_auth.py` with both HMAC-SHA256 flows (WebApp and Login Widget), stdlib only
- Added POST `/m/auth/telegram-webapp` (public) and GET `/m/auth/link-required` to mobile router
- Created `app/templates/mobile/tg_link_required.html` instruction screen ("Привяжите Telegram-аккаунт")
- Added auto-auth JS to `base_mobile.html`: fires on every mobile page open inside Telegram WebApp
- Added Telegram section to desktop profile page with Login Widget embed, linked status display, and unlink button

## Task Commits

1. **Task 1: Telegram auth service + WebApp auth endpoint + tg_link_required page** - `1d0ad4e` (feat)
2. **Task 2: Telegram Login Widget on desktop profile page** - `1a4dc5c` (feat)

## Files Created/Modified

- `app/services/telegram_auth.py` — validate_telegram_webapp_initdata + validate_telegram_login_widget (stdlib HMAC)
- `app/routers/mobile.py` — Added POST /m/auth/telegram-webapp and GET /m/auth/link-required (public endpoints)
- `app/templates/mobile/tg_link_required.html` — Instruction page for unlinked Telegram users
- `app/templates/base_mobile.html` — Added telegram-web-app.js script + auto-auth JS block + error banner div
- `app/main.py` — UIAuthMiddleware now skips paths starting with /m/auth/
- `app/routers/profile.py` — Added link-telegram + unlink-telegram endpoints; profile_page passes telegram_bot_username
- `app/templates/profile/index.html` — Telegram section with Login Widget, linked status, tg_linked/tg_unlinked/tg_error banners

## Decisions Made

- On 404 from the telegram-webapp endpoint (user not found), JS redirects to `/m/auth/link-required` for smooth UX rather than showing a JSON error banner.
- The plan referenced `app/templates/profile.html` but the actual file is `app/templates/profile/index.html` — adapted without deviation.
- `UIAuthMiddleware` excludes `/m/auth/` via `path.startswith("/m/auth/")` rather than adding each URL individually to `PUBLIC_PATHS`.

## Deviations from Plan

None — plan executed exactly as written. The template path discrepancy (profile.html vs profile/index.html) was a plan documentation issue, not a deviation.

## Issues Encountered

None.

## User Setup Required

None — no new external service configuration required beyond `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME` added in Plan 01.

## Next Phase Readiness

- Telegram auth foundation is complete: WebApp users auto-authenticate, unlinked users see instruction screen
- Desktop users can link Telegram via Login Widget on profile page
- Plan 03 (PWA + offline) can build on this base — auth flow is fully working
- All mobile phases (27-31) inherit automatic Telegram auth from base_mobile.html

---
*Phase: 26-mobile-foundation*
*Completed: 2026-04-10*
