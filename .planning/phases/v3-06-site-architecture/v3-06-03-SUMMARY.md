---
phase: v3-06-site-architecture
plan: "03"
subsystem: ui
tags: [fastapi, jinja2, htmx, d3js, architecture, sitemap, inlinks]

# Dependency graph
requires:
  - phase: v3-06-01
    provides: ArchitectureRole, SitemapEntry, PageLink models and migration 0025
  - phase: v3-06-02
    provides: architecture_service with URL tree, sitemap, role detection, inlinks diff

provides:
  - FastAPI architecture router with 10 endpoints (SF import, sitemap fetch/upload/results, tree, detect-roles, role override, roles list, inlinks-diff)
  - Jinja2 template architecture/index.html with D3.js collapsible tree, sitemap comparison, role map, inlinks diff
  - Architecture page registered in main.py and linked from site detail page

affects:
  - future UI phases that link from site detail
  - any phase that extends architecture features

# Tech tracking
tech-stack:
  added: [d3.js v7 (CDN)]
  patterns:
    - architecture router follows gap.py pattern (file upload via NamedTemporaryFile, HTMX JSON responses)
    - D3.js collapsible tree loaded from JSON endpoint, role-colored nodes
    - All Russian UI copy, Tailwind-compatible inline styles

key-files:
  created:
    - app/routers/architecture.py
    - app/templates/architecture/index.html
  modified:
    - app/main.py (import + include_router already present)
    - app/templates/sites/detail.html (Архитектура button already present)

key-decisions:
  - "D3.js v7 loaded from CDN (unpkg) to avoid build toolchain for interactive tree visualization"
  - "Architecture router prefix /architecture matches help module map entry in main.py"
  - "Sitemap results endpoint accepts optional status filter (all/orphan/missing) for progressive loading"

patterns-established:
  - "Architecture router: all endpoints require_admin, follow gap.py file upload pattern"
  - "D3.js tree: role-colored nodes (pillar=purple, service=blue, article=green, trigger=orange, authority=teal, link_accelerator=pink)"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-03
---

# Phase v3-06 Plan 03: Router, D3.js tree UI, and integration Summary

**FastAPI architecture router with 10 endpoints + D3.js collapsible URL tree + sitemap/role/inlinks Jinja2 UI, integrated into site detail page**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-03T08:27:00Z
- **Completed:** 2026-04-03T08:32:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Architecture router with all 10 required endpoints: SF import, sitemap fetch/upload/results, URL tree, detect-roles, role override, roles grouped list, inlinks diff
- Jinja2 template with D3.js v7 collapsible tree, sitemap comparison table (orphan/missing/ok), architecture role map with editable selects, inlinks diff view with crawl selector
- Router registered in main.py and Архитектура button already present in sites/detail.html

## Task Commits

Each task was committed atomically:

1. **Task 01: Create architecture router** - `103846b` (feat)
2. **Task 02: Create architecture page template with D3.js tree** - `103846b` (feat)
3. **Task 03: Register router and add button** - `103846b` (feat — all three tasks in single commit, files already existed)

## Files Created/Modified
- `app/routers/architecture.py` - 10 endpoints: SF import, sitemap fetch/upload/results, URL tree JSON, detect-roles, role PUT, roles GET, inlinks-diff
- `app/templates/architecture/index.html` - Full architecture page: D3.js tree, sitemap comparison, role map with editable selects, inlinks diff
- `app/main.py` - Import and registration of architecture_router (already in place)
- `app/templates/sites/detail.html` - "Архитектура" button link to /architecture/{site_id} (already in place)

## Decisions Made
- D3.js loaded from unpkg CDN (d3@7) to avoid build toolchain
- Architecture router follows identical pattern to gap.py for file upload handling
- Sitemap results endpoint has `status` query parameter for filtering without full page reload

## Deviations from Plan

None - all files were already created and committed in commit `103846b` during prior execution. This SUMMARY captures the documentation of that completed work.

## Issues Encountered
None — all acceptance criteria verified:
- `grep -c "@router" app/routers/architecture.py` returns 10 (plan required ≥9)
- D3 CDN reference confirmed
- "Архитектура сайта" text confirmed in template
- "Screaming Frog" text confirmed in template
- sitemap reference confirmed
- pillar reference confirmed
- architecture_router in main.py confirmed
- "Архитектура" in sites/detail.html confirmed

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase v3-06 (Site Architecture) is fully complete: models, migration, service layer, and UI/router all implemented
- Architecture page accessible at /architecture/{site_id}
- SF import ready to accept CSV/XLSX Screaming Frog exports
- Sitemap comparison, D3 tree, role management, and inlinks diff all wired end-to-end

---
*Phase: v3-06-site-architecture*
*Completed: 2026-04-03*
