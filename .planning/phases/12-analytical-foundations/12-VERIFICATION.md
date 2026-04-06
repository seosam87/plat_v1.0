---
phase: 12-analytical-foundations
verified: 2026-04-06T15:45:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 12: Analytical Foundations Verification Report

**Phase Goal:** Users can see which pages are Quick Wins (positions 4–20 with unfixed issues) and which are Dead Content (zero traffic + falling positions), backed by normalized URL JOINs and a fast position lookup table
**Verified:** 2026-04-06T15:45:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | normalize_url() strips UTM parameters, normalizes http to https, and handles trailing slash consistently | VERIFIED | 14 tests all pass; `normalize_url("http://example.com/page?utm_source=yandex")` returns `"https://example.com/page/"` |
| 2 | keyword_latest_positions table exists and contains one row per (keyword_id, engine) with the most recent position | VERIFIED | Model + migration both present; uq_klp_keyword_engine unique constraint confirmed; model import succeeds |
| 3 | After a position check batch write, keyword_latest_positions is updated automatically | VERIFIED | `refresh_latest_positions(db, site_id)` called at line 121 of position_service.py inside `write_positions_batch()` |
| 4 | Dashboard CTE query can be replaced with a simple SELECT from keyword_latest_positions | VERIFIED | keyword_latest_positions indexed on (site_id, position) via ix_klp_site_position; quick_wins_service uses `SELECT ... FROM keyword_latest_positions` |
| 5 | User can open /analytics/{site_id}/quick-wins and see pages ranked by opportunity score | VERIFIED | Route exists in quick_wins.py; service returns list sorted by opportunity_score DESC; template renders score badges |
| 6 | Each page shows TOC/Schema/Links/Content check columns as pass/fail icons | VERIFIED | quick_wins_table.html has_toc, has_schema, has_low_links, has_thin_content columns with pass/fail icon rendering |
| 7 | Opportunity score = (21 - avg_position) x weekly_traffic for pages with position 4-20 | VERIFIED | Line 127 of quick_wins_service.py: `opportunity_score = (21 - avg_pos) * weekly_traffic`; 6 service tests cover this |
| 8 | User can select pages and dispatch batch fix through existing content pipeline | VERIFIED | dispatch_batch_fix() creates WpContentJob(status=pending) records; router POST /batch-fix endpoint wired |
| 9 | User can open /analytics/{site_id}/dead-content and see pages with zero traffic or position drop > 10 | VERIFIED | Route exists in dead_content.py; get_dead_content() detects is_zero_traffic and avg_delta < -10 |
| 10 | Each dead content page shows an auto-recommendation (delete/redirect/rewrite/merge) that user can override | VERIFIED | compute_recommendation() pure function; update_recommendation() stores in Redis; inline select in dead_content_table.html |
| 11 | User can select pages and create SEO tasks for dead content | VERIFIED | create_dead_content_tasks() creates SeoTask(manual/p3/open); POST /create-tasks endpoint; template "Создать задачи" button present |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/utils/url_normalize.py` | URL normalization utility | VERIFIED | 79 lines; `def normalize_url(` present; stdlib only |
| `app/models/keyword_latest_position.py` | KeywordLatestPosition SQLAlchemy model | VERIFIED | `class KeywordLatestPosition(Base)` with uq_klp_keyword_engine constraint and ix_klp_site_position index |
| `alembic/versions/0037_add_keyword_latest_positions.py` | Alembic migration | VERIFIED | Creates table + index; down_revision = "0036"; drop in downgrade |
| `app/services/quick_wins_service.py` | Quick Wins aggregation with opportunity score | VERIFIED | get_quick_wins() and dispatch_batch_fix() present; (21 - avg_pos) * weekly_traffic formula |
| `app/routers/quick_wins.py` | Quick Wins router | VERIFIED | 4 routes confirmed via `python -c "from app.routers.quick_wins import router; print(len(router.routes))"` → 4 |
| `app/templates/analytics/quick_wins.html` | Quick Wins page template | VERIFIED | Contains "Quick Wins", "Запустить фикс", "Тип проблемы", "Не запускать" |
| `app/templates/analytics/partials/quick_wins_table.html` | Quick Wins table partial | VERIFIED | Contains opportunity_score badge rendering with tier thresholds |
| `app/templates/analytics/partials/fix_status.html` | Fix status polling partial | VERIFIED | 1051 bytes; HTMX polling partial present |
| `app/services/dead_content_service.py` | Dead content detection + recommendation engine | VERIFIED | get_dead_content(), compute_recommendation(), update_recommendation(), create_dead_content_tasks() all present |
| `app/routers/dead_content.py` | Dead Content router | VERIFIED | 3 routes confirmed via import check |
| `app/templates/analytics/dead_content.html` | Dead Content page template | VERIFIED | Contains "Мёртвый контент", "Создать задачи", "Нет трафика (30 дн.)", "Не создавать" |
| `app/templates/analytics/partials/dead_content_table.html` | Dead Content table partial | VERIFIED | All 4 recommendation badge types (merge/redirect/rewrite/delete) present |
| `tests/test_url_normalize.py` | Unit tests for normalize_url | VERIFIED | 14 test functions; all pass |
| `tests/test_keyword_latest_positions.py` | Unit tests for flat table refresh | VERIFIED | 7 tests: 3 structural (pass locally), 4 DB integration (require Docker) |
| `tests/test_quick_wins_service.py` | Unit tests for quick wins service | VERIFIED | 6 async integration tests |
| `tests/test_dead_content_service.py` | Unit tests for dead content service | VERIFIED | 14 tests: 10 pure-function (pass locally), 4 async integration |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| app/services/position_service.py | app/models/keyword_latest_position.py | refresh_latest_positions() called after write_positions_batch() | WIRED | Line 121: `await refresh_latest_positions(db, site_id)`; function defined at line 203 |
| app/utils/url_normalize.py | analytical JOINs | normalize_url used in quick_wins_service and dead_content_service | WIRED | Imported and called in both services for URL normalization before cross-table lookup |
| app/services/quick_wins_service.py | app/models/keyword_latest_position.py | SQL JOIN on keyword_latest_positions for position 4-20 range | WIRED | Raw SQL at line 57-65: `FROM keyword_latest_positions WHERE position >= :pos_min AND position <= :pos_max` |
| app/services/quick_wins_service.py | content pipeline | dispatch_batch_fix creates WpContentJob records | WIRED | Creates WpContentJob(status=pending) directly; deviates from plan's `create_fix_job` pattern but achieves same goal (pipeline pickup) — documented decision in 12-02-SUMMARY.md |
| app/routers/quick_wins.py | app/services/quick_wins_service.py | route handlers call get_quick_wins() and dispatch_batch_fix() | WIRED | Lines 16, 46, 71, 101 |
| app/services/dead_content_service.py | app/models/metrika.py | MetrikaTrafficPage for 30-day zero-traffic detection | WIRED | Import at line 29; SELECT with period_end >= cutoff at lines 162-177 |
| app/services/dead_content_service.py | app/models/keyword_latest_position.py | keyword_latest_positions for position drop detection | WIRED | Import at line 28; SELECT with avg(delta) at lines 181-200 |
| app/services/dead_content_service.py | app/models/task.py | SeoTask creation for dead content pages | WIRED | Import at line 30; SeoTask(task_type=manual, priority=p3) created at line 408 |
| app/navigation.py | Quick Wins | "quick-wins" child under analytics section | WIRED | Line 49 of navigation.py |
| app/navigation.py | Dead Content | "dead-content" child under analytics section | WIRED | Line 57 of navigation.py |
| app/main.py | both routers | include_router for quick_wins and dead_content | WIRED | Lines 140-144 of main.py |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| quick_wins.html | `pages` | get_quick_wins() queries keyword_latest_positions + metrika_traffic_pages + pages tables | Yes — live DB queries with no static fallback | FLOWING |
| dead_content.html | `result["pages"]` | get_dead_content() queries CrawlJob, Page, MetrikaTrafficPage, KeywordLatestPosition, Keyword tables | Yes — live DB queries with no static fallback | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| normalize_url strips UTM and upgrades http | `python -c "from app.utils.url_normalize import normalize_url; print(normalize_url('http://example.com/page?utm_source=yandex'))"` | `https://example.com/page/` | PASS |
| normalize_url passes all 14 unit tests | `python -m pytest tests/test_url_normalize.py -v` | 14 passed in 0.03s | PASS |
| KeywordLatestPosition model importable | `python -c "from app.models.keyword_latest_position import KeywordLatestPosition; print(KeywordLatestPosition.__tablename__)"` | `keyword_latest_positions` | PASS |
| quick_wins router has 4 routes | `python -c "from app.routers.quick_wins import router; print(len(router.routes))"` | 4 | PASS |
| dead_content router has 3 routes | `python -c "from app.routers.dead_content import router; print(len(router.routes))"` | 3 | PASS |
| quick_wins service importable | `python -c "from app.services.quick_wins_service import get_quick_wins, dispatch_batch_fix; print('OK')"` | OK | PASS |
| dead_content service importable | `python -c "from app.services.dead_content_service import get_dead_content, compute_recommendation, update_recommendation, create_dead_content_tasks; print('OK')"` | OK | PASS |
| Dead content recommendation unit tests | `python -m pytest tests/test_dead_content_service.py -k "recommendation" -v` | 10 passed in 0.03s | PASS |
| KLP structural model tests | `python -m pytest tests/test_keyword_latest_positions.py -k "structural or model" -v` | 3 passed in 0.05s | PASS |
| All 7 commits present in git log | `git log --oneline` | 9741157, 6375181, 3ba9d89, a3d77b5, 2f67d21, ab9940c, dc61582 all found | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-V2-01 | 12-01-PLAN.md | normalize_url() унифицирует URL при JOIN между pages, metrika, positions | SATISFIED | app/utils/url_normalize.py; 14 passing tests; imported in quick_wins_service and dead_content_service |
| INFRA-V2-02 | 12-01-PLAN.md | keyword_latest_positions flat-таблица для быстрых запросов без сканирования всех партиций | SATISFIED | Model + migration 0037; refresh wired in write_positions_batch(); indexed on (site_id, position) |
| QW-01 | 12-02-PLAN.md | Пользователь видит список страниц с позициями 4–20, у которых есть хотя бы одна нерешённая SEO-проблема | SATISFIED | get_quick_wins() filters `has_any_issue` and position BETWEEN 4 AND 20; template displays table |
| QW-02 | 12-02-PLAN.md | Каждая страница имеет opportunity score = (21 - позиция) x недельный трафик, список отсортирован по score | SATISFIED | `opportunity_score = (21 - avg_pos) * weekly_traffic`; `results.sort(key=lambda x: x["opportunity_score"], reverse=True)` |
| QW-03 | 12-02-PLAN.md | Пользователь может запустить батч-фикс выбранных страниц через существующий content pipeline | SATISFIED | dispatch_batch_fix() creates WpContentJob(status=pending); POST /batch-fix endpoint; modal in template |
| DEAD-01 | 12-03-PLAN.md | Пользователь видит страницы с 0 визитов за 30 дней и/или падением позиций > 10 за 30 дней | SATISFIED | get_dead_content() detects `is_zero_traffic = traffic_30d == 0` and `is_position_drop = avg_delta < -10` |
| DEAD-02 | 12-03-PLAN.md | Каждая мёртвая страница имеет рекомендацию: merge, redirect, rewrite или delete | SATISFIED | compute_recommendation() pure function with all 4 branches; inline override select in template |

All 7 requirement IDs present in REQUIREMENTS.md under Phase 12 — all marked Complete. No orphaned requirements.

---

### Anti-Patterns Found

No blockers or significant warnings found.

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| app/services/quick_wins_service.py | dispatch_batch_fix creates WpContentJob directly instead of via audit_fix_service.create_fix_job as the plan key-link specified | Info | Functional equivalent achieved; documented decision in 12-02-SUMMARY.md (pending vs awaiting_approval status) |
| tests/test_keyword_latest_positions.py + tests/test_quick_wins_service.py + tests/test_dead_content_service.py (async tests) | DB integration tests require live PostgreSQL — cannot run without Docker stack | Info | Standard pattern across codebase; structural/unit tests all pass locally; no blocking issue |

---

### Human Verification Required

#### 1. Quick Wins Page Visual Rendering

**Test:** Log in, open `/analytics/{site_id}/quick-wins` for a site that has had a position check run
**Expected:** Table shows pages with position 4-20, opportunity score badges in correct color tiers (amber/yellow/gray), pass/fail icons in TOC/Schema/Links/Content columns
**Why human:** Template rendering and color-coded badge display require visual inspection

#### 2. HTMX Filter Refresh

**Test:** On the Quick Wins page, change the "Тип проблемы" dropdown to "Без TOC"
**Expected:** Table updates without full page reload, showing only pages where has_toc = False
**Why human:** HTMX partial swap behavior requires browser interaction to verify

#### 3. Batch Fix Modal Flow

**Test:** Select 2 rows, click "Запустить фикс (2 стр.)", verify modal appears with correct URL list and fix-type checkboxes checked, confirm
**Expected:** Modal shows selected pages, checkboxes for TOC/Schema/Links all pre-checked, POST creates jobs, toast notification appears
**Why human:** JS-driven modal visibility, selection state management, and fetch POST require browser interaction

#### 4. Dead Content Recommendation Override

**Test:** Open `/analytics/{site_id}/dead-content`, change a recommendation dropdown for any page
**Expected:** Dropdown POST fires via HTMX `hx-trigger="change"`, toast "Рекомендация обновлена" appears, reload shows the same override value
**Why human:** HTMX trigger-on-change, toast display, and Redis persistence require live browser + Redis interaction

#### 5. Dead Content Task Creation

**Test:** Select pages on Dead Content page, click "Создать задачи", confirm in dialog, verify tasks appear in SEO Tasks list
**Expected:** N tasks created, toast "Задачи созданы: N страниц добавлено в очередь", tasks visible in tasks list with type=manual
**Why human:** End-to-end confirmation dialog flow and task list visibility require browser interaction

---

### Gaps Summary

No gaps found. All 11 observable truths are verified. All 16 artifacts exist and are substantive. All key links are wired. All 7 requirement IDs are satisfied. The 14/14 normalize_url tests pass, the 10 pure-function dead content tests pass, and all 3 structural KLP tests pass. DB integration tests (requiring Docker PostgreSQL) are consistent with the established codebase pattern and are not a blocking issue.

The only notable deviation from plan is `dispatch_batch_fix` creating `WpContentJob` records directly rather than calling `audit_fix_service.create_fix_job`. This is a documented decision (pending status vs awaiting_approval) that achieves the same pipeline goal.

---

_Verified: 2026-04-06T15:45:00Z_
_Verifier: Claude (gsd-verifier)_
