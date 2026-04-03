---
phase: v3-04-analytics-workspace
verified: 2026-04-03T10:00:00Z
status: gaps_found
score: 5/7 must-haves verified
re_verification: false
gaps:
  - truth: "User can trigger position check and SERP parse via Celery tasks that actually produce data"
    status: failed
    reason: "check_group_positions catches ImportError for missing check_single_keyword_position and marks session positions_checked without writing any position data. parse_group_serp calls parse_serp() but only parse_serp_sync() exists — all keywords fail silently, parsed=0, session advances to serp_parsed with zero SERP records."
    artifacts:
      - path: "app/tasks/analytics_tasks.py"
        issue: "check_group_positions: check_single_keyword_position does not exist in position_service.py; ImportError is caught, task still marks session positions_checked without actually checking positions"
      - path: "app/tasks/analytics_tasks.py"
        issue: "parse_group_serp: calls parse_serp() but serp_parser_service.py only exports parse_serp_sync(); all keywords fail with AttributeError (caught silently), parsed=0 always"
    missing:
      - "Either add async parse_serp() wrapper in serp_parser_service.py that calls parse_serp_sync() via asyncio.run_in_executor, or change _parse_serp to call parse_serp_sync directly via loop.run_in_executor"
      - "Add check_single_keyword_position() to position_service.py or change _check_group to use the existing write_position/write_positions_batch pattern with XMLProxy/existing position check flow"
  - truth: "SERP-to-brief pipeline produces real data end-to-end"
    status: failed
    reason: "Because parse_group_serp always produces zero SERP records, get_session_serp_summary returns empty, get_top_competitor returns None, crawl_competitor_pages returns early (no competitor_domain set), and generate_brief produces a brief with empty headings_json and empty competitor_data_json. The pipeline completes but produces hollow output."
    artifacts:
      - path: "app/tasks/analytics_tasks.py"
        issue: "Downstream consequence of parse_serp missing: competitor detection, crawl, and brief generation all proceed but produce empty/minimal results"
    missing:
      - "Fix parse_group_serp to call the correct serp_parser_service function (see gap above)"
human_verification:
  - test: "6-step wizard navigation in browser"
    expected: "Each step indicator click shows the correct step panel; step-6 (brief result) correctly shows generated brief text after generateBrief() call"
    why_human: "JS showStep() DOM manipulation and step indicator highlighting can only be verified visually in a browser"
  - test: "Session creation and keyword selection flow"
    expected: "Selecting keywords from filter results, naming a session, and clicking Save Session creates a session and advances to step 2 with correct keyword count"
    why_human: "Multi-step JS state (selectedKwIds, currentSessionId) and DOM update after API response requires browser"
---

# Phase v3-04: Analytics Workspace Verification Report

**Phase Goal:** Analytics Workspace — Filter keywords -> save temp group (session) -> check positions -> SERP analysis -> competitor comparison -> content brief (TZ) generation. Step-by-step wizard interface.
**Verified:** 2026-04-03T10:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can filter keywords by 8+ axes (frequency, position, intent, cluster, group, region, engine, search) | VERIFIED | `analytics_service.filter_keywords` implements all 8 axes; `GET /analytics/sites/{site_id}/keywords` endpoint wired with all query params; wizard step 1 renders filter form with all fields populated from `filter_options` |
| 2 | User can save keyword selection as a named analysis session | VERIFIED | `create_session` persists `AnalysisSession` with keyword_ids JSON; `POST /sites/{site_id}/sessions` endpoint wired; JS `saveSession()` calls endpoint and advances to step 2 |
| 3 | User can trigger position check and SERP parse via Celery tasks | FAILED | `check_group_positions` task marks session `positions_checked` without writing position data (missing `check_single_keyword_position`); `parse_group_serp` task always produces 0 parsed results (`parse_serp` function does not exist — only `parse_serp_sync` exists in `serp_parser_service.py`) |
| 4 | SERP results show top competitor domains with site type classification | PARTIAL | `analyze_serp_results`, `classify_site_type`, and `get_session_serp_summary` are fully implemented and tested; `GET /sessions/{session_id}/serp-summary` returns real analysis — but the upstream SERP parse task produces zero data, so in practice summary will always be empty |
| 5 | User can view side-by-side competitor vs own-site SEO comparison | VERIFIED | `GET /sessions/{session_id}/comparison` queries both `CompetitorPageData` (from session) and `Page` (from crawl data matching keyword target_urls); comparison endpoint returns structured `{our_pages, competitor_pages}` dict; wizard step 4 renders HTML table from this data |
| 6 | User can generate a content brief (TZ) from session data | VERIFIED | `generate_brief` in `brief_service.py` assembles `ContentBrief` from session keywords, competitor headings (via `build_heading_structure`), and SEO field suggestions; brief export as text and CSV implemented; wizard step 5/6 wired via JS `generateBrief()` -> `POST /sessions/{id}/brief` -> `GET /briefs/{id}/export` |
| 7 | All workflow steps are accessible via a 6-step wizard UI | VERIFIED | `app/templates/analytics/index.html` (367 lines) renders all 6 step panels with `showStep()` JS toggling; navigation accessible from base.html (`/ui/analytics`) and `sites/detail.html` (`/analytics/sites/{id}`) |

