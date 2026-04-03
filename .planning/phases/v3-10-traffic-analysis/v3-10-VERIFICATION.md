---
phase: v3-10-traffic-analysis
verified: 2026-04-03T00:00:00Z
status: gaps_found
score: 5/7 must-haves verified
re_verification: false
gaps:
  - truth: "Traffic timeline chart renders real visit data from a session"
    status: failed
    reason: "Neither upload_log nor analyze_metrika saves TrafficVisit rows to the DB. All four detail endpoints (/visits, /bots, /anomalies, /injections) query traffic_visits which is always empty after ingestion."
    artifacts:
      - path: "app/routers/traffic_analysis.py"
        issue: "upload_log() classifies parsed visits in memory then discards them — no db.add(TrafficVisit(...)) loop. analyze_metrika() creates only the session record, never individual visit rows."
    missing:
      - "In upload_log(): after classifying parsed visits, iterate and bulk-insert TrafficVisit rows (ip_address, timestamp, page_url, source, is_bot, bot_reason, referer, user_agent, session_id)"
      - "In analyze_metrika(): convert MetrikaTrafficDaily rows into TrafficVisit rows (one per day, or synthetic per-visit rows) and persist them so the Chart.js endpoints return data"

  - truth: "Bot detection table shows bot-flagged visits after log upload"
    status: failed
    reason: "Depends on same root cause: TrafficVisit rows are never written, so GET /sessions/{id}/bots always returns []."
    artifacts:
      - path: "app/routers/traffic_analysis.py"
        issue: "session_bots() queries traffic_visits filtered by is_bot=True but the table is always empty."
    missing:
      - "Same fix as gap 1 — persist TrafficVisit rows during ingestion"
human_verification:
  - test: "Upload a test access.log with mixed bot/human lines, then open the session dashboard and verify the Chart.js timeline renders stacked bars and the bot table is populated."
    expected: "Timeline shows bars for at least one day; bot table shows rows with IP, UA and bot_reason columns filled."
    why_human: "Requires a running server and a real (or synthetic) access.log file."
  - test: "Trigger Metrika analysis for a site that has MetrikaTrafficDaily rows, then open the session and verify the anomaly banner and timeline render."
    expected: "Anomaly banner shows green or red depending on data; timeline shows organic visit bars per day."
    why_human: "Requires live DB with pre-existing Metrika data."
---

# Phase v3-10: Traffic Analysis & Bot Detection Verification Report

**Phase Goal:** Traffic Analysis & Bot Detection — analyze traffic injection patterns, detect bots from Metrika/logs, entry point analysis, anomaly detection, Chart.js dashboard.
**Verified:** 2026-04-03
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Models compile and import cleanly | VERIFIED | `app/models/traffic_analysis.py` — VisitSource enum, TrafficAnalysisSession, TrafficVisit, BotPattern all present with correct fields |
| 2 | Bot detection classifies visits correctly | VERIFIED | `classify_visit()` in service; 4 bot tests pass (UA match, empty UA, generic bot UA, human) |
| 3 | Anomaly detection identifies spikes | VERIFIED | `detect_anomalies()` with mean+2*std_dev threshold; 2 tests pass (spike detected, normal no anomaly) |
| 4 | Access log can be parsed | VERIFIED | `parse_access_log()` in service (co-located, not a separate file); 2 tests pass; regex compiled at module level |
| 5 | Dashboard template renders with all required sections | VERIFIED | index.html: source card, anomaly alert, sessions table, Chart.js timeline, sources doughnut, referers, landings, bot table with filter, injection patterns, period comparison — all present |
| 6 | Traffic timeline chart renders real visit data from a session | FAILED | Chart.js template is wired to `/visits` endpoint which queries `traffic_visits` table — but neither ingestion endpoint (upload_log, analyze_metrika) writes TrafficVisit rows to DB. Dashboard always shows empty charts after analysis. |
| 7 | Bot detection table shows bot-flagged visits after log upload | FAILED | Same root cause: `session_bots()` queries `traffic_visits WHERE is_bot=True` — always empty because visits are never persisted. |

