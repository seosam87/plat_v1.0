---
phase: v4-03-section-sites
plan: "02"
subsystem: crawl-templates
tags: [tailwind, htmx, crawl, templates, ui-migration]
dependency_graph:
  requires: [v4-03-01]
  provides: [crawl-history-tailwind, crawl-feed-tailwind]
  affects: [crawl-ui]
tech_stack:
  added: []
  patterns: [tailwind-card, tailwind-badge, htmx-swap-tbody]
key_files:
  created: []
  modified:
    - app/templates/crawl/history.html
    - app/templates/crawl/feed.html
    - app/templates/crawl/feed_rows.html
decisions:
  - "Start Crawl button uses hx-post /sites/site_id/crawl with hx-swap=none — fire-and-forget HTMX post matching the existing trigger_crawl endpoint in sites router"
  - "Filter buttons in feed.html use conditional Tailwind class rendering (bg-indigo-600 active vs bg-gray-100 inactive) — no JS required"
  - "feed_rows.html partial uses truncate class instead of word-break:break-all for long URLs — cleaner Tailwind approach"
metrics:
  duration: "~2 min"
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_modified: 3
---

# Phase v4-03 Plan 02: Crawl Templates Tailwind Migration Summary

Migrated three crawl templates (history, feed, feed_rows) from inline CSS/legacy classes to Tailwind CSS with consistent v4 badge palette and zero inline `style=` attributes; added "Запустить краул" HTMX button to crawl history page.

## What Was Built

Three crawl templates fully migrated to Tailwind CSS:

1. **app/templates/crawl/history.html** — Crawl history page rewritten with Tailwind card layout, Tailwind-styled table with `min-w-full divide-y divide-gray-200`, status badges using emerald/amber/red palette, and a new "Запустить краул" button that fires `hx-post="/sites/{{ site.id }}/crawl"` with `hx-swap="none"` (per D-11).

2. **app/templates/crawl/feed.html** — Change feed page rewritten with Tailwind card layout, filter buttons using conditional `bg-indigo-600 text-white` (active) vs `bg-gray-100 text-gray-700` (inactive) styling, all HTMX filter attributes preserved (`hx-get`, `hx-target="#pages-tbody"`, `hx-swap="innerHTML"`, `hx-push-url="false"`).

3. **app/templates/crawl/feed_rows.html** — HTMX partial rewritten with `px-3 py-2` cell padding, `max-w-xs truncate` for URL cells, and consistent v4 badge classes throughout.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Rewrite crawl/history.html to Tailwind + add Start Crawl button | 30dcf81 | app/templates/crawl/history.html |
| 2 | Rewrite crawl/feed.html and feed_rows.html to Tailwind | 9f333a0 | app/templates/crawl/feed.html, app/templates/crawl/feed_rows.html |

## Decisions Made

- **Start Crawl button endpoint:** Uses existing `POST /sites/{site_id}/crawl` endpoint in sites router (not `/ui/sites/{site_id}/crawl`) — matches the trigger_crawl handler signature.
- **hx-swap="none" for crawl trigger:** Crawl is fire-and-forget; no DOM update needed on success. Button shows loading state via inline `onclick` + `hx-on::after-request`.
- **Back navigation:** history.html links to `/ui/sites` (Все сайты); feed.html links back to `/ui/sites/{{ job.site_id }}/crawls` (История краулов).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all templates render live data from router context variables (`site`, `jobs`, `job`, `page_rows`, `filter`).

## Self-Check

- FOUND: app/templates/crawl/history.html
- FOUND: app/templates/crawl/feed.html
- FOUND: app/templates/crawl/feed_rows.html
- FOUND: .planning/phases/v4-03-section-sites/v4-03-02-SUMMARY.md
- FOUND commit: 30dcf81
- FOUND commit: 9f333a0

## Self-Check: PASSED
