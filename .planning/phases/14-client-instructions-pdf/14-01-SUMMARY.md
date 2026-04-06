---
phase: 14-client-instructions-pdf
plan: 01
subsystem: database, pdf, reporting
tags: [weasyprint, subprocess, jinja2, sqlalchemy, celery, client-report, pdf-generation]

# Dependency graph
requires:
  - phase: 13-impact-scoring-growth-opportunities
    provides: error_impact_scores table, impact_score_service query patterns
  - phase: 12-analytical-foundations
    provides: quick_wins_service.get_quick_wins(), dead_content_service.get_dead_content()

provides:
  - ClientReport SQLAlchemy model (client_reports table, UUID pk, site_id FK, blocks_config JSON, pdf_data LargeBinary, status lifecycle)
  - Alembic migration 0039 creating client_reports table with ix_cr_site_created index
  - subprocess_pdf.render_pdf_in_subprocess() — WeasyPrint rendering in child process with timeout (D-12 memory leak fix)
  - client_report_service with gather_report_data(), generate_client_report(), and CRUD helpers
  - All 7 Russian instruction templates hardcoded per D-07
  - Jinja2 PDF template app/templates/reports/client_instructions.html (A4, inline CSS, Russian)

affects:
  - 14-02 (Celery task + router consume ClientReport model and generate_client_report service)
  - 14-03 (UI page uses get_report_history, create_report_record)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Subprocess PDF isolation: render_pdf_in_subprocess() runs WeasyPrint in child process to prevent memory leak"
    - "INSTRUCTION_TEMPLATES dict: hardcoded Russian instruction text per check_code type"
    - "gather_report_data(): aggregates 4 data sources into unified problem_groups list"
    - "TOP_N=20 limit per problem group with overflow tracking"

key-files:
  created:
    - app/models/client_report.py
    - alembic/versions/0039_add_client_reports.py
    - app/services/subprocess_pdf.py
    - app/services/client_report_service.py
    - app/templates/reports/client_instructions.html
  modified: []

key-decisions:
  - "TOP_N=20 per problem group (D-02 discretion) — balances readability vs completeness"
  - "subprocess.run with Python -c script for WeasyPrint isolation (D-12) — simplest approach, no multiprocessing module complexity"
  - "Audit errors deduplicated against quick_wins groups — same issue type not shown twice in report"

patterns-established:
  - "subprocess_pdf pattern: write HTML to temp file, run child process, read PDF bytes, cleanup both temp files in finally block"
  - "blocks_config dict pattern: {'quick_wins': bool, 'audit_errors': bool, 'dead_content': bool, 'positions': bool}"

requirements-completed: [CPDF-01, CPDF-02, CPDF-03]

# Metrics
duration: 4min
completed: 2026-04-06
---

# Phase 14 Plan 01: Client Instructions PDF — Backend Foundation Summary

**ClientReport model + subprocess-isolated WeasyPrint renderer + data aggregation service with 7 Russian instruction templates and A4 Jinja2 PDF template**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-06T20:08:40Z
- **Completed:** 2026-04-06T20:12:55Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- ClientReport SQLAlchemy model with UUID pk, site_id FK (CASCADE), blocks_config JSON, pdf_data LargeBinary, status lifecycle (pending/generating/ready/failed), and Alembic migration 0039
- subprocess_pdf.render_pdf_in_subprocess() runs WeasyPrint in a child process with configurable timeout — child exits after rendering, freeing all WeasyPrint-leaked memory (D-12)
- client_report_service.gather_report_data() aggregates Quick Wins (grouped by issue type), audit errors (from error_impact_scores, grouped by check_code), dead content pages, and position statistics into a unified problem_groups list with overflow tracking
- All 7 Russian instruction templates (D-07): 404, noindex, missing_toc, missing_schema, thin_content, low_internal_links, dead_content — with D-06 деловой-прямой imperative tone
- A4 Jinja2 PDF template with inline CSS only (no Tailwind CDN), summary box (indigo left border), problem groups with overflow notes, position distribution bar chart, Russian footer

## Task Commits

1. **Task 1: ClientReport model, migration 0039, subprocess PDF renderer** - `209ad1d` (feat)
2. **Task 2: client_report_service + Jinja2 PDF template** - `0e97f01` (feat)

## Files Created/Modified

- `app/models/client_report.py` — ClientReport SQLAlchemy model
- `alembic/versions/0039_add_client_reports.py` — Migration creating client_reports table + ix_cr_site_created index
- `app/services/subprocess_pdf.py` — render_pdf_in_subprocess() with subprocess.run and temp file cleanup
- `app/services/client_report_service.py` — gather_report_data(), generate_client_report(), INSTRUCTION_TEMPLATES, CRUD helpers
- `app/templates/reports/client_instructions.html` — A4 PDF template with Russian text, summary-box, problem groups, position distribution

## Decisions Made

- TOP_N=20 per problem group (D-02 set at Claude's discretion) — sufficient for actionability without overwhelming the specialist
- subprocess.run with `-c` script chosen over multiprocessing.Process — simpler, no shared memory concerns, clear child process boundary
- Audit errors deduplicated against quick_wins groups to avoid the same issue type appearing twice in the same report

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. Migration 0039 needs to be applied to the database as part of the normal deployment process.

## Next Phase Readiness

- ClientReport model and migration ready — Plan 14-02 can create the Celery task using create_report_record/save_report_pdf/mark_report_failed
- generate_client_report() ready for consumption by the Celery task in Plan 14-02
- get_report_history() and get_report_by_id() ready for the UI router in Plan 14-03
- Template loads and renders correctly — verified via Jinja2 Environment import test

---
*Phase: 14-client-instructions-pdf*
*Completed: 2026-04-06*