**Score:** 5/7 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models/traffic_analysis.py` | ORM models for sessions, visits, bot patterns | VERIFIED | All three models + VisitSource enum; correct FK relations; UUID PKs |
| `alembic/versions/0027_add_traffic_analysis_tables.py` | Migration creating tables + seeding 8 bot patterns | VERIFIED | Creates traffic_analysis_sessions, traffic_visits, bot_patterns; seeds 8 UA patterns; index on session_id |
| `app/services/traffic_analysis_service.py` | Pure analysis functions | VERIFIED | classify_visit, detect_anomalies, analyze_traffic_sources, detect_injection_patterns, parse_access_log — all present and substantive |
| `app/parsers/access_log_parser.py` | Separate access log parser module (per PLAN-01 files_modified) | NOTE | Per PLAN-01 acceptance criteria, parse_access_log is in traffic_analysis_service.py. The separate parsers/ file was not created. SUMMARY-01 documents this as an intentional decision. No impact on functionality. |
| `app/routers/traffic_analysis.py` | 9 router endpoints, all require_admin | VERIFIED | 9 `@router` decorators confirmed; all use `Depends(require_admin)` |
| `app/templates/traffic_analysis/index.html` | Full Russian dashboard with Chart.js | VERIFIED | 580-line template; Chart.js 4.4.0 CDN; stacked bar + doughnut charts; all sections in Russian |
| `tests/test_traffic_analysis_service.py` | 10 unit tests passing | VERIFIED | 10 tests, all pass in 0.02s |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/main.py` | `traffic_analysis_router` | `app.include_router()` | WIRED | Line 41 imports; line 180 registers |
| `index.html` JS | `/traffic-analysis/{site_id}/analyze-metrika` | `fetch() POST` | WIRED | analyzeMetrika() calls the endpoint correctly |
| `index.html` JS | `/traffic-analysis/{site_id}/upload-log` | `fetch() POST FormData` | WIRED | uploadLog() submits form data correctly |
| `index.html` JS | `/traffic-analysis/sessions/{id}/visits` | `loadSession() fetch` | WIRED but HOLLOW | Call made; endpoint returns real DB query; but traffic_visits table is always empty |
| `index.html` JS | `/traffic-analysis/sessions/{id}/bots` | `loadSession() fetch` | WIRED but HOLLOW | Same — always returns [] |
| `router.upload_log` | `TrafficVisit` (persist) | `db.add(TrafficVisit(...))` | NOT_WIRED | Visits are parsed and classified in memory but never persisted |
| `router.analyze_metrika` | `TrafficVisit` (persist) | `db.add(TrafficVisit(...))` | NOT_WIRED | Daily Metrika totals used only for session summary; no per-visit rows written |
| `sites/detail.html` | `/traffic-analysis/{site_id}` | `<a href="...">` | WIRED | "Анализ трафика" button present at line 51 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `index.html` traffic-chart canvas | `currentVisits` array | `GET /sessions/{id}/visits` → `SELECT * FROM traffic_visits` | No — traffic_visits is never populated by ingestion endpoints | HOLLOW — wired but data disconnected |
| `index.html` bots-section | `allBotVisits` array | `GET /sessions/{id}/bots` → `SELECT * FROM traffic_visits WHERE is_bot=True` | No — same root cause | HOLLOW — wired but data disconnected |
| `index.html` injections-section | `injections.patterns` | `GET /sessions/{id}/injections` → `detect_injection_patterns()` on DB visits | No — visits always empty, patterns always [] | HOLLOW — wired but data disconnected |
| `index.html` sessions table | `sessions` list | `GET /{site_id}` dashboard route → `SELECT traffic_analysis_sessions` | Yes — sessions are saved correctly | FLOWING |
| `router.analyze_metrika` anomaly_result | `visits_by_day` | `metrika_service.get_daily_traffic()` → `SELECT MetrikaTrafficDaily` | Yes — reads real DB data | FLOWING (session-level only) |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 10 unit tests pass | `python -m pytest tests/test_traffic_analysis_service.py -x -q` | 10 passed in 0.02s | PASS |
| Router has 9 endpoints | `grep -c "@router" app/routers/traffic_analysis.py` | 9 | PASS |
| Router registered in main.py | `grep traffic_analysis app/main.py` | lines 41 and 180 | PASS |
| Migration 0027 exists with correct revision chain | file exists with `revision = "0027"`, `down_revision = "0026"` | confirmed | PASS |
| Chart.js loaded in template | `grep chart.js index.html` | cdn.jsdelivr.net/npm/chart.js@4.4.0 at line 197 | PASS |
| TrafficVisit rows saved during upload_log | `grep "db.add(TrafficVisit" app/routers/traffic_analysis.py` | no match | FAIL |

---

## Requirements Coverage

