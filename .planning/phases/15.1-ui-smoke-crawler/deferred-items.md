# Phase 15.1 — Deferred Items

Bugs exposed by the UI smoke gate (tests/test_ui_smoke.py) during Plan 03
first run. These are **real pre-existing bugs**, not caused by Plan 03's
test infrastructure. They are out of scope for the smoke-crawler phase
itself — the phase's success criterion is the gate catching them.

Recommended: file as a follow-up phase / quick fixes.

## Failing routes (12)

| Route | Likely cause |
|---|---|
| `/analytics/sessions/{session_id}/export` | handler or template error |
| `/analytics/{site_id}/fix-status/{task_id}` | handler or template error |
| `/analytics/{site_id}/opportunities/tabs/cannibal` | partial render error |
| `/analytics/{site_id}/opportunities/tabs/losses` | partial render error |
| `/analytics/{site_id}/quick-wins/table` | handler or template error |
| `/audit/checks` | structural HTML / handler assertion |
| `/metrika/{site_id}/compare` | Metrika integration page |
| `/metrika/{site_id}/pages` | Metrika integration page |
| `/metrika/{site_id}/widget` | Metrika integration page |
| `/monitoring/rules` | structural HTML / handler assertion |
| `/traffic-analysis/sessions/{session_id}` | handler or template error |
| `/traffic-analysis/sessions/{session_id}/anomalies` | handler or template error |

## Fixed during execution (not deferred)

- `/analytics/{site_id}/opportunities` and `/opportunities/tabs/gaps` —
  `data.items` → `data.rows` in `opportunities_gaps.html`. The fix was
  already committed to the git repo (commit f1259c1) but the deployment
  tree at `/opt/seo-platform/app/templates/` was stale. Synced during
  Plan 03 verification run. Regression test
  `test_data_items_dict_collision_regression` now passes.

## Deployment note

`/opt/seo-platform/app/` is a separate tree from `/projects/test/app/`.
Template / code changes committed to the git repo do not automatically
propagate to the running container until someone rsyncs or redeploys.
The smoke gate should be run against the deployment tree to catch drift.
