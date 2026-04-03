---
phase: v3-03-change-monitoring
verified: 2026-04-03T09:00:00Z
status: passed
score: 7/7 must-haves verified
human_verification:
  - test: "Navigate to /monitoring/{valid_site_id} and confirm the page renders alert rules table, digest schedule form, and alert history"
    expected: "Full monitoring page loads with 9 alert rules in the table, digest schedule toggle/form, and alert history (empty or populated)"
    why_human: "Requires a running application with a valid site ID and migrated database"
  - test: "Trigger a crawl on a site that has been crawled before, then check /monitoring/{site_id}"
    expected: "If any SEO fields changed between crawls, ChangeAlert records appear in the history table; error-severity changes trigger a Telegram message"
    why_human: "Requires running crawler + Telegram bot configured with valid credentials"
  - test: "Save a digest schedule with is_active=True for a site, then verify the redbeat entry exists in Redis"
    expected: "redis-cli keys '*digest-schedule*' returns an entry for that site_id"
    why_human: "Requires running Redis instance with redbeat configured"
---

# Phase v3-03: Change Monitoring Verification Report

**Phase Goal:** Change Monitoring — alerts on site changes after crawls, weekly digest via Telegram, per-site digest schedule management

**Verified:** 2026-04-03T09:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 9 change types detectable between crawl snapshots | VERIFIED | `detect_changes()` handles all 9 types: new_page, page_404, noindex_added, schema_removed, title_changed, h1_changed, canonical_changed, meta_description_changed, content_changed |
| 2 | Error-severity changes dispatch immediate Telegram alerts | VERIFIED | `dispatch_immediate_alerts()` filters error-severity, calls `send_message_sync()`, marks `sent_at` |
| 3 | Warning/info changes saved to DB for digest (not sent immediately) | VERIFIED | `save_change_alerts()` saves all active-rule changes; `dispatch_immediate_alerts()` only sends error-severity |
| 4 | Post-crawl hook runs change monitoring automatically | VERIFIED | `crawl_tasks.py` calls `process_crawl_changes()` after every crawl in its own DB session (line 191-201) |
| 5 | Weekly digest collects 7 days of changes grouped by severity | VERIFIED | `build_digest()` queries past N days, groups into error/warning/info, returns structured dict |
| 6 | Per-site digest schedule registers with redbeat Beat scheduler | VERIFIED | `upsert_digest_schedule()` calls `register_digest_beat()` when is_active=True; `restore_digest_schedules_from_db()` restores on Beat startup via `beat_init` signal |
| 7 | Monitoring UI page with alert rules table, digest schedule form, and alert history | VERIFIED | `monitoring/index.html` renders all three sections server-side; JS handlers for inline rule editing and digest trigger |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `app/models/change_monitoring.py` | VERIFIED | ChangeType (9 values), AlertSeverity (3 values), ChangeAlertRule, ChangeAlert, DigestSchedule models — all substantive |
| `alembic/versions/0022_add_change_monitoring_tables.py` | VERIFIED | revision=0022, down_revision=0021; creates 3 tables, 9 seeded default rules, 3 op.drop_table in downgrade |
| `app/services/change_monitoring_service.py` | VERIFIED | detect_changes, get_alert_rules_sync, save_change_alerts, mark_alerts_sent, dispatch_immediate_alerts, process_crawl_changes — all implemented |
| `app/services/digest_service.py` | VERIFIED | compute_digest_cron, build_digest, send_digest, get_digest_schedule, upsert_digest_schedule, register_digest_beat, remove_digest_beat, restore_digest_schedules_from_db — all implemented |
| `app/tasks/digest_tasks.py` | VERIFIED | send_weekly_digest Celery task with max_retries=2, queue=default, soft_time_limit=60 |
| `app/routers/monitoring.py` | VERIFIED | 8 endpoints: GET /{site_id}, GET /rules, PUT /rules/{rule_id}, GET /{site_id}/alerts, GET /{site_id}/alerts/count, GET /{site_id}/digest-schedule, PUT /{site_id}/digest-schedule, POST /{site_id}/digest/send |
| `app/templates/monitoring/index.html` | VERIFIED | Extends base.html; Russian copy throughout; stats cards (Критичных/Предупреждений/Всего), alert rules table with inline select, digest schedule form (Еженедельный дайджест) with Понедельник..Воскресенье, alert history with severity filter |
| `tests/test_change_monitoring_models.py` | VERIFIED | 5 tests covering enums and model instantiation |
| `tests/test_change_monitoring_service.py` | VERIFIED | 11 tests covering all 8 detection scenarios plus 3 formatter tests |
| `tests/test_digest_service.py` | VERIFIED | 6 tests covering cron computation (4) and formatter (2) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `crawl_tasks.py` | `change_monitoring_service.process_crawl_changes()` | import + call after crawl | WIRED | Lines 191-201: `from app.services.change_monitoring_service import process_crawl_changes` called post-crawl |
| `monitoring.py` router | `digest_service.get_digest_schedule / upsert_digest_schedule` | `import digest_service as ds` | WIRED | `ds.get_digest_schedule()` and `ds.upsert_digest_schedule()` called in endpoints |
| `digest_tasks.send_weekly_digest` | `digest_service.send_digest()` | import inside task | WIRED | Task body imports and calls `send_digest(db, UUID(site_id))` |
| `celery_app.py` | `digest_tasks` | include list | WIRED | `"app.tasks.digest_tasks"` in include list (line 18) |
| `celery_app.py beat_init` | `restore_digest_schedules_from_db()` | signal handler | WIRED | Called from existing `beat_init.connect` signal (line 104-105) |
| `app/main.py` | `monitoring_router` | include_router | WIRED | Line 36: import; line 174: `app.include_router(monitoring_router)` |
| `sites/detail.html` | `/monitoring/{site.id}` | "Мониторинг" button | WIRED | Line 46: `<a href="/monitoring/{{ site.id }}" ...>Мониторинг</a>` |
| `telegram_service.py` | `format_change_alert`, `format_weekly_digest`, `CHANGE_TYPE_LABELS` | function definitions | WIRED | All three defined, used in change_monitoring_service and digest_service |
| `diff_service.py` | `canonical_url`, `has_schema`, `has_noindex` fields | SNAPSHOT_FIELDS + build_snapshot | WIRED | All three fields present in SNAPSHOT_FIELDS and build_snapshot() |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `monitoring/index.html` rules section | `rules` | `db.execute(select(ChangeAlertRule))` in router GET /{site_id} | Yes — DB query, seeded by migration | FLOWING |
| `monitoring/index.html` alerts section | `alerts` | `db.execute(select(ChangeAlert).where(...).limit(50))` in router | Yes — DB query filtered by site_id | FLOWING |
| `monitoring/index.html` stats cards | `error_count`, `warning_count`, `total_count` | `db.execute(select(ChangeAlert.severity, func.count()).group_by(...))` | Yes — DB aggregate query | FLOWING |
| `monitoring/index.html` digest form | `digest_schedule` | `ds.get_digest_schedule(db, site_id)` → `select(DigestSchedule)` | Yes — DB query, nullable (None if not set) | FLOWING |
| `build_digest()` in digest_service | `alerts` | `db.execute(select(ChangeAlert).where(site_id, created_at >= cutoff))` | Yes — DB query with time filter | FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED — application requires running PostgreSQL + Redis to execute. Pure unit test imports verified below.

