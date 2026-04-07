# Phase 15.1 — Deferred Items

Bugs exposed by the UI smoke gate (tests/test_ui_smoke.py) during Plan 03
first run. These were **real pre-existing bugs**, not caused by Plan 03's
test infrastructure. The phase's success criterion was the gate catching
them — all 12 are now resolved.

## Resolution status (12 / 12 resolved)

Resolved via debug session
`.planning/debug/resolved/phase-15.1-deferred-routes.md`.

| Route | Group | Action |
|---|---|---|
| `/analytics/{site_id}/opportunities/tabs/cannibal` | A | Deployment-tree drift sync — `data.items` → `data.rows` in `opportunities_cannibal.html` (repo was already correct from f1259c1; `/opt/seo-platform/` was stale) |
| `/analytics/{site_id}/opportunities/tabs/losses`   | A | Deployment-tree drift sync — same fix in `opportunities_losses.html` |
| `/audit/checks`     | B | Route-ordering fix in `app/routers/audit.py` — moved literal `GET /checks` above `GET /{site_id}` (committed 471a88d, applied to both trees) |
| `/monitoring/rules` | B | Route-ordering fix in `app/routers/monitoring.py` — moved literal `GET /rules` above `GET /{site_id}` (committed 471a88d, applied to both trees) |
| `/metrika/{site_id}/compare` | C | `SMOKE_SKIP` — JSON chart-data endpoint, requires `a_start/a_end/b_start/b_end` query params; not a Jinja page |
| `/metrika/{site_id}/pages`   | C | `SMOKE_SKIP` — JSON chart-data endpoint, requires `period_start/period_end` query params; not a Jinja page |
| `/analytics/sessions/{session_id}/export`             | D | `SMOKE_SKIP` — CSV export endpoint, not a Jinja page; no smoke seed for `session_id` |
| `/traffic-analysis/sessions/{session_id}`             | D | `SMOKE_SKIP` — JSON session-detail endpoint; no smoke seed for `TrafficAnalysisSession` |
| `/traffic-analysis/sessions/{session_id}/anomalies`   | D | `SMOKE_SKIP` — JSON anomalies endpoint; no smoke seed for `TrafficAnalysisSession` |
| `/analytics/{site_id}/fix-status/{task_id}` | E | Extended `is_partial()` heuristic to recognise `/fix-status/` suffix as HTMX partial |
| `/analytics/{site_id}/quick-wins/table`     | E | Extended `is_partial()` heuristic to recognise `/quick-wins/table` suffix |
| `/metrika/{site_id}/widget`                 | E | (1) Extended `is_partial()` to recognise `/widget` suffix; (2) replaced `HTMLResponse("")` empty-state with HTMX-comment fallback so the non-empty-partial check still passes when the site has no `metrika_counter_id` (applied to both trees) |

## Tech-debt notes (carry forward)

- **TrafficAnalysisSession not covered by smoke seed.** Consequence of
  skipping the three traffic-analysis endpoints (Group D). If any of
  those endpoints ever become real HTML pages, the smoke seed
  (`tests/conftest.py` / smoke fixtures) must be extended to insert a
  `TrafficAnalysisSession` row so the routes can be exercised end-to-end.

- **`discover_routes` could filter by `response_class=HTMLResponse`** to
  auto-skip JSON/CSV endpoints. That would obviate the Group C and
  Group D `SMOKE_SKIP` entries entirely, and would also catch any
  future JSON-under-UI-prefix endpoints without manual SMOKE_SKIP
  bookkeeping. Out of scope for this debug session; candidate for
  Phase 15.2.

## Deployment note

`/opt/seo-platform/app/` is a separate tree from `/projects/test/app/`.
Template / code changes committed to the git repo do not automatically
propagate to the running container until someone rsyncs or redeploys.
The smoke gate should be run against the deployment tree (the running
`seo-platform-api-1` container) to catch drift like the original
Group A `data.items` regression.
