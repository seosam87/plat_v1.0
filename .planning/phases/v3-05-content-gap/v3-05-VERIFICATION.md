---
phase: v3-05-content-gap
verified: 2026-04-03T09:00:00Z
status: gaps_found
score: 6/8 must-haves verified
re_verification: false
gaps:
  - truth: "GET /gap/score-formula endpoint is reachable and returns formula text"
    status: failed
    reason: >
      The /score-formula route is declared at line 292 of gap.py, after the parameterized
      GET /{site_id} route at line 54. FastAPI evaluates routes in declaration order.
      When a request arrives for GET /gap/score-formula, it matches /{site_id} first,
      attempts to coerce "score-formula" to uuid.UUID, and returns HTTP 422 Unprocessable
      Entity. The /score-formula endpoint is never invoked. The SCORE_FORMULA_DESCRIPTION
      constant and the endpoint handler both exist — only the route ordering is wrong.
    artifacts:
      - path: "app/routers/gap.py"
        issue: >
          @router.get('/score-formula') at line 292 is shadowed by @router.get('/{site_id}')
          at line 54. Move /score-formula declaration above /{site_id} to fix.
    missing:
      - "Reorder @router.get('/score-formula') to appear before @router.get('/{site_id}') in gap.py"

  - truth: "SERP-based gap detection filters out keywords we already rank for"
    status: failed
    reason: >
      detect_gaps_from_session() computes our_phrases (the set of our keyword phrases) at
      line 59 but never references our_phrases in the loop that builds gaps[]. Every SERP
      keyword where the competitor appears is included as a gap regardless of whether we
      already rank for it. The function comment says "competitor ranks, we don't" but the
      code does not enforce the "we don't" condition. The our_position field is also always
      set to None in the returned dicts.
    artifacts:
      - path: "app/services/gap_service.py"
        issue: >
          our_phrases set is computed (line 59) but never used. The gap append at line 88
          fires whenever comp_pos is not None, with no check against our_phrases or site domain.
    missing:
      - >
        In the inner loop, track whether our domain appears in results (compare site URL against
        r['url']). Only append to gaps[] when comp_pos is set AND our domain is absent from TOP-10.
        Alternatively, filter gap phrases against our_phrases set before returning.
human_verification:
  - test: "File upload import (CSV and XLSX)"
    expected: "Upload a keys.so or Topvisor CSV file; import-status shows 'Импортировано: N, gap-ключей: N'; keywords appear in the table on reload"
    why_human: "Requires a running server and a real or test file; cannot verify multipart upload + file parsing end-to-end without executing the app"
  - test: "Proposal approval with content plan link"
    expected: "Click Одобрить on a pending proposal; proposal status changes to Одобрено; if project_id supplied, a ContentPlanItem is created and linked"
    why_human: "Requires a live DB session and a project to exist; cannot verify the FK write to content_plan_items without running state"
---

# Phase v3-05: Content Gap Analysis Verification Report

**Phase Goal:** Content Gap Analysis — competitor keywords we don't have, import from CSV/XLSX, potential scoring, grouping, proposals to content plan.
**Verified:** 2026-04-03T09:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GapKeyword, GapGroup, GapProposal models exist with correct schema | VERIFIED | app/models/gap.py — all three models, UniqueConstraint, ProposalStatus enum, potential_score on both GapKeyword and GapProposal |
| 2 | Migration 0024 creates all three tables with downgrade | VERIFIED | alembic/versions/0024_add_content_gap_tables.py — revision="0024", down_revision="0023", creates gap_groups/gap_keywords/gap_proposals + proposalstatus enum, downgrade drops all 3 |
| 3 | CSV/XLSX import detects gaps using multi-format column auto-detection | VERIFIED | gap_parser.py uses find_column() with Russian and English candidates (keys.so, Topvisor, generic); import_competitor_keywords() in gap_service.py wires parser to DB upsert |
| 4 | Potential score computed via frequency x position-factor formula with SCORE_FORMULA_DESCRIPTION constant | VERIFIED | compute_potential_score() at line 24 of gap_service.py matches spec exactly; SCORE_FORMULA_DESCRIPTION constant populated at line 17 |
| 5 | Manual grouping of gap keywords via GapGroup CRUD | VERIFIED | create_gap_group, list_gap_groups, assign_to_group, delete_gap_group all present and async in gap_service.py; all wired to router endpoints |
| 6 | Proposals with pending/approved/rejected status and optional ContentPlanItem creation on approve | VERIFIED | create_proposals_from_gaps, approve_proposal (creates ContentPlanItem when project_id given), reject_proposal, list_proposals all present; ProposalStatus enum enforced at DB level |
| 7 | GET /gap/score-formula endpoint returns formula text | FAILED | Route declared after /{site_id} — shadowed by parameterized route; returns 422 in practice |
| 8 | SERP detection correctly filters out keywords we already rank for | FAILED | our_phrases computed but unused in detection loop; all keywords where competitor appears are included regardless of our own ranking |

