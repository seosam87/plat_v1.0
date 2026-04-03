# Phase v4-03: Секция «Сайты» - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate all site management functionality into the sidebar «Сайты» section. Restructure navigation to 3 sub-items (Список, Краулы, Расписание), remove the standalone site detail page, enrich the site list with key metrics, and convert crawl/feed templates to Tailwind.

</domain>

<decisions>
## Implementation Decisions

### Navigation Structure
- **D-01:** Sidebar «Сайты» section gets 3 children: «Список сайтов» (/ui/sites), «Краулы» (/ui/sites/{site_id}/crawls), «Расписание» (new page, /ui/sites/{site_id}/schedule)
- **D-02:** Remove «Детали сайта» from NAV_SECTIONS entirely
- **D-03:** Краулы and Расписание are site-dependent — show "Выберите сайт" placeholder when no site selected in site selector (same pattern as other site-dependent sections)

### Site List Page
- **D-04:** Light redesign: rewrite to Tailwind + add key metrics from detail.html (keyword count, crawl count, open tasks count) as additional columns or inline badges in site rows
- **D-05:** Keep table layout (not cards), retain existing columns (Name, URL, Group, WP Username, Status, Schedule, Active, Actions) and add metrics

### Detail Page Removal
- **D-06:** Delete detail.html template entirely — Quick Actions covered by sidebar, Recent Tasks/Crawls available through dedicated pages, Metrika belongs in Аналитика section
- **D-07:** Key metrics (Keywords, Crawls, Tasks counts) move to site list rows (D-04)

### Claude's Discretion
- **D-08:** Detail URL (/ui/sites/{site_id}/detail) handling — Claude decides whether to add 301 redirect to /ui/sites or simply remove the route
- **D-09:** Schedule page format — Claude decides optimal layout (table of all sites with schedules vs per-site detailed view) based on existing codebase patterns

### Crawls & Change Feed
- **D-10:** Rewrite crawl/history.html and crawl/feed.html to Tailwind — preserve existing functionality (filters, HTMX partials, diff display)
- **D-11:** Add "Запустить краул" button to crawl history page — currently crawl is triggered from detail.html which is being removed
- **D-12:** feed_rows.html partial — Tailwind migration, keep HTMX swap pattern intact

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Navigation System
- `app/navigation.py` — NAV_SECTIONS definition, build_sidebar_sections(), resolve_nav_context()
- `app/template_engine.py` — Central template injection of nav context, site_id resolution
- `app/templates/components/sidebar.html` — Sidebar rendering, active state styling

### Site Management (current)
- `app/templates/sites/index.html` — Current site list template (to be redesigned)
- `app/templates/sites/detail.html` — Detail page being removed (reference for metrics to extract)
- `app/templates/sites/create.html` — Site creation form
- `app/templates/sites/edit.html` — Site edit form
- `app/routers/sites.py` — Site API router (CRUD, verify, schedule endpoints)
- `app/main.py` — UI route handlers for /ui/sites/*

### Crawl Pages
- `app/templates/crawl/history.html` — Crawl history template (to be Tailwind-migrated)
- `app/templates/crawl/feed.html` — Change feed template (to be Tailwind-migrated)
- `app/templates/crawl/feed_rows.html` — HTMX partial for feed rows
- `app/routers/crawl.py` — Crawl router (history page, feed page, API)

### v4 Migration Pattern
- `app/templates/dashboard/index.html` — v4-02 dashboard rewrite (reference for Tailwind pattern)
- `app/templates/base.html` — v4 base layout with sidebar
- `.planning/ROADMAP-v4.md` — v4 milestone roadmap with phase dependencies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `templates.TemplateResponse` from `app/template_engine.py` — auto-injects nav context, site_id, breadcrumbs
- `.card` CSS class — used by v4-02 for table sections, retain for consistency
- HTMX patterns in crawl/feed: `hx-get` with filter parameter, `hx-target` tbody swap
- Site schedule HTMX handler already exists in main.py (POST /ui/sites/{site_id}/schedule)

### Established Patterns
- v4-02 Tailwind pattern: explicit classes, no inline style=, grid-cols-* for layout
- Sidebar active state: `resolve_nav_context()` matches URL to section/child
- Site-dependent pages: check `selected_site_id`, redirect or show placeholder

### Integration Points
- NAV_SECTIONS in `navigation.py` — update children list for «Сайты» section
- `main.py` — add new schedule page route, add redirect or remove detail route
- `crawl.py` — add crawl trigger endpoint accessible from history page (currently only via sites router)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the established v4 Tailwind migration pattern.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: v4-03-section-sites*
*Context gathered: 2026-04-03*
