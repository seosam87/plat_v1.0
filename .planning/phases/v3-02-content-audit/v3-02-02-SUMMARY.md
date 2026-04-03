---
phase: v3-02-content-audit
plan: "02"
subsystem: audit
tags: [content-audit, check-engine, html-detection, content-type, pytest]

requires:
  - phase: v3-02-01
    provides: ContentType enum on Page, AuditCheckDefinition, AuditResult, SchemaTemplate models in app/models/audit.py, migration 0021

provides:
  - detect_author_block: regex-based CSS class + rel=author HTML detection
  - detect_related_posts: plugin class patterns + Russian text marker detection
  - detect_cta_block: CTA class patterns + Russian button text detection
  - classify_content_type: page_type -> content_type mapping with URL-based landing rules
  - run_checks_for_page: check engine with applies_to filtering, pass/fail/warning status
  - save_audit_results: PostgreSQL ON CONFLICT upsert via insert().on_conflict_do_update()
  - async DB helpers: get_active_checks, get_audit_results_for_site, update_content_type, classify_and_update_pages, get_check_definitions, update_check_definition, create_check_definition
  - 28 unit tests covering all pure functions

affects:
  - v3-02-03 (content audit pipeline Celery task uses these functions)
  - v3-02-04 (content audit UI shows results from save_audit_results)
  - v3-02-05 (admin check configuration uses get_check_definitions, update_check_definition)

tech-stack:
  added: []
  patterns:
    - "Detection functions are pure (no DB) — regex compiled at module level for performance"
    - "Check engine dispatches via inline dict of lambdas keyed by check code"
    - "ON CONFLICT upsert via SQLAlchemy PostgreSQL insert().on_conflict_do_update() — idempotent re-runs"
    - "applies_to='unknown' means the check runs for all content types"

key-files:
  created:
    - tests/test_audit_service.py
  modified:
    - app/services/audit_service.py

key-decisions:
  - "Check engine functions added to existing audit_service.py (not a new file) to match plan acceptance criteria while preserving log_action for audit logging"
  - "applies_to filtering: 'unknown' matches all content types; specific values (informational/commercial) are exclusive"
  - "noindex_check severity=error means failure yields 'fail' status; other checks default to 'warning'"

patterns-established:
  - "Pure detection functions use module-level compiled regexes (_AUTHOR_CLASS_RE etc.) for performance"
  - "run_checks_for_page dispatches via local dict — easy to extend with new check codes"
  - "All async DB helpers use db.flush() (not commit) to let callers control transaction boundaries"

requirements-completed: []

duration: 4min
completed: 2026-04-03
---

# Phase v3-02 Plan 02: Audit Service Summary

**Regex-based HTML detection engine (author block, related posts, CTA) + content_type classifier + check engine with applies_to filtering, backed by PostgreSQL ON CONFLICT upsert persistence and 28 unit tests.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-03T06:43:32Z
- **Completed:** 2026-04-03T06:47:23Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added all 14 functions from the plan spec to `app/services/audit_service.py`, extending existing log_action file without breaking callers
- Pure detection functions use module-level compiled regexes and detect both CSS class patterns and Russian-language text markers
- Check engine respects `applies_to` filtering: commercial-only checks skip informational pages and vice versa
- 28 unit tests (plan required 15) covering all detection functions, classifier, and check engine edge cases
- All tests pass in 0.06s — zero dependencies on DB, Docker, or network

## Task Commits

1. **Task 01: Create audit_service.py with check engine and detection functions** - `1d9664e` (feat)
2. **Task 02: Unit tests for detection functions and check engine** - `710bbf1` (test)

**Plan metadata:** (docs commit pending)

## Files Created/Modified

- `app/services/audit_service.py` - Extended with detect_author_block, detect_related_posts, detect_cta_block, classify_content_type, check_internal_links, run_checks_for_page + 8 async DB helpers
- `tests/test_audit_service.py` - 28 unit tests for pure functions (detection + classify + check engine)

## Decisions Made

- Check engine functions added to `app/services/audit_service.py` (not a new file) — plan acceptance criteria explicitly import from `audit_service`, and that module already existed for `log_action`. Extended it rather than creating a name collision.
- `applies_to='unknown'` convention: checks that apply to all content types use `unknown` as the sentinel value rather than `None` or a separate `all` enum value.
- `db.flush()` in async DB helpers (not `commit()`) — lets callers control transaction boundaries, consistent with SQLAlchemy async patterns used elsewhere in the codebase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] audit_service.py already existed (audit logging, not content audit)**
- **Found during:** Task 01 (creating audit_service.py)
- **Issue:** `app/services/audit_service.py` already existed with `log_action` for audit logging; plan expected a new file. Creating a new file would require renaming the existing one and updating all importers.
- **Fix:** Extended the existing file — added all check engine functions below the existing `log_action` function, keeping backward compatibility.
- **Files modified:** app/services/audit_service.py (extended, not replaced)
- **Verification:** `python -c "from app.services.audit_service import log_action, detect_author_block"` succeeds; existing callers (auth.py, site_service.py, etc.) unaffected.
- **Committed in:** 1d9664e (Task 01 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - existing file conflict resolved by extension)
**Impact on plan:** No scope change. All acceptance criteria satisfied. Backward compatibility preserved.

## Issues Encountered

None beyond the existing file conflict documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All pure detection functions and DB helpers are ready for the Celery pipeline (v3-02-03)
- `run_checks_for_page` is callable from any async task with rendered HTML and page metadata dict
- `save_audit_results` handles upserts safely — Celery retries are idempotent
- Check definitions must be seeded to DB before pipeline runs (migration or seed script expected in v3-02-03 or v3-02-05)

---
*Phase: v3-02-content-audit*
*Completed: 2026-04-03*
