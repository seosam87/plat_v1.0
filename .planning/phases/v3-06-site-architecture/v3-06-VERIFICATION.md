---
phase: v3-06-site-architecture
verified: 2026-04-03T09:00:00Z
status: gaps_found
score: 9/10 must-haves verified
re_verification: false
gaps:
  - truth: "D3.js tree nodes are colored by architecture_role"
    status: failed
    reason: "The renderTree() function uses fixed colors (#4f46e5 for parent nodes, #059669 for leaves). ROLE_COLORS map is defined but not referenced inside renderTree(). The /tree API endpoint only returns url/name/page_count/children — no architecture_role field in tree nodes."
    artifacts:
      - path: "app/templates/architecture/index.html"
        issue: "renderTree() uses hardcoded fill colors, not ROLE_COLORS. Line 159: .attr('fill', d => d.children ? '#4f46e5' : '#059669')"
      - path: "app/services/architecture_service.py"
        issue: "build_url_tree() returns nodes with keys: name, full_url, page_count, children. No architecture_role field. The /tree endpoint only queries Page.url, not Page.architecture_role."
    missing:
      - "Include architecture_role in build_url_tree() node output by joining Page.architecture_role when building nodes"
      - "Update /tree endpoint to query Page.architecture_role alongside Page.url"
      - "Update renderTree() to use ROLE_COLORS: .attr('fill', d => ROLE_COLORS[d.data.role] || '#9ca3af')"
human_verification:
  - test: "SF import end-to-end"
    expected: "Upload a Screaming Frog CSV/XLSX, verify pages appear with source='sf_import' in the DB"
    why_human: "Requires a real Screaming Frog export file and live DB to verify the upsert path"
  - test: "Sitemap fetch + comparison"
    expected: "Click 'Загрузить с сайта' on a site with sitemap.xml; orphan/missing/ok counts should be non-zero and table should populate"
    why_human: "Requires live site with reachable sitemap.xml and running server"
  - test: "Collapsible tree interaction"
    expected: "D3 tree loads and renders on page open; nodes are clickable to show page details"
    why_human: "D3 DOM rendering and click behavior cannot be verified without a browser"
---

# Phase v3-06: Site Architecture Verification Report

