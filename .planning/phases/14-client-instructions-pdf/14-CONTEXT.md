# Phase 14: Client Instructions PDF - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can generate a configurable PDF report for site owners that explains each SEO problem and its fix steps in plain Russian, using subprocess-isolated WeasyPrint. The report combines Quick Wins, audit errors, Dead Content, and position statistics into a non-technical format grouped by problem type. A dedicated sidebar section provides generation UI, delivery (download/email/Telegram), and report history.

</domain>

<decisions>
## Implementation Decisions

### Report Content
- **D-01:** Configurable blocks via checkboxes before generation: Quick Wins, audit errors (with impact_score), Dead Content, position statistics. User selects which blocks to include.
- **D-02:** TOP-N limit per block — show highest-priority items (by opportunity_score / impact_score), remainder summarized as "и ещё N проблем". Exact N at Claude's discretion.
- **D-03:** Brief summary at the top of the report: pages checked, total problems found, critical count, overall assessment (3-5 lines).

### Instruction Format
- **D-04:** Target audience is a technical specialist (developer / content manager), not the site owner directly. No step-by-step WP admin button instructions.
- **D-05:** Problems grouped by type (all "нет TOC" together, then all "нет schema", etc.) — specialist fixes one type in batch.
- **D-06:** Tone: деловой-прямой, императив. Example: "Добавьте FAQ schema через Yoast → Custom Schema на следующих страницах:"
- **D-07:** Each problem type has a Russian-language instruction template explaining the fix approach. Standard types covered: 404, noindex, missing TOC, missing schema, thin content, low internal links.

### Entry Point & UX
- **D-08:** Dedicated sidebar section "Клиентские отчёты" — not inside existing reports section.
- **D-09:** Single page: site selector + block checkboxes + "Сгенерировать" button + history table of previously generated PDFs.
- **D-10:** Delivery: download button per report + send to email + send to Telegram. All three channels available.
- **D-11:** Report history stored in DB with date, site, selected blocks. Can re-download or re-send.

### Subprocess Isolation
- **D-12:** WeasyPrint runs in a subprocess per report to prevent memory leak from killing the Celery worker. Implementation details (fork, multiprocessing, subprocess.run) at Claude's discretion.

### Claude's Discretion
- TOP-N limit value per block (likely 15-25)
- Subprocess isolation approach (multiprocessing.Process, subprocess.run, or similar)
- Whether to migrate existing `generate_pdf_report()` to subprocess isolation too
- Summary assessment logic (how to compute "overall health" indicator)
- PDF template visual design — clean, professional, consistent with existing `reports/brief.html` style
- Sidebar section icon and placement within existing navigation structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing PDF infrastructure
- `app/services/report_service.py` — Current `generate_pdf_report()` with WeasyPrint (synchronous call in executor). Pattern to extend or replace with subprocess isolation.
- `app/templates/reports/brief.html` — Existing PDF template with inline CSS, A4 layout, Jinja2 variables. Reference for styling.
- `app/templates/reports/detailed.html` — Detailed report template.
- `app/tasks/report_tasks.py` — Celery tasks for report generation and delivery.
- `app/routers/reports.py` — Report router endpoints.

### Data sources for report content
- `app/services/quick_wins_service.py` — `get_quick_wins()` returns pages with opportunity_score, issue flags.
- `app/services/dead_content_service.py` — Dead content detection with recommendations.
- `app/services/impact_score_service.py` — `error_impact_scores` table, impact scoring logic.
- `app/models/audit.py` — `AuditCheckDefinition` (code, name, severity, applies_to) and `AuditResult` models.

### Delivery infrastructure
- `app/celery_app.py` — Celery config with Redis broker.
- Telegram delivery — existing integration (see report_tasks.py).
- SMTP delivery — existing aiosmtplib integration.

### Navigation
- `app/templates/components/sidebar.html` — Sidebar with 6 sections. New section to be added.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `report_service.generate_pdf_report()`: WeasyPrint rendering pattern (Jinja2 → HTML → PDF). Will need subprocess wrapper.
- `reports/brief.html`: CSS styling for A4 PDF — reuse font sizes, colors, table styles.
- `quick_wins_service.get_quick_wins()`: Returns ranked pages with issues — direct data source.
- `dead_content_service`: Dead content with recommendations — direct data source.
- `impact_score_service`: Audit errors ranked by traffic impact — direct data source.
- `report_tasks.py`: Celery task pattern for async PDF generation and delivery.
- `brief_service.py`: Russian-language brief formatting (`format_brief_text()`) — reference for tone/structure.

### Established Patterns
- Jinja2 templates with inline CSS for PDF (no Tailwind — WeasyPrint doesn't support CDN)
- Celery tasks with `retry=3` for external calls (email, Telegram)
- HTMX partial updates for UI interactions
- Tailwind CSS for web UI templates (sidebar, pages)
- `asyncio.get_event_loop().run_in_executor()` for sync operations in async context

### Integration Points
- New sidebar section: add to `sidebar.html` component
- New model: `ClientReport` (site_id, blocks_config, pdf_bytes or file_path, created_at)
- New Celery task: `generate_client_pdf` with subprocess isolation
- New router: `/ui/client-reports/` for the dedicated section
- Delivery reuses existing Telegram bot and SMTP infrastructure

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-client-instructions-pdf*
*Context gathered: 2026-04-06*
