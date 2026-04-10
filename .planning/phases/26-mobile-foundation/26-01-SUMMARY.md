---
phase: 26-mobile-foundation
plan: "01"
subsystem: mobile
tags: [mobile, pwa, routing, templates, alembic, auth]
dependency_graph:
  requires: []
  provides:
    - base_mobile.html (standalone mobile base template with bottom nav)
    - /m/ routing (UIAuthMiddleware-protected mobile router)
    - telegram_id column on users (migration 0051)
    - TELEGRAM_BOT_USERNAME config setting
  affects:
    - app/main.py (UIAuthMiddleware now protects /m/ paths)
    - app/models/user.py (new telegram_id field)
    - app/templates/base.html (Мобильная версия footer link added)
tech_stack:
  added: []
  patterns:
    - Plain Jinja2Templates for mobile routes (no sidebar injection)
    - Depends(get_current_user) on all mobile endpoints (not UIAuthMiddleware alone)
    - Standalone offline.html (no template inheritance — required for SW cache)
key_files:
  created:
    - app/templates/base_mobile.html
    - app/templates/mobile/index.html
    - app/templates/mobile/offline.html
    - app/routers/mobile.py
    - alembic/versions/0051_add_telegram_id_to_users.py
  modified:
    - app/models/user.py
    - app/config.py
    - app/main.py
    - app/templates/base.html
decisions:
  - "Separate base_mobile.html (not extending base.html) so mobile pages have no sidebar and load fast on mobile"
  - "Plain Jinja2Templates instance in mobile.py — nav-aware wrapper from template_engine.py not used for mobile"
  - "Both UIAuthMiddleware and Depends(get_current_user) protect /m/ — defence in depth"
  - "offline.html is standalone HTML (no Jinja2 inheritance) — required for service worker offline cache"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 4
---

# Phase 26 Plan 01: Mobile Foundation Summary

**One-liner:** Standalone `base_mobile.html` with bottom nav + `/m/` FastAPI router + `telegram_id` DB column + Alembic migration 0051.

## What Was Built

### Task 1: DB migration, config, User model update
- Added `telegram_id: Mapped[int | None]` (BigInteger, nullable, unique, indexed) to `User` model
- Added `BigInteger` import to `app/models/user.py`
- Added `TELEGRAM_BOT_USERNAME: str = ""` to `app/config.py` Settings
- Created `alembic/versions/0051_add_telegram_id_to_users.py` with correct `down_revision = "0050"`, proper upgrade/downgrade

**Commit:** `8587ff0`

### Task 2: base_mobile.html, mobile pages, /m/ router, main.py registration
- Created `app/templates/base_mobile.html` — standalone (does NOT extend base.html):
  - `viewport-fit=cover`, `theme-color=#1e1b4b`, PWA manifest link, apple-touch-icon
  - Version-switch strip: "Полная версия" link to `/ui/dashboard`
  - Bottom nav: fixed 64px, `#1e1b4b`, 4 tabs (Дайджест, Сайты, Позиции, Ещё) with SVG icons
  - Active tab via `active_tab` Jinja2 variable, accent color `#818cf8` (indigo-400)
  - `env(safe-area-inset-bottom)` padding for iPhone X+ safe area
  - Toast container offset above nav bar (bottom: 80px)
  - Service worker registration script
  - `{% block telegram_auth %}{% endblock %}` for Plan 02 TG auth
- Created `app/templates/mobile/index.html` extending `base_mobile.html`:
  - Site selector dropdown (full-width, `#eef2ff` bg, `#c7d2fe` border)
  - Quick-link cards for future phases (disabled/greyed except Позиции)
  - Empty state: "Нет подключённых сайтов" heading + instructional body
- Created `app/templates/mobile/offline.html` — standalone HTML (no Jinja2 inheritance)
  - White background, centered wifi-off SVG, "Нет подключения" heading
  - No JS, no CDN loads — fully offline renderable
- Created `app/routers/mobile.py`:
  - `APIRouter(prefix="/m")` with plain `Jinja2Templates` (not nav-aware)
  - `GET /m/` with `Depends(get_current_user)` + `Depends(get_db)`
  - Queries `get_sites(db)` and renders `mobile/index.html`
- Updated `app/main.py`:
  - `UIAuthMiddleware` now protects both `/ui/` and `/m/` paths
  - `/auth/telegram-webapp` added to `PUBLIC_PATHS`
  - `mobile_router` imported and registered
  - "Мобильная версия" footer link added to `base.html`

**Commit:** `69281b1`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- Quick-link cards in `mobile/index.html` for Здоровье сайта, Трафик, Отчёт клиенту are disabled placeholders (opacity 0.5, cursor not-allowed). These are intentional — the corresponding apps (Phases 28–30) will activate them. Goal of Phase 26 is the foundation shell, not full app functionality.
- `static/service-worker.js`, `static/manifest.json`, and `static/icons/` are referenced but created in Plan 26-03 (PWA support files). The `/m/` page loads without errors if these files are absent — SW registration is wrapped in `if ('serviceWorker' in navigator)`.

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits verified in git log.
