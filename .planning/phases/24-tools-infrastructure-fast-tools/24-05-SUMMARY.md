---
phase: 24-tools-infrastructure-fast-tools
plan: "05"
subsystem: tools-router
tags: [tools, auth, tests, integration]
dependency_graph:
  requires: ["24-02", "24-03", "24-04"]
  provides: ["tools-router-complete", "tools-auth-enforced", "tools-tests"]
  affects: ["app/routers/tools.py", "app/templates/tools/", "tests/test_tools_router.py"]
tech_stack:
  added: []
  patterns:
    - "UIAuthMiddleware bypass via JWT cookie in tests (dependency_overrides insufficient for middleware)"
    - "AsyncMock DB session for router tests without live DB"
    - "Per-tool Jinja2 template directories (commercialization, meta-parser) mirroring relevant-url pattern"
key_files:
  created:
    - tests/test_tools_router.py
    - app/templates/tools/commercialization/index.html
    - app/templates/tools/commercialization/results.html
    - app/templates/tools/commercialization/partials/job_status.html
    - app/templates/tools/meta-parser/index.html
    - app/templates/tools/meta-parser/results.html
    - app/templates/tools/meta-parser/partials/job_status.html
  modified:
    - app/routers/tools.py
    - app/templates/tools/index.html
decisions:
  - "Tests mock UIAuthMiddleware by passing JWT cookie alongside get_current_user override"
  - "Per-tool templates created for commercialization and meta-parser (copies of generic tool_landing.html)"
metrics:
  duration: "10 min"
  completed_date: "2026-04-10"
  tasks: 2
  files: 9
requirements:
  - TOOL-INFRA-01
  - TOOL-INFRA-02
---

# Phase 24 Plan 05: Tools Router Integration Summary

**One-liner:** Complete tools section integration — authenticated index with DB job count badges, all 7 handlers secured, 12 router tests covering all endpoints, auth, and ownership.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | tools_index: job counts from DB + get_current_user on all 7 handlers + index.html badge | a54f3c1 | app/routers/tools.py, app/templates/tools/index.html |
| 2 | Router integration tests (12 tests) + missing tool templates | 5c66f85 | tests/test_tools_router.py, 6 new templates |

## What Was Built

### Task 1: Router Authentication + Job Count Badges

`tools_index` was the only handler missing `get_current_user`. Added it with DB queries:
- Queries `func.count(Model.id).where(Model.user_id == user.id)` for all 3 job models
- Passes `job_count` per tool to index.html
- index.html renders a gray pill badge ("N заданий") when job_count > 0

All 7 route handlers now have `Depends(get_current_user)`. Verification: `grep -c "Depends(get_current_user)" app/routers/tools.py` returns 7.

### Task 2: Router Integration Tests

12 tests in `tests/test_tools_router.py` covering:
- `test_tools_index_returns_200` — index renders all 3 tool names
- `test_tools_index_requires_auth` — unauthenticated request → 302/401/403
- `test_tool_landing_commercialization` — GET returns 200 with CTA text
- `test_tool_landing_meta_parser` — GET returns 200
- `test_tool_landing_relevant_url` — GET returns 200 with domain field
- `test_tool_landing_unknown_slug_returns_404` — unknown slug → 404
- `test_tool_submit_creates_job_and_redirects` — POST → 303 redirect
- `test_tool_submit_empty_input_returns_422` — empty POST → 422
- `test_tool_submit_exceeds_limit_returns_422` — 201 phrases → 422
- `test_tool_submit_unknown_slug_returns_404` — POST to unknown slug → 404
- `test_tool_delete_removes_job` — DELETE owned job → 200
- `test_tool_delete_other_users_job_returns_404` — DELETE other user's job → 404

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Missing per-tool landing templates for commercialization and meta-parser**

- **Found during:** Task 2 execution (TemplateNotFound error)
- **Issue:** Router uses `tools/{slug}/index.html` path, but only `relevant-url/` had a subdirectory. `commercialization` and `meta-parser` had no subdirectory templates.
- **Fix:** Created `app/templates/tools/commercialization/` and `app/templates/tools/meta-parser/` directories with `index.html`, `results.html`, and `partials/job_status.html` (copies of generic `tool_landing.html` and `tool_results.html`)
- **Files modified:** 6 new template files
- **Commit:** 5c66f85 (included in Task 2 commit)

**2. [Rule 3 - Blocker] UIAuthMiddleware intercepts /ui/* before FastAPI DI**

- **Found during:** Task 2 execution (302 redirect on test requests)
- **Issue:** `UIAuthMiddleware` in `app/main.py` intercepts all `/ui/*` requests to validate JWT cookie before FastAPI dependency injection runs. Overriding `get_current_user` alone is insufficient.
- **Fix:** Tests pass a valid JWT cookie via `_jwt_cookie()` helper using `create_access_token()`. This satisfies the middleware, while `get_current_user` override avoids real DB user lookup.
- **Files modified:** tests/test_tools_router.py
- **Commit:** 5c66f85

## Verification Results

```
31 passed, 15 warnings in 0.39s
```

Tests run: `tests/test_tools_router.py` (12), `tests/test_commerce_check_service.py` (5), `tests/test_meta_parse_service.py` (5), `tests/test_relevant_url_service.py` (9)

All 4 verification checks pass:
1. `pytest tests/test_tools_router.py -x` — exits 0
2. `pytest tests/test_commerce_check_service.py tests/test_meta_parse_service.py tests/test_relevant_url_service.py -x` — exits 0
3. `grep -c "get_current_user" app/routers/tools.py` — returns 8 (1 import + 7 handlers)
4. `grep -q "job_count" app/templates/tools/index.html` — exits 0

## Known Stubs

None. All tool cards render with real `job_count` from DB queries. No placeholder data.

## Self-Check: PASSED

- `a54f3c1` exists in git log
- `5c66f85` exists in git log
- `tests/test_tools_router.py` exists and contains 12 test functions
- `app/routers/tools.py` has 7 `Depends(get_current_user)` calls
- `app/templates/tools/index.html` contains `job_count`
- All new template files exist under `app/templates/tools/commercialization/` and `app/templates/tools/meta-parser/`
