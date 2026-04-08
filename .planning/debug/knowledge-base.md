# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## smoke-collection-shrinkage-146-to-69 — smoke test count dropped 146→69 after PEP 563 tier-2 fix
- **Date:** 2026-04-08
- **Error patterns:** smoke test count shrinkage, 146 to 69, _is_html_route, tier-2, PEP 563, annotations, get_type_hints, JSON endpoints included as HTML smoke, silent coverage drop
- **Root cause:** Pre-999.3, tier-2 of _is_html_route read endpoint.__annotations__["return"] which under PEP 563 (from __future__ import annotations) returns string literals ("dict", "list[dict]") instead of live types. get_origin("dict") is None so tier-2 fell through to tier-3 (conservative include), erroneously counting 38 JSON API endpoints as HTML routes. The "146" baseline was also misread — it was 97 smoke + 49 helpers combined, never smoke-only. After the 999.3 fix (typing.get_type_hints()), tier-2 resolves strings to live types and correctly excludes JSON endpoints. Correct baseline: 69 smoke + 51 helpers = 120 total.
- **Fix:** No code change needed — 999.3 fix was correct. Documentation-only: explanatory comment block added to tests/test_ui_smoke.py recording the true baseline and explaining the pre-999.3 inflation.
- **Files changed:** tests/test_ui_smoke.py
---

## phase-15.1-deferred-routes — 12 UI smoke routes failing across 5 root-cause groups
- **Date:** 2026-04-07
- **Error patterns:** 422 uuid_parsing, 404 Session not found, builtin_function_or_method, missing <title>, partial returned empty body, data.items, route ordering, deployment drift, JSON endpoint under UI prefix, HTMLResponse empty
- **Root cause:** Five distinct issues — (A) deployment-tree drift between repo and /opt/seo-platform; (B) FastAPI route declaration order — literal segments after /{site_id} UUID get captured as path params; (C) JSON chart-data endpoints mounted under UI prefix; (D) JSON/CSV exports under UI prefix needing seed data the smoke fixture lacks; (E) is_partial() heuristic missed /widget /fix-status/ /quick-wins/table suffixes plus a HTMLResponse("") empty-body case.
- **Fix:** (A) rsync repo → deployment; (B) move literal routes above /{site_id} in audit.py and monitoring.py both trees; (C+D) SMOKE_SKIP allowlist with reason comments; (E) extend is_partial() suffix list and replace HTMLResponse("") with HTMX comment fallback.
- **Files changed:** app/routers/audit.py, app/routers/monitoring.py, app/routers/metrika.py (both /projects/test and /opt/seo-platform trees), tests/_smoke_helpers.py, tests/test_smoke_helpers.py, .planning/phases/15.1-ui-smoke-crawler/deferred-items.md
---
