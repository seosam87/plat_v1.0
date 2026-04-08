---
status: resolved
trigger: "smoke test collection dropped from ~141 expected to 69 items after Phase 999.3 changes"
created: 2026-04-08T00:00:00Z
updated: 2026-04-08T02:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — H2 (_is_html_route too aggressive) is partially right, but the deeper
  truth is the opposite: the pre-999.3 tier-2 was BROKEN for PEP 563 codebases, causing JSON
  endpoints to be erroneously included. 999.3 fixed tier-2 correctly. The 69 count is right.
  The 146 count was wrong (it counted 38 JSON API endpoints as HTML smoke routes).
test: verified by inspecting all 38 excluded routes — none contain TemplateResponse; all return
  raw dict/list Python objects (genuine JSON)
expecting: no code change needed to _is_html_route; documentation update required
next_action: update planning docs and add api_json_smoke baseline; verify 69 is stable

## Symptoms

expected: ~141 items collected (146 minus 5 intentionally removed HTML routes)
actual: 69 items collected, 69 passed — silent coverage drop of ~72 routes
errors: no errors; just silent shrinkage
reproduction: docker compose up -d --force-recreate api && docker exec seo-platform-api-1 pytest tests/test_ui_smoke.py
started: after Phase 999.3 gap-closure commit 4c200b3 and force-recreate of api container

## Eliminated

- hypothesis: seed/fixture drift (H1)
  evidence: SMOKE_IDS is a static dict; discover_routes runs at collection time with no DB;
    seed fixture produces same entities every time. Route count is independent of seed.
  timestamp: 2026-04-08T01:00:00Z

- hypothesis: routes actually removed (H3)
  evidence: 113 UI GET routes still present. No routes deleted. git log shows only additions
    since 15.1 original commit.
  timestamp: 2026-04-08T01:00:00Z

- hypothesis: _is_html_route excluding legitimate HTML pages (H2, partial)
  evidence: All 38/40 excluded routes have template_in_func=False (no TemplateResponse in
    their source). All return raw Python dict/list objects. None serve Jinja2 templates.
  timestamp: 2026-04-08T01:00:00Z

## Evidence

- timestamp: 2026-04-08T01:00:00Z
  checked: docker exec ... pytest --collect-only tests/test_ui_smoke.py -q
  found: 69 tests collected; list of 68 parametrized routes + 1 regression test
  implication: current baseline is 69, not ~141

- timestamp: 2026-04-08T01:00:00Z
  checked: python script analyzing all 113 UI GET routes at each filter stage
  found: 113 total → 73 after _is_html_route → 68 after SMOKE_SKIP → 69 with regression test
    40 routes excluded by _is_html_route: 38 have dict/list return annotation, 2 have PlainTextResponse
  implication: the filter is working correctly

- timestamp: 2026-04-08T01:00:00Z
  checked: git show 4c200b3 (Phase 999.3 fix commit)
  found: pre-999.3 tier-2 used endpoint.__annotations__.get("return") which returns STRING
    "dict" or "list[dict]" under PEP 563 (from __future__ import annotations); get_origin("dict")
    returns None, isinstance("dict", type) is False => tier-2 fell through to tier-3 (conservative
    include) => all 38 JSON API endpoints were INCORRECTLY included in smoke suite
  implication: 999.3 fix was correct; it unexposed the pre-existing false positives

- timestamp: 2026-04-08T01:00:00Z
  checked: .planning/debug/resolved/phase-15.1-deferred-routes.md lines 54-56
  found: "tests/test_ui_smoke.py — 97 passed; tests/test_smoke_helpers.py — 49 passed; Total: 146 passed"
  implication: the "146" was never all from test_ui_smoke.py; it was 97 smoke + 49 helpers =
    146 combined. The 999.3 CONTEXT.md and PLAN.md incorrectly treated 146 as the smoke-only
    baseline. After 999.3 fix: 69 smoke + 51 helpers = 120 total (helpers grew by 2 tests).

- timestamp: 2026-04-08T01:00:00Z
  checked: template directories for all sections with excluded routes
  found: each section only has index.html (served by /{site_id} route with response_class=HTMLResponse,
    already included in smoke). Sub-routes (/tree, /sessions/{id}, /results, etc.) are HTMX
    data loaders called by JS on those pages — they return JSON, not HTML templates.
  implication: no HTML page coverage gap exists; 69 is the correct and complete HTML smoke count

- timestamp: 2026-04-08T01:00:00Z
  checked: inspect.getsource(endpoint) for all 38 dict/list-excluded routes
  found: template_in_func=False for ALL 38 routes — none contain TemplateResponse
  implication: strong evidence all 38 are genuine JSON endpoints, not mislabeled HTML pages

## Resolution

root_cause: |
  The "146" total in Phase 15.1 debug knowledge base was 97 (test_ui_smoke.py) + 49
  (test_smoke_helpers.py). Phase 999.3 CONTEXT.md/PLAN.md incorrectly referenced "146" as
  the test_ui_smoke.py-only baseline.

  Pre-999.3, tier-2 of _is_html_route used endpoint.__annotations__.get("return"), which
  under PEP 563 (from __future__ import annotations — the project-wide convention) returns
  string literals ("dict", "list[dict]") instead of live type objects. Since get_origin("dict")
  is None and isinstance("dict", type) is False, tier-2 silently fell through to tier-3
  (conservative include) for all 38 JSON API endpoints. This caused 38 JSON data routes to
  be erroneously included as "HTML smoke tests".

  After the 999.3 fix (commit 4c200b3: use typing.get_type_hints()), tier-2 correctly resolves
  PEP 563 strings to live type objects. "dict" → dict, "list[dict]" → list[dict]. Now tier-2
  properly excludes these 38 JSON endpoints. The 69 collected tests are exactly right.

  No HTML page coverage gap exists: every section's page view has response_class=HTMLResponse
  (caught by tier-1) and is included. The 38 excluded routes are HTMX/JS data endpoints
  returning raw JSON.

fix: |
  No code change to _is_html_route or smoke suite needed — the filter is correct.
  Documentation fix only: added explanatory comment block to tests/test_ui_smoke.py
  (after ROUTES/PARAM_MAP definitions) documenting:
    - correct baseline: 69 smoke + 51 helpers = 120 total
    - why the pre-999.3 "97" count was inflated (PEP 563 bug in tier-2)
    - why "146" was never the test_ui_smoke.py-alone count

verification: |
  - pytest --collect-only tests/test_ui_smoke.py: 69 tests collected (unchanged)
  - pytest tests/test_smoke_helpers.py tests/test_ui_smoke.py -q: 120 passed
  - All 38 excluded routes confirmed as genuine JSON API endpoints (template_in_func=False)
  - No HTML page coverage gap: all TemplateResponse routes have response_class=HTMLResponse
    and are included in smoke via tier-1

files_changed:
  - tests/test_ui_smoke.py (explanatory comment block after ROUTES/PARAM_MAP)
