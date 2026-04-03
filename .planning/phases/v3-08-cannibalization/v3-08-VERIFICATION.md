---
phase: v3-08-cannibalization
verified: 2026-04-03T13:30:00Z
status: gaps_found
score: 5/7 must-haves verified
gaps:
  - truth: "Clicking a resolution button in the UI creates a resolution record in the database"
    status: failed
    reason: "HTMX <form hx-post='.../resolve'> sends application/x-www-form-urlencoded but the endpoint uses a Pydantic BaseModel body (ResolveRequest) which requires application/json. FastAPI returns HTTP 422 Unprocessable Entity when the form is submitted. No json-enc HTMX extension is loaded."
    artifacts:
      - path: "app/routers/clusters.py"
        issue: "create_cannibalization_resolve takes `payload: ResolveRequest` (Pydantic BaseModel = JSON body), not Form() parameters"
      - path: "app/templates/clusters/cannibalization.html"
        issue: "Form uses hx-post without hx-ext='json-enc'; HTMX sends form-encoded data, not JSON"
    missing:
      - "Either change endpoint to accept Form() parameters (url: str = Form(...), etc.) matching the HTML form fields, OR add hx-ext='json-enc' to the form and load the json-enc HTMX extension in base.html"
  - truth: "Status update buttons ('В работу', 'Решено') update a resolution's status"
    status: failed
    reason: "Status buttons use hx-vals='{\"status\": \"in_progress\"}' without json-enc extension, which still sends form-encoded data. The status endpoint takes `payload: StatusUpdateRequest` (Pydantic BaseModel). Same HTTP 422 failure as the resolve endpoint."
    artifacts:
      - path: "app/routers/clusters.py"
        issue: "update_resolution_status takes `payload: StatusUpdateRequest` (Pydantic BaseModel = JSON body)"
      - path: "app/templates/clusters/cannibalization.html"
        issue: "hx-vals without json-enc sends form-encoded, not JSON"
    missing:
      - "Either change StatusUpdateRequest to use `status: str = Form(...)` in the endpoint signature, OR add hx-ext='json-enc' to the buttons/parent container"
  - truth: "A SeoTask is automatically created (type=cannibalization) when a resolution is proposed"
    status: failed
    reason: "create_resolution_task() exists in the service but is never called from the resolve router endpoint. The endpoint only calls create_resolution(). The task_id field on the resolution will always be NULL after creation."
    artifacts:
      - path: "app/routers/clusters.py"
        issue: "create_cannibalization_resolve endpoint at line 136 does not call cannibalization_service.create_resolution_task()"
    missing:
      - "Add `await cannibalization_service.create_resolution_task(db, r.id)` after create_resolution() call in create_cannibalization_resolve, before db.commit()"
---

# Phase v3-08: Cannibalization Resolver Verification Report

**Phase Goal:** Cannibalization Resolver — action plans for cannibalization cases (merge/canonical/redirect/split), resolution tracking with status, UI action buttons and history.
**Verified:** 2026-04-03T13:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                 | Status     | Evidence                                                              |
|----|-----------------------------------------------------------------------|------------|-----------------------------------------------------------------------|
| 1  | 4 resolution types exist with distinct action plan text               | VERIFIED   | ResolutionType enum + _ACTION_TEMPLATES in cannibalization_service.py |
| 2  | Action plans contain Russian-language step-by-step instructions       | VERIFIED   | Templates use "Объединить", "Установить canonical", "Разнести ключи"  |
| 3  | Clicking a resolution button creates a resolution record              | FAILED     | HTMX form sends form-encoded; endpoint expects JSON — HTTP 422 error  |
| 4  | A SeoTask is auto-created (type=cannibalization) on resolution        | FAILED     | create_resolution_task() defined but never called from router         |
| 5  | check_resolution re-runs detect_cannibalization and reports status    | VERIFIED   | cannibalization_service.py:145 uses `phrase` key (bug already fixed)  |
| 6  | Status update buttons change resolution status in the database        | FAILED     | Same form-encoded vs JSON mismatch as gap #1; HTTP 422 at runtime     |
| 7  | Resolution history renders with status badges and collapsible plans   | VERIFIED   | cannibalization.html:100–161 renders resolutions dict with badges     |

