---
phase: 13-impact-scoring-growth-opportunities
verified: 2026-04-06T16:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
---

# Phase 13: Impact Scoring + Growth Opportunities Verification Report

**Phase Goal:** Users can see all audit errors ranked by traffic impact and drill into a unified Growth Opportunities dashboard aggregating gap keywords, lost positions, and cannibalization
**Verified:** 2026-04-06T16:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                    | Status     | Evidence                                                                                     |
|----|----------------------------------------------------------------------------------------------------------|------------|----------------------------------------------------------------------------------------------|
| 1  | Every audit error has impact_score = severity_weight x monthly Metrika traffic                           | VERIFIED  | `SEVERITY_WEIGHTS`, `compute_single_impact_score`, `build_impact_rows` all exist and tested  |
| 2  | Impact scores are pre-computed by a Celery task and stored in error_impact_scores table                  | VERIFIED  | `compute_impact_scores` task in `app/tasks/impact_tasks.py`, migration 0038 creates table    |
| 3  | Impact score computation triggers automatically after audit completion                                    | VERIFIED  | `compute_impact_scores.delay(site_id)` at line 131-132 of `app/tasks/audit_tasks.py`         |
| 4  | User can view Growth Opportunities dashboard at /analytics/{site_id}/opportunities                       | VERIFIED  | Route `GET /{site_id}/opportunities` in `app/routers/opportunities.py`, registered in main.py|
| 5  | Dashboard has four tabs: Gaps, Потери, Каннибализация, Тренд                                             | VERIFIED  | All four tab buttons confirmed in `opportunities.html` with HTMX hx-get wiring               |
| 6  | Gaps tab shows gap keyword count and potential traffic from GapKeyword table                             | VERIFIED  | `get_gap_summary` queries GapKeyword, partial renders count + potential_traffic               |
| 7  | Losses tab shows keywords with position delta <= -5 from keyword_latest_positions                        | VERIFIED  | `get_lost_positions` uses `delta <= -5` filter on `keyword_latest_positions`                 |
| 8  | Cannibalization tab shows keywords with 2+ pages in top-50 from keyword_latest_positions                 | VERIFIED  | CTE in `get_cannibalization` uses `position <= 50` + `HAVING COUNT(DISTINCT url) >= 2`       |
| 9  | Trend tab shows visibility numbers: current/previous week and month with % change (no charts)            | VERIFIED  | `compute_visibility_trend` pure function, trend partial has numbers only, no Chart.js        |
| 10 | Tab switching uses HTMX partial swap without full page reload                                            | VERIFIED  | Each tab button has `hx-get`, `hx-target="#tab-content"`, `hx-swap="innerHTML"`             |
| 11 | Kanban can be sorted by impact_score so highest-traffic errors appear first                              | VERIFIED  | `ui_kanban` has `sort: str = "created"` param, sorts groups by `impact_score DESC`          |
| 12 | User can click Opportunities rows to open slide-over with details and a "Подробнее" link                 | VERIFIED  | 3 detail routes, slide_over.html partial, all tab partials have `hx-on::after-request="openSlideOver()"` |

**Score:** 12/12 truths verified

---

## Required Artifacts

### Plan 01 Artifacts (IMP-01)

| Artifact                                             | Expected                                  | Status    | Details                                                       |
|------------------------------------------------------|-------------------------------------------|-----------|---------------------------------------------------------------|
| `app/models/impact_score.py`                         | ErrorImpactScore SQLAlchemy model         | VERIFIED | Contains `class ErrorImpactScore`, `__tablename__ = "error_impact_scores"`, `UniqueConstraint("site_id", "page_url", "check_code", name="uq_eis_site_page_check")` |
| `alembic/versions/0038_add_error_impact_scores.py`   | Migration for error_impact_scores table   | VERIFIED | Creates table, unique constraint, index; `down_revision = "0037"` |
| `app/services/impact_score_service.py`               | Service with SEVERITY_WEIGHTS + functions | VERIFIED | All 5 required functions present: `get_impact_scores_for_site`, `upsert_impact_scores`, `get_max_impact_score_by_url`, `compute_single_impact_score`, `build_impact_rows` |
| `app/tasks/impact_tasks.py`                          | Celery task compute_impact_scores         | VERIFIED | Decorated with `@celery_app.task`, `bind=True`, `max_retries=3`, `queue="default"`, `self.retry(exc=exc, countdown=30)` |
| `tests/test_impact_score_service.py`                 | Unit tests for impact score service       | VERIFIED | 16 test functions, 142 lines, **16/16 pass**                  |
| `app/models/__init__.py`                             | ErrorImpactScore registered               | VERIFIED | `from app.models.impact_score import ErrorImpactScore` at line 2 |
| `app/tasks/audit_tasks.py`                           | compute_impact_scores.delay() trigger     | VERIFIED | `compute_impact_scores.delay(site_id)` at lines 131-132       |
| `app/celery_app.py`                                  | impact_tasks in include list              | VERIFIED | `"app.tasks.impact_tasks"` at line 23                         |

