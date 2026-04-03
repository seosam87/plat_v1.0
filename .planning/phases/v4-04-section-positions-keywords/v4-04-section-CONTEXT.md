# Phase v4-04: Секция «Позиции и ключи» - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate all keyword, position, cluster, cannibalization, intent, and bulk operation pages into the sidebar «Позиции и ключи» section with Tailwind CSS. All pages must respond to site selector changes. Upload page moves to «Настройки» (handled in v4-07).

</domain>

<decisions>
## Implementation Decisions

### Navigation Structure
- **D-01:** Keep existing 6 children in NAV_SECTIONS: Ключевые слова, Позиции, Кластеры, Каннибализация, Интент, Массовые операции — no changes needed
- **D-02:** Upload page (/ui/uploads) moves to «Настройки» section — NOT this phase. Remove or update any "Import" links on keywords page to point to future location in Настройки. This will be addressed in Phase v4-07.

### Site Selector Behavior
- **D-03:** When user changes site in site selector, use `window.location` redirect — JS replaces {site_id} in the current URL path and navigates. Full page reload but sidebar persists. No HTMX partial replacement needed.
- **D-04:** All 6 pages are site-dependent — show "Выберите сайт" placeholder when no site selected (established pattern from v4-03)

### Tailwind Migration
- **D-05:** All 6 templates get pure Tailwind migration — zero `style=` attributes, use Tailwind utility classes throughout. Follow v4-02/v4-03 established pattern.
- **D-06:** Preserve all existing functionality: HTMX inline edits, Chart.js modals, async task polling, filter panels, export buttons. No functional changes.

### Claude's Discretion
- **D-07:** Tailwind class choices for each template — Claude decides optimal Tailwind patterns (grid layouts, badge colors, table styles) based on v4-02/v4-03 established patterns
- **D-08:** Whether to split into multiple plans by page group or process all 6 templates in fewer plans — Claude decides based on file size and complexity

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Navigation System
- `app/navigation.py` — NAV_SECTIONS definition with «Позиции и ключи» children
- `app/template_engine.py` — Template injection of nav context, site_id resolution
- `app/templates/components/sidebar.html` — Sidebar rendering

### Keywords & Positions
- `app/templates/keywords/index.html` — Keywords list (table, add form, group filter, HTMX inline edits, pagination)
- `app/templates/positions/index.html` — Positions (distribution bar, filters, table, Chart.js modal, compare modal, lost/gained modal, async check)
- `app/routers/keywords.py` — Keywords API
- `app/routers/positions.py` — Positions API (distribution, history, compare, lost-gained, check)

### Clusters & Semantics
- `app/templates/clusters/index.html` — Clusters (cards with intent dropdown, auto-cluster, CSV export)
- `app/templates/clusters/cannibalization.html` — Cannibalization detection (resolution forms, status history)
- `app/templates/intent/index.html` — Intent detection (async analysis, proposals table, bulk confirm)
- `app/routers/clusters.py` — Clusters + cannibalization API
- `app/routers/intent.py` — Intent detection API

### Bulk Operations
- `app/templates/bulk/index.html` — Bulk ops (filter panel, selectable table, move/assign/delete, import/export)
- `app/routers/bulk.py` — Bulk operations API

### Upload (reference only — moves to v4-07)
- `app/templates/uploads/index.html` — File upload page (Topvisor/KC/SF)
- `app/routers/uploads.py` — Upload API

### v4 Migration Pattern
- `app/templates/sites/index.html` — v4-03 site list (Tailwind reference pattern)
- `app/templates/dashboard/index.html` — v4-02 dashboard (Tailwind reference pattern)
- `.planning/ROADMAP-v4.md` — v4 milestone roadmap

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `templates.TemplateResponse` auto-injects nav context, site_id, breadcrumbs
- `.card` CSS class used in v4-02/v4-03 for table sections
- HTMX patterns throughout: hx-get, hx-post, hx-target, hx-swap, HX-Trigger headers
- Chart.js already loaded in positions page for history chart
- Async task polling pattern (positions check, intent detection) with 3s intervals

### Established Patterns
- v4-02/v4-03 Tailwind: explicit classes, zero inline style=, grid-cols-* layouts
- Badge colors: bg-emerald-100/text-emerald-700 (success), bg-red-100/text-red-700 (error), bg-sky-100/text-sky-700 (info)
- Site selector onChange: `window.location.href` with URL substitution

### Integration Points
- Site selector JS in base.html — already handles site change redirect
- Keywords page links to /ui/uploads (needs update when uploads moves to Настройки)
- Clusters page links to cannibalization and intent pages (cross-section links OK)
- Bulk page import section may need redirect to new uploads location

</code_context>

<specifics>
## Specific Ideas

No specific requirements — follow v4-02/v4-03 Tailwind migration pattern across all 6 templates.

</specifics>

<deferred>
## Deferred Ideas

- Upload page (/ui/uploads) migration to «Настройки» — Phase v4-07
- Any import links on keywords/bulk pages will temporarily point to /ui/uploads until v4-07 relocates it

</deferred>

---

*Phase: v4-04-section-positions-keywords*
*Context gathered: 2026-04-03*
