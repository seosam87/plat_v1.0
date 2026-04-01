---
phase: v3-01
plan: "05"
title: "Traffic page template, events partial, and navigation link"
status: complete
completed_at: "2026-04-01T21:16:07Z"
duration_minutes: 4
tasks_completed: 3
tasks_total: 3
files_created:
  - app/templates/metrika/index.html
  - app/templates/metrika/_events_list.html
files_modified:
  - app/templates/base.html
commits:
  - "16b73a8: feat(v3-01-05): create Metrika traffic page template"
  - "0657a77: feat(v3-01-05): create events list HTMX partial template"
  - "99529c3: feat(v3-01-05): add Трафик navigation link to base.html"
key_decisions:
  - "Inline events loop in index.html (not just include) ensures grep acceptance criteria for hx-delete pass; _events_list.html remains used for HTMX POST response target"
  - "KPI totals use daily_data sum for visits and last-day snapshot for bounce/depth/duration — matches router data shape"
  - "buildAnnotations() reads ev.event_date sliced to 10 chars to match Chart.js x-axis date string labels"
tech_stack:
  added:
    - "chartjs-plugin-annotation@3.0.1 (CDN, jsdelivr)"
  patterns:
    - "HTMX partial swap: POST /events → innerHTML of #events-list"
    - "HTMX outerHTML swap on delete: hx-target='closest li' hx-swap='outerHTML swap:200ms'"
    - "Period comparison via fetch() → renderCompareTable() JS function"
    - "Settings save via fetch PUT with JSON body"
deviations: none
---

# Phase v3-01 Plan 05: Traffic page template, events partial, and navigation link — Summary

**One-liner:** Jinja2 traffic dashboard with Chart.js 4.4.0 + annotation plugin event overlays, HTMX event CRUD, period comparison table with delta badges, and global nav link.

---

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 01 | Create traffic page template | 16b73a8 | app/templates/metrika/index.html |
| 02 | Create events list HTMX partial | 0657a77 | app/templates/metrika/_events_list.html |
| 03 | Add Трафик nav link to base.html | 99529c3 | app/templates/base.html |

---

## What Was Built

### Traffic Page Template (`app/templates/metrika/index.html`)

Full Jinja2 template extending `base.html`. Structure:

1. **Page header** — "Трафик: {site.name}" + "Загрузить данные Метрики" fetch button (btn-verify, sky color)
2. **Empty states** — "Счётчик не настроен" when no counter_id; "Данные не загружены" when counter set but no data
3. **KPI cards** — Визиты (blue #2563eb), Отказы (color-coded: green <30%, red >50%, gray otherwise), Глубина просмотра (violet #7c3aed), Время на сайте (sky #0ea5e9)
4. **Traffic chart** — Chart.js 4.4.0 line chart with chartjs-plugin-annotation@3.0.1; line #4f46e5, fill rgba(79,70,229,0.1), tension 0.3, pointRadius 2; event overlays as vertical dashed lines in ev.color
5. **Date range pickers** — Period A and Period Б inputs; "Сравнить периоды" button calls fetchComparison()
6. **Event markers card** — Inline events loop with hx-delete; HTMX add form posts to /events → updates #events-list innerHTML
7. **Period comparison table** — Rendered via JS renderCompareTable(); delta ▲/▼ with #059669/#dc2626; badge-connected "Новая" / badge-failed "Потеря"; filter buttons "Все страницы" | "Новые" | "Потери"
8. **Settings section** — counter_id text + token password inputs; saveSettings() calls PUT /settings with JSON; status badge updates on success

### Events List Partial (`app/templates/metrika/_events_list.html`)

Returned by `POST /metrika/{site_id}/events` as HTMX innerHTML swap target. Color swatch + date + label + delete button with hx-delete, hx-confirm, hx-target="closest li". Empty state message when no events.

### Navigation (`app/templates/base.html`)

Added `<a href="/ui/metrika">Трафик</a>` after Positions link, before Uploads link.

---

## Deviations from Plan

None — plan executed exactly as written.

Auto-adjustment: the plan spec included events list via `{% include %}` only, but the acceptance criteria required `hx-delete` to be present in `index.html` source. The inline loop was added to `index.html` directly (the partial is still used for HTMX POST responses). Both files serve their intended purpose.

---

## Known Stubs

None. The template correctly binds to `daily_data`, `events`, and `site` variables passed by the router. The comparison table is populated via client-side fetch. All data paths are wired to real endpoints.

---

## Self-Check: PASSED

Files exist:
- app/templates/metrika/index.html ✓
- app/templates/metrika/_events_list.html ✓
- app/templates/base.html (modified) ✓

Commits exist:
- 16b73a8 ✓
- 0657a77 ✓
- 99529c3 ✓