### Plan 02 Artifacts (GRO-01)

| Artifact                                                    | Expected                               | Status    | Details                                                      |
|-------------------------------------------------------------|----------------------------------------|-----------|--------------------------------------------------------------|
| `app/services/opportunities_service.py`                     | 4-tab service functions                | VERIFIED | All 5 functions present: `get_gap_summary`, `get_lost_positions`, `get_cannibalization`, `compute_visibility_trend`, `get_visibility_trend` |
| `app/routers/opportunities.py`                              | Router with page + 4 tab partials      | VERIFIED | 8 routes total (5 original + 3 detail); `router = APIRouter(prefix="/analytics")` |
| `app/templates/analytics/opportunities.html`                | Main dashboard with tab nav            | VERIFIED | Four HTMX tab buttons with `hx-get`, `hx-target="#tab-content"`, `hx-swap="innerHTML"`; slide_over.html included |
| `app/templates/analytics/partials/opportunities_gaps.html`  | Gaps tab partial                       | VERIFIED | Table with "Фраза" column, detail hx-get links              |
| `app/templates/analytics/partials/opportunities_losses.html`| Losses tab partial                     | VERIFIED | "Изменение" column, delta display, detail hx-get links      |
| `app/templates/analytics/partials/opportunities_cannibal.html` | Cannibalization tab partial         | VERIFIED | Groups by page_count, detail hx-get links                   |
| `app/templates/analytics/partials/opportunities_trend.html` | Trend tab partial                      | VERIFIED | Numbers-only, no charts, `week_change_pct` and `month_change_pct` badges |
| `tests/test_opportunities_service.py`                       | Unit tests for service layer           | VERIFIED | 12 test functions, 322 lines, **12/12 pass**                 |
| `app/main.py`                                               | opportunities_router registered        | VERIFIED | `from app.routers.opportunities import router as opportunities_router` at line 146; `app.include_router(opportunities_router)` at line 147 |
| `app/navigation.py`                                         | Growth Opportunities nav entry         | VERIFIED | `{"id": "opportunities", "label": "Growth Opportunities", "url": "/analytics/{site_id}/opportunities"}` at line 58 |

### Plan 03 Artifacts (IMP-02, GRO-02)

| Artifact                                                   | Expected                                    | Status    | Details                                                      |
|------------------------------------------------------------|---------------------------------------------|-----------|--------------------------------------------------------------|
| `app/templates/projects/kanban.html`                       | Sort toggle + impact score badges           | VERIFIED | `name="sort"`, `value="impact"`, `hx-get`, `hx-push-url`; orange badge on `task.impact_score > 0` |
| `app/main.py` (ui_kanban function)                         | sort param + get_max_impact_score_by_url    | VERIFIED | `sort: str = "created"` param; imports and calls `get_max_impact_score_by_url`; `normalize_url(t.url)` lookup |
| `app/templates/analytics/partials/slide_over.html`         | Reusable slide-over drawer                  | VERIFIED | `id="slide-over"`, `closeSlideOver()` and `openSlideOver()` JS functions, backdrop click-to-close |
| `app/templates/analytics/partials/detail_gap.html`         | Gap keyword detail panel                    | VERIFIED | "Подробнее: перейти к Gap-анализу" link, `href="/gap/{{ site.id }}"`, closeSlideOver X button |
| `app/templates/analytics/partials/detail_loss.html`        | Lost position detail panel                  | VERIFIED | "Подробнее: перейти к позициям", `/ui/positions/{{ site.id }}`                 |
| `app/templates/analytics/partials/detail_cannibal.html`    | Cannibalization detail panel                | VERIFIED | "Подробнее: перейти к каннибализации", `/ui/cannibalization/{{ site.id }}`     |
| `app/routers/opportunities.py` (detail routes)             | 3 detail route handlers                     | VERIFIED | `/detail/gap/{gap_keyword_id}`, `/detail/loss/{keyword_id}`, `/detail/cannibal/{keyword_id}`; total 8 routes |

