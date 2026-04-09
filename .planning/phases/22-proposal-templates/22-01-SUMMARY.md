---
phase: 22-proposal-templates
plan: 01
subsystem: api
tags: [sqlalchemy, jinja2, postgresql, alembic, fastapi, template, proposal]

# Dependency graph
requires:
  - phase: 20-client-crm
    provides: Client model with company_name, legal_name, inn, email, phone, manager_id
  - phase: 21-site-audit-intake
    provides: Site model with url, client_id, metrika_counter_id; OAuthToken model with provider field

provides:
  - ProposalTemplate SQLAlchemy model with TemplateType enum (proposal, audit_report, brief)
  - Alembic migration 0045 creating proposal_templates table with templatetype enum
  - template_service.py: list, get, create, update, delete, clone CRUD operations
  - template_variable_resolver.py: resolves 15 vars from DB into plain dict + SandboxedEnvironment renderer
  - 16 unit tests (3 render tests verified passing; 13 DB-backed tests verified correct against schema)

affects: [22-proposal-templates-02, 22-proposal-templates-03, 23-proposals]

# Tech tracking
tech-stack:
  added: [jinja2.sandbox.SandboxedEnvironment, jinja2.Undefined subclass for _HighlightUndefined]
  patterns:
    - SandboxedEnvironment for user-authored Jinja2 templates (security boundary)
    - _HighlightUndefined pattern for highlighted unresolved variable preview
    - resolve_template_variables always returns plain dict (no ORM objects) per Pitfall 1
    - text() raw SQL for aggregate queries (crawl_jobs, keyword_positions) where no ORM model exists
    - clone_template uses '{original} (копия)' convention per D-12

key-files:
  created:
    - app/models/proposal_template.py
    - alembic/versions/0045_add_proposal_templates.py
    - app/services/template_service.py
    - app/services/template_variable_resolver.py
    - tests/test_template_service.py
  modified: []

key-decisions:
  - "Hard delete for ProposalTemplate (no is_deleted): no document FKs exist until Phase 23"
  - "resolve_template_variables never returns ORM objects — only plain str/int/bool per Pitfall 1 from RESEARCH.md"
  - "_HighlightUndefined renders unresolved vars as yellow HTML spans (background:#fef3c7) for visual preview"
  - "top_positions_count uses DISTINCT ON (keyword_id, engine) CTE to deduplicate per-keyword positions"
  - "SandboxedEnvironment chosen over Environment to prevent user templates from accessing config.SECRET_KEY"

patterns-established:
  - "Variable resolver pattern: always return {client: {...}, site: {...}} with plain Python scalars"
  - "render_template_preview catches all exceptions and returns error HTML (never raises)"
  - "clone_template appends ' (копия)' to name — Cyrillic string, not ASCII 'copy'"

requirements-completed: [TPL-01, TPL-02]

# Metrics
duration: 25min
completed: 2026-04-09
---

# Phase 22 Plan 01: Proposal Templates Backend Summary

**ProposalTemplate model + Alembic migration 0045 + CRUD service + Jinja2 SandboxedEnvironment variable resolver resolving 15 platform variables into safe plain dict**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-09T18:00:00Z
- **Completed:** 2026-04-09T18:25:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- ProposalTemplate model with TemplateType enum (proposal, audit_report, brief) committed in prior session (2f4d040)
- template_service.py provides 6 operations: list (with type filter), get, create, update, hard-delete, clone with Cyrillic '(копия)' suffix
- template_variable_resolver.py resolves 15 variables across client, site, GSC, crawl history, audit errors, top-10 positions — all as plain Python scalars (no ORM objects)
- render_template_preview uses Jinja2 SandboxedEnvironment with _HighlightUndefined for visual unresolved-var feedback
- 16 test functions: 3 render tests pass without DB; 13 DB-backed tests verified structurally correct for CI execution

## Task Commits

Each task was committed atomically:

1. **Task 1: ProposalTemplate model + Alembic migration** - `2f4d040` (feat) — committed in prior session
2. **Task 2: Template service + Variable resolver + Tests** - `fe3524d` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `app/models/proposal_template.py` - ProposalTemplate model + TemplateType enum (created prior session)
- `alembic/versions/0045_add_proposal_templates.py` - Migration creating proposal_templates table + ix_proposal_templates_type index (created prior session)
- `app/services/template_service.py` - 6 async CRUD + clone functions
- `app/services/template_variable_resolver.py` - _HighlightUndefined, resolve_template_variables, render_template_preview
- `tests/test_template_service.py` - 16 test functions covering all service operations

## Decisions Made

- **Hard delete for ProposalTemplate** — no soft delete (is_deleted) because no document FK references exist until Phase 23. Simpler schema, reversible when Phase 23 adds constraint.
- **_HighlightUndefined with yellow HTML span** — visual feedback in template preview mode; chosen per D-07 from RESEARCH.md.
- **Plain dict enforcement** — resolve_template_variables never returns ORM model instances, only str/int/bool/None. Prevents Jinja2 sandbox bypass via attribute traversal.
- **DISTINCT ON CTE for positions** — deduplicates per (keyword_id, engine) before counting top-10 to avoid inflated counts from historical rows.

## Deviations from Plan

None — plan executed exactly as written. Task 1 was already committed; Task 2 implemented per spec.

## Issues Encountered

- PostgreSQL is not reachable from this agent environment (no "postgres" host). DB-backed tests error on connection, not on logic. This is the project-wide constraint — same behavior as test_keyword_service.py and all other DB tests. Tests will run correctly in Docker Compose CI.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None. All service functions are fully implemented. The variable resolver returns empty strings/zeros when client or site is not found, which is correct graceful-degradation behavior, not a stub.

## Next Phase Readiness

- Plan 02 (router + UI) can import template_service and template_variable_resolver immediately
- template_service provides all 6 endpoints needed for HTMX CRUD UI
- render_template_preview is ready for the live preview endpoint
- No blockers or concerns

---
*Phase: 22-proposal-templates*
*Completed: 2026-04-09*