**Score:** 6/8 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models/gap.py` | GapKeyword, GapGroup, GapProposal, ProposalStatus | VERIFIED | 115 lines; all models with correct fields, FK constraints, UniqueConstraint |
| `alembic/versions/0024_add_content_gap_tables.py` | Migration creating 3 tables + downgrade | VERIFIED | revision="0024", 3 op.create_table calls, 3 op.drop_table in downgrade |
| `app/services/gap_service.py` | Scoring, detection, import, CRUD, proposals | VERIFIED | 349 lines; all required functions present; SCORE_FORMULA_DESCRIPTION constant |
| `app/parsers/gap_parser.py` | Multi-format parser with find_column() | VERIFIED | 47 lines; keys.so Russian headers, Topvisor, generic English; uses base.find_column() |
| `app/routers/gap.py` | 14 endpoints at /gap prefix | VERIFIED | 295 lines; 14 @router decorators confirmed; all endpoints require_admin |
| `app/templates/gap/index.html` | Gap analysis UI with Russian copy | VERIFIED | 228 lines; import modes, keyword table, groups, proposals, scoring tooltip, all Russian copy |
| `tests/test_gap_models.py` | 4 model unit tests | VERIFIED | 4 test functions covering enum values and model field assignment |
| `tests/test_gap_service.py` | 10 unit tests for scoring and parser | VERIFIED | 10 test functions: 5 scoring bands, 4 parser formats, 1 formula description |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `gap/index.html` | `GET /gap/{site_id}` | gap_page() in gap.py | WIRED | Template renders keywords, groups, proposals from service calls; score_formula passed as context |
| `gap/index.html` JS | `POST /gap/{site_id}/detect` | fetch() in detectGaps() | WIRED | session_id + competitor_domain POSTed; response shows gaps_detected count |
| `gap/index.html` JS | `POST /gap/{site_id}/import` | fetch() in importFile() | WIRED | FormData with file + competitor_domain; response shows imported/gaps_found |
| `gap/index.html` JS | `POST /gap/{site_id}/proposals` | fetch() in createProposals() | WIRED | selected keyword_ids sent; page reloads |
| `gap/index.html` JS | `POST /gap/proposals/{id}/approve` | fetch() in approveProposal() | WIRED | approveProposal(pid) calls correct endpoint |
| `gap.py router` | `gap_service` functions | `import gap_service as gs` | WIRED | All 14 endpoints delegate to gs.* functions |
| `gap_service.py` | `gap_parser.parse_gap_file` | imported in import_competitor_keywords | WIRED | Called with rows from base.read_file() |
| `gap_service.py` | `GapKeyword` PostgreSQL upsert | `insert().on_conflict_do_update()` | WIRED | UniqueConstraint used as conflict target |
| `approve_proposal()` | `ContentPlanItem` creation | FK write + flush | WIRED | ContentPlanItem created when project_id provided; linked via content_plan_item_id |
| `app/main.py` | `gap_router` | `app.include_router(gap_router)` | WIRED | Line 176 of main.py |
| `sites/detail.html` | `/gap/{site.id}` | anchor href | WIRED | Line 48: Gap-анализ button present |
| `GET /score-formula` endpoint | `SCORE_FORMULA_DESCRIPTION` | route handler | BROKEN | Route shadowed by /{site_id}; returns 422 not formula text |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `gap/index.html` keywords table | `keywords` (list[dict]) | `gs.list_gap_keywords(db, site_id)` → SELECT GapKeyword | Yes — DB query with filters | FLOWING |
| `gap/index.html` proposals section | `proposals` (list[GapProposal]) | `gs.list_proposals(db, site_id)` → SELECT GapProposal | Yes — DB query | FLOWING |
| `gap/index.html` summary stats | `total_keywords`, `avg_score`, `proposals\|length` | computed from keywords/proposals lists | Yes — derived from real queries | FLOWING |
| `gap/index.html` session dropdown | `sessions` | `analytics_service.list_sessions(db, site_id)` | Yes — DB query | FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED for live endpoints (requires running server + DB). Static checks performed instead:

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| `compute_potential_score(1000, 2)` returns 1000.0 | Code inspection: freq=1000, pos<=3, factor=1.0, result=1000.0 | Correct | PASS |
| `compute_potential_score(500, 7)` returns 350.0 | Code inspection: pos<=10, factor=0.7, result=350.0 | Correct | PASS |
| `parse_gap_file` with keys.so headers detects "Запрос" column | "Запрос" in _PHRASE_CANDIDATES list; find_column() used | Correct | PASS |
| 14 router endpoints present | `grep -c "@router" app/routers/gap.py` → 14 | 14 confirmed | PASS |
| `GET /gap/score-formula` reachable | Route declared after /{site_id}; UUID coercion fails | 422 response | FAIL |
| SERP detection respects our keyword set | our_phrases computed but never referenced in loop | Gap filter absent | FAIL |

---

### Requirements Coverage

No `requirements_addressed` field in any of the three PLAN files — no REQ-IDs were mapped to this phase. Phase goal coverage assessed against ROADMAP-v3 Phase 5 description:

| ROADMAP Item | Status | Evidence |
|---|---|---|
| Пересечение SERP-данных конкурентов с нашими ключами | PARTIAL | detect_gaps_from_session() detects by competitor presence but does not filter against our keyword set (our_phrases unused) |
| Ключи, по которым конкуренты в TOP-10, а мы нет → «упущенные темы» | PARTIAL | Competitor TOP-10 check present; "а мы нет" condition missing |
| Автоматическое создание предложений в контент-план | SATISFIED | create_proposals_from_gaps() → GapProposal; approve_proposal() → ContentPlanItem |
| Группировка gap-ключей по тематике | SATISFIED | GapGroup CRUD + assign_to_group() + template grouping UI |
| Оценка потенциала: частотность × вероятность попадания в TOP | SATISFIED | compute_potential_score() with exact formula; tooltip in UI |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/services/gap_service.py` | 59 | `our_phrases` computed but never used | Warning | Gap detection does not exclude keywords we already have; inflated gap count |
| `app/routers/gap.py` | 292 | `@router.get("/score-formula")` declared after `@router.get("/{site_id}")` at line 54 | Blocker | /gap/score-formula returns 422; endpoint unreachable |