---

## Key Link Verification

| From                              | To                                    | Via                                              | Status    | Details                                                              |
|-----------------------------------|---------------------------------------|--------------------------------------------------|-----------|----------------------------------------------------------------------|
| `app/tasks/impact_tasks.py`       | `app/services/impact_score_service.py`| `upsert_impact_scores` call                      | WIRED    | `build_impact_rows` and `upsert_impact_scores` imported and called in `_compute_scores()` |
| `app/tasks/audit_tasks.py`        | `app/tasks/impact_tasks.py`           | `compute_impact_scores.delay()` after completion | WIRED    | Lines 131-132: delayed import + `.delay(site_id)` call              |
| `app/routers/opportunities.py`    | `app/services/opportunities_service.py` | service function calls in route handlers       | WIRED    | All 4 service functions imported and called in corresponding routes  |
| `app/main.py`                     | `app/routers/opportunities.py`        | `app.include_router`                             | WIRED    | Lines 146-147: import + `include_router(opportunities_router)`       |
| `app/navigation.py`               | `/analytics/{site_id}/opportunities`  | NAV_SECTIONS entry                               | WIRED    | Line 58 in analytics children list                                   |
| `app/main.py` (ui_kanban)         | `app/services/impact_score_service.py`| `get_max_impact_score_by_url()` call             | WIRED    | Lines 880, 893: import + await call with project.site_id             |
| `app/templates/analytics/opportunities.html` | `app/templates/analytics/partials/slide_over.html` | `{% include %}` | WIRED | Line 72: `{% include "analytics/partials/slide_over.html" %}`  |
| `app/routers/opportunities.py`    | detail partials                       | detail route handlers (`/detail/`)               | WIRED    | Three detail routes, each renders respective detail_*.html template  |

---

## Data-Flow Trace (Level 4)

| Artifact                              | Data Variable      | Source                                                        | Produces Real Data | Status      |
|---------------------------------------|--------------------|---------------------------------------------------------------|--------------------|-------------|
| `opportunities_gaps.html`             | `data.items`       | `get_gap_summary` → SELECT GapKeyword WHERE site_id           | Yes                | FLOWING    |
| `opportunities_losses.html`           | `data.items`       | `get_lost_positions` → raw SQL on keyword_latest_positions    | Yes                | FLOWING    |
| `opportunities_cannibal.html`         | `data.items`       | `get_cannibalization` → CTE on keyword_latest_positions       | Yes                | FLOWING    |
| `opportunities_trend.html`            | `trend.*`          | `get_visibility_trend` → SELECT MetrikaTrafficDaily last 60d  | Yes                | FLOWING    |
| `kanban.html` impact badge            | `task.impact_score`| `get_max_impact_score_by_url` → GROUP BY page_url on error_impact_scores | Yes    | FLOWING    |
| `detail_gap.html`                     | `item.*`           | Route queries GapKeyword by id + site_id                      | Yes                | FLOWING    |
| `detail_loss.html`                    | `item.*`           | Route queries keyword_latest_positions JOIN keywords           | Yes                | FLOWING    |
| `detail_cannibal.html`                | `item.*`           | Route queries keyword_latest_positions position <= 50          | Yes                | FLOWING    |

---

## Behavioral Spot-Checks