**Score:** 4/7 truths verified (gaps_found)

### Required Artifacts

| Artifact                                               | Expected                              | Status   | Details                                                          |
|--------------------------------------------------------|---------------------------------------|----------|------------------------------------------------------------------|
| `app/models/cannibalization.py`                        | ORM model + enums                     | VERIFIED | ResolutionType, ResolutionStatus, CannibalizationResolution all present; 42 lines |
| `alembic/versions/0026_add_cannibalization_resolver.py`| Migration for cannibalization_resolutions table | VERIFIED | Creates table + PG ENUMs; index on site_id; proper downgrade |
| `app/services/cannibalization_service.py`              | Pure functions + async CRUD           | VERIFIED | suggest_resolution_type, generate_action_plan, 5 async CRUD functions; 161 lines |
| `tests/test_cannibalization_service.py`                | 6+ unit tests                         | VERIFIED | 7 tests, all passing (0.02s)                                     |
| `app/routers/clusters.py` (resolution endpoints)       | 4 endpoints: resolve, resolutions, status, check | PARTIAL | Endpoints exist and URL paths match template, but JSON/form-encoding mismatch causes runtime 422 |
| `app/templates/clusters/cannibalization.html`          | Action buttons, primary URL selector, history | VERIFIED | All UI elements present; 163 lines                              |
| `app/main.py` (ui_cannibalization handler)             | Handler serializes resolutions to dicts | VERIFIED | Lines 2448–2478; serializes ORM objects before template pass   |

### Key Link Verification

| From                              | To                                             | Via                         | Status       | Details                                                                 |
|-----------------------------------|------------------------------------------------|-----------------------------|--------------|-------------------------------------------------------------------------|
| cannibalization.html form         | /clusters/sites/{id}/cannibalization/resolve   | hx-post (form-encoded)      | NOT_WIRED    | Form sends x-www-form-urlencoded; endpoint requires JSON body           |
| cannibalization.html status btns  | /clusters/cannibalization/resolutions/{id}/status | hx-post + hx-vals (form-encoded) | NOT_WIRED | hx-vals without json-enc sends form-encoded; endpoint requires JSON     |
| cannibalization.html check btn    | /clusters/cannibalization/resolutions/{id}/check | hx-post (no body)          | WIRED        | No body required; POST to endpoint works correctly                      |
| cannibalization.html refresh btn  | /clusters/sites/{id}/cannibalization/resolutions | hx-get                    | WIRED        | GET request; no body issue; returns serialized dict list                |
| resolve endpoint                  | create_resolution_task()                       | direct service call         | NOT_WIRED    | create_resolution_task exists in service but is never called by router  |
| CannibalizationResolution model   | alembic/env.py                                 | import                      | ORPHANED     | Model not imported in env.py (pre-existing pattern; Proxy model same issue; manual migration works) |
| ui_cannibalization                | detect_cannibalization + list_resolutions      | direct service call         | WIRED        | main.py:2451–2473 calls both, serializes results                        |

### Data-Flow Trace (Level 4)

| Artifact                    | Data Variable  | Source                               | Produces Real Data | Status   |
|-----------------------------|----------------|--------------------------------------|--------------------|----------|
| cannibalization.html        | `results`      | detect_cannibalization() in main.py  | DB query (cluster_service) | FLOWING |
| cannibalization.html        | `resolutions`  | list_resolutions() in main.py        | DB query (CannibalizationResolution) | FLOWING |
| Resolution form submission  | payload        | HTMX form POST                       | No — 422 at runtime | DISCONNECTED |
| Status update buttons       | payload.status | hx-vals POST                         | No — 422 at runtime | DISCONNECTED |

