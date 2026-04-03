# Phase v4-05: Секция «Аналитика» - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate all analytics pages (Analytics Workspace, Gap Analysis, Architecture, Metrika, Traffic Analysis, Competitors) into the sidebar «Аналитика» section with Tailwind CSS. Preserve all interactive elements (Chart.js, D3.js, HTMX, async operations).

</domain>

<decisions>
## Implementation Decisions

### Navigation Structure
- **D-01:** Keep existing 6 children in NAV_SECTIONS: Воркспейс, Gap-анализ, Архитектура, Трафик (Metrika), Анализ трафика, Конкуренты — no changes needed

### Site Selector & Behavior
- **D-02:** window.location redirect on site change (established pattern from v4-04 D-03)
- **D-03:** Show "Выберите сайт" placeholder when no site selected (established pattern)

### Tailwind Migration
- **D-04:** All 6 templates + _widget.html partial get pure Tailwind migration — zero `style=` attributes. Follow v4-02/v4-03/v4-04 established pattern.
- **D-05:** Preserve all existing functionality: Chart.js graphs (Metrika, Traffic Analysis), D3.js tree (Architecture), HTMX interactions, multi-step wizard (Analytics), file uploads, date pickers, modal dialogs. No functional changes.

### Claude's Discretion
- **D-06:** All Tailwind class choices, plan splitting strategy, and migration order — Claude decides based on template complexity and file groupings
- **D-07:** Whether Metrika _widget.html partial needs migration (used by dashboard) — Claude checks and decides

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Navigation System
- `app/navigation.py` — NAV_SECTIONS with «Аналитика» children
- `app/template_engine.py` — Template injection of nav context

### Analytics Templates
- `app/templates/analytics/index.html` — Analytics Workspace (367 lines, multi-step wizard, keyword filter, sessions)
- `app/templates/gap/index.html` — Gap Analysis (227 lines, dual import, summary cards, gap keywords table)
- `app/templates/architecture/index.html` — Architecture (211 lines, SF import, D3.js tree, page roles, inlinks diff)
- `app/templates/metrika/index.html` — Metrika (437 lines, Chart.js, KPI cards, date pickers, events CRUD)
- `app/templates/metrika/_widget.html` — Metrika widget partial (50 lines, used by dashboard)
- `app/templates/traffic_analysis/index.html` — Traffic Analysis (581 lines, anomaly detection, charts, sessions, bot filter)
- `app/templates/competitors/index.html` — Competitors (130 lines, form, table, compare modal)

### Routers
- `app/routers/analytics.py` — Analytics Workspace API
- `app/routers/gap.py` — Gap Analysis API
- `app/routers/architecture.py` — Architecture API
- `app/routers/metrika.py` — Metrika API
- `app/routers/traffic_analysis.py` — Traffic Analysis API
- `app/routers/competitors.py` — Competitors API
- `app/main.py` — UI routes for analytics, metrika, competitors

### v4 Migration Pattern
- `app/templates/positions/index.html` — v4-04 positions (complex template with Chart.js — reference)
- `.planning/ROADMAP-v4.md` — v4 milestone roadmap

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Chart.js already used in Metrika and Traffic Analysis
- D3.js used in Architecture for URL tree visualization
- HTMX patterns: hx-get, hx-post for Metrika events, competitor compare
- Multi-step wizard pattern in Analytics Workspace

### Established Patterns
- v4-02/v4-03/v4-04 Tailwind: explicit classes, zero inline style=, grid-cols-* layouts
- Badge colors: bg-emerald-100/text-emerald-700, bg-red-100/text-red-700, bg-sky-100/text-sky-700
- Chart.js canvas elements preserved as-is (positions template pattern from v4-04)

### Integration Points
- Metrika _widget.html is included by dashboard (v4-02) — ensure Tailwind migration doesn't break dashboard widget
- Some routes served from routers directly (/gap, /architecture, /traffic-analysis), others from main.py (/ui/analytics, /ui/metrika, /ui/competitors)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — follow established Tailwind migration pattern across all templates.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: v4-05-section-analytics*
*Context gathered: 2026-04-03*
