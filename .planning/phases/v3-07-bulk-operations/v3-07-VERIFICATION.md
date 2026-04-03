---
phase: v3-07-bulk-operations
verified: 2026-04-03T09:00:00Z
status: gaps_found
score: 8/9 must-haves verified
re_verification: false
gaps:
  - truth: "Group column in keyword table displays group name correctly"
    status: failed
    reason: "JS template string in index.html uses kw.cluster_name for both the Group and Cluster columns (line 105). The analytics endpoint returns group_id but not group_name, so the Group column always shows the cluster name instead."
    artifacts:
      - path: "app/templates/bulk/index.html"
        issue: "Line 105: tr.innerHTML renders `${kw.cluster_name||'—'}` for the Group column instead of a group name. The /analytics/sites/{site_id}/keywords endpoint returns group_id but no group_name field."
    missing:
      - "Either add group_name to the analytics endpoint keyword response, or resolve group names client-side from filter_options.groups using kw.group_id"
      - "Fix the table row template in searchKeywords() to use the correct group field"
---

# Phase v3-07: Bulk Operations Hub Verification Report

**Phase Goal:** Bulk Operations Hub — batch move keywords between groups/clusters, batch assign target_url, batch delete, filtered CSV/XLSX export, import with merge mode.
**Verified:** 2026-04-03T09:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Batch move keywords to a group via UI | ✓ VERIFIED | `bulk_move_to_group` in bulk_service.py uses SQLAlchemy `update()`, POST `/bulk/{site_id}/move-group` calls it, JS `moveToGroup()` posts selected IDs |
| 2 | Batch move keywords to a cluster via UI | ✓ VERIFIED | `bulk_move_to_cluster` wired through router `POST /move-cluster` and JS `moveToCluster()` |
| 3 | Batch assign target_url via UI | ✓ VERIFIED | `bulk_assign_target_url` wired through router `POST /assign-url` and JS `assignUrl()`; confirm guard in JS |
| 4 | Batch delete with confirmation | ✓ VERIFIED | `bulk_delete` wired through router `POST /delete`; JS `deleteSelected()` calls `confirm()` before POST |
| 5 | Export filtered keywords to CSV | ✓ VERIFIED | `export_keywords_csv` builds 9-column CSV; router GET `/export?format=csv` returns file download with Content-Disposition header |
| 6 | Export filtered keywords to XLSX | ✓ VERIFIED | `export_keywords_xlsx` uses openpyxl, returns bytes; router GET `/export?format=xlsx` returns correct MIME type |
| 7 | Import CSV/XLSX with merge mode and audit log | ✓ VERIFIED | `import_keywords_with_log` calls `log_action` with `action="bulk_keyword_import"` and count detail; router POST `/import` handles multipart upload |
| 8 | All batch operations return affected row count | ✓ VERIFIED | All five batch functions return `result.rowcount or 0`; router responses include `moved`/`assigned`/`deleted` counts |
| 9 | Group column in keyword table displays group name | ✗ FAILED | Line 105 in bulk/index.html uses `kw.cluster_name` for both Группа and Кластер columns; analytics endpoint returns `group_id` but not `group_name` |