### Behavioral Spot-Checks

| Behavior                                    | Command                                                                     | Result  | Status |
|---------------------------------------------|-----------------------------------------------------------------------------|---------|--------|
| All 7 service unit tests pass               | `python -m pytest tests/test_cannibalization_service.py -v`                 | 7 passed | PASS  |
| Model imports cleanly                       | `python -c "from app.models.cannibalization import CannibalizationResolution"` | exit 0 | PASS |
| Service imports cleanly                     | `python -c "from app.services.cannibalization_service import suggest_resolution_type, generate_action_plan, create_resolution"` | exit 0 | PASS |
| Form-encoded POST to Pydantic endpoint fails | In-process FastAPI test: POST with Content-Type form-urlencoded to Pydantic body endpoint | HTTP 422 | FAIL (confirms gap) |
| create_resolution_task called from router   | grep "create_resolution_task" app/routers/clusters.py                       | 0 matches | FAIL (confirms gap) |

### Requirements Coverage

No `requirements_addressed` IDs declared in the plan. ROADMAP-v3.md Phase 8 success criteria verified:

| ROADMAP Goal                            | Status   | Evidence                                                              |
|-----------------------------------------|----------|-----------------------------------------------------------------------|
| Merge/canonical/redirect/split actions  | VERIFIED | 4 types in ResolutionType enum, 4 action plan templates               |
| Создание задачи (task creation)         | FAILED   | create_resolution_task() not called from router endpoint              |
| Отслеживание после действий (re-check)  | VERIFIED | check_resolution() in service + /check endpoint wired                |

### Anti-Patterns Found

| File                                    | Line     | Pattern                                          | Severity  | Impact                                                            |
|-----------------------------------------|----------|--------------------------------------------------|-----------|-------------------------------------------------------------------|
| `app/routers/clusters.py`               | 125–129  | `class ResolveRequest(BaseModel)` used for HTMX form | BLOCKER | All resolution creation from UI fails with HTTP 422              |
| `app/routers/clusters.py`               | 132–133  | `class StatusUpdateRequest(BaseModel)` used for HTMX hx-vals | BLOCKER | All status updates from UI fail with HTTP 422              |
| `app/routers/clusters.py`               | 136–160  | `create_resolution_task` never called             | BLOCKER   | SeoTask never created; task_id always NULL; D-02 unmet           |
| `alembic/env.py`                        | —        | `app/models/cannibalization.py` not imported      | WARNING   | Future `alembic revision --autogenerate` silently omits this model (pre-existing pattern; Proxy model same issue) |

### Human Verification Required

None — all gaps are code-level and verifiable programmatically.

## Gaps Summary

Three functional gaps block goal achievement:

**Gap 1 & 2 — HTMX form-encoded vs JSON mismatch (root cause shared):**
Both the resolution creation form and the status update buttons post `application/x-www-form-urlencoded` (HTMX default), but both endpoints use Pydantic `BaseModel` request bodies which require `application/json`. This results in HTTP 422 responses for all interactive actions. Fix by either: (a) converting both endpoints to use FastAPI `Form()` parameters matching the HTML field names, or (b) loading the HTMX `json-enc` extension globally and adding `hx-ext="json-enc"` to the form and buttons.

**Gap 3 — SeoTask not created on resolution (wiring omission):**
`create_resolution_task()` is fully implemented in the service and creates a properly typed `SeoTask`, but the resolve router endpoint never calls it. The plan's D-02 deliverable ("SeoTask created with type=cannibalization") is therefore unmet. Fix: call `await cannibalization_service.create_resolution_task(db, r.id)` in `create_cannibalization_resolve` after `create_resolution()` and before `db.commit()`.

The service logic, model, migration, and tests are solid. The gaps are entirely in the integration layer between the HTML UI and the backend endpoints.

---

_Verified: 2026-04-03T13:30:00Z_
_Verifier: Claude (gsd-verifier)_