**Score:** 5/7 truths verified (2 failed/partial)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models/analytics.py` | 4 models + SessionStatus enum | VERIFIED | 142 lines; AnalysisSession, SessionSerpResult, CompetitorPageData, ContentBrief with correct field specs and UniqueConstraint |
| `alembic/versions/0023_add_analytics_workspace_tables.py` | Migration creating 4 tables + sessionstatus enum | VERIFIED | revision="0023", down_revision="0022"; 4 `op.drop_table` in downgrade |
| `app/services/analytics_service.py` | filter_keywords, session CRUD, export | VERIFIED | 358 lines; all required functions present with real DB queries |
| `app/services/serp_analysis_service.py` | classify_site_type, analyze_serp_results, save_serp_results, get_top_competitor | VERIFIED | 181 lines; pure functions and async DB layer fully implemented |
| `app/services/brief_service.py` | generate_brief, build_heading_structure, suggest_seo_fields, export functions | VERIFIED | 281 lines; all required functions implemented |
| `app/tasks/analytics_tasks.py` | check_group_positions, parse_group_serp, crawl_competitor_pages Celery tasks | STUB | 291 lines; tasks exist and are structured correctly, but check_group_positions does not actually check positions and parse_group_serp always produces 0 results due to missing function references |
| `app/routers/analytics.py` | 20 endpoints at /analytics prefix | VERIFIED | 472 lines; 20 `@router` decorators confirmed; all workflow endpoints present |
| `app/templates/analytics/index.html` | 6-step wizard UI | VERIFIED | 367 lines; all 6 step panels rendered; JS state (selectedKwIds, currentSessionId, currentBriefId) maintained across steps |
| `tests/test_analytics_models.py` | 5 unit tests | VERIFIED | 60 lines; 5 test functions covering enum and all 4 model instantiations |
| `tests/test_analytics_service.py` | 6 unit tests | VERIFIED | 47 lines; 6 test functions for CSV export |
| `tests/test_serp_analysis_service.py` | 10 unit tests | VERIFIED | 97 lines; 10 test functions for classification and SERP analysis |
| `tests/test_brief_service.py` | 8 unit tests | VERIFIED | 85 lines; 8 test functions for pure brief generation functions |
| `tests/test_analytics_integration.py` | 6 integration tests | VERIFIED | 111 lines; 6 pure-function integration tests composing SERP analysis and brief workflow |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/main.py` | `app/routers/analytics.py` | `app.include_router(analytics_router)` | WIRED | Line 175 in main.py; line 37 import confirmed |
| `app/routers/analytics.py` | `app/services/analytics_service.py` | `from app.services import analytics_service as ans` | WIRED | Line 16 import; filter_keywords, session CRUD all called from router |
| `app/routers/analytics.py` | `app/services/brief_service.py` | `from app.services import brief_service as bs` | WIRED | Line 18 import; generate_brief, list_briefs, get_brief, export_brief_text/csv called |
| `app/routers/analytics.py` | `app/services/serp_analysis_service.py` | `from app.services import serp_analysis_service as sas` | WIRED | Line 17 import; get_session_serp_summary called from serp-summary endpoint |
| `app/routers/analytics.py` | `app/tasks/analytics_tasks.py` | `check_group_positions.delay()` | WIRED | Lines 202-224; all three Celery tasks triggered via .delay() from router endpoints |
| `app/celery_app.py` | `app/tasks/analytics_tasks.py` | `include="app.tasks.analytics_tasks"` | WIRED | Line 19 in celery_app.py includes analytics_tasks |
| `app/tasks/analytics_tasks.py` | `app/services/position_service.check_single_keyword_position` | `from app.services.position_service import check_single_keyword_position` | NOT_WIRED | Function does not exist in position_service.py; ImportError caught silently; positions are NOT actually checked |
| `app/tasks/analytics_tasks.py` | `app/services/serp_parser_service.parse_serp` | `from app.services.serp_parser_service import parse_serp` | NOT_WIRED | Only parse_serp_sync() exists; `parse_serp` import raises AttributeError; SERP data is NEVER written |
| `app/templates/analytics/index.html` | `GET /analytics/sites/{id}/keywords` | JS fetch() in searchKeywords() | WIRED | Line 238; response used to populate keyword table |
| `app/templates/analytics/index.html` | `POST /analytics/sites/{id}/sessions` | JS fetch() in saveSession() | WIRED | Line 258-263; session id stored in currentSessionId |
| `app/templates/base.html` | `/ui/analytics` | `<a href="/ui/analytics">Аналитика</a>` | WIRED | Line 48 |
| `app/templates/sites/detail.html` | `/analytics/sites/{id}` | `<a href="/analytics/sites/{{ site.id }}">` | WIRED | Line 47 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `analytics/index.html` step 1 | filter results table | `GET /analytics/sites/{id}/keywords` -> `filter_keywords()` -> DB query | Yes — real KeywordPosition subquery | FLOWING |
| `analytics/index.html` step 3 | SERP summary divs | `GET /sessions/{id}/serp-summary` -> `get_session_serp_summary()` -> DB query on SessionSerpResult | Source exists but parse_group_serp task never writes SessionSerpResult records | STATIC (empty in practice) |
| `analytics/index.html` step 4 | comparison table | `GET /sessions/{id}/comparison` -> DB query on CompetitorPageData + Page | Source exists but crawl_competitor_pages depends on SERP data that's never written | STATIC (empty in practice) |
| `analytics/index.html` step 5/6 | brief content | `POST /sessions/{id}/brief` -> `generate_brief()` -> DB insert ContentBrief | Brief is created with real keywords but empty headings (no competitor data) and no competitor summary | PARTIAL |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| analytics router importable | `python -c "from app.routers.analytics import router"` | Not run (would need venv setup) | SKIP |
| migration revision correct | `grep 'revision = "0023"' alembic/versions/0023_add_analytics_workspace_tables.py` | Found | PASS |
| router has 20 endpoints | `grep -c "@router" app/routers/analytics.py` | 20 | PASS |
| analytics_tasks registered | `grep "analytics_tasks" app/celery_app.py` | Found at line 19 | PASS |
| parse_serp function exists | `grep "def parse_serp" app/services/serp_parser_service.py` | Not found (only parse_serp_sync) | FAIL |
| check_single_keyword_position exists | `grep "def check_single_keyword_position" app/services/position_service.py` | Not found | FAIL |

