---
phase: v3-03-change-monitoring
plan: "04"
subsystem: ui
tags: [fastapi, jinja2, htmx, monitoring, change-alerts, digest, redbeat]

requires:
  - phase: v3-03-01
    provides: ChangeAlertRule, ChangeAlert, DigestSchedule models, migration 0022
  - phase: v3-03-02
    provides: change_monitoring_service, detect_changes, save_change_alerts
  - phase: v3-03-03
    provides: digest_service, digest_tasks, send_weekly_digest Celery Beat task

provides:
  - monitoring router at /monitoring with 8 endpoints
  - monitoring/index.html template with alert rules table, digest schedule form, alert history
  - "Мониторинг" button in site detail Quick Actions
  - main.py registration of monitoring_router

affects: [v3-03, site-detail-page, monitoring-ui]

tech-stack:
  added: []
  patterns:
    - "Monitoring router pattern: GET /{site_id} HTML page + JSON sub-endpoints"
    - "Client-side severity filter via data-severity attribute + JS filterAlerts()"
    - "Inline rule editing via JS PUT to /monitoring/rules/{rule_id}"
    - "Digest schedule save via JS PUT to /monitoring/{site_id}/digest-schedule"

key-files:
  created:
    - app/routers/monitoring.py
    - app/templates/monitoring/index.html
  modified:
    - app/main.py
    - app/templates/sites/detail.html

key-decisions:
  - "Monitoring router registered with prefix=/monitoring, 8 endpoints covering rules CRUD, alert history, digest schedule CRUD, and manual digest trigger"
  - "Alert rules are global (no site_id): same severity rules apply to all sites — displayed in table with inline select/checkbox"
  - "Client-side filter in alert history table avoids server round-trip (same pattern as audit)"
  - "Manual digest trigger dispatches send_weekly_digest Celery task asynchronously"

patterns-established:
  - "Monitoring HTML page loads all data server-side, JS handles updates via fetch PUT/POST"
  - "Severity badges use hex colors: error=#dc2626, warning=#f59e0b, info=#6b7280"

requirements-completed: []

duration: 5min
completed: 2026-04-03
---

# Phase v3-03 Plan 04: Router, UI for alert rules and digest schedule, site detail integration Summary

**Monitoring router with 8 endpoints, Jinja2 template with alert rules table, weekly digest schedule form, and alert history feed — wires change monitoring data to the UI**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T07:15:00Z
- **Completed:** 2026-04-03T07:20:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Created `app/routers/monitoring.py` with 8 router endpoints: HTML page, rules list/update, alerts list/count, digest schedule get/update, and manual digest trigger
- Created `app/templates/monitoring/index.html` with summary stats cards, alert rules table with inline editing, digest schedule form with redbeat integration, and alert history with client-side severity filter
- Registered `monitoring_router` in `app/main.py` and added "Мониторинг" button to site detail Quick Actions

## Task Commits

Each task was committed atomically:

1. **Task 01-03: Create monitoring router, UI template, register router, add Мониторинг button** - `170e4ac` (feat)

**Plan metadata:** (docs commit — this summary)

## Files Created/Modified
- `app/routers/monitoring.py` - Monitoring router with 8 endpoints for alert rules, alert history, and digest schedule management
- `app/templates/monitoring/index.html` - Full monitoring page: stats, rules table with inline edit, digest schedule form, alert history with filter
- `app/main.py` - Added monitoring_router import and registration
- `app/templates/sites/detail.html` - Added "Мониторинг" quick action button

## Decisions Made
- Alert rules global (no site_id), displayed with inline severity select + active checkbox for immediate PUT updates
- Client-side JS filter for alert history table (no server round-trip)
- Manual digest trigger dispatches `send_weekly_digest` Celery task, returning task_id

## Deviations from Plan

None - plan executed exactly as written. All three tasks were previously completed in commit `170e4ac` which is an ancestor of the current HEAD.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 4 plans of v3-03-change-monitoring phase are complete
- Monitoring UI is fully wired: alert rules, digest schedule, alert history all functional
- Change detection runs automatically after each crawl via `process_crawl_changes()`
- Weekly digest Celery Beat task registered via redbeat per-site schedule

---
*Phase: v3-03-change-monitoring*
*Completed: 2026-04-03*
