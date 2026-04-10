---
phase: 24-tools-infrastructure-fast-tools
verified: 2026-04-10T09:00:00Z
status: gaps_found
score: 5/7 must-haves verified
gaps:
  - truth: "Results page shows partial results when job status is 'partial'"
    status: failed
    reason: "router tool_results only fetches result rows when job.status == 'complete'; 'partial' jobs return empty results_rows list even though DB has rows"
    artifacts:
      - path: "app/routers/tools.py"
        issue: "Line 400: `if job.status == 'complete':` — should be `if job.status in ('complete', 'partial'):`"
    missing:
      - "Change condition in tool_results to load results rows for both complete and partial status"
  - truth: "Meta Tag Parser results page renders correct data (input_url, meta_description columns)"
    status: failed
    reason: "tools/commercialization/results.html and tools/meta-parser/results.html (shared template copies) use wrong column names for the meta-parser slug: r.url instead of r.input_url, r.description instead of r.meta_description; and r.relevant_url/r.top3_competitors instead of r.url/r.top_competitors for relevant-url slug"
    artifacts:
      - path: "app/templates/tools/commercialization/results.html"
        issue: "Lines 108,110: uses r.url and r.description for meta-parser section; lines 122,124: uses r.relevant_url and r.top3_competitors for relevant-url section"
      - path: "app/templates/tools/meta-parser/results.html"
        issue: "Same wrong column references as above (it is a copy of commercialization/results.html)"
    missing:
      - "Fix meta-parser section in both templates: r.url → r.input_url, r.description → r.meta_description"
      - "Fix relevant-url section in both templates: r.relevant_url → r.url, r.top3_competitors → r.top_competitors (these sections are unreachable since router dispatches to tools/{slug}/results.html, but they are dead buggy code)"
      - "Note: tools/relevant-url/results.html uses correct column names and is the actual template used for relevant-url slug"
human_verification:
  - test: "Submit 5 phrases to Commercialization Check and verify XMLProxy integration works end-to-end in Docker"
    expected: "Job transitions from pending to running to complete; results show commercialization %, intent, geo flag"
    why_human: "Requires live Docker environment with XMLProxy credentials configured"
  - test: "Submit 3 URLs to Meta Tag Parser and verify async fetch returns real meta data"
    expected: "title, H1, meta description, canonical extracted correctly from real pages"
    why_human: "Requires network access to external URLs inside Docker"
  - test: "Submit phrases to Relevant URL Finder with a target domain and verify TOP-10 filtering"
    expected: "Matching URLs from target domain appear with correct positions; non-matching phrase shows 'Не найден'"
    why_human: "Requires live XMLProxy credentials in Docker"
---

# Phase 24: Tools Infrastructure & Fast Tools — Verification Report

**Phase Goal:** Users can access a new "Tools" sidebar section with three standalone SERP instruments — commercialization check, meta-tag parser, and relevant URL finder — each running as an async Celery job with typed result storage, downloadable CSV output, and no site binding required

**Verified:** 2026-04-10T09:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Tools sidebar section appears, accessible to admin and manager roles | VERIFIED | `app/navigation.py` has `id: "tools"`, `icon: "wrench"`, `admin_only: False`; sidebar template has wrench SVG block at lines 48 and 94 |
| 2 | Each tool follows input form → submit → HTMX polling → results table → CSV/XLSX download UX | VERIFIED | All 3 tool landing templates have form + job list; results templates have status partial + export links; `hx-trigger="load delay:10s"` confirmed in all 3 job_status.html partials |
| 3 | Commercialization Check: 200 phrases, returns %, intent, geo-dependency, powered by XMLProxy | VERIFIED | `CommerceCheckJob` model, `analyze_commercialization` service, `run_commerce_check` Celery task all exist and importable; limit=200 in TOOL_REGISTRY; 5/5 service tests pass |
| 4 | Meta Tag Parser: 500 URLs, returns HTTP status, title, H1, H2 list, meta description, canonical; async httpx + Semaphore(5) | VERIFIED | `MetaParseJob/Result` models, `fetch_and_parse_urls` service with `asyncio.Semaphore(5)`; 5/5 service tests pass |
| 5 | Relevant URL Finder: 100 phrases + domain, returns matching URL, position, top-3 competitors | VERIFIED | `RelevantUrlJob/Result` models with `target_domain`, `find_relevant_url` service with `_normalize_domain`; 9/9 service tests pass |
| 6 | All tools rate-limited (10/min), Celery-only, retry=3, service-layer tests pass | VERIFIED | `@limiter.limit("10/minute")` on tool_submit; all 3 Celery tasks have `max_retries=3`; 31/31 tests pass |
| 7 | Results page shows results for partial jobs (XMLProxy balance exhaustion) | FAILED | Router `tool_results` only fetches rows when `job.status == "complete"` (line 400). Template shows the results card for both `complete` and `partial`, but the router passes empty `results_rows=[]` for partial jobs. Partial results saved to DB by Celery tasks but never shown in UI. |

