---
phase: v4-03-section-sites
plan: "01"
subsystem: ui-navigation
tags: [navigation, sites, tailwind, htmx, schedule]
dependency_graph:
  requires: [v4-01-navigation-foundation]
  provides: [sites-schedule-page, sites-nav-update, sites-metrics-table]
  affects: [dashboard, sidebar]
tech_stack:
  added: []
  patterns: [tailwind-card, htmx-schedule-update, per-site-metrics]
key_files:
  created:
    - app/templates/sites/schedule.html
  modified:
    - app/navigation.py
    - app/main.py
    - app/templates/sites/index.html
    - app/templates/dashboard/index.html
decisions:
  - sites-detail removed; NAV_SECTIONS now has 3 children: sites-list, sites-crawls, sites-schedule
  - site_metrics computed per-site in ui_sites handler using count_keywords + SQL counts
  - ui_site_detail replaced with 301 redirect to /ui/sites (template retained)
  - Sidebar disabled-link mechanism from v4-01 handles Краулы/Расписание without site selected
metrics:
  duration: ~8 min
  completed: "2026-04-03T21:17:43Z"
  tasks: 2
  files: 5
---

# Phase v4-03 Plan 01: Sites Navigation + List Redesign + Schedule Page Summary

**One-liner:** Sidebar Сайты updated to 3 children (Список/Краулы/Расписание), site list rewritten with Tailwind + per-site keyword/crawl/task metrics columns, new schedule management page at /ui/sites/{site_id}/schedule, detail page 301-redirected.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update NAV_SECTIONS + site list redesign with metrics + schedule page route | 541db7d | app/navigation.py, app/main.py, app/templates/sites/index.html, app/templates/sites/schedule.html, app/templates/dashboard/index.html |
| 2 | Site-dependent placeholder for Краулы and Расписание when no site selected | (no code change) | — |

## What Was Built

### NAV_SECTIONS Update (app/navigation.py)
- Removed `sites-detail` child from the sites section
- Added `sites-schedule` child with URL `/ui/sites/{site_id}/schedule`
- Sites section now has exactly 3 children: `sites-list`, `sites-crawls`, `sites-schedule`

### Site List Redesign (app/templates/sites/index.html)
- Full rewrite from old CSS-class + inline style pattern to explicit Tailwind utilities
- Zero `style=` attributes remain
- Added 3 new metric columns: Keywords (indigo), Crawls (emerald), Tasks (amber)
- Site name is no longer a link to /detail — displayed as styled text
- All HTMX attributes preserved exactly (hx-post, hx-patch, hx-delete, hx-target, hx-swap, hx-confirm)
- Added Schedule and Edit quick-action buttons in the Actions column

### Site List Metrics (app/main.py ui_sites handler)
- Added `site_metrics` dict computed from `count_keywords()` + SQL count on `CrawlJob` and `SeoTask`
- Passed as `site_metrics` context variable to the template

### Schedule Page (app/templates/sites/schedule.html + app/main.py ui_site_schedule)
- New page at `/ui/sites/{site_id}/schedule`
- Two schedule controls: crawl schedule (HTMX hx-put) and position check schedule (JS fetch)
- Tailwind card layout with responsive 2-column grid
- Loads current schedule values from `get_schedule()` and `get_position_schedule()` services

### Detail Page Redirect (app/main.py)
- `ui_site_detail` handler replaced with a single-line 301 redirect to `/ui/sites`
- Template file `detail.html` retained (not deleted)

### Dashboard Update (app/templates/dashboard/index.html)
- Sites overview table site name links changed from `/ui/sites/{id}/detail` to `/ui/sites`

## Task 2: No Code Changes Required
The existing `build_sidebar_sections()` mechanism (from v4-01) already handles site-dependent URLs correctly:
- When `site_id=None`: URLs with `{site_id}` resolve to `#` and `disabled=True`
- When `site_id` provided: URLs resolved with the actual UUID

Verified with automated test against both `sites-crawls` and `sites-schedule` children.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All metric values are computed from live DB queries. Schedule values are fetched from the schedule service.

## Self-Check: PASSED
- app/navigation.py: sites section has 3 children, no sites-detail
- app/templates/sites/index.html: 0 style= attributes, contains site_metrics
- app/templates/sites/schedule.html: exists, contains Расписание and hx-put
- app/main.py: contains ui_site_schedule, site_metrics, 301 RedirectResponse for detail
- app/templates/dashboard/index.html: no /detail links
- Commit 541db7d verified in git log