| Behavior                                      | Command                                                                             | Result             | Status |
|-----------------------------------------------|-------------------------------------------------------------------------------------|--------------------|--------|
| Impact score service tests pass               | `pytest tests/test_impact_score_service.py -x -v`                                  | 16/16 passed       | PASS  |
| Opportunities service tests pass              | `pytest tests/test_opportunities_service.py -x -v`                                 | 12/12 passed       | PASS  |
| Opportunities router has 8 routes             | `python3 -c "from app.routers.opportunities import router; print(len(router.routes))"` | 8               | PASS  |
| Celery task importable                        | `python3 -c "from app.tasks.impact_tasks import compute_impact_scores; print(compute_impact_scores.name)"` | Importable | PASS  |
| ErrorImpactScore model importable             | `python3 -c "from app.models.impact_score import ErrorImpactScore; print(ErrorImpactScore.__tablename__)"` | `error_impact_scores` | PASS  |
| Kanban sort toggle has value="impact"         | `grep -c 'value="impact"' app/templates/projects/kanban.html`                       | 1                  | PASS  |
| Slide-over included in opportunities.html     | `grep 'slide_over.html' app/templates/analytics/opportunities.html`                 | Found at line 72   | PASS  |
| "Подробнее" present in all 3 detail partials  | `grep -c "Подробнее" app/templates/analytics/partials/detail_*.html`               | 1 each             | PASS  |

---

## Requirements Coverage

| Requirement | Source Plan | Description                                                                                       | Status    | Evidence                                                                   |
|-------------|------------|---------------------------------------------------------------------------------------------------|-----------|----------------------------------------------------------------------------|
| IMP-01      | 13-01      | Все ошибки имеют impact_score = severity_weight x месячный трафик страницы                        | SATISFIED | ErrorImpactScore model, SEVERITY_WEIGHTS, build_impact_rows, Celery task, migration 0038 |
| IMP-02      | 13-03      | Задачи в Kanban можно сортировать по impact_score; самые критичные ошибки видны первыми           | SATISFIED | `sort: str = "created"` param in ui_kanban, sort dropdown in kanban.html, orange badges |
| GRO-01      | 13-02      | Дашборд Growth Opportunities агрегирует: gap-ключи, потерянные позиции, каннибализации, visibility тренд | SATISFIED | Four-tab dashboard at /analytics/{site_id}/opportunities, all four service functions wired |
| GRO-02      | 13-03      | Пользователь может drill-down из карточки Opportunities в соответствующий раздел                  | SATISFIED | Slide-over panel, 3 detail routes, "Подробнее" links in all 3 detail partials |

No orphaned requirements — all 4 IDs (IMP-01, IMP-02, GRO-01, GRO-02) are claimed by plan files and verified in the codebase.

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None | — | — | No stub or placeholder patterns found in any phase 13 files |

Scan covered: `app/services/impact_score_service.py`, `app/services/opportunities_service.py`, `app/routers/opportunities.py`, `app/tasks/impact_tasks.py`, all template files in `app/templates/analytics/partials/`, `app/templates/projects/kanban.html`. No TODO, FIXME, placeholder, or empty-return stubs found in any phase 13 artifact.

---

## Human Verification Required

### 1. Kanban Sort UX

**Test:** Open a project Kanban board, select "По Impact Score" in the sort dropdown
**Expected:** Page reloads with tasks sorted highest-impact-score first; orange badges appear on task cards with non-zero scores
**Why human:** HTMX full-page reload behavior with `hx-target="body"` and `hx-push-url="true"` requires browser interaction to confirm

### 2. Tab Switching No Full Reload

**Test:** Open Growth Opportunities dashboard, click each of the 4 tabs in sequence
**Expected:** Tab content changes without full page reload; active tab gets indigo underline; JS `switchTab()` correctly toggles classes
**Why human:** HTMX partial swap behavior requires browser network inspection

### 3. Slide-Over Open/Close

**Test:** Click a row in any Opportunities tab (Gaps, Потери, or Каннибализация)
**Expected:** Right-side drawer slides in with detail content; backdrop click closes it; X button also closes it
**Why human:** CSS transition animation and overlay click behavior require browser interaction

### 4. Impact Scores After Audit

**Test:** Run a full site audit via the audit task; then check error_impact_scores table
**Expected:** Rows appear with severity_weight x monthly_traffic values; rows with no Metrika data have impact_score = 0
**Why human:** Requires a running Celery worker and PostgreSQL with audit data

---

## Gaps Summary

No gaps found. All 12 observable truths are verified, all 19 artifacts exist and are substantive, all 8 key links are wired, all data flows are connected to real DB queries, both test suites pass (28 tests total, 0 failures), and all 4 requirements (IMP-01, IMP-02, GRO-01, GRO-02) are fully satisfied.

---

_Verified: 2026-04-06T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
