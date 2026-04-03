---
phase: v3-02-content-audit
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, postgresql, content-audit, schema-org]

# Dependency graph
requires:
  - phase: v3-02-content-audit
    provides: CONTEXT.md — phase goals and content audit design
provides:
  - ContentType enum (informational/commercial/unknown) on Page model
  - cta_template_html field on Site model
  - AuditCheckDefinition model with 7 seeded default checks
  - AuditResult model with per-page per-check status tracking
  - SchemaTemplate model with 5 seeded default templates
  - Alembic migration 0021 creating all audit tables
affects: [v3-02-02, v3-02-03, v3-02-04, v3-02-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Audit check definitions as DB rows — enables configurable checklist without code deploy"
    - "Schema templates with site_id=None as system-wide defaults (overridable per site)"
    - "SAEnum with native_enum=True for ContentType (PostgreSQL ENUM type)"

key-files:
  created:
    - app/models/audit.py
    - alembic/versions/0021_add_content_audit_tables.py
    - tests/test_audit_models.py
  modified:
    - app/models/crawl.py
    - app/models/site.py

key-decisions:
  - "ContentType enum uses str+PyEnum pattern (informational/commercial/unknown) matching existing PageType style"
  - "AuditResult uses (site_id, page_url, check_code) unique constraint — upsert-friendly design"
  - "SchemaTemplate site_id nullable — NULL = system default, UUID = site override"

patterns-established:
  - "Audit seed data via op.bulk_insert in migration — 7 check definitions + 5 schema templates"
  - "auto_fixable + fix_action on AuditCheckDefinition drives the fix pipeline in later plans"

requirements-completed: []

# Metrics
duration: 15min
completed: 2026-04-02
---

# Phase v3-02 Plan 01: Models, migrations, and seed data for content audit Summary

**ContentType enum on Page, cta_template_html on Site, and three new audit tables (audit_check_definitions, audit_results, schema_templates) with Alembic migration 0021 seeding 7 default checks and 5 schema templates**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-02T07:30:00Z
- **Completed:** 2026-04-02T07:45:00Z
- **Tasks:** 5
- **Files modified:** 5

## Accomplishments

- `ContentType` enum (informational/commercial/unknown) added to `crawl.py` and wired to `Page.content_type` column
- `cta_template_html` (Text, nullable) added to `Site` model for per-site CTA HTML block storage
- Three SQLAlchemy models in `app/models/audit.py`: `AuditCheckDefinition`, `AuditResult`, `SchemaTemplate`
- Alembic migration 0021 creates all tables, columns, indexes, unique constraints, and seeds 12 rows of default data
- 6-test unit test suite passes confirming enum values, field presence, and model instantiation

## Task Commits

Each task was committed atomically:

1. **Task 01: Add content_type enum and field to Page model** - `9d7f6c2` (feat)
2. **Task 02: Add cta_template_html field to Site model** - `9d7f6c2` (feat — combined with task 01)
3. **Task 03: Create audit models file with three tables** - `73d5f7d` (feat)
4. **Task 04: Create Alembic migration 0021** - `db57b0b` (feat)
5. **Task 05: Unit tests for audit models** - `e54b65a` (test)

## Files Created/Modified

- `app/models/crawl.py` — Added `ContentType` enum and `Page.content_type` mapped column
- `app/models/site.py` — Added `Site.cta_template_html` Text column
- `app/models/audit.py` — Three new models: `AuditCheckDefinition`, `AuditResult`, `SchemaTemplate`
- `alembic/versions/0021_add_content_audit_tables.py` — Migration: contenttype PG enum, 3 tables, 2 columns, seed data
- `tests/test_audit_models.py` — 6 unit tests covering enum values, field presence, model instantiation

## Decisions Made

- ContentType enum uses `native_enum=True` (PostgreSQL ENUM type) consistent with PageType pattern in the codebase
- `AuditResult` UniqueConstraint on `(site_id, page_url, check_code)` enables safe upsert semantics in the audit engine
- `SchemaTemplate.site_id` is nullable — `NULL` means system-wide default, UUID means site-specific override (overrides system defaults for same schema_type)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Data layer complete; Plan 02 (audit service with check engine and HTML detection) can proceed
- `ContentType` enum available for use in crawl service and audit service
- `AuditCheckDefinition` seed data in DB enables check engine to query active checks without hardcoding
- Migration 0021 must run before any audit service code executes

---
*Phase: v3-02-content-audit*
*Completed: 2026-04-02*
