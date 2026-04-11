---
phase: 29-reports-tools
plan: "01"
subsystem: ui
tags: [mobile, htmx, jinja2, redis, pdf, telegram, smtp, fastapi]

requires:
  - phase: 28-positions-traffic
    provides: mobile router pattern, position_progress.html polling partial, showToast JS, base_mobile.html
  - phase: 14-client-instructions-pdf
    provides: report_service.generate_pdf_report (WeasyPrint subprocess isolation)
  - phase: 17-in-app-notifications
    provides: smtp_service.send_email_with_attachment_sync
  - phase: existing
    provides: telegram_service.send_message_sync, client_service list_clients, project_service.get_accessible_projects

provides:
  - /m/reports/new GET+POST — mobile single-page report creation form
  - /m/reports/download/{token} GET — token-protected PDF streaming (Redis-backed, 7-day TTL)
  - /m/reports/{token}/send/telegram POST — link-based Telegram delivery
  - /m/reports/{token}/send/email POST — PDF attachment email delivery
  - mobile_reports_service.py — list_clients_for_reports, store_report_pdf, load_report_pdf, build_download_url
  - APP_BASE_URL settings field for absolute URL construction

affects:
  - 29-02-tools-mobile (uses same mobile router pattern)
  - 29-03-uat-fixes (verify these endpoints work end-to-end)

tech-stack:
  added: []
  patterns:
    - "Redis binary storage (no decode_responses) for PDF bytes under reports:dl:{token} key prefix"
    - "Token-as-auth pattern: secrets.token_urlsafe(32) stored in Redis, 7-day TTL, no session required for download"
    - "HTMX inline result reveal: POST returns partial template injected into #result-slot via hx-swap=innerHTML"
    - "Lazy service imports inside FastAPI handlers to avoid circular imports"
    - "build_download_url uses /m/ prefix (router prefix included in path)"

key-files:
  created:
    - app/services/mobile_reports_service.py
    - app/templates/mobile/reports/new.html
    - app/templates/mobile/reports/partials/result_block.html
  modified:
    - app/config.py (APP_BASE_URL field added)
    - app/routers/mobile.py (5 new endpoints appended)

key-decisions:
  - "D-03: Single-page form — no multi-step wizard. Project select + 2 radio-cards + submit on one page."
  - "D-06: Telegram delivery is link-based (not document attach). Token stored in Redis, send_message_sync sends URL."
  - "D-04: Result block revealed via HTMX hx-target=#result-slot hx-swap=innerHTML after POST."
  - "build_download_url includes /m/ prefix because download endpoint lives under mobile router."
  - "PDF bytes use separate Redis client (no decode_responses=True) to avoid UTF-8 decode error on binary data."

patterns-established:
  - "Redis binary PDF storage: aioredis.from_url(REDIS_URL) without decode_responses, r.set(key, bytes, ex=TTL)"
  - "Mobile endpoint imports: lazy from-import inside handler body to avoid circular imports in mobile router"
  - "HTMX form POST → partial template response pattern consistent with position_progress.html"

requirements-completed:
  - REP-01
  - REP-02

duration: 10min
completed: 2026-04-11
---

# Phase 29 Plan 01: Mobile Reports Summary

**Mobile PDF report creation UI with Redis token-protected download, Telegram link delivery, and email attachment — covering REP-01 and REP-02 in 5 new endpoints**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-11T22:09:00Z
- **Completed:** 2026-04-11T22:19:17Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Mobile single-page report form at `/m/reports/new` with project select, 2 radio-cards (brief/detailed), JS-driven submit-button enable/disable
- Redis token-protected PDF download endpoint with 7-day TTL — token serves as bearer auth for one-tap download
- Telegram link-based delivery and email attachment delivery via existing `send_message_sync` / `send_email_with_attachment_sync`

## Task Commits

1. **Task 1: APP_BASE_URL setting + mobile_reports_service** — `f4d03ff` (feat)
2. **Task 2: Mobile report endpoints** — `5ec18f4` (feat)
3. **Task 3: Mobile report templates** — `8b73667` (feat)

## Files Created/Modified

- `app/config.py` — Added `APP_BASE_URL: str = "http://localhost:8000"` for absolute URL construction in Telegram messages
- `app/services/mobile_reports_service.py` — New service: `list_clients_for_reports`, `store_report_pdf`, `load_report_pdf`, `build_download_url` with Redis binary client
- `app/routers/mobile.py` — 5 new endpoints: GET/POST `/m/reports/new`, GET `/m/reports/download/{token}`, POST send telegram/email; also added `StreamingResponse` import
- `app/templates/mobile/reports/new.html` — Single-page form extending `base_mobile.html`, HTMX POST to `#result-slot`, radio-card JS interaction
- `app/templates/mobile/reports/partials/result_block.html` — Inline result block with Скачать PDF / Отправить в Telegram / Отправить email CTAs, showToast feedback

## Decisions Made

- `build_download_url` uses `/m/reports/download/` prefix (not `/reports/download/`) because the download endpoint is registered on the `/m/` router — updated from plan's original note
- Lazy imports inside handler bodies retained throughout to match existing mobile.py style and avoid circular import risk
- `StreamingResponse` added to top-level imports (not lazy) since it's a core FastAPI response class with no circular import risk

## Deviations from Plan

None — plan executed exactly as written. The `/m/` prefix clarification was anticipated in the plan's constraint note (Task 2 action section explicitly mentioned it).

## Issues Encountered

None.

## User Setup Required

Set `APP_BASE_URL` in `.env` to the public URL of the deployment (e.g. `APP_BASE_URL=https://seo.example.com`) so Telegram messages contain correct absolute download links. Default `http://localhost:8000` works for local development.

## Known Stubs

None — all three CTAs wire to real service calls. The result block only appears after actual PDF generation and Redis storage.

## Next Phase Readiness

- Plan 02 (mobile tools list + run + result views) can proceed; it uses the same `mobile_templates`, `router`, and `showToast` pattern established here
- `APP_BASE_URL` is available for any future mobile endpoint needing absolute URLs

---
*Phase: 29-reports-tools*
*Completed: 2026-04-11*