**Score:** 6/7 truths verified (Truth 7 fails due to router gap; Truth 4 partially fails due to template column name bugs — see below)

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `app/navigation.py` | VERIFIED | Contains tools entry with wrench icon |
| `app/templates/tools/index.html` | VERIFIED | Contains "Инструменты SEO" heading, loops over tools, shows job_count badges |
| `app/routers/tools.py` | VERIFIED | TOOL_REGISTRY with all 3 slugs, 7 handlers, rate limiting, lazy imports |
| `app/models/commerce_check_job.py` | VERIFIED | CommerceCheckJob + CommerceCheckResult with correct columns |
| `app/models/meta_parse_job.py` | VERIFIED | MetaParseJob + MetaParseResult with input_urls, url_count |
| `app/models/relevant_url_job.py` | VERIFIED | RelevantUrlJob + RelevantUrlResult with target_domain, top_competitors |
| `app/services/commerce_check_service.py` | VERIFIED | analyze_commercialization with COMMERCIAL_THRESHOLD=60 |
| `app/services/meta_parse_service.py` | VERIFIED | fetch_and_parse_urls with asyncio.Semaphore(5) |
| `app/services/relevant_url_service.py` | VERIFIED | find_relevant_url with _normalize_domain |
| `app/tasks/commerce_check_tasks.py` | VERIFIED | run_commerce_check, max_retries=3, handles codes 32/33 |
| `app/tasks/meta_parse_tasks.py` | VERIFIED | run_meta_parse, max_retries=3, asyncio.run() bridge |
| `app/tasks/relevant_url_tasks.py` | VERIFIED | run_relevant_url, max_retries=3, handles codes 32/33 |
| `app/templates/tools/commercialization/results.html` | STUB | Wrong column names for meta-parser section (r.url, r.description) and relevant-url section (r.relevant_url, r.top3_competitors). Since router dispatches by slug, meta-parser slug uses this template and renders blank data for URL and description columns |
| `app/templates/tools/meta-parser/results.html` | STUB | Same wrong column names as above (copy of commercialization template) |
| `app/templates/tools/relevant-url/results.html` | VERIFIED | Correct column names: r.url, r.top_competitors |
| `alembic/versions/0047_add_commerce_check_tables.py` | VERIFIED | File exists |
| `alembic/versions/0048_add_meta_parse_tables.py` | VERIFIED | File exists |
| `alembic/versions/0049_add_relevant_url_tables.py` | VERIFIED | File exists |
| `tests/test_tools_router.py` | VERIFIED | 12 tests, all pass |
| `tests/test_commerce_check_service.py` | VERIFIED | 5 tests, all pass |
| `tests/test_meta_parse_service.py` | VERIFIED | 5 tests, all pass |
| `tests/test_relevant_url_service.py` | VERIFIED | 9 tests, all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/navigation.py` | `app/templates/components/sidebar.html` | wrench icon rendering | VERIFIED | Sidebar has `{% elif section.icon == 'wrench' %}` at lines 48 and 94 |
| `app/routers/tools.py` | `app/templates/tools/index.html` | TemplateResponse | VERIFIED | `templates.TemplateResponse(request, "tools/index.html", ...)` |
| `app/routers/tools.py` | `app/models/commerce_check_job.py` | `_get_tool_models` | VERIFIED | Lazy import in `_get_tool_models` function |
| `app/tasks/commerce_check_tasks.py` | `app/services/xmlproxy_service.py` | `search_yandex_sync` | VERIFIED | Lazy import + call inside task body |
| `app/tasks/commerce_check_tasks.py` | `app/services/commerce_check_service.py` | `analyze_commercialization` | VERIFIED | Lazy import + call inside task body |
| `app/tasks/meta_parse_tasks.py` | `app/services/meta_parse_service.py` | `fetch_and_parse_urls` | VERIFIED | Lazy import + `asyncio.run()` call |
| `app/tasks/relevant_url_tasks.py` | `app/services/xmlproxy_service.py` | `search_yandex_sync` | VERIFIED | Lazy import + call inside task body |
| `app/tasks/relevant_url_tasks.py` | `app/services/relevant_url_service.py` | `find_relevant_url` | VERIFIED | Lazy import + call inside task body |
| `app/celery_app.py` | task modules | include list | VERIFIED | `commerce_check_tasks`, `meta_parse_tasks`, `relevant_url_tasks` all in include= |
| `app/routers/tools.py` | `app/templates/tools/{slug}/results.html` | TemplateResponse | PARTIAL | Router dispatches correctly; but commercialization/results.html and meta-parser/results.html contain wrong column names for their own slug sections |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `tools/index.html` | `tools` (with `job_count`) | `tools_index` queries `func.count(Model.id)` per tool | Yes — real DB count queries | FLOWING |
| `tools/commercialization/results.html` | `results` | `tool_results` — `select(ResultModel)` | Yes (when status=complete) | FLOWING for complete; HOLLOW for partial |
| `tools/meta-parser/results.html` | `results` (rendered as `r.url`, `r.description`) | DB query returns `MetaParseResult` rows with `input_url`, `meta_description` | Rows exist but wrong attrs accessed | HOLLOW — columns `r.url` and `r.description` don't exist on `MetaParseResult`; Jinja2 returns blank/empty for missing attrs |
| `tools/relevant-url/results.html` | `results` | `tool_results` fetches `RelevantUrlResult` rows | Yes, correct columns (`r.url`, `r.top_competitors`) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Navigation entry exists | `python -c "from app.navigation import NAV_SECTIONS; assert any(s['id']=='tools' for s in NAV_SECTIONS)"` | exit 0 | PASS |
| Celery task modules registered | `python -c "from app.celery_app import celery_app; includes = celery_app.conf.get('include', []); assert 'app.tasks.commerce_check_tasks' in includes"` | exit 0 | PASS |
| All 3 tasks importable | `python -c "from app.tasks.commerce_check_tasks import run_commerce_check; from app.tasks.meta_parse_tasks import run_meta_parse; from app.tasks.relevant_url_tasks import run_relevant_url"` | exit 0 | PASS |
| Service layer tests (31 total) | `python -m pytest tests/test_tools_router.py tests/test_commerce_check_service.py tests/test_meta_parse_service.py tests/test_relevant_url_service.py -v` | 31 passed, 15 warnings | PASS |
| Commerce check analyze works | `python -c "from app.services.commerce_check_service import analyze_commercialization; r = analyze_commercialization('купить', [{'domain':'ozon.ru','title':'','url':'','snippet':'','position':1}]); assert r['intent']=='commercial'"` | exit 0 | PASS |

### Requirements Coverage

The requirement IDs `TOOL-INFRA-01`, `TOOL-INFRA-02`, `COM-01`, `META-01`, `REL-01` referenced in the PLAN frontmatter do **not appear** in `.planning/REQUIREMENTS.md`. REQUIREMENTS.md covers v3.0 requirements (CRM, INTAKE, TPL, DOC series) only. Phase 24 requirements are defined exclusively in ROADMAP.md under Phase 24's `Requirements:` and `Success Criteria` fields.

**Assessment:** The ROADMAP.md Success Criteria (items 1–6) serve as the effective requirements contract for this phase. Five of six are fully satisfied; item 2 (HTMX flow) is partially satisfied due to partial-status results not loading in the router; and the meta-parser results page has rendering bugs.

| ROADMAP Criterion | Status | Evidence |
|-------------------|--------|---------|
| SC-1: Tools sidebar with recent job indicators | VERIFIED | Sidebar entry + job_count badges on index |
| SC-2: Input → HTMX polling → results → CSV/XLSX | PARTIAL | Flow works for complete jobs; partial status jobs show status banner but empty results table |
| SC-3: Commercialization Check (200 phrases, XMLProxy) | VERIFIED | Full implementation with tests |
| SC-4: Meta Tag Parser (500 URLs, httpx/Semaphore) | PARTIAL | Backend correct; results.html renders r.url/r.description (blank) instead of r.input_url/r.meta_description |
| SC-5: Relevant URL Finder (100 phrases, domain, XMLProxy) | VERIFIED | Full implementation with correct template |
| SC-6: Rate limiting, Celery-only, retry=3, tests | VERIFIED | All 31 tests pass; limiter on POST; retries confirmed |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routers/tools.py` | 400 | `if job.status == "complete":` — partial results never loaded | Blocker | Partial jobs (XMLProxy balance exhaustion) show status banner but empty results table; user sees no data after partial completion |
| `app/templates/tools/commercialization/results.html` | 108,110 | `r.url`, `r.description` — wrong attribute names for meta-parser slug | Blocker | Meta Tag Parser results page renders blank URL and description columns |
| `app/templates/tools/meta-parser/results.html` | 108,110 | Same — copy of above | Blocker | Same blank columns |
| `app/templates/tools/commercialization/results.html` | 122,124 | `r.relevant_url`, `r.top3_competitors` — wrong for relevant-url slug (unused, router dispatches to relevant-url/results.html) | Warning | Dead buggy code; unreachable but confusing |

