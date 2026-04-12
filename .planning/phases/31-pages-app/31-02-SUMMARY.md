---
phase: 31-pages-app
plan: "02"
subsystem: mobile-pipeline
tags: [mobile, pipeline, htmx, 2-tap, celery, wp-push, serp-preview]
dependency_graph:
  requires: [31-01]
  provides: [PAG-02-pipeline-queue, PAG-03-title-meta-edit]
  affects: [app/routers/mobile.py, mobile templates]
tech_stack:
  added: []
  patterns: [2-tap-confirmation, markupsafe-xss-escape, celery-dispatch-from-route, 303-redirect-after-post]
key_files:
  created:
    - app/templates/mobile/pipeline/index.html
    - app/templates/mobile/pipeline/partials/pipeline_content.html
    - app/templates/mobile/pipeline/partials/job_card.html
    - app/templates/mobile/pages/edit.html
  modified:
    - app/routers/mobile.py
decisions:
  - "Used router (not mobile_router) — variable name in mobile.py per Plan 01 decision"
  - "markupsafe.escape() applied per-line BEFORE wrapping in ins/del (RESEARCH Pitfall 2)"
  - "wp_post_id resolved from latest WpContentJob for page_url, not from Page model (RESEARCH Pitfall 1)"
  - "Site.url used for SERP preview domain — Site model has no domain field"
  - "Reject sets status=rolled_back and returns empty div (job removed from list)"
  - "_parse_diff_lines skips +++ --- @@ header lines to show only content diffs"
metrics:
  duration_min: 5
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_modified: 5
---

# Phase 31 Plan 02: Pipeline Approve Queue + Title/Meta Edit Summary

**One-liner:** Mobile pipeline approve queue (/m/pipeline) with HTML diff rendering, 2-tap approve/reject/rollback via JS+HTMX, Celery task dispatch, and /m/pages/{site_id}/{page_id}/edit with live SERP preview.

## What Was Built

### Task 1: Pipeline approve queue — endpoints + templates + 2-tap JS

- Added `GET /m/pipeline` endpoint in `mobile.py` with:
  - Site cookie `m_pages_site_id` shared with /m/pages
  - Status filter: awaiting_approval / pushed / failed
  - `_parse_diff_lines()` helper that escapes each line with `markupsafe.escape()` BEFORE wrapping in `<ins>`/`<del>` (XSS protection per Pitfall 2)
  - 3 count queries for tab badges
  - HTMX partial vs full page response
- Added `POST /m/pipeline/{job_id}/approve` — sets `job.status = JobStatus.approved`, commits, dispatches `push_to_wp.delay(str(job.id))`, returns updated job card with HX-Trigger toast
- Added `POST /m/pipeline/{job_id}/reject` — sets `job.status = JobStatus.rolled_back`, returns empty div (removes card from list), HX-Trigger toast
- Added `POST /m/pipeline/{job_id}/rollback` — dispatches `rollback_job.delay(str(job.id))`, returns updated job card, HX-Trigger toast
- Created `mobile/pipeline/index.html` — extends base_mobile.html, site dropdown with HX partial swap, 3 status tabs with count badges (amber/green/red colors), `#pipeline-content` div, `initTwoTapButton` JS with 2-second setTimeout, `htmx:afterSettle` reinitializer for swapped content
- Created `mobile/pipeline/partials/pipeline_content.html` — loops jobs with job_card include, per-tab empty states
- Created `mobile/pipeline/partials/job_card.html` — aria-live="polite" container, URL/type/status badge header, collapsible diff block with "Показать весь diff" toggle, 2-tap action buttons per status (approve+reject for awaiting_approval, rollback for pushed, retry for failed)

### Task 2: Title/Meta edit screen with SERP preview

- Added `GET /m/pages/{site_id}/{page_id}/edit` — loads page+site, verifies site_id match
- Added `POST /m/pages/{site_id}/{page_id}/edit` — validates title not empty (error rendered inline), resolves `wp_post_id` from latest `WpContentJob` for matching `page_url` (not from Page model — Pitfall 1 avoidance), computes diff via `compute_content_diff`, creates `WpContentJob` with `post_type="title_meta"`, `status=JobStatus.awaiting_approval`, redirects 303 to `/m/pipeline`
- Created `mobile/pages/edit.html` — extends base_mobile.html, back link, SERP preview block (serp-title, serp-url, serp-desc), character counters (title/60, meta/160), form with title input (`maxlength=120`) and meta textarea (`maxlength=300`), submit button, live JS updating preview on input events

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes on Variable Names

The plan verify script references `mobile_router` but the actual variable in `mobile.py` is `router` (documented in Plan 01 SUMMARY). Verify was run using `from app.routers.mobile import router as mobile_router` and all routes confirmed present.

## Known Stubs

None — all functionality is wired:
- Pipeline endpoint queries real `WpContentJob` records from DB
- Approve dispatches real `push_to_wp.delay` Celery task
- Rollback dispatches real `rollback_job.delay` Celery task
- Edit creates real `WpContentJob` with `awaiting_approval` status

## Self-Check: PASSED

All created files confirmed present. Both commits (a95e78a, ca5d9c5) confirmed in git log.
