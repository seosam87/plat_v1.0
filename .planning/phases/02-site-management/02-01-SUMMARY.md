---
phase: 02-site-management
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, fernet, fastapi, postgresql, encryption]

requires:
  - phase: 01-stack-auth
    provides: User model, auth dependencies (require_admin), audit_service.log_action, DB session, JWT

provides:
  - Site SQLAlchemy model with ConnectionStatus enum
  - Fernet-based CryptoService (encrypt/decrypt) for WP Application Passwords
  - Alembic migration 0003 — sites table with all 9 columns
  - SiteService: create/update/delete/get_sites/get_site/set_connection_status/get_decrypted_password
  - Admin-only CRUD router at /sites (POST/GET/PUT/DELETE)

affects:
  - 02-02 (WP REST verify + UI)
  - 02-03 (enable/disable + Celery guard + WP CRUD)
  - All subsequent phases that read/write Site rows

tech-stack:
  added: [cryptography>=42 (Fernet)]
  patterns:
    - Fernet encryption via CryptoService — never store plain WP passwords; always encrypt on write, decrypt on use
    - Service layer holds all DB logic; routers call services only
    - SiteOut response schema omits encrypted_app_password and app_password fields
    - Audit log entry on every site create/update/delete

key-files:
  created:
    - app/models/site.py
    - app/services/crypto_service.py
    - app/services/site_service.py
    - app/routers/sites.py
    - alembic/versions/0003_add_sites_table.py
    - tests/test_sites.py
    - tests/test_crypto_service.py
  modified:
    - app/config.py (FERNET_KEY field)
    - app/main.py (include sites_router)
    - alembic/env.py (import Site model)
    - .env.example (FERNET_KEY placeholder)

key-decisions:
  - "encrypted_app_password stored as Fernet token (URL-safe base64 text) — non-deterministic, decrypt only at call time"
  - "SiteOut response model never exposes encrypted_app_password or raw app_password"
  - "url.rstrip('/') normalised on create/update to avoid duplicate-URL issues"
  - "FERNET_KEY added to Settings as required field (no default) — deploy fails fast if key missing"

requirements-completed: [SITE-01, SITE-03, SEC-02]

duration: 6min
completed: 2026-04-01
---

# Phase 02 Plan 01: Site Model + Crypto Service + Migration + CRUD Summary

**Fernet-encrypted Site model with admin CRUD endpoints — WP Application Passwords never persist in plain text**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-01T06:46:42Z
- **Completed:** 2026-04-01T06:52:48Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Site SQLAlchemy model with 9 columns (id, name, url, wp_username, encrypted_app_password, connection_status, is_active, created_at, updated_at)
- Fernet CryptoService: non-deterministic encrypt/decrypt, round-trip verified, key loaded from FERNET_KEY env var
- Alembic migration 0003: sites table + connectionstatus enum type + ix_sites_url unique index
- Admin-only CRUD API (/sites POST/GET/PUT/DELETE) with audit logging; SiteOut never exposes passwords
- 7 tests pass (4 CRUD + auth tests, 3 crypto unit tests)

## Task Commits

1. **Test: crypto failing tests** - `60b6c8f` (test — TDD RED)
2. **Task 1: Site model + Fernet crypto service + config** - `e0a0c78` (feat — TDD GREEN)
3. **Task 2: Alembic migration — sites table** - `dd90e01` (feat)
4. **Test: site CRUD failing tests** - `2d4627d` (test — TDD RED)
5. **Task 3: Site service + admin CRUD router + wire to main** - `063da06` (feat — TDD GREEN)

## Files Created/Modified

- `app/models/site.py` — Site model with ConnectionStatus enum
- `app/services/crypto_service.py` — Fernet encrypt/decrypt functions
- `app/services/site_service.py` — CRUD service layer with audit logging
- `app/routers/sites.py` — FastAPI router with SiteCreate/SiteUpdate/SiteOut schemas
- `alembic/versions/0003_add_sites_table.py` — DB migration (revision 0002→0003)
- `alembic/env.py` — added Site model import for autogenerate
- `app/config.py` — FERNET_KEY field added to Settings
- `app/main.py` — sites_router included
- `.env.example` — FERNET_KEY placeholder
- `tests/test_sites.py` — 4 tests (create, 403, list, delete)
- `tests/test_crypto_service.py` — 3 crypto unit tests

## Decisions Made

- Fernet token stored as Text (URL-safe base64 string) — keeps column type simple, decodes at call time only
- `url.rstrip('/')` normalisation on create/update prevents duplicate-URL bugs downstream
- `FERNET_KEY` has no default — Settings validation fails fast if key is missing from environment
- `get_decrypted_password()` lives in service layer, never in router — routers never touch raw passwords

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Docker container required explicit restart (`docker compose up -d api`) to pick up new FERNET_KEY env var from .env — `restart` command alone did not reload env_file. Non-blocking, resolved immediately.
- `alembic/versions/` and `tests/` directories are not volume-mounted in docker-compose.yml — migration and test files were copied into the running container via `docker cp` for the current session. Files are committed to git and will be included in the next image build.

## Next Phase Readiness

- Site model and CRUD API are ready. Plan 02-02 can implement WP REST verification and the Jinja2/HTMX UI.
- `site_service.get_decrypted_password()` is the canonical way to retrieve WP credentials — 02-02 and 02-03 should use this.
- Migration 0003 is applied to the running dev DB.

---
*Phase: 02-site-management*
*Completed: 2026-04-01*