**Phase Goal:** SF import, URL tree visualization (D3.js), sitemap comparison (orphan/missing pages), pillar-service-article role detection, inlinks diff between crawls.
**Verified:** 2026-04-03T09:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                       | Status      | Evidence                                                                    |
|----|-----------------------------------------------------------------------------|-------------|-----------------------------------------------------------------------------|
| 1  | SF CSV/XLSX can be imported, pages saved with source='sf_import'            | VERIFIED  | `import_sf_data()` sets `source="sf_import"` (line 46); POST /{site_id}/import-sf endpoint wired |
| 2  | Sitemap.xml can be fetched from site URL or uploaded                        | VERIFIED  | `fetch_sitemap()` + `upload_sitemap()` endpoints both call `compare_sitemap()`; parse handles sitemapindex |
| 3  | Orphan/missing/ok comparison persisted in SitemapEntry                      | VERIFIED  | `compare_sitemap()` upserts all three statuses; UI shows counts from sm_stats |
| 4  | URL tree returned in D3.js-compatible nested format                         | VERIFIED  | `build_url_tree()` returns `{name, full_url, page_count, children}` hierarchy; tested by 4 unit tests |
| 5  | D3.js tree renders visually with role-colored nodes                         | FAILED   | Tree renders but nodes are fixed-color (#4f46e5 / #059669). ROLE_COLORS defined but not used in renderTree(). Tree API returns no architecture_role field. |
| 6  | Architecture roles auto-detected via heuristics                             | VERIFIED  | `detect_architecture_roles()` classifies 8 roles; `_classify_role()` checks URL patterns + page_type + inlinks |
| 7  | Architecture roles editable per page via UI                                 | VERIFIED  | PUT /{site_id}/pages/{page_id}/role wired; roles table shows editable selects that call setRole() |
| 8  | Inlinks diff computed between two crawl jobs                                | VERIFIED  | `compute_inlinks_diff()` returns added/removed/counts; GET /{site_id}/inlinks-diff wired to PageLink query |
| 9  | Architecture page linked from site detail                                   | VERIFIED  | sites/detail.html line 49: "Архитектура" button links to /architecture/{site.id} |
| 10 | Router registered in main.py                                                | VERIFIED  | main.py line 39: import; line 177: app.include_router(architecture_router) |

**Score:** 9/10 truths verified

### Required Artifacts

| Artifact                                              | Expected                              | Status      | Details                                                          |
|-------------------------------------------------------|---------------------------------------|-------------|------------------------------------------------------------------|
| `app/models/architecture.py`                          | SitemapEntry + PageLink models        | VERIFIED  | Both models present, correct fields, UniqueConstraint on sitemap |
| `app/models/crawl.py`                                 | ArchitectureRole enum + Page fields   | VERIFIED  | 8-value enum; Page.source (String 20) + Page.architecture_role (SAEnum) |
| `alembic/versions/0025_add_architecture_tables.py`    | Migration for all above               | VERIFIED  | revision="0025", down_revision="0024"; creates enum, 2 columns, 2 tables, 1 index; 2 op.drop_table in downgrade |
| `app/services/architecture_service.py`                | All 8 service functions               | VERIFIED  | import_sf_data, parse_sitemap_xml, fetch_sitemap, compare_sitemap, build_url_tree, detect_architecture_roles, compute_inlinks_diff, save_page_links all present and substantive |
| `app/routers/architecture.py`                         | 10 endpoints                          | VERIFIED  | Exactly 10 @router decorators; all require_admin; file upload pattern matches gap.py |
| `app/templates/architecture/index.html`               | D3.js tree + all sections             | VERIFIED (partial) | All sections present; D3@7 CDN loaded; Russian copy; tree renders but nodes not role-colored |
| `tests/test_architecture_models.py`                   | 5 unit tests                          | VERIFIED  | 5 tests: enum count, enum values, Page fields, SitemapEntry, PageLink |
| `tests/test_architecture_service.py`                  | 9+ unit tests for pure functions      | VERIFIED  | 10 tests: 4 tree, 3 sitemap parsing, 3 inlinks diff |

### Key Link Verification

| From                               | To                                  | Via                                          | Status      | Details                                                     |
|------------------------------------|-------------------------------------|----------------------------------------------|-------------|-------------------------------------------------------------|
| `architecture/index.html`          | `POST /architecture/{id}/import-sf` | `importSF()` fetch call                      | WIRED     | Form data sent; response updates import-status span         |
| `architecture/index.html`          | `GET /architecture/{id}/tree`       | `loadTree()` → `renderTree()`                | WIRED     | Called on page load (line 208); renders D3 SVG              |
| `architecture/index.html`          | `POST /architecture/{id}/detect-roles` | `detectRoles()` fetch call               | WIRED     | POST + loadRoles() callback                                 |
| `architecture/index.html`          | `GET /architecture/{id}/roles`      | `loadRoles()` fetch call                     | WIRED     | Called on page load (line 209); renders roles table         |
| `architecture/index.html`          | `GET /architecture/{id}/inlinks-diff` | `loadInlinksDiff()` with crawl_a/b         | WIRED     | Query params from select dropdowns                          |
| `architecture_router`              | `architecture_service`              | import as arch                               | WIRED     | All 8 service functions invoked via arch.* in router        |
| `architecture_router`              | `app/main.py`                       | include_router                               | WIRED     | Lines 39 + 177 of main.py                                   |
| `build_url_tree()`                 | D3 tree visualization               | renderTree() reads d.data.name/page_count    | PARTIAL   | name/page_count rendered; architecture_role absent from node data so role-coloring impossible |

### Data-Flow Trace (Level 4)

| Artifact                         | Data Variable      | Source                                  | Produces Real Data | Status      |
|----------------------------------|--------------------|-----------------------------------------|--------------------|-------------|
| architecture/index.html (tree)   | D3 hierarchy data  | GET /tree → build_url_tree(Page.url)    | Yes — DB query on Page.url | FLOWING  |
| architecture/index.html (roles)  | roles groups dict  | GET /roles → Page query by site_id      | Yes — DB query on Page     | FLOWING  |
| architecture/index.html (sm_stats) | sm_stats object  | Page load → SitemapEntry query          | Yes — DB query on SitemapEntry | FLOWING |
| architecture/index.html (crawls) | crawls list        | Page load → CrawlJob query              | Yes — DB query on CrawlJob | FLOWING  |
| architecture/index.html (tree node color) | d.data.role | Not present in tree node data      | No — field missing from build_url_tree output | HOLLOW  |

### Behavioral Spot-Checks

Step 7b: SKIPPED for endpoints requiring DB/HTTP. Pure function checks handled by unit tests (verified in artifacts section).

| Behavior                      | Command                                                       | Result              | Status  |
|-------------------------------|---------------------------------------------------------------|---------------------|---------|
| build_url_tree produces tree  | Verified via test_architecture_service.py (10 tests)          | 10 tests pass (per SUMMARY) | PASS  |
| migration revision is 0025    | grep revision 0025_add_architecture_tables.py                 | revision = "0025"   | PASS  |
| downgrade drops 2 tables      | grep -c op.drop_table                                         | 2                   | PASS  |
| 10 router endpoints exist     | grep -c @router architecture.py                               | 10                  | PASS  |
| Router registered in main.py  | grep architecture_router app/main.py                          | lines 39, 177       | PASS  |

### Requirements Coverage

No `requirements` fields declared in any of the three PLANs (`requirements_addressed: []`). The ROADMAP-v3.md Phase 6 section does not assign formal REQ-IDs, so no orphaned requirements to flag.

Phase goal items covered:
- SF import: SATISFIED — import_sf_data + /import-sf endpoint
- URL tree visualization (D3.js): PARTIAL — tree renders; role-coloring absent
- Sitemap comparison (orphan/missing): SATISFIED — full compare_sitemap pipeline
- Pillar-service-article role detection: SATISFIED — _classify_role heuristic covers all 8 roles
- Inlinks diff between crawls: SATISFIED — compute_inlinks_diff + /inlinks-diff endpoint

### Anti-Patterns Found

| File                                       | Line | Pattern                                               | Severity | Impact                                      |
|--------------------------------------------|------|-------------------------------------------------------|----------|---------------------------------------------|
| `app/templates/architecture/index.html`    | 159  | `d.children ? '#4f46e5' : '#059669'` — hardcoded fill | Warning  | D3 tree node color ignores architecture_role; ROLE_COLORS defined but unused in renderTree() |
| `app/services/architecture_service.py`     | 54-56 | `except Exception: pass` — silent skip on insert     | Info     | Duplicate SF import rows silently skipped; no logging of how many were skipped |
| `app/routers/architecture.py`              | 229  | Returns `{"error": "..."}` with HTTP 200 on missing params | Info | Should return HTTP 400 instead of 200 with error key |

### Human Verification Required

#### 1. SF Import End-to-End

**Test:** Upload a real Screaming Frog CSV or XLSX export via the Screaming Frog import form on the architecture page.
**Expected:** Pages appear in the DB with `source='sf_import'`; the import count response is non-zero; no 500 errors.
**Why human:** Requires a real SF export file and live DB — cannot verify the screaming_frog_parser integration path without the actual file format.

#### 2. Sitemap Fetch from Live Site

**Test:** Open the architecture page for a site with a reachable sitemap.xml and click "Загрузить с сайта".
**Expected:** Status message shows non-zero total_sitemap count; orphan/missing counts update; page refreshes and sitemap comparison card shows populated data.
**Why human:** Requires a running server with network access to an external site.

#### 3. D3 Tree Collapsible Interaction

**Test:** Open the architecture page; the URL tree should render immediately on load; verify nodes display segment names and page counts in tooltips.
**Expected:** SVG renders without JS errors; tooltips show `full_url (N стр.)`; tree is scrollable.
**Why human:** D3 DOM rendering and tooltip behavior require a browser.

#### 4. Role Detection Accuracy

**Test:** After crawling a site with known pillar/service/article pages, click "Автоопределение" and verify that pages with `/uslugi/` in URL are classified as service/subservice.
**Expected:** The roles table populates with correctly classified pages matching heuristic rules.
**Why human:** Requires a real site's crawl data to assess classification quality.

### Gaps Summary

**One gap blocks full goal achievement:**

The phase goal explicitly requires "URL tree visualization (D3.js)" with role-colored nodes. The plan (v3-06-03) acceptance criteria include `grep -q "pillar|Pillar"` which passes, but the actual D3 tree rendering function (`renderTree`) uses fixed colors. The `ROLE_COLORS` constant is defined in the template but only applied to the roles table section. Additionally, `build_url_tree()` does not include `architecture_role` in node output, and the `/tree` endpoint only queries `Page.url` — so even if `renderTree` were fixed to use `ROLE_COLORS`, the data would not be present.

This is a single cohesive gap requiring three coordinated changes: (1) include `architecture_role` in tree node data from the service, (2) query it in the `/tree` endpoint, and (3) apply `ROLE_COLORS` in `renderTree()`.

All other goals are fully achieved: SF import, sitemap comparison, role detection engine, role editing UI, and inlinks diff are all implemented, wired, and tested.

---

_Verified: 2026-04-03T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
