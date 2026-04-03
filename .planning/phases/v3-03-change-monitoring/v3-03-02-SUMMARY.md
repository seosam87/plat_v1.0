---
phase: v3-03
plan: "02"
subsystem: monitoring
tags: [change-detection, telegram, celery, sqlalchemy, alert-rules]

# Dependency graph
requires:
  - phase: v3-03-01
    provides: ChangeType, AlertSeverity, ChangeAlertRule, ChangeAlert, DigestSchedule models with migration 0022

provides:
  - detect_changes() pure function — detects 9 SEO-critical change types between snapshots
  - process_crawl_changes() orchestrator — called post-crawl to detect, save, and dispatch alerts
  - dispatch_immediate_alerts() — sends error-severity changes via Telegram synchronously
  - save_change_alerts() / mark_alerts_sent() — DB CRUD for ChangeAlert records
  - get_alert_rules_sync() — loads ChangeAlertRule rules from DB for matching
  - format_change_alert() / format_weekly_digest() — Telegram message formatters in Russian
  - crawl_tasks.py hook — process_crawl_changes() called after every crawl

affects: [v3-03-03, v3-03-04, digest-service, crawl-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pure detection function (detect_changes) with no DB dependencies — easy to unit test
    - Sync DB functions for Celery task context (get_alert_rules_sync, save_change_alerts)
    - Change alert dispatch filters by severity at error level; warning/info saved for digest

key-files:
  created:
    - app/services/change_monitoring_service.py
    - tests/test_change_monitoring_service.py
  modified:
    - app/services/diff_service.py
    - app/services/telegram_service.py
    - app/tasks/crawl_tasks.py

key-decisions:
  - "detect_changes() treats empty old_snap as new_page — simplifies orchestrator logic"
  - "title/h1/meta_description changes only detected when both old and new are non-empty — avoids false positives from missing data"
  - "canonical_changed fires when either old or new is non-empty and they differ — catches canonical removal"
  - "dispatch_immediate_alerts() handles both enum and string severity comparisons for flexibility"

patterns-established:
  - "Change detection is pure Python (no DB) — all DB interaction is in separate sync functions"
  - "Telegram formatters produce HTML-formatted messages with Russian labels"
  - "Post-crawl hooks are wrapped in their own get_sync_db() context"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-04-03
---

# Phase v3-03 Plan 02: Change Detection Service, Alert Dispatch, and Telegram Formatters Summary

**Change detection service with 9 SEO alert types, rule-based severity matching, immediate Telegram dispatch for error-level changes, and crawl pipeline hook**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-03T07:07:02Z
- **Completed:** 2026-04-03T07:17:00Z
- **Tasks:** 5
- **Files modified:** 5

## Accomplishments

- `detect_changes()` pure function handles all 9 change types: new_page, page_404, noindex_added, schema_removed, title_changed, h1_changed, canonical_changed, meta_description_changed, content_changed
- `process_crawl_changes()` orchestrator wires detection → rule matching → alert save → Telegram dispatch in one call
- Telegram formatters produce structured Russian messages: `format_change_alert()` for immediate alerts, `format_weekly_digest()` with error/warning/info sections
- crawl_tasks.py now calls `process_crawl_changes()` after every crawl completion inside its own DB session
- 11 unit tests cover all detection scenarios and formatter output structure

## Task Commits

Each task was committed atomically:

1. **Task 01-05: All tasks combined** - `5c51bb7` (feat)

**Plan metadata:** Pending docs commit

## Files Created/Modified

- `app/services/change_monitoring_service.py` - Full change monitoring service: detect_changes, get_alert_rules_sync, save_change_alerts, mark_alerts_sent, dispatch_immediate_alerts, process_crawl_changes
- `tests/test_change_monitoring_service.py` - 11 unit tests for detection logic and Telegram formatters
- `app/services/diff_service.py` - Already contained canonical_url, has_schema, has_toc, has_noindex fields (verified)
- `app/services/telegram_service.py` - Added format_change_alert, format_weekly_digest, CHANGE_TYPE_LABELS
- `app/tasks/crawl_tasks.py` - Added process_crawl_changes hook after create_auto_tasks

## Decisions Made

- `detect_changes()` is a pure function with no DB dependencies — simplifies testing and reuse
- title/h1/meta_description changes only fire when both old and new are non-empty, preventing false positives from missing data
- canonical_changed fires when either old or new is non-empty (catches canonical removal/addition)
- error-severity alerts dispatched immediately; warning/info saved for digest only

## Deviations from Plan

None - plan executed exactly as written. All files were created per spec with acceptance criteria verified.

## Issues Encountered

None - all acceptance criteria passed. Tests run without DB connection (pure function testing).

## User Setup Required

None - no external service configuration required beyond existing TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID settings.

## Next Phase Readiness

- Ready for v3-03-03: digest service can use `format_weekly_digest()` and query `ChangeAlert` records
- Ready for v3-03-04: monitoring router can expose `ChangeAlert` history via API
- Crawl pipeline fully wired — every crawl will now detect and store change alerts

---
*Phase: v3-03-change-monitoring*
*Completed: 2026-04-03*
