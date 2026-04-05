---
phase: 10-reports-ads
plan: "04"
subsystem: ad-traffic-ui
tags: [ad-traffic, chart.js, htmx, report-service, comparison]
dependency_graph:
  requires: [app/models/ad_traffic.py, app/routers/reports.py existing upload+compare]
  provides: [ad_traffic_trend service function, GET /reports/.../trend endpoint, GET/POST /ui/ads/ UI routes, ads/index.html, ads/partials/comparison_table.html]
  affects: [app/navigation.py, app/main.py, app/services/report_service.py]
tech_stack:
  added: [chart.js@4.4.0 CDN]
  patterns: [HTMX multipart upload, HTMX partial swap, Chart.js line chart with fetch, Jinja2 conditional Tailwind classes]
key_files:
  created:
    - app/templates/ads/index.html
    - app/templates/ads/partials/comparison_table.html
    - tests/test_ad_traffic.py
  modified:
    - app/services/report_service.py
    - app/routers/reports.py
    - app/main.py
    - app/navigation.py
decisions:
  - "ad_traffic_trend uses raw SQL with date_trunc for weekly/monthly grouping; returns Chart.js-compatible labels+datasets dict"
  - "CR% zero-division guard returns 0.0 when sessions==0; CPC returns None when conversions==0; delta_cpc_pct also None in that case"
  - "Chart.js 4.4.0 via CDN; trend loaded via fetch() on DOMContentLoaded; granularity toggle uses classList.add/remove('btn-primary')"
  - "Comparison table delta cells use Jinja2 conditional Tailwind classes (text-emerald-600/text-red-600/text-gray-500) - zero inline style="
  - "Navigation entry 'Рекламный трафик' added to analytics section in navigation.py pointing to /ui/ads/{site_id}"
metrics:
  duration: "199s"
  completed_date: "2026-04-05"
  tasks_completed: 2
  files_changed: 7
---

# Phase 10 Plan 04: Ad Traffic UI Summary

Ad traffic module built: CSV upload, period comparison with CR% and cost-per-conversion (D-11), and weekly/monthly Chart.js trend chart (D-12) — all sourced from Yandex Direct only per D-10.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extend ad_traffic_comparison with CR%/CPC, add trend endpoint | 52937c9 | app/services/report_service.py, app/routers/reports.py, tests/test_ad_traffic.py |
| 2 | Build ad traffic UI page with upload, comparison, and Chart.js | eb25cb4 | app/main.py, app/navigation.py, app/templates/ads/index.html, app/templates/ads/partials/comparison_table.html |

## What Was Built

### Service Layer (report_service.py)
- Extended `ad_traffic_comparison()` to compute `cr_a`, `cr_b`, `delta_cr_pct`, `cpc_a`, `cpc_b`, `delta_cpc_pct` per source
- Zero-division guards: CR% returns 0.0 when sessions==0; CPC returns None when conversions==0
- New `ad_traffic_trend(db, site_id, granularity)` using raw SQL `date_trunc` for weekly/monthly grouping, returns Chart.js-compatible `{"labels": [...], "datasets": [...]}`

### API Layer (reports.py)
- New `GET /reports/sites/{site_id}/ad-traffic/trend?granularity=weekly|monthly` endpoint

### UI Layer (main.py)
- `GET /ui/ads/{site_id}` — renders `ads/index.html` with site context
- `POST /ui/ads/{site_id}/compare` — HTMX partial returning `ads/partials/comparison_table.html`

### Templates
- `ads/index.html`: CSV upload form (HTMX multipart), period comparison form (HTMX partial swap), Chart.js trend chart with weekly/monthly toggle
- `ads/partials/comparison_table.html`: 13-column table with Sessions, Conversions, CR%, CPC columns each with Period A, Period B, Delta% — delta cells use conditional Tailwind classes

### Tests (5 passing)
- `test_comparison_includes_cr_and_cpc_fields` — verifies cr_a, cr_b, cpc_a, cpc_b present with correct values
- `test_cr_handles_zero_sessions` — CR% returns 0.0 when sessions==0
- `test_cpc_handles_zero_conversions` — CPC returns None when conversions==0
- `test_trend_returns_labels_and_datasets` — trend output shape validated
- `test_trend_empty_returns_empty_labels` — empty DB yields empty labels/datasets

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Minor Implementation Notes

- `_delta()` helper moved outside the inner loop in `ad_traffic_comparison` to avoid repeated redefinition (Rule 1 - clean code)
- Trend datasets include `borderColor`, `backgroundColor`, and `tension` for Chart.js rendering quality; palette matches Tailwind indigo-500/emerald-500/amber-500/red-500

## Known Stubs

None — all data flows from real DB queries via the existing `ad_traffic` table.

## Self-Check: PASSED

- `app/templates/ads/index.html` — FOUND
- `app/templates/ads/partials/comparison_table.html` — FOUND
- `tests/test_ad_traffic.py` — FOUND
- Commit 52937c9 — FOUND
- Commit eb25cb4 — FOUND
- All 5 tests pass: pytest tests/test_ad_traffic.py — 5 passed
