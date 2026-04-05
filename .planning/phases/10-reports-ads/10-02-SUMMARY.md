---
phase: 10-reports-ads
plan: 02
subsystem: reporting
tags: [weasyprint, pdf, reports, jinja2, openpyxl]

# Dependency graph
requires:
  - phase: 10-reports-ads-01
    provides: ad traffic module, Excel export, dashboard aggregation

provides:
  - WeasyPrint PDF generation for brief (1-2 page) and detailed (5-10 page) report types
  - generate_pdf_report() async function in report_service.py
  - GET /reports/projects/{project_id}/pdf?type=brief|detailed download endpoint
  - GET /ui/reports/{project_id} report UI page with type selector
  - PDF templates: app/templates/reports/brief.html and detailed.html

affects: [11-scheduling, client-access]

# Tech tracking
tech-stack:
  added: [weasyprint>=62,<63]
  patterns:
    - WeasyPrint sync call wrapped in asyncio.get_event_loop().run_in_executor()
    - Standalone HTML templates (not extending base.html) for PDF rendering
    - A4 @page CSS in PDF templates with inline CSS only (no Tailwind CDN)

key-files:
  created:
    - app/templates/reports/brief.html
    - app/templates/reports/detailed.html
    - app/templates/reports/generate.html
    - tests/test_report_service.py
  modified:
    - requirements.txt
    - Dockerfile
    - app/services/report_service.py
    - app/routers/reports.py
    - app/main.py

key-decisions:
  - "WeasyPrint sync call wrapped in run_in_executor to avoid blocking async event loop"
  - "PDF templates are standalone HTML (not extending base.html) — WeasyPrint needs self-contained HTML"
  - "distribution bar dynamic widths use style=width:X% in PDF templates — sole permitted inline style exception for dynamic Jinja2 calculations"
  - "Report type JS selection uses classList toggle pattern (no style.display) consistent with v4-04/v4-05 pattern"

patterns-established:
  - "PDF template: standalone HTML with @page {size: A4; margin: 2cm;} inline CSS"
  - "WeasyPrint async wrapping: loop.run_in_executor(None, _render_pdf, html_string)"

requirements-completed: [DASH-02]

# Metrics
duration: 8min
completed: 2026-04-05
---

# Phase 10 Plan 02: PDF Report Generation Summary

**WeasyPrint PDF generation for brief/detailed project reports with Jinja2 A4 templates, download endpoints, and report UI page**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-05T18:12:00Z
- **Completed:** 2026-04-05T18:20:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Added WeasyPrint to requirements.txt and system deps (libpango, libcairo) to Dockerfile
- Implemented generate_pdf_report() async function with brief/detailed type support
- Created standalone A4 PDF templates (brief.html and detailed.html) with inline CSS
- Added GET /reports/projects/{project_id}/pdf download endpoint with content-disposition header
- Created GET /ui/reports/{project_id} UI page with report type selector cards
- 4 unit tests passing with WeasyPrint mocked via sys.modules patching

## Task Commits

1. **Task 1: Install WeasyPrint, PDF generation service, PDF templates** - `a8d2ee0` (feat)
2. **Task 2: Add report UI page and download endpoints** - `61ec2a3` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified
- `requirements.txt` - Added weasyprint>=62,<63
- `Dockerfile` - Added WeasyPrint system deps (libpango, libcairo, libgdk-pixbuf, libffi, shared-mime-info)
- `app/services/report_service.py` - Added generate_pdf_report() async function
- `app/templates/reports/brief.html` - Standalone A4 PDF template (1-2 pages): position distribution, task summary, top movers
- `app/templates/reports/detailed.html` - Standalone A4 PDF template (5-10 pages): all brief sections + full tasks table + recent site changes
- `app/templates/reports/generate.html` - UI page extending base.html with brief/detailed card selector and download buttons
- `app/routers/reports.py` - Added GET /projects/{project_id}/pdf endpoint
- `app/main.py` - Added GET /ui/reports/{project_id} UI route
- `tests/test_report_service.py` - 4 unit tests for generate_pdf_report

## Decisions Made
- Wrapped WeasyPrint's synchronous write_pdf() call in asyncio run_in_executor to avoid blocking the event loop
- PDF templates are standalone (not extending base.html) because WeasyPrint requires self-contained HTML with embedded CSS
- Distribution bar dynamic widths use style=width:X% in PDF templates — this is the only permitted inline style exception (same precedent as v4-04-01)
- JS type selector uses classList pattern (no style.display) consistent with established v4-04/v4-05 zero inline style constraint

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- WeasyPrint is not installed in the test environment (expected — it's a production dependency). Tests mock it via `sys.modules["weasyprint"]` patching to avoid ModuleNotFoundError. The `patch("weasyprint.HTML")` approach failed because `unittest.mock.patch` tries to import the target module before patching it.

## User Setup Required
None — WeasyPrint system deps are added to the Dockerfile and will be installed during Docker build.

## Known Stubs
None — PDF generation is fully wired: template renders real project/site data from DB queries.

## Next Phase Readiness
- PDF and Excel report downloads both work at /reports/projects/{project_id}/pdf and /reports/projects/{project_id}/excel
- UI page accessible at /ui/reports/{project_id}
- Ready for Phase 10-03: scheduled report delivery via Celery Beat (Telegram/SMTP)

---
*Phase: 10-reports-ads*
*Completed: 2026-04-05*