### Human Verification Required

#### 1. Commercialization Check End-to-End

**Test:** In Docker, configure XMLProxy credentials, submit 5 phrases to commercialization check, wait for completion.
**Expected:** Job shows "Готово — 5 результатов"; table rows show commercialization %, intent badges (commercial/informational/mixed), geo badge.
**Why human:** Requires live XMLProxy connection and Docker environment.

#### 2. Meta Tag Parser URL Rendering (after gap fix)

**Test:** After fixing `r.url` → `r.input_url` and `r.description` → `r.meta_description`, submit 3 real URLs to Meta Tag Parser.
**Expected:** Results table shows input URLs, titles, meta descriptions, H1s, canonical, robots.
**Why human:** Requires live network access from inside Docker container.

#### 3. Partial Result Rendering (after gap fix)

**Test:** After fixing `if job.status == "complete":` → `if job.status in ("complete", "partial"):`, simulate balance exhaustion.
**Expected:** Partial job shows "Получено N из M" banner AND renders the N results rows in the table below with export links.
**Why human:** Requires XMLProxy with near-zero balance in Docker.

### Gaps Summary

Two bugs block full goal achievement:

**Bug 1 — Router partial results not loaded (app/routers/tools.py line 400):**
The Celery tasks correctly save partial results when XMLProxy balance codes 32/33 are received, and the templates correctly show the results card for `status in ('complete', 'partial')`. But the router only executes the `select(ResultModel)` query for `status == "complete"`. A user whose balance runs out mid-run sees the amber "partial" status banner but an empty results table — defeating the partial-save feature. Fix: change `if job.status == "complete":` to `if job.status in ("complete", "partial"):`.

**Bug 2 — Meta Tag Parser results template uses wrong column names:**
`app/templates/tools/commercialization/results.html` and `app/templates/tools/meta-parser/results.html` (the latter being a copy) contain a `meta-parser` slug branch that accesses `r.url` and `r.description`. The `MetaParseResult` model has `input_url` and `meta_description` as column names. Jinja2 silently returns empty string for missing attributes, so URL and Description columns render blank for every row. Fix: change `r.url` → `r.input_url` and `r.description` → `r.meta_description` in both templates' meta-parser sections.

The relevant-url tool is unaffected because `tools/relevant-url/results.html` was written by plan 24-04 directly and uses the correct column names.

---

_Verified: 2026-04-10T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
