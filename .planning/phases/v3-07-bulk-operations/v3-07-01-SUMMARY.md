---
phase: v3-07
plan: "01"
subsystem: bulk-service
tags: [bulk-operations, export, import, audit-log, keywords]
dependency_graph:
  requires: [app/services/keyword_service.py, app/services/audit_service.py, app/models/keyword.py]
  provides: [app/services/bulk_service.py]
  affects: [keyword management, export pipeline, import pipeline]
tech_stack:
  added: []
  patterns: [SQLAlchemy bulk UPDATE/DELETE, openpyxl XLSX export, CSV io.StringIO export]
key_files:
  created: []
  modified:
    - app/services/bulk_service.py
    - tests/test_bulk_service.py
decisions:
  - Used SQLAlchemy UPDATE/DELETE statements instead of row-by-row loops for batch operations (performance)
  - export_keywords_csv/xlsx accepts **filters kwargs matching analytics_service.filter_keywords signature
  - import_keywords_with_log uses base.read_file + find_column for generic CSV/XLSX parsing (works for both KC and Topvisor formats)
  - _CSV_HEADERS constant exposed publicly for test reuse
metrics:
  duration: ~5 min
  completed: 2026-04-03
  tasks_completed: 2
  files_modified: 2
---

# Phase v3-07 Plan 01: Bulk Service Summary

**One-liner:** Bulk operations service with batch move/assign/delete, CSV+XLSX export (9 columns including Position/Delta), and import with audit_log entry per operation.

## Tasks Completed

| # | Title | Commit | Files |
|---|-------|--------|-------|
| 01 | Create bulk_service.py | b95d422 | app/services/bulk_service.py |
| 02 | Unit tests for bulk service | 0f328c4 | tests/test_bulk_service.py |

## What Was Built

### bulk_service.py

**Batch operations** (all return affected row count):
- `bulk_move_to_group(db, keyword_ids, group_id)` — SQLAlchemy UPDATE; `group_id=None` removes from group
- `bulk_move_to_cluster(db, keyword_ids, cluster_id)` — same pattern for cluster assignment
- `bulk_assign_target_url(db, keyword_ids, target_url)` — sets target_url on all selected keywords
- `bulk_delete(db, keyword_ids)` — SQLAlchemy DELETE by ID list
- `bulk_delete_by_filter(db, site_id, *, group_id, cluster_id, search)` — filter-first then DELETE

**Export** (CSV string / XLSX bytes):
- `export_keywords_csv(db, site_id, keyword_ids=None, **filters)` — 9-column CSV
- `export_keywords_xlsx(db, site_id, keyword_ids=None, **filters)` — same data as XLSX bytes
- Columns: Phrase, Frequency, Region, Engine, Group, Cluster, Target URL, Position, Delta
- Joins group names, cluster names, and latest position in a single async query set

**Import with audit log:**
- `import_keywords_with_log(db, site_id, file_path, on_duplicate, user_id)` — parses any CSV/XLSX via `base.read_file` + `find_column`, calls `bulk_add_keywords`, writes `audit_log` entry with action `"bulk_keyword_import"` and detail dict `{file, on_duplicate, total, added, updated, skipped}`

### tests/test_bulk_service.py

6 pure-function tests covering CSV/XLSX format validation:
- Header structure (9 columns)
- Row data integrity
- Empty export (header-only)
- XLSX magic bytes (PK zip header)
- XLSX headers match `_CSV_HEADERS` constant
- Multiple rows line count

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing file had incomplete export (missing Position/Delta columns)**
- **Found during:** Task 01
- **Issue:** The pre-existing bulk_service.py had 7-column export missing Position and Delta; also used row-by-row ORM loops instead of batch UPDATE/DELETE
- **Fix:** Rewrote with SQLAlchemy `update()`/`delete()` statements and full 9-column export with position join
- **Files modified:** app/services/bulk_service.py

**2. [Rule 1 - Bug] Existing tests imported removed private helpers (_keywords_to_csv, _keywords_to_xlsx)**
- **Found during:** Task 02
- **Issue:** Previous test file imported `_keywords_to_csv` and `_keywords_to_xlsx` which no longer exist in the rewritten module
- **Fix:** Rewrote tests to use inline helper functions that replicate the CSV/XLSX build logic (pure-function testable without DB)
- **Files modified:** tests/test_bulk_service.py

## Known Stubs

None — all export columns are wired (group/cluster names resolved via joins, positions fetched from keyword_positions table).

## Self-Check: PASSED

- app/services/bulk_service.py — FOUND
- tests/test_bulk_service.py — FOUND
- Commit b95d422 — FOUND
- Commit 0f328c4 — FOUND
- 6 tests pass: `python -m pytest tests/test_bulk_service.py -x -q` → 6 passed