No formal REQ-IDs are declared in either PLAN's `requirements_addressed` field (both are `[]`). Phase 10 is described in ROADMAP-v3.md as a narrative spec. Coverage assessed against ROADMAP success criteria:

| Criterion | Status | Evidence |
|-----------|--------|---------|
| Timeline of visits by type | PARTIAL | Chart.js timeline exists and is fully implemented; data is hollow because visits are never persisted |
| Bot detection by UA pattern | VERIFIED | classify_visit() + 4 passing tests |
| Anomaly spike detection | VERIFIED | detect_anomalies() mean+2*std_dev; 2 passing tests |
| Access log parser (Apache/Nginx combined) | VERIFIED | parse_access_log() regex; 2 passing tests |
| Metrika as primary analysis source | PARTIAL | analyze_metrika creates a session and detects anomalies at session level; per-visit Metrika data is not written to traffic_visits for chart rendering |
| Injection pattern detection | VERIFIED (logic) | detect_injection_patterns() implemented; but data hollow in live dashboard |
| "до/во время/после" comparison | VERIFIED (logic) | renderInjections() renders three-column before/during/after when anomaly_days present |
| Period comparison | VERIFIED | comparePeriods() filters currentVisits by date range; works once visits are flowing |
| All copy in Russian | VERIFIED | Template is fully in Russian |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routers/traffic_analysis.py` | 112–143 | `upload_log` parses and classifies visits into `parsed` dict list, then discards — only `TrafficAnalysisSession` is saved, no `TrafficVisit` rows | BLOCKER | All chart and bot-table data endpoints return empty responses; dashboard displays no visit data |
| `app/routers/traffic_analysis.py` | 70 | `get_daily_traffic(db, site_id, body.date_from, body.date_to)` passes `str` where `date` is typed | WARNING | asyncpg may coerce ISO date strings silently; works in practice but bypasses type safety |
| `app/services/traffic_analysis_service.py` | 165–173 | `ref_bounces`/`ref_total` dicts built but `ref_bounces` is never populated (the inner check is skipped with a comment) | INFO | Pattern 3 (high bounce from referer) is silently omitted; minor, documented as simplification |

---

## Human Verification Required

### 1. Dashboard renders data after log upload

**Test:** Start the app, navigate to a site's traffic analysis page, upload a valid Apache/Nginx access.log file (needs 50+ lines with mixed bot/human UAs), wait for completion, then click the newly created session row.
**Expected:** Chart.js timeline shows stacked bars per day; bot table shows rows with IP, UA, and bot_reason; injection patterns card may show patterns if thresholds are met.
**Why human:** Requires a running server, real file upload, and visual confirmation that Chart.js renders non-empty data.

### 2. Metrika analysis populates session anomaly data

**Test:** For a site with MetrikaTrafficDaily rows spanning 14+ days, trigger "Анализировать Метрику" with a date range covering those rows.
**Expected:** Session is created; if a traffic spike exists, the red anomaly banner appears with date/deviation details; the sessions history table shows "Аномалии: Да" for that session.
**Why human:** Requires pre-existing Metrika data in DB and visual confirmation of the alert banner color/state.

---

## Gaps Summary

The phase built all models, service logic, tests, router skeleton, and template correctly. The critical gap is a **data persistence disconnect**: both ingestion endpoints (`upload_log` and `analyze_metrika`) parse/analyze traffic data but only save a summary `TrafficAnalysisSession` record — they never write individual `TrafficVisit` rows. All four chart-feeding endpoints (`/visits`, `/bots`, `/anomalies`, `/injections`) query the `traffic_visits` table, which is always empty. The visual dashboard is structurally complete and wired correctly; it simply has no data to display.

**Fix scope:** In `upload_log`, add a loop after classification that bulk-inserts `TrafficVisit` objects (ip_address, timestamp parsed from log, page_url, source, is_bot, bot_reason, referer, user_agent, session_id). In `analyze_metrika`, either synthesize one `TrafficVisit` row per `MetrikaTrafficDaily` record (using midnight timestamp, source=organic, totals for count) or document that Metrika analysis sessions only produce session-level summaries and disable the visits/bots/injections endpoints for metrika-sourced sessions.

The `app/parsers/access_log_parser.py` file mentioned in PLAN-01's `files_modified` list was intentionally co-located in the service module — this is a documentation discrepancy, not a functional gap.

---

_Verified: 2026-04-03_
_Verifier: Claude (gsd-verifier)_