### Requirements Coverage

No requirement IDs declared in PLAN frontmatter (`requirements_addressed: []` across all 7 plans). Phase goal from ROADMAP-v3.md is narrative only. Verification assessed against observable truths derived from the goal.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/tasks/analytics_tasks.py` | 57-62 | `except (ImportError, Exception): checked += 1` swallows failure and falsely advances state | Blocker | Position check step completes with "success" but writes zero position records; misleads user that positions were checked |
| `app/tasks/analytics_tasks.py` | 119-133 | `from serp_parser_service import parse_serp` fails (only parse_serp_sync exists); all keywords silently skipped, parsed=0 | Blocker | SERP parse step reports success but writes zero SessionSerpResult records; competitor detection, crawl, and brief heading generation all fail downstream |

### Human Verification Required

### 1. 6-Step Wizard Navigation

**Test:** Open `/analytics/sites/{site_id}` in browser; click each numbered step indicator (1-6); verify panel visibility changes and active indicator highlights in indigo.
**Expected:** Each step panel appears/hides correctly; only the active step is visible; step indicator turns indigo for the active step.
**Why human:** JS `showStep()` DOM manipulation can only be verified in a browser.

### 2. Keyword Filter and Session Save Flow

**Test:** Use the filter form to search for keywords, check several rows, enter a session name, click "Сохранить сессию".
**Expected:** Session is created (POST returns 201), step advances to 2, session name and keyword count display correctly.
**Why human:** Multi-step client state (selectedKwIds Set, currentSessionId) and DOM updates after fetch() require browser interaction.

## Gaps Summary

Two blockers in the Celery tasks layer prevent real data from flowing through the analytics pipeline:

**Gap 1: Position check task is a no-op.** `_check_group` in `analytics_tasks.py` imports `check_single_keyword_position` from `position_service.py`, which does not exist. The `ImportError` is caught silently, `checked` is incremented anyway, and the session is marked `positions_checked` without any position data being written. This misleads users and leaves Step 3 data empty.

**Gap 2: SERP parse task always produces zero results.** `_parse_serp` attempts to import `parse_serp` from `serp_parser_service.py`, but only `parse_serp_sync` exists. Every keyword throws an exception (caught silently with a warning log), resulting in `parsed=0`. Since no `SessionSerpResult` records are written, `get_session_serp_summary` returns empty data, `get_top_competitor` returns None, `crawl_competitor_pages` exits early (no competitor domain set), and `generate_brief` produces a brief with no headings and no competitor summary.

The entire SERP → Competitor Detection → Comparison → Brief pipeline is end-to-end hollow because the SERP parse task is broken. The service layer (analysis functions, DB helpers, brief generation) is fully correct and well-tested. Only the two Celery task function references need to be fixed to restore end-to-end data flow.

The filter, session CRUD, wizard UI, router, models, migration, and all pure-function logic are fully verified and wired correctly.

---

_Verified: 2026-04-03T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
