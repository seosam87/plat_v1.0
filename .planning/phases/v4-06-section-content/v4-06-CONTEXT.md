# Phase v4-06: Секция «Контент» - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate all content-related pages — Content Audit, WP Pipeline (jobs), DOCX Publisher, Projects, Kanban, Content Plan, and Change Monitoring — into the sidebar «Контент» section with Tailwind CSS. Pure visual migration: preserve all existing functionality (HTMX interactions, modals, tabs, forms, diff viewer, status transitions). No backend changes.

</domain>

<decisions>
## Implementation Decisions

### Navigation Structure
- **D-01:** Keep existing children in NAV_SECTIONS for «Контент» — no changes needed. Navigation config already defines the correct sub-items.

### Site Selector & Behavior
- **D-02:** `window.location` redirect on site change (established pattern from v4-04/v4-05)
- **D-03:** Show "Выберите сайт" placeholder when no site selected (established pattern)

### Tailwind Migration
- **D-04:** All 7 templates get pure Tailwind migration — zero `style=` attributes. Follow v4-02/v4-03/v4-04/v4-05 established pattern.
- **D-05:** Preserve all existing functionality: HTMX status transitions (Kanban), diff modal (Pipeline jobs), tab viewer (Publisher), alert rules management (Monitoring), audit checks with modals (Audit). No functional changes.

### Claude's Discretion
- **D-06:** All Tailwind class choices, plan splitting strategy, and migration order — Claude decides based on template complexity and logical groupings.
- **D-07:** How to split 7 templates into plans — recommended: group by domain (pipeline+publisher, projects+kanban+plan, monitoring, audit) into 2-3 plans.
- **D-08:** Kanban card styling, badge colors, grid layout — follow existing Tailwind patterns from v4-04/v4-05 (emerald/red/sky/amber badge palette).
- **D-09:** Audit page modal and form patterns — follow existing modal patterns from positions/analytics templates.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Navigation System
- `app/navigation.py` — NAV_SECTIONS with «Контент» children
- `app/template_engine.py` — Template injection of nav context

### Content Templates (migration targets)
- `app/templates/audit/index.html` — Content Audit (300 lines, stats cards, filters, checks table, CTA editor, schema modals)
- `app/templates/pipeline/publish.html` — DOCX Publisher (133 lines, upload form, preview, tabs, recent table)
- `app/templates/pipeline/jobs.html` — Pipeline Jobs (133 lines, job table, bulk actions, diff modal)
- `app/templates/projects/index.html` — Projects list (80 lines, form, table)
- `app/templates/projects/kanban.html` — Kanban board (78 lines, 5-column grid, task cards, HTMX transitions)
- `app/templates/projects/plan.html` — Content Plan (49 lines, items table, create draft button)
- `app/templates/monitoring/index.html` — Change Monitoring (162 lines, stats, alert rules, digest settings, history)

### Routers (for understanding URL patterns)
- `app/routers/content_audit.py` — Content audit endpoints
- `app/routers/wp_pipeline.py` — Pipeline endpoints
- `app/routers/projects.py` — Projects/kanban endpoints
- `app/routers/monitoring.py` — Monitoring endpoints
- `app/main.py` — UI routes for content pages

### v4 Migration Pattern (reference)
- `app/templates/positions/index.html` — v4-04 complex Tailwind migration reference
- `app/templates/analytics/index.html` — v4-05 multi-section Tailwind reference
- `app/templates/intent/index.html` — v4-04 modal + table pattern reference
- `.planning/ROADMAP-v4.md` — v4 milestone roadmap

### Prior Phase Context (content domain knowledge)
- `.planning/phases/v3-02-content-audit/v3-02-CONTEXT.md` — Content audit decisions (page types, checklists, schema templates)
- `.planning/phases/v3-03-change-monitoring/v3-03-CONTEXT.md` — Monitoring decisions (alert rules, digest, Telegram)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Tailwind badge palette from v4-04/v4-05: `bg-emerald-100/text-emerald-700`, `bg-red-100/text-red-700`, `bg-sky-100/text-sky-700`, `bg-amber-100/text-amber-700`
- HTMX patterns: `hx-get`, `hx-post`, `hx-patch` for Kanban status transitions, pipeline approvals
- Modal pattern from positions/intent templates (hidden div + JS toggle)
- Tab pattern from publisher (JS tab switching)
- Chart.js not used in content templates — simpler migration than analytics

### Established Patterns
- v4-02..v4-05 Tailwind: explicit utility classes, zero inline `style=`, `grid-cols-*` layouts
- Form inputs: `w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-indigo-500 focus:border-indigo-500`
- Buttons: `px-3 py-1.5 text-sm font-medium rounded bg-indigo-600 text-white hover:bg-indigo-700`
- Stat cards: `bg-white rounded-lg shadow-sm border border-gray-200 text-center p-4`

### Integration Points
- Sidebar navigation already configured for «Контент» section
- All routers already registered in `app/main.py`
- No new routes needed — just template visual migration

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Migration pattern is well-established from v4-02 through v4-05.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: v4-06-section-content*
*Context gathered: 2026-04-04*
