# Phase 10: Reports & Ads - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

User can view a live dashboard aggregating all projects, export project reports as PDF and Excel, schedule automatic delivery via Telegram or email, and upload/compare ad traffic data (Yandex Direct only).

</domain>

<decisions>
## Implementation Decisions

### Dashboard
- **D-01:** Dashboard is a table of projects with key metrics per row (not cards or health map). Columns at Claude's discretion based on available DB data.
- **D-02:** Dashboard is the start page after login — URL: /ui/dashboard. Replaces current landing.
- **D-03:** Dashboard must load in <3s with 50 active projects. Use Redis cache (5-min TTL) for aggregation queries.

### Report Content & Format
- **D-04:** Two report types available — "brief" (1-2 pages: TOP-3/10/30 trends, task summary, recent site changes) and "detailed" (5-10 pages: full keyword table with changes, trend charts, all tasks with comments).
- **D-05:** User selects report type (brief/detailed) when generating.
- **D-06:** PDF = polished client-facing report (with logo, charts via WeasyPrint). Excel = raw data export for internal analytics (openpyxl).

### Delivery & Scheduling
- **D-07:** Morning digest is a compact Telegram text message (Markdown format: projects, key metrics, link to full report). Not PDF attachment.
- **D-08:** Reports go only to admin (single Telegram chat + email). No per-project recipient management.
- **D-09:** Schedule granularity: daily digest + optional weekly summary report. Configurable send time. Celery Beat + redbeat.

### Ad Traffic
- **D-10:** Only Yandex Direct as ad source. CSV format: source, date, sessions, conversions, cost.
- **D-11:** Period comparison via two date-pickers (Period A vs Period B). Table with % and absolute delta for sessions, conversions, CR%, cost-per-conversion.
- **D-12:** Weekly/monthly trend chart per source using Chart.js.

### Claude's Discretion
- Dashboard table columns — Claude selects optimal set based on available data in DB
- Chart styling and colors — follow existing Tailwind palette
- Report template design — clean, professional look

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above and REQUIREMENTS.md (DASH-01..04, ADS-01..03).

### Stack
- `CLAUDE.md` — WeasyPrint for PDF, openpyxl for Excel, python-telegram-bot 21.x, aiosmtplib, Celery Beat + redbeat, Chart.js
- `.planning/REQUIREMENTS.md` — DASH-01..04, ADS-01..03 requirement definitions

### Existing Code
- `app/templates/dashboard/index.html` — existing dashboard template (will be replaced/extended)
- `app/services/position_service.py` — position distribution queries (reusable for report data)
- `app/models/project.py` — project model with status, tasks
- `app/celery_app.py` — Celery config, task routing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/position_service.py`: get_position_distribution(), get_lost_gained_keywords() — reuse for report position data
- `app/templates/dashboard/index.html`: existing dashboard template, will need major rework
- `app/templates/components/sidebar.html`: sidebar navigation — add dashboard link
- Celery infrastructure already configured with Redis broker and redbeat

### Established Patterns
- HTMX for partial updates (all existing templates use this)
- Tailwind CSS for styling (hex palette per ui-brand)
- Jinja2 templates with {% block %} inheritance
- FastAPI async handlers with SQLAlchemy async sessions

### Integration Points
- Dashboard: new route /ui/dashboard, redirect / after login
- Reports: new endpoints /reports/projects/{id}/generate, /reports/projects/{id}/download
- Delivery: new Celery Beat tasks for morning digest and weekly summary
- Ad traffic: new model ad_traffic, new routes /ui/ads/{site_id}, CSV upload endpoint

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

*Phase: 10-reports-ads*
*Context gathered: 2026-04-05*
