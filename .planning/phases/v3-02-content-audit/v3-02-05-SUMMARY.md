---
phase: v3-02-content-audit
plan: "05"
subsystem: audit
tags: [audit, content-pipeline, toc, schema, cta, internal-links, diff, fix-workflow]

requires:
  - phase: v3-02-content-audit
    provides: "audit models (AuditResult, AuditCheckDefinition, SchemaTemplate), content_audit_service check engine, schema_service template rendering, content_pipeline pure functions"
  - phase: v3-02-content-audit
    provides: "audit router (Plan 04) with site audit UI, Celery audit task, fix endpoint stubs"

provides:
  - "audit_fix_service.py with 7 pure/async functions: generate_toc_fix, generate_cta_fix, generate_schema_fix, generate_links_fix, verify_html_integrity, create_fix_job, mark_audit_fixed"
  - "Three fix endpoints on audit router: POST /fix/preview, /fix/apply, /fix/apply-and-approve"
  - "Fix preview partial template _fix_preview.html with diff display and action buttons"
  - "13 unit tests covering all fix generators and integrity checks"

affects: [v3-02-content-audit, wp-pipeline, audit-ui]

tech-stack:
  added: []
  patterns:
    - "Fix generators are pure functions (HTML in → dict out) enabling unit testing without DB"
    - "verify_html_integrity sanity-checks processed HTML before pipeline job creation"
    - "Fix apply creates WpContentJob in awaiting_approval status, reusing existing pipeline approve/push flow"
    - "mark_audit_fixed upserts AuditResult.status=fixed with job_id reference for traceability"

key-files:
  created:
    - app/services/audit_fix_service.py
    - app/templates/audit/_fix_preview.html
    - tests/test_audit_fix_service.py
  modified:
    - app/routers/audit.py

key-decisions:
  - "Fix generators are pure (no DB, no side effects) so they can be unit tested synchronously and used in both preview and apply endpoints without code duplication"
  - "verify_html_integrity checks heading count preservation, absence of unclosed script tags, and content length ratio >= 80% of original"
  - "apply-and-approve endpoint sets job.status=approved and dispatches push_to_wp.delay() immediately — no manual pipeline step needed"
  - "JobStatus import added to audit router (Rule 1 fix) — was referenced in fix_apply_and_approve but not imported"

patterns-established:
  - "generate_*_fix() pattern: returns None if fix cannot be applied, dict with processed_html+diff if applicable"
  - "Pipeline integration: create_fix_job() + mark_audit_fixed() always called together when applying a fix"

requirements-completed: []

duration: 15min
completed: 2026-04-03
---

# Phase v3-02 Plan 05: Fix Workflow Summary

**TOC/CTA/schema/internal-links fix generators with HTML integrity verification, pipeline job creation, and three REST endpoints wired to existing approve/push flow**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-03T06:50:00Z
- **Completed:** 2026-04-03T07:05:00Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Pure fix generator functions for all four auto-fixable check types (TOC, CTA, schema, internal links)
- HTML integrity verification catches heading count loss, unclosed scripts, and catastrophic content shrinkage
- Three REST endpoints enabling preview-before-apply workflow: preview (no save), apply (awaiting_approval job), apply-and-approve (push immediately)
- 13 unit tests all passing — fix generators are fully exercised without DB or network

## Task Commits

1. **Task 01: Create audit_fix_service.py** - `60a74c9` (feat) — fix generators, integrity check, pipeline helpers
2. **Task 02: Add fix endpoints to audit router** - `60a74c9` (feat) — preview/apply/apply-and-approve endpoints
3. **Task 03: Create fix preview partial template** - `60a74c9` (feat) — _fix_preview.html with diff display and action buttons
4. **Task 04: Unit tests for fix generators** - `60a74c9` (feat) — 13 tests covering all generators and integrity function

**Bug fix (Rule 1):** `f84cf6b` (fix) — missing JobStatus import in audit router

## Files Created/Modified

- `app/services/audit_fix_service.py` — 7 functions: 4 pure fix generators, integrity checker, 2 async pipeline helpers
- `app/routers/audit.py` — added 3 fix endpoints + FixRequest Pydantic model + _get_fix_result() helper + JobStatus import
- `app/templates/audit/_fix_preview.html` — Jinja2 partial for fix preview modal: diff stats, diff text, apply/approve/cancel buttons
- `tests/test_audit_fix_service.py` — 13 unit tests for all fix generators and verify_html_integrity

## Decisions Made

- Fix generators return `None` instead of raising exceptions when fix is not applicable — clean sentinel for "no fix needed"
- `verify_html_integrity` runs before creating any pipeline job (in `_get_fix_result`) so both preview and apply benefit from the check
- `_get_fix_result` private helper in router deduplicates HTML fetch + fix generation logic shared by all three fix endpoints

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added missing JobStatus import in audit router**
- **Found during:** Post-implementation review
- **Issue:** `fix_apply_and_approve` endpoint sets `job.status = JobStatus.approved` but `JobStatus` was not imported in the router module
- **Fix:** Added `from app.models.wp_content_job import JobStatus` to imports
- **Files modified:** `app/routers/audit.py`
- **Verification:** Import statement added; function references valid enum value
- **Committed in:** `f84cf6b`

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Fix required for `apply-and-approve` endpoint to work at runtime. No scope creep.

## Issues Encountered

- Plan 05 work was already committed (`60a74c9`) by a parallel agent prior to this execution. All files verified against acceptance criteria before proceeding to summary.

## Next Phase Readiness

- Fix workflow complete: preview → apply → pipeline approve/push → audit result updated to "fixed"
- All four check types (TOC, CTA, schema, links) have corresponding fix generators
- Fix endpoints ready for UI integration (HTMX calls from audit index table "Исправить" buttons)
- Phase v3-02 content audit all 5 plans complete

---
*Phase: v3-02-content-audit*
*Completed: 2026-04-03*