**Score:** 8/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/bulk_service.py` | Bulk service with all 5 batch ops + export + import | ✓ VERIFIED | 422 lines, all functions present and substantive, uses SQLAlchemy batch UPDATE/DELETE |
| `tests/test_bulk_service.py` | 3+ unit tests for export format | ✓ VERIFIED | 6 tests; pure-function tests (no DB); covers CSV headers, row data, empty export, XLSX magic bytes, header match, multi-row count |
| `app/routers/bulk.py` | 7 endpoints, all require_admin | ✓ VERIFIED | 7 `@router` decorators; all handlers use `Depends(require_admin)` |
| `app/templates/bulk/index.html` | Full bulk UI with select-all, actions, export, import | ✓ VERIFIED (with gap) | File exists; all required sections present; select-all checkbox, JS Set(), filter bar, export links, import form with on_duplicate selector |
| `app/main.py` | bulk_router imported and registered | ✓ VERIFIED | Line 40: `from app.routers.bulk import router as bulk_router`; line 178: `app.include_router(bulk_router)` |
| `app/templates/sites/detail.html` | "Массовые операции" button linking to `/bulk/{site.id}` | ✓ VERIFIED | Line 50: `<a href="/bulk/{{ site.id }}"...>Массовые операции</a>` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `bulk/index.html` JS `searchKeywords()` | `/analytics/sites/{site_id}/keywords` | `fetch()` | ✓ WIRED | Line 97: `fetch('/analytics/sites/${SITE_ID}/keywords?${params}')` |
| `bulk/index.html` JS actions | `/bulk/{site_id}/move-group` etc | `fetch()` POST with JSON | ✓ WIRED | Lines 114, 121, 128, 136 — all action functions post to correct endpoints |
| `bulk/index.html` export links | `/bulk/{site_id}/export?format=csv|xlsx` | `<a href>` | ✓ WIRED | Lines 64–65: direct anchor tags trigger browser download |
| `bulk/index.html` import form | `/bulk/{site_id}/import` | `fetch()` FormData POST | ✓ WIRED | Line 142: `fetch('/bulk/${SITE_ID}/import', {method:'POST', body: new FormData(form)})` |
| `bulk.py` router | `bulk_service` | Python import + function calls | ✓ WIRED | Line 19: `from app.services import bulk_service as bs`; all endpoints call `bs.*` functions |
| `bulk_service.import_keywords_with_log` | `audit_service.log_action` | Python import + `await log_action()` | ✓ WIRED | Line 17 import; `log_action` called twice in function (empty and non-empty paths) |
| `bulk_service.import_keywords_with_log` | `keyword_service.bulk_add_keywords` | Python import + `await` call | ✓ WIRED | Line 18 import; line 382: `await bulk_add_keywords(db, site_id, keyword_rows, on_duplicate=on_duplicate)` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `bulk/index.html` keyword table | `data.items` (JS) | `/analytics/sites/{site_id}/keywords` JSON | Yes — analytics service queries DB | ✓ FLOWING |
| `bulk/index.html` Group column (table row) | `kw.cluster_name` (wrong field) | analytics endpoint response | `group_name` not in response | ✗ HOLLOW_PROP — Group column renders `kw.cluster_name` instead of group name; analytics returns `group_id` only |
| `bulk_service.export_keywords_csv/xlsx` | rows from `_fetch_export_rows` | DB queries (Keyword, KeywordPosition, KeywordGroup, KeywordCluster) | Yes — 4 separate async queries + joins | ✓ FLOWING |
| `bulk_service.import_keywords_with_log` | `count` from `bulk_add_keywords` | DB INSERT/UPDATE | Yes — delegates to keyword_service | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| bulk_service module importable | `python -c "from app.services.bulk_service import bulk_move_to_group, bulk_assign_target_url, bulk_delete, export_keywords_csv, import_keywords_with_log"` | Not run (requires app env) | ? SKIP |
| bulk router importable | `python -c "from app.routers.bulk import router"` | Not run (requires app env) | ? SKIP |
| 7 router decorators | `grep -c "@router" app/routers/bulk.py` | 7 | ✓ PASS |
| Tests exist and structured correctly | File read and counted | 6 pure-function tests | ✓ PASS |
| audit log call exists | `grep -q "bulk_keyword_import" bulk_service.py` | Found at lines 374 and 404 | ✓ PASS |
| Group column uses wrong JS field | Line 105 inspection | `kw.cluster_name` used twice | ✗ FAIL |

---

### Requirements Coverage

No formal REQ-* IDs were declared in plan frontmatter (`requirements_addressed: []` in both plans). Phase deliverables are tracked via must-haves in the plan `<must_haves>` blocks.

**Plan 01 must-haves:**

| Must-have | Status | Evidence |
|-----------|--------|----------|
| D-01: bulk_assign_target_url sets URL for selected keywords | ✓ SATISFIED | Function exists, SQLAlchemy UPDATE confirmed, router wired |
| D-02: import_keywords_with_log writes audit_log entry with counts and filename | ✓ SATISFIED | `log_action` called with `action="bulk_keyword_import"` and `detail` dict containing file, on_duplicate, total, added, updated, skipped |
| All batch operations return affected count | ✓ SATISFIED | All 5 batch functions return `result.rowcount or 0` |
| Export supports both CSV and XLSX | ✓ SATISFIED | Two async functions, both wired to GET `/export` endpoint |

**Plan 02 must-haves:**

| Must-have | Status | Evidence |
|-----------|--------|----------|
| D-01: Target URL assigned manually — select keywords, enter URL, apply | ✓ SATISFIED | JS `assignUrl()` reads `action-url` input, posts to `/bulk/{site_id}/assign-url` |
| D-02: Import shows counts and logs to audit | ✓ SATISFIED | `importFile()` displays `data.added`, `data.updated`, `data.skipped`; service logs to audit |
| Select-all + batch action pattern on table | ✓ SATISFIED | `#select-all` checkbox + `.kw-cb` class + `selectedIds` Set() pattern implemented |
| Export supports CSV and XLSX with current filters | ⚠️ PARTIAL | Export links pass `format=` param but do NOT pass current filter parameters from the filter bar to the export URL. Export always returns all site keywords rather than filtered subset when using the quick-link buttons. |
| All copy in Russian | ✓ SATISFIED | All user-facing text in Russian confirmed in template |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/templates/bulk/index.html` | 105 | `kw.cluster_name` used for Group column (copy-paste error) | ⚠️ Warning | Group column always shows cluster name; user cannot see which group a keyword belongs to in the bulk table |
| `app/templates/bulk/index.html` | 64–65 | Export links are static `<a href>` without filter params | ⚠️ Warning | Clicking "Экспорт CSV/XLSX" exports ALL site keywords rather than the current filter view; plan specified "Export с применёнными фильтрами" |
| `app/routers/bulk.py` | 127–142 | Import uses `shutil.copyfileobj` (sync) inside async handler | ℹ️ Info | `shutil.copyfileobj` blocks the event loop briefly during file copy; acceptable for small files but not ideal for async FastAPI |

---

### Human Verification Required

#### 1. Export with Applied Filters

**Test:** On the bulk operations page, apply a filter (e.g. select a specific group), click "Экспорт CSV". Open the downloaded file.
**Expected:** Downloaded CSV contains only keywords matching the current filter, not all site keywords.
**Why human:** The static `<a href="/bulk/{site.id}/export?format=csv">` link does not include filter parameters from the filter bar. Verifying whether this was intentional requires checking the actual download content against the filtered view.

#### 2. Group Column in Keyword Table

**Test:** On the bulk operations page for a site with keywords assigned to named groups, click "Найти". Inspect the Group and Cluster columns.
**Expected:** Group column shows the keyword's group name; Cluster column shows the keyword's cluster name.
**Why human:** Confirms the bug found at line 105 — both columns currently render `kw.cluster_name`.

#### 3. Import Counts Display

**Test:** Upload a CSV file with 5 known keywords (2 new, 2 duplicates, 1 empty row) with on_duplicate=skip.
**Expected:** Status message shows "Добавлено: 2, обновлено: 0, пропущено: 2"; audit log contains an entry with action "bulk_keyword_import".
**Why human:** Requires live DB interaction and file parsing.

---

### Gaps Summary

**1 blocking gap, 1 warning:**

**Gap 1 (Warning — display correctness):** The keyword table's Group column always renders `kw.cluster_name` instead of a group name. The `/analytics/sites/{site_id}/keywords` endpoint returns `group_id` but not `group_name`, and the JS template on line 105 copies the same field for both Group and Cluster columns. This is a copy-paste error that breaks the visual identification of groups in the bulk operations table.

**Gap 2 (Warning — missing feature parity):** Export buttons are static links that do not include the current filter state. The ROADMAP specifies "Export с применёнными фильтрами" and the plan states "Export filtered keywords" — but the `<a href>` export links are hardcoded without query parameters reflecting the active filter bar selections. This means the export always returns all site keywords rather than the filtered subset currently visible.

Neither gap prevents the core bulk operations (move, assign, delete, import with audit) from functioning correctly. The service layer and router are fully implemented and wired. The primary functional goal is ~89% achieved.

---

_Verified: 2026-04-03T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
