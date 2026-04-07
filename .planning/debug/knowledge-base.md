# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## phase-15.1-deferred-routes — 12 UI smoke routes failing across 5 root-cause groups
- **Date:** 2026-04-07
- **Error patterns:** 422 uuid_parsing, 404 Session not found, builtin_function_or_method, missing <title>, partial returned empty body, data.items, route ordering, deployment drift, JSON endpoint under UI prefix, HTMLResponse empty
- **Root cause:** Five distinct issues — (A) deployment-tree drift between repo and /opt/seo-platform; (B) FastAPI route declaration order — literal segments after /{site_id} UUID get captured as path params; (C) JSON chart-data endpoints mounted under UI prefix; (D) JSON/CSV exports under UI prefix needing seed data the smoke fixture lacks; (E) is_partial() heuristic missed /widget /fix-status/ /quick-wins/table suffixes plus a HTMLResponse("") empty-body case.
- **Fix:** (A) rsync repo → deployment; (B) move literal routes above /{site_id} in audit.py and monitoring.py both trees; (C+D) SMOKE_SKIP allowlist with reason comments; (E) extend is_partial() suffix list and replace HTMLResponse("") with HTMX comment fallback.
- **Files changed:** app/routers/audit.py, app/routers/monitoring.py, app/routers/metrika.py (both /projects/test and /opt/seo-platform trees), tests/_smoke_helpers.py, tests/test_smoke_helpers.py, .planning/phases/15.1-ui-smoke-crawler/deferred-items.md
---
