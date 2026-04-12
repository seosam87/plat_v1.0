---
phase: 30-errors-quick-task
plan: "03"
subsystem: mobile-quick-task
tags: [mobile, tasks, copywriter-brief, htmx, jinja2]
dependency_graph:
  requires: ["30-01"]
  provides: ["TSK-01", "TSK-02"]
  affects: ["app/routers/mobile.py", "app/services/mobile_brief_service.py"]
tech_stack:
  added: []
  patterns: ["HTMX swap on mode toggle", "Jinja2 text template for brief", "SeoTask auto-fill from form data"]
key_files:
  created:
    - app/services/mobile_brief_service.py
    - app/templates/briefs/copywriter_brief.txt.j2
    - app/templates/mobile/tasks/new.html
    - app/templates/mobile/tasks/partials/task_form.html
    - app/templates/mobile/tasks/partials/brief_form.html
  modified:
    - app/routers/mobile.py
decisions:
  - "Use site.url (not site.domain) — Site model has url field, no domain field"
  - "Use get_accessible_projects() from project_service instead of raw user_id query — Project has no user_id field, uses project_users many-to-many"
  - "Use Client.company_name for display (not Client.name) — Client model has company_name not name"
  - "Use send_message_sync (not send_message_to_user_by_email) for Telegram — existing telegram_service API"
  - "SMTP_USE_TLS not in config — removed from send_brief_email, uses hostname+port only"
metrics:
  duration: 8
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_changed: 6
---

# Phase 30 Plan 03: Quick Task & Copywriter Brief Summary

Quick task creation + copywriter brief generation for /m/tasks/new with mode toggle, HTMX partial swap, and Telegram/email delivery.

## What Was Built

- `/m/tasks/new` page with mode toggle (Задача / ТЗ копирайтеру) defaulting to task mode per D-12
- `GET /m/tasks/new/form?mode=` HTMX endpoint returning partial form for mode toggle swap
- `POST /m/tasks/new` unified submit handler for both modes
- `app/services/mobile_brief_service.py` — `render_brief()`, `list_clients_for_brief()`, `send_brief_telegram()`, `send_brief_email()` with graceful error handling
- `app/templates/briefs/copywriter_brief.txt.j2` — Jinja2 plain-text brief template with 5 placeholders

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | ecd5626 | feat(30-03): brief service + copywriter template + /m/tasks/new endpoints |
| Task 2 | be8c750 | feat(30-03): Jinja2 templates for /m/tasks/new page with mode toggle |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Site field is `url` not `domain`**
- **Found during:** Task 1
- **Issue:** Plan's brief service used `site.domain` but Site model has `url` field, no `domain`
- **Fix:** Changed to `site.url` in the router POST handler
- **Files modified:** app/routers/mobile.py

**2. [Rule 1 - Bug] Project has no `user_id` field**
- **Found during:** Task 1
- **Issue:** Plan specified `select(Project).where(Project.user_id == user.id)` but Project uses project_users many-to-many + client_user_id
- **Fix:** Used `get_accessible_projects(db, user)` from project_service (already used in reports endpoint)
- **Files modified:** app/routers/mobile.py

**3. [Rule 1 - Bug] Client display name is `company_name` not `name`**
- **Found during:** Task 1
- **Issue:** Plan used `c.name` but Client model has `company_name`
- **Fix:** Changed to `c.company_name` in `list_clients_for_brief()`
- **Files modified:** app/services/mobile_brief_service.py

**4. [Rule 1 - Bug] SMTP_USE_TLS not in settings**
- **Found during:** Task 1
- **Issue:** Plan's `send_brief_email` referenced `settings.SMTP_USE_TLS` but config.py has no such field
- **Fix:** Removed use_tls parameter from aiosmtplib.send() call
- **Files modified:** app/services/mobile_brief_service.py

**5. [Rule 1 - Bug] Telegram service API mismatch**
- **Found during:** Task 1
- **Issue:** Plan used `send_message_to_user_by_email` which doesn't exist in telegram_service; actual API is `send_message_sync`
- **Fix:** Changed to use `send_message_sync(msg)` for brief Telegram delivery
- **Files modified:** app/services/mobile_brief_service.py

## Known Stubs

None — all data flows are wired. Brief rendering uses real Jinja2 template. Projects and clients are loaded from DB.

## Self-Check: PASSED

All 6 files confirmed present on disk. Both commits (ecd5626, be8c750) confirmed in git log.
