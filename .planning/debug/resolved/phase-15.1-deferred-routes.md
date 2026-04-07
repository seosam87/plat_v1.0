---
status: resolved
trigger: "Phase 15.1 — fix or checkpoint the 12 UI routes failing the smoke gate"
created: 2026-04-07
updated: 2026-04-07
---

## Current Focus

hypothesis: 12 failures cluster into 5 distinct root causes (A–E)
test: per-group inspection of routers + templates
expecting: each group fixable independently or surfaced as checkpoint
next_action: RESOLVED — all 12 routes addressed; smoke + helper tests green

## Symptoms

expected: All 12 routes return 200/redirect and pass smoke body+structural checks.
actual: 12 distinct failures, captured via `pytest tests/test_ui_smoke.py --tb=line`.
errors: see Evidence below
reproduction: docker exec seo-platform-api-1 python -m pytest tests/test_ui_smoke.py
started: pre-existing, exposed by Phase 15.1 smoke gate

## Eliminated

(none — all hypotheses confirmed)

## Evidence

- Group A — data.items dict-collision in templates (same class as f1259c1):
  - opportunities_cannibal.html:14 — `{% for item in data.items %}` → TypeError
  - opportunities_losses.html:25 — `{% for item in data.items %}` → TypeError
  - Repo was already correct (f1259c1); /opt/seo-platform tree was stale.

- Group B — literal path segment captured by UUID `{site_id}` (route ordering bug):
  - /audit/checks → 422 uuid_parsing on `site_id="checks"`
  - /monitoring/rules → 422 uuid_parsing on `site_id="rules"`

- Group C — required query params, no defaults, JSON response (route-design 422):
  - /metrika/{site_id}/compare — JSON chart-data, requires a_start/a_end/b_start/b_end
  - /metrika/{site_id}/pages — JSON chart-data, requires period_start/period_end

- Group D — JSON/CSV endpoints under UI prefix, depend on TrafficAnalysisSession seed:
  - /analytics/sessions/{session_id}/export — CSV export, 404 (no seed)
  - /traffic-analysis/sessions/{session_id} — JSON, 404 "Session not found"
  - /traffic-analysis/sessions/{session_id}/anomalies — JSON, 404 "Session not found"

- Group E — partials not recognised by is_partial() heuristic:
  - /analytics/{site_id}/fix-status/{task_id} — HTMX row swap, no <title>
  - /analytics/{site_id}/quick-wins/table — HTMX table swap, no <title>
  - /metrika/{site_id}/widget — HTMX widget partial; also returned empty
    body when site has no metrika_counter_id (now HTMX comment)

- Final verification (in seo-platform-api-1 container against seo_platform_test):
  - tests/test_ui_smoke.py — 97 passed
  - tests/test_smoke_helpers.py — 49 passed
  - Total: 146 passed, 0 failed

## Resolution

root_cause:
  A: deployment-tree drift (repo had data.rows fix from f1259c1, /opt/... stale)
  B: route declaration order — /{site_id} UUID shadows literal /checks and /rules
  C: Metrika chart-data endpoints (/pages, /compare) are JSON APIs under UI prefix, require query params — not real Jinja pages
  D: sessions endpoints are JSON/CSV APIs under UI prefix + need TrafficAnalysisSession seed rows — not real Jinja pages
  E: is_partial() heuristic too narrow — missed /quick-wins/table, /fix-status/, /widget; widget also had empty-body empty-state
fix:
  A: synced opportunities_cannibal.html + opportunities_losses.html from repo to deployment (no repo commit needed — repo already correct)
  B: moved GET /checks above GET /{site_id} in audit.py; GET /rules above GET /{site_id} in monitoring.py (both trees) — commit 471a88d
  C: SMOKE_SKIP added with reason — JSON chart-data endpoints
  D: SMOKE_SKIP added with reason — JSON/CSV exports + missing seed
  E1: extended is_partial() to recognise /widget, /fix-status/, /quick-wins/table suffixes; updated unit tests
  E4: /metrika/{site_id}/widget empty-state now returns HTMX comment instead of empty body (both trees)
verification: 146 / 146 tests pass in container against seo_platform_test (97 smoke + 49 helper). User-confirmed approval received before commits.
files_changed:
  - /opt/seo-platform/app/templates/analytics/partials/opportunities_cannibal.html (deployment sync, no repo commit)
  - /opt/seo-platform/app/templates/analytics/partials/opportunities_losses.html (deployment sync, no repo commit)
  - /projects/test/app/routers/audit.py (commit 471a88d)
  - /opt/seo-platform/app/routers/audit.py (deployment sync of 471a88d)
  - /projects/test/app/routers/monitoring.py (commit 471a88d)
  - /opt/seo-platform/app/routers/monitoring.py (deployment sync of 471a88d)
  - /projects/test/tests/_smoke_helpers.py (E1 + C/D commits)
  - /projects/test/tests/test_smoke_helpers.py (E1 commit)
  - /projects/test/app/routers/metrika.py (E4 commit)
  - /opt/seo-platform/app/routers/metrika.py (deployment sync of E4)
  - /projects/test/.planning/phases/15.1-ui-smoke-crawler/deferred-items.md
commits:
  - 471a88d fix(routers): declare literal /checks and /rules before /{site_id}
  - (E1) test(smoke): extend is_partial() to recognise widget/fix-status/quick-wins-table
  - (E4) fix(metrika): return HTMX comment instead of empty body when counter unconfigured
  - (C+D) test(smoke): SMOKE_SKIP five JSON/CSV endpoints under UI prefixes
  - (docs) docs(15.1): record deferred-items resolution + tech-debt notes
