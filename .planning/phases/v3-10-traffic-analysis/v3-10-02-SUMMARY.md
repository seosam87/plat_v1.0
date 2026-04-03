---
phase: v3-10
plan: "02"
title: "Traffic analysis router, dashboard UI with Chart.js timeline"
subsystem: traffic-analysis
tags: [router, dashboard, chart-js, htmx, jinja2, traffic-analysis]
dependency_graph:
  requires: [v3-10-01]
  provides: [traffic-analysis-ui, traffic-analysis-endpoints]
  affects: [sites-detail]
tech_stack:
  added: []
  patterns: [stacked-bar-chart, doughnut-chart, period-comparison, bot-filter]
key_files:
  created: []
  modified:
    - app/routers/traffic_analysis.py
    - app/templates/traffic_analysis/index.html
decisions:
  - Session data loaded on-demand via fetch() to avoid slow page load with large datasets
  - Period comparison works on in-memory visits array (loaded from /visits endpoint)
  - Bot reason filter populated dynamically from actual bot visit data
  - Anomaly days highlighted via Chart.js tooltip callback (no plugin import needed)
metrics:
  duration: "8 min"
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_modified: 2
---

# Phase v3-10 Plan 02: Router and Dashboard UI Summary

**One-liner:** FastAPI traffic analysis router with 9 endpoints (visits/anomalies/bots/injections) plus a full Russian-language Jinja2+Chart.js dashboard with stacked timeline, source doughnut, bot table with filter, injection pattern cards, and period comparison.

## What Was Built

### Task 01: Traffic analysis router (4 new endpoints)

Added 4 missing endpoints to `app/routers/traffic_analysis.py` (total now 9 `@router` decorators):

- `GET /sessions/{session_id}/visits` — paginated visit data (up to 5,000 rows) for Chart.js
- `GET /sessions/{session_id}/anomalies` — anomaly detection using `detect_anomalies()` on DB visits grouped by day
- `GET /sessions/{session_id}/bots` — bot-flagged visits (up to 1,000), ordered by timestamp desc
- `GET /sessions/{session_id}/injections` — calls `detect_injection_patterns()` + `analyze_traffic_sources()`, returns patterns + source summary + top referers/landings

All endpoints require admin, return JSON, use async SQLAlchemy selects.

### Task 02: Comprehensive dashboard template

Replaced the minimal template with a full dashboard (`app/templates/traffic_analysis/index.html`):

1. **Header + source card** — Metrika date pickers + "Анализировать Метрику" button; file upload form for access.log
2. **Anomaly alert banner** — red if anomalies detected; green "Нет аномалий" if clean
3. **Session history table** — clickable rows that call `loadSession()` to fetch all session data
4. **Traffic timeline** — Chart.js stacked bar chart (organic/direct/referral/bot/injection), anomaly days annotated in tooltip
5. **Sources doughnut** — per-source counts with color legend + numeric grid
6. **Top referers** — horizontal bar list with proportional bars
7. **Top landing pages** — table with proportional bars and external links
8. **Bot detection** — table (timestamp/IP/UA/referer/URL/reason) with dynamic reason filter dropdown
9. **Injection patterns** — pattern cards with confidence badges; before/during/after comparison when anomaly dates known
10. **Period comparison** — two date range pickers, side-by-side stats (total/bots/organic/direct/referral) with delta %

## Deviations from Plan

None — plan executed exactly as written. The router already had 5 endpoints from wave 1; 4 new ones were added to reach 9.

## Self-Check: PASSED

- app/routers/traffic_analysis.py: FOUND
- app/templates/traffic_analysis/index.html: FOUND
- Commit 23dbd0a (router endpoints): FOUND
- Commit fdc718a (dashboard template): FOUND
