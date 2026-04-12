---
phase: 31-pages-app
plan: "01"
subsystem: mobile-pages
tags: [mobile, pages, htmx, crawl-audit, jinja2]
dependency_graph:
  requires: []
  provides: [PAG-01-pages-list, PAG-01-page-detail]
  affects: [base_mobile.html, mobile.py]
tech_stack:
  added: []
  patterns: [htmx-outerHTML-pagination, cookie-site-selection, latest-crawl-subquery]
key_files:
  created:
    - app/templates/mobile/pages/index.html
    - app/templates/mobile/pages/partials/pages_content.html
    - app/templates/mobile/pages/partials/page_row.html
    - app/templates/mobile/pages/partials/page_detail.html
  modified:
    - app/templates/base_mobile.html
    - app/routers/mobile.py
decisions:
  - "Used router (not mobile_router) per actual variable name in mobile.py"
  - "Pagination Загрузить ещё uses hx-swap=outerHTML on itself (Pitfall 5 avoidance)"
  - "Latest crawl subquery uses scalar_subquery() — avoids JOIN complexity"
metrics:
  duration_min: 2
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_modified: 6
---

# Phase 31 Plan 01: Pages App — List + Detail Summary

**One-liner:** Mobile pages list screen with SQLAlchemy latest-crawl subquery, 4 HTMX audit tabs with count-badges, outerHTML pagination, and inline expand/collapse detail with conditional quick fix buttons.

## What Was Built

### Task 1: Bottom nav + /m/pages endpoint + list templates

- Added 5th bottom nav tab "Страницы" (Heroicons document-text icon) to `base_mobile.html` with `active_tab == 'pages'` active state
- Created `GET /m/pages` endpoint in `mobile.py` with:
  - Site dropdown with cookie persistence (`m_pages_site_id`, 30-day TTL)
  - Latest-crawl subquery (`CrawlJob.finished_at.desc()`, `scalar_subquery()`)
  - 4 count queries for tab badges (all, no_schema, no_toc, noindex)
  - Tab-filtered page query with `.limit(21).offset()` for has_more detection
  - HTMX partial response vs full page based on `HX-Request` header
- Created `mobile/pages/index.html` — extends base_mobile.html, site dropdown, `#pages-content` div, bulk action buttons outside swap target
- Created `mobile/pages/partials/pages_content.html` — 4 filter tabs with count-badges, empty state with Запустить краулинг CTA, page cards list, outerHTML-swap Загрузить ещё
- Created `mobile/pages/partials/page_row.html` — compact row with schema/toc/index status icons (checkmarks/x-marks/exclamation in semantic colors)

### Task 2: Inline expand detail + collapse

- Created `GET /m/pages/detail/{page_id}` returning `page_detail.html` with full page metadata
- Created `GET /m/pages/detail/{page_id}/collapsed` returning `page_row.html` (collapse handler)
- Created `mobile/pages/partials/page_detail.html` with:
  - `border-l-2 border-indigo-600` expanded state visual cue
  - 2-column metadata grid: title, h1, meta_description, word_count, http_status
  - Conditional quick fix buttons: "Добавить TOC" (if `not page.has_toc`), "Добавить Schema" (if `not page.has_schema`)
  - "Изменить Title / Meta" link to `/m/pages/{site_id}/{page_id}/edit`
  - "Создать задачу" link to `/m/tasks/new?mode=task&page_id=...`
  - "Свернуть ▲" collapse trigger (hx-get to collapsed endpoint)

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Note:** Plan referenced `mobile_router` as the router variable name, but actual code uses `router`. Used `router` per the existing codebase pattern (no deviation, just corrected reference).

## Known Stubs

- Quick fix endpoints (`POST /m/pages/fix/{page_id}/toc`, `POST /m/pages/fix/{page_id}/schema`) are referenced in buttons but not implemented — will be addressed in Plan 02 or 03 per phase scope
- Bulk operation endpoints (`/m/pages/bulk/schema/confirm`, `/m/pages/bulk/toc/confirm`) are linked but not implemented — future plan scope

## Self-Check: PASSED

- `/opt/seo-platform/app/templates/mobile/pages/index.html` — FOUND
- `/opt/seo-platform/app/templates/mobile/pages/partials/pages_content.html` — FOUND
- `/opt/seo-platform/app/templates/mobile/pages/partials/page_row.html` — FOUND
- `/opt/seo-platform/app/templates/mobile/pages/partials/page_detail.html` — FOUND
- Commit `d5e3609` (Task 1) — verified
- Commit `a64c3f6` (Task 2) — verified
- All 17 acceptance criteria passed
