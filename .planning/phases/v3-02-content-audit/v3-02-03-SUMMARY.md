---
phase: v3-02-content-audit
plan: "03"
subsystem: api
tags: [schema, json-ld, template-engine, sqlalchemy, pytest]

# Dependency graph
requires:
  - phase: v3-02-01
    provides: SchemaTemplate model with site_id nullable (NULL=system default, UUID=site-specific)
provides:
  - schema_service.py with render_schema_template, generate_schema_tag, get_page_data_for_schema
  - select_schema_type_for_page maps content_type+page_type to Article/Product/Service/LocalBusiness
  - async CRUD: get_template (site-specific with system default fallback), get_all_templates, create_site_template (upsert), delete_site_template, reset_to_default, render_schema_for_page
  - 12 unit tests covering rendering, type selection, and page data helpers
affects: [v3-02-04, v3-02-05, content-audit, audit-fix]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "{{placeholder}} substitution via regex for JSON-LD templates (not Jinja2 — templates are JSON strings)"
    - "Template selection priority: site-specific > system default (site_id=NULL)"
    - "Upsert pattern for site template CRUD: query existing before insert"

key-files:
  created:
    - app/services/schema_service.py
    - tests/test_schema_service.py
  modified: []

key-decisions:
  - "Simple string regex replacement (not Jinja2) for {{placeholder}} in JSON-LD templates — templates are JSON strings, Jinja2 would add unnecessary complexity and risk breaking JSON syntax"
  - "render_schema_template logs warning (not exception) when rendered string is invalid JSON — returns raw string as fallback for resilience"
  - "select_schema_type_for_page defaults to Article for unknown types — safe fallback for all informational content"

patterns-established:
  - "Schema CRUD: get_template falls back site-specific → system default (site_id=NULL, is_default=True)"
  - "create_site_template performs upsert — query existing first, update if found, insert if not"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-03
---

# Phase v3-02 Plan 03: Schema Template Engine and CRUD Summary

**Schema template service with {{placeholder}} rendering, content-type-to-schema-type mapping, and async CRUD for site-specific JSON-LD template overrides with system default fallback**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T06:45:41Z
- **Completed:** 2026-04-03T06:50:41Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Schema template rendering engine using regex `{{placeholder}}` substitution with JSON validation and graceful fallback
- Schema type selection function mapping content_type+page_type combinations to Article/Product/Service/LocalBusiness
- Full async CRUD layer: get_template with site-specific-to-default fallback, upsert create_site_template, safe delete (guards against system default deletion), reset_to_default
- High-level `render_schema_for_page` composing all functions into a single call returning a `<script>` tag
- 12 unit tests covering all pure functions (render, tag generation, type selection, page data)

## Task Commits

Both tasks were implemented together in a prior parallel execution:

1. **Task 1: Create schema_service.py with template engine and CRUD** - `2f67de2` (feat)
2. **Task 2: Unit tests for schema template engine** - `2f67de2` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `/projects/test/.claude/worktrees/agent-ae9f498e/app/services/schema_service.py` - Schema template engine: render_schema_template, generate_schema_tag, get_page_data_for_schema, select_schema_type_for_page, and async CRUD (get_template, get_all_templates, create_site_template, delete_site_template, reset_to_default, render_schema_for_page)
- `/projects/test/.claude/worktrees/agent-ae9f498e/tests/test_schema_service.py` - 12 unit tests covering rendering, missing placeholder handling, Cyrillic support, schema tag generation, type selection (all 5 cases), and page data helpers

## Decisions Made

- Simple regex `{{placeholder}}` replacement (not Jinja2) for JSON-LD templates — templates are JSON strings, not HTML; Jinja2 would add unnecessary complexity and risk breaking JSON syntax
- `render_schema_template` logs warning (not exception) on invalid JSON output — returns raw string as fallback for resilience
- `select_schema_type_for_page` defaults to `Article` for unknown content/page type combinations — safe fallback for all unrecognized content

## Deviations from Plan

None - plan executed exactly as written. Both tasks were implemented together in commit `2f67de2` during concurrent wave 2 execution.

## Issues Encountered

None — the implementation was straightforward. Tests run with env vars injected (no DB connection required for pure-function tests).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Schema template engine ready for consumption by audit fix service (v3-02-05) and any WP content pipeline integration
- `render_schema_for_page(db, site_id, page_data, content_type, page_type)` is the single high-level entry point
- System default templates seeded in migration 0021 (Plan 01) are consumed correctly by `get_template` fallback logic

---
*Phase: v3-02-content-audit*
*Completed: 2026-04-03*
