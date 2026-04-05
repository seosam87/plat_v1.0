---
phase: 10-reports-ads
plan: 03
subsystem: reporting
tags: [celery, redbeat, smtp, telegram, aiosmtplib, jinja2, htmx]

# Dependency graph
requires:
  - phase: 10-reports-ads-02
    provides: generate_pdf_report async function, report_service, project PDF templates
  - phase: 10-reports-ads-01
    provides: dashboard_service.projects_table, AsyncSession patterns
provides:
  - ReportSchedule singleton model (report_schedules table) for morning/weekly delivery config
  - morning_digest_service.build_morning_digest — compact cross-project Telegram text (sync, for Celery)
  - smtp_service.send_email_sync — aiosmtplib wrapper with silent skip when unconfigured
  - report_tasks.send_morning_digest — Celery Beat task for daily Telegram digest
  - report_tasks.send_weekly_summary_report — Celery Beat task for weekly PDF via SMTP
  - register_report_beats / restore_report_schedules_from_db — redbeat lifecycle management
  - Admin UI at /ui/admin/report-schedule for schedule configuration
affects:
  - celery beat schedule restore
  - SMTP delivery configuration
  - admin settings navigation

# Tech tracking
tech-stack:
  added:
    - aiosmtplib>=3,<4 (async SMTP via asyncio.run wrapper for Celery sync tasks)
  patterns:
    - Singleton DB row (id=1) for global schedule config — same pattern used for all platform-wide settings
    - register_or_remove_beat helper consolidates redbeat add/delete logic
    - asyncio.run() wraps async report generation inside Celery sync task
    - SMTP silently skips when SMTP_HOST empty — matches Telegram is_configured() pattern
    - restore_report_schedules_from_db called from beat_init signal — survives Redis flush

key-files:
  created:
    - app/models/report_schedule.py
    - app/services/morning_digest_service.py
    - app/services/smtp_service.py
    - app/tasks/report_tasks.py
    - app/templates/admin/report_schedule.html
    - alembic/versions/9c65e7d94183_add_report_schedules_table.py
    - tests/test_morning_digest_service.py
  modified:
    - app/config.py (SMTP_HOST/PORT/USER/PASSWORD/FROM settings)
    - app/celery_app.py (added report_tasks include + beat_init restore)
    - app/main.py (GET/POST /ui/admin/report-schedule routes)
    - app/navigation.py (Report Schedule child in settings section)
    - alembic/env.py (ReportSchedule import for Alembic autogenerate)
    - requirements.txt (aiosmtplib)

key-decisions:
  - "ReportSchedule uses singleton row id=1 — simpler than nullable FK; always upsert on POST"
  - "Morning digest sends Telegram text (not PDF) per D-07 — compact cross-project summary"
  - "Weekly report task calls asyncio.run() around async generate_pdf_report — Celery tasks are sync"
  - "register_or_remove_beat always deletes then re-creates to handle schedule changes atomically"
  - "SMTP silently skips when SMTP_HOST is empty — matches existing Telegram is_configured() pattern"
  - "restore_report_schedules_from_db hooked into beat_init signal alongside existing crawl restore"

requirements-completed: [DASH-03, DASH-04]

# Metrics
duration: 15min
completed: 2026-04-05
---

# Phase 10 Plan 03: Reports & Ads — Scheduled Delivery Summary

**ReportSchedule model + morning digest Telegram service + SMTP wrapper + Celery Beat tasks for daily/weekly delivery with admin config UI at /ui/admin/report-schedule**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-05T18:15:00Z
- **Completed:** 2026-04-05T18:30:00Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments

- ReportSchedule singleton model migrated (report_schedules table, id=1)
- morning_digest_service.build_morning_digest generates compact cross-project Telegram HTML (D-07)
- smtp_service.send_email_sync wraps aiosmtplib for SMTP delivery with silent skip when unconfigured (D-08)
- Two Celery Beat tasks: send_morning_digest (daily Telegram text) + send_weekly_summary_report (PDF via SMTP + Telegram)
- register_report_beats + restore_report_schedules_from_db manage redbeat lifecycle (D-09)
- Admin UI at /ui/admin/report-schedule with morning digest and weekly report configuration
- 5 tests for morning_digest_service — all pass

## Task Commits

1. **Task 1: ReportSchedule model, morning digest service, SMTP service, config** - `26331d0` (feat)
2. **Task 2: Celery Beat tasks and admin schedule UI** - `aef45fd` (feat)

## Files Created/Modified

- `app/models/report_schedule.py` — ReportSchedule singleton model
- `app/services/morning_digest_service.py` — build_morning_digest (sync, for Celery)
- `app/services/smtp_service.py` — send_email_sync with aiosmtplib
- `app/tasks/report_tasks.py` — send_morning_digest, send_weekly_summary_report, register_report_beats
- `app/templates/admin/report_schedule.html` — admin config UI
- `alembic/versions/9c65e7d94183_add_report_schedules_table.py` — migration
- `tests/test_morning_digest_service.py` — 5 unit tests
- `app/config.py` — SMTP_HOST/PORT/USER/PASSWORD/FROM settings
- `app/celery_app.py` — report_tasks include + beat_init restore hook
- `app/main.py` — GET/POST /ui/admin/report-schedule routes
- `app/navigation.py` — Report Schedule nav entry in settings section
- `alembic/env.py` — ReportSchedule import for Alembic
- `requirements.txt` — aiosmtplib>=3,<4

## Decisions Made

- ReportSchedule singleton row (id=1) — upsert pattern on every POST save
- Morning digest is Telegram text only (no PDF) per D-07 specification
- asyncio.run() wraps async generate_pdf_report inside Celery sync task (existing pattern from WeasyPrint)
- register_or_remove_beat always deletes existing entry before re-creating to handle cron changes atomically
- beat_init restore hooked alongside existing crawl/digest restore hooks in celery_app.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Project.archived filter — model uses status enum not boolean column**
- **Found during:** Task 1 (build_morning_digest implementation)
- **Issue:** Plan specified `Project.archived.is_(False)` but Project model has `status: ProjectStatus` enum; no `archived` column
- **Fix:** Changed filter to `Project.status != ProjectStatus.archived`
- **Files modified:** app/services/morning_digest_service.py
- **Verification:** Tests pass with corrected filter
- **Committed in:** 26331d0 (Task 1 commit)

**2. [Rule 1 - Bug] Cleaned generated Alembic migration — removed spurious drop statements**
- **Found during:** Task 1 (running alembic autogenerate)
- **Issue:** Autogenerate detected partitioned keyword_positions tables and other tables not tracked in this Alembic instance as "removed"; included ~50 dangerous drop_table statements
- **Fix:** Replaced generated migration with clean hand-written migration that only creates report_schedules
- **Files modified:** alembic/versions/9c65e7d94183_add_report_schedules_table.py
- **Verification:** alembic upgrade head applied cleanly
- **Committed in:** 26331d0 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes essential — incorrect model query would crash at runtime; migration would have destroyed data.

## Issues Encountered

- Alembic autogenerate ran inside Docker container (PostgreSQL only accessible in Docker network), then migration file was synced to host project directory for git tracking.

## Known Stubs

None — morning digest builds from real DB data; SMTP and Telegram send silently skip when unconfigured.

## Next Phase Readiness

- Plan 10-03 complete. Plan 10-04 (if any) can build on report schedule config.
- SMTP configuration requires SMTP_HOST/PORT/USER/PASSWORD/FROM env vars to deliver email.
- Celery Beat worker must be restarted to pick up new report_tasks include.

---
*Phase: 10-reports-ads*
*Completed: 2026-04-05*