---

### Human Verification Required

#### 1. File Upload Import (CSV and XLSX)

**Test:** Navigate to /gap/{site_id}. In the file upload section, upload a keys.so CSV file with columns Запрос, Частотность, Позиция. Enter a competitor domain. Click "Загрузить".
**Expected:** Status message shows "Импортировано: N, gap-ключей: N". Page reloads showing keywords in the table. Repeat with an XLSX file.
**Why human:** Requires running app with DB; multipart file upload + tmp file lifecycle + parser end-to-end cannot be verified via grep.

#### 2. Proposal Approval with Content Plan Link

**Test:** Create gap keywords via import or SERP detection. Select keywords and click "Создать предложения". In the proposals table, click "Одобрить" on a pending proposal.
**Expected:** Proposal status badge changes to "Одобрено" (green). If a project_id is supplied in the approve request body, a ContentPlanItem is created and the proposal.content_plan_item_id is populated.
**Why human:** Requires live DB state with a project; FK write to content_plan_items cannot be verified without running state.

#### 3. SERP Session Detection Flow

**Test:** With an existing analytics session containing SERP results, navigate to /gap/{site_id}. Select the session and enter a competitor domain. Click "Найти gap-ключи".
**Expected:** Status shows "Найдено gap-ключей: N". Keywords appear in the table with source=serp.
**Why human:** Requires a DB with populated SessionSerpResult rows; cannot test without live session data.

---

### Gaps Summary

Two gaps block complete goal achievement:

**Gap 1 — /score-formula endpoint unreachable (route ordering bug):** The `GET /score-formula` endpoint at line 292 of `app/routers/gap.py` is declared after the parameterized `GET /{site_id}` route at line 54. FastAPI routes in declaration order; the /{site_id} pattern matches "score-formula" first, attempts UUID coercion, and returns HTTP 422. The fix is a single-line move: place the `/score-formula` decorator before `/{site_id}`. The handler and constant are both correct.

**Gap 2 — SERP gap detection does not filter against our keyword set:** `detect_gaps_from_session()` computes `our_phrases` (the set of our site's keyword phrases) but never uses it in the detection loop. Every SERP keyword where the competitor appears is recorded as a gap, even keywords we already rank for. The `our_position` field is always `None` in returned dicts. This contradicts the phase goal "ключи, по которых конкуренты в TOP-10, а мы нет." The fix requires checking whether `row.keyword_phrase.lower().strip()` is absent from `our_phrases` before appending to gaps, and/or tracking whether our site domain appears in the SERP results for that row.

Both gaps are in existing files and require targeted edits — no new files needed.

---

_Verified: 2026-04-03T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
