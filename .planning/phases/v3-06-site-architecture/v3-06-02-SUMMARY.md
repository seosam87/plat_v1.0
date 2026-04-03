---
phase: v3-06-site-architecture
plan: "02"
subsystem: api
tags: [architecture, screaming-frog, sitemap, url-tree, inlinks, role-detection, sqlalchemy]

requires:
  - phase: v3-06-01
    provides: ArchitectureRole enum, Page.source field, SitemapEntry, PageLink models, migration 0025

provides:
  - architecture_service.py with SF import, sitemap parse/fetch/compare, URL tree, role detection, inlinks diff
  - 10 passing unit tests covering pure functions (tree, sitemap, diff)

affects: [v3-06-03, any router/task using architecture_service]

tech-stack:
  added: []
  patterns:
    - "pure functions (build_url_tree, parse_sitemap_xml, compute_inlinks_diff) tested without DB"
    - "async DB functions (import_sf_data, compare_sitemap, detect_architecture_roles) use AsyncSession"
    - "sync DB function (save_page_links) uses Session for Celery compatibility"
    - "_classify_role heuristic uses URL patterns + page_type + inlinks_count for role assignment"

key-files:
  created:
    - app/services/architecture_service.py
    - tests/test_architecture_service.py
  modified: []

key-decisions:
  - "SF import uses synthetic crawl_job_id (uuid4()) per import — sitemap unique constraint is (crawl_job_id, url)"
  - "build_url_tree returns D3.js-compatible nested dict with page_count computed recursively"
  - "detect_architecture_roles classifies authority/trigger first (URL patterns), then pillar/service/article by page_type"
  - "link_accelerator threshold: inlinks >= 10 for informational pages"
  - "save_page_links is sync (Session) for Celery task context; all other DB functions are async"

patterns-established:
  - "Role detection: URL patterns take priority over page_type heuristics"
  - "Sitemap comparison normalizes URLs by stripping trailing slash before set operations"

requirements-completed: []

duration: 5min
completed: 2026-04-03
---

# Phase v3-06 Plan 02: Architecture Service Summary

**Architecture service implementing SF import, sitemap fetch/compare, D3-compatible URL tree, heuristic role detection (8 roles), and inlinks diff — with 10 passing unit tests for all pure functions**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-03T08:24:00Z
- **Completed:** 2026-04-03T08:29:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Full `architecture_service.py` with 8 public functions covering all plan requirements
- URL tree builder producing D3.js-compatible nested structure with recursive `page_count`
- Sitemap XML parser handling both regular sitemaps and sitemap index files
- Architecture role auto-detection using URL patterns + `page_type` + `inlinks_count` heuristics
- 10 unit tests covering URL tree (4), sitemap parsing (3), inlinks diff (3) — all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create architecture_service.py** - `77e4733` (feat)
2. **Task 2: Unit tests** - `77e4733` (feat — committed together with service)

**Plan metadata:** (this commit)

## Files Created/Modified
- `app/services/architecture_service.py` — SF import, sitemap parse/fetch/compare, URL tree, role detection, inlinks diff, save_page_links
- `tests/test_architecture_service.py` — 10 pure-function tests (tree, sitemap, diff)

## Decisions Made
- SF import uses a synthetic `crawl_job_id = uuid.uuid4()` per call since the unique constraint is `(crawl_job_id, url)` — each SF import creates its own partition of pages
- `build_url_tree` recursively computes `page_count` as count of all descendant pages (leaves with a `full_url`)
- `detect_architecture_roles` checks authority/trigger URL patterns first, then pillar (landing + high inlinks), then service/subservice (URL segment depth), then article/link_accelerator, defaulting to `unknown`
- `save_page_links` is synchronous (`Session`) to be safe for Celery sync task context; all other functions use `AsyncSession`

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None — the service and tests existed from a prior parallel execution (commit `77e4733`). Verified all acceptance criteria pass before writing this SUMMARY.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Architecture service complete — ready for v3-06-03 (router/UI wiring)
- All pure functions tested; async DB functions require integration test environment

---
*Phase: v3-06-site-architecture*
*Completed: 2026-04-03*