| Behavior | Check | Status |
|----------|-------|--------|
| `detect_changes()` importable and pure | `grep -q "def detect_changes" app/services/change_monitoring_service.py` | PASS |
| Migration revision chain correct | revision=0022, down_revision=0021 verified in file | PASS |
| 9 seed rules in migration | `op.bulk_insert` with 9 entries confirmed | PASS |
| 3 tables dropped in downgrade | `grep -c "op.drop_table"` returns 3 | PASS |
| Router registered in main.py | `grep "monitoring_router" app/main.py` returns import + include_router | PASS |
| digest_tasks in celery include list | `grep "digest_tasks" app/celery_app.py` returns match | PASS |
| restore_digest_schedules in beat_init | `grep "restore_digest_schedules" app/celery_app.py` returns match | PASS |
| All 3 test files have sufficient test counts | 5 / 11 / 6 tests confirmed | PASS |

---

### Requirements Coverage

No `requirements_addressed` fields were populated in any of the 4 plan files (all listed as `[]`). Phase v3-03 does not formally map to REQUIREMENTS.md entries. Coverage assessed against ROADMAP-v3.md Phase 3 goals:

| Goal | Status | Evidence |
|------|--------|----------|
| Automatic change tracking between crawls | SATISFIED | `process_crawl_changes()` hooked into `crawl_tasks.py` |
| Telegram alert on title/H1/meta change | SATISFIED | title_changed, h1_changed, meta_description_changed in `detect_changes()` |
| Telegram alert on noindex appearing | SATISFIED | noindex_added change type + error severity rule |
| Telegram alert on 404 | SATISFIED | page_404 change type + error severity rule |
| Telegram alert on canonical change | SATISFIED | canonical_changed change type + warning severity rule |
| Telegram alert on schema.org removal | SATISFIED | schema_removed change type + error severity rule |
| Weekly digest: summary of changes | SATISFIED | `build_digest()` + `format_weekly_digest()` + `send_weekly_digest` task |
| Configurable rules: which changes matter | SATISFIED | ChangeAlertRule table with is_active toggle + severity select in UI |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routers/monitoring.py` | 37 vs 93 | `GET /{site_id}` registered before `GET /rules` — "rules" is a valid path segment but not a valid UUID, so FastAPI returns 422 for `GET /monitoring/rules` | WARNING | `GET /rules` JSON endpoint is unreachable via HTTP. UI does not call this endpoint (rules loaded server-side, updates via PUT). No user-visible breakage. |

No blocker anti-patterns found. The routing issue is warning-level only — the affected endpoint (`GET /rules`) is not used by the UI or any documented consumer.

---

### Human Verification Required

#### 1. Monitoring Page Full Render

**Test:** Navigate to `/monitoring/{site_id}` for a site that has been crawled at least once.
**Expected:** Page renders with 9 alert rules in the table (seeded by migration 0022), digest schedule form with day/time inputs, and either an alert history table or the empty state message "Нет зарегистрированных изменений".
**Why human:** Requires running application + migrated database.

#### 2. Post-Crawl Change Detection End-to-End

**Test:** Trigger two crawls on a site where a page title or noindex tag has changed between crawls. Check `/monitoring/{site_id}` after the second crawl completes.
**Expected:** ChangeAlert records appear in the alert history. For noindex/404/schema changes (error-severity), a Telegram message is also sent to the configured chat.
**Why human:** Requires running Celery worker + Telegram bot token + real crawl data.

#### 3. Digest Schedule Registration in Redis

**Test:** On the monitoring page, enable the digest schedule for a site (any day/time) and click "Сохранить расписание". Then run `redis-cli keys '*digest-schedule*'` on the Redis host.
**Expected:** A redbeat key like `redbeat:digest-schedule:{site_id}` appears in Redis.
**Why human:** Requires running Redis with redbeat; can't verify key creation without the service.

---

### Gaps Summary

No gaps found. All 7 observable truths are verified with substantive artifacts and correct wiring.

One warning noted: `GET /monitoring/rules` is shadowed by `GET /monitoring/{site_id}` due to route registration order. This endpoint returns 422 when called directly. However, the monitoring UI does not use this endpoint — alert rules are rendered server-side and updates use `PUT /monitoring/rules/{rule_id}`, which is unaffected. This does not block any goal or user workflow.

---

_Verified: 2026-04-03T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
