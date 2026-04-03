---
phase: v3-09-intent-detect
verified: 2026-04-03T12:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase v3-09: Intent Auto-Detect Verification Report

**Phase Goal:** Intent Auto-Detect — parse Yandex SERP to determine commercial vs informational intent, batch processing of unclustered keywords, semi-auto UI for review and confirm.
**Verified:** 2026-04-03
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                               | Status     | Evidence                                                                            |
|----|-------------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------|
| 1  | SERP parsed via Playwright with proxy support and captcha fallback                 | VERIFIED   | `proxy_serp_service.py` — full Playwright context, proxy config, _solve_captcha()  |
| 2  | Intent detected from SERP TOP-10 with commercial/informational count + confidence  | VERIFIED   | `intent_service.detect_intent_from_serp()` — threshold logic, confidence formula   |
| 3  | Batch processing of unclustered keywords via Celery task                           | VERIFIED   | `intent_tasks.batch_detect_intents` — asyncio.new_event_loop, get_unclustered_keywords |
| 4  | Semi-auto UI: proposals table with per-keyword confirm/skip and bulk confirm        | VERIFIED   | `intent/index.html` — proposals-tbody rendered by JS fetch, Подтвердить/Пропустить/Подтвердить все |
| 5  | Cluster intent updated when user confirms                                           | VERIFIED   | `intent_service.confirm_intent()` updates `KeywordCluster.intent`, router commits  |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact                                | Expected                                     | Status     | Details                                                                      |
|-----------------------------------------|----------------------------------------------|------------|------------------------------------------------------------------------------|
| `app/services/proxy_serp_service.py`    | Playwright+proxy+captcha SERP parser         | VERIFIED   | 174 lines, full implementation with proxy context, captcha solving, fallback |
| `app/services/intent_service.py`        | Intent detection + batch + confirm functions | VERIFIED   | 161 lines, detect_intent_from_serp, batch_detect_intent, confirm_intent, bulk_confirm_intents, get_unclustered_keywords |
| `app/tasks/intent_tasks.py`             | Celery batch task                            | VERIFIED   | 56 lines, @celery_app.task with bind/retry/queue/soft_time_limit, asyncio.new_event_loop pattern |
| `app/routers/intent.py`                 | 5-endpoint intent router                     | VERIFIED   | 120 lines, GET /{site_id}, POST /detect, GET /proposals, POST /confirm, POST /bulk-confirm |
| `app/templates/intent/index.html`       | Semi-auto review UI                          | VERIFIED   | 228 lines, unclustered table, proposals section, confidence color coding, all JS handlers |
| `tests/test_intent_service.py`          | Unit tests for detection logic               | VERIFIED   | 6 tests covering commercial/informational/mixed/confidence-high/confidence-low/empty |

---

### Key Link Verification

| From                       | To                               | Via                                              | Status  | Details                                                      |
|----------------------------|----------------------------------|--------------------------------------------------|---------|--------------------------------------------------------------|
| `app/main.py`              | `app/routers/intent.py`          | `app.include_router(intent_router)`              | WIRED   | Line 42 import, line 181 include_router                      |
| `app/celery_app.py`        | `app/tasks/intent_tasks`         | `include` in CELERY_IMPORTS                      | WIRED   | Line 20: `"app.tasks.intent_tasks"` in autodiscover list     |
| `intent_tasks.py`          | `intent_service.batch_detect_intent` | `_batch_detect` async helper                 | WIRED   | Line 36 import, line 48 call                                 |
| `intent_service.py`        | `proxy_serp_service.parse_serp_with_proxy` | lazy import on cache miss              | WIRED   | Lines 94-96, fallback to empty list on exception             |
| `intent_service.py`        | `SessionSerpResult` (cache)      | `select(SessionSerpResult)` query                | WIRED   | Lines 81-89, ordered by parsed_at desc                       |
| `intent_service.py`        | `serp_analysis_service.classify_site_type` | top-level import, called per result  | WIRED   | Line 9 import, line 28 call in loop                          |
| `intent/index.html`        | `POST /intent/{site_id}/detect`  | `fetch()` in `runDetect()`                       | WIRED   | Line 106, triggers Celery task                               |
| `intent/index.html`        | `GET /intent/{site_id}/proposals`| `fetch()` in `loadProposals()`                   | WIRED   | Line 129, populates proposals table                          |
| `intent/index.html`        | `POST /intent/{site_id}/confirm` | `fetch()` in `confirmOne()`                      | WIRED   | Line 177, confirms single keyword                            |
| `intent/index.html`        | `POST /intent/{site_id}/bulk-confirm` | `fetch()` in `confirmAll()`               | WIRED   | Line 208, bulk confirmation                                  |
| `clusters/index.html`      | `/intent/{site_id}`              | `<a href="/intent/{{ site_id }}">Интент</a>`     | WIRED   | Line 21 of clusters/index.html                               |

---

### Data-Flow Trace (Level 4)

| Artifact                   | Data Variable  | Source                                          | Produces Real Data | Status   |
|----------------------------|----------------|-------------------------------------------------|--------------------|----------|
| `intent/index.html`        | `unclustered`  | `intent_service.get_unclustered_keywords()` DB query | Yes — SELECT Keyword outerjoin KeywordCluster WHERE intent='unknown' | FLOWING |
| `intent/index.html`        | `_proposals`   | `GET /proposals` → `batch_detect_intent()` → SERP cache or proxy parse | Yes — SessionSerpResult DB cache, live Playwright fallback | FLOWING |
| `intent_service.py`        | `serp_results` | `SessionSerpResult` DB query OR `parse_serp_with_proxy()` | Yes — DB query ordered by parsed_at, live SERP on cache miss | FLOWING |

---

### Behavioral Spot-Checks

| Behavior                                    | Command                                                                      | Result                | Status |
|---------------------------------------------|------------------------------------------------------------------------------|-----------------------|--------|
| intent_service imports clean                | `python -c "from app.services.intent_service import detect_intent_from_serp, batch_detect_intent, confirm_intent"` | Exit 0 | PASS   |
| intent router imports clean                 | `python -c "from app.routers.intent import router"` | Exit 0 | PASS   |
| Celery task imports clean                   | `python -c "from app.tasks.intent_tasks import batch_detect_intents"` | Exit 0 | PASS   |
| proxy_serp_service imports clean            | `python -c "from app.services.proxy_serp_service import parse_serp_with_proxy, is_proxy_configured"` | Exit 0 | PASS   |
| Unit tests: 6 tests pass                    | `python -m pytest tests/test_intent_service.py -x -q`                       | 6 passed in 0.02s     | PASS   |

---

### Requirements Coverage

No `requirements_addressed` IDs declared in PLAN frontmatter. Phase goal is functionally verified through must-haves and truths above. The ROADMAP Phase 9 success criteria are fully satisfied:

| Criterion                                           | Status     | Evidence                                                        |
|-----------------------------------------------------|------------|-----------------------------------------------------------------|
| Парсинг Яндекс SERP по ключу + регион               | SATISFIED  | proxy_serp_service.py — yandex URL with `lr=` region param     |
| Анализ выдачи: коммерческий/информационный          | SATISFIED  | detect_intent_from_serp — threshold logic, classify_site_type  |
| Полуавтомат: система предлагает, специалист подтверждает | SATISFIED | proposals table with per-row confirm/skip/select               |
| Пакетная обработка некластеризованных ключей        | SATISFIED  | batch_detect_intents Celery task, get_unclustered_keywords      |
| Обновление intent кластера на основе результатов    | SATISFIED  | confirm_intent updates KeywordCluster.intent, router commits   |

---

### Anti-Patterns Found

No blocker or warning anti-patterns detected.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routers/intent.py` | 90 | `return []` | Info | Valid guard: early exit when no unclustered keywords exist, not a stub |

---

### Human Verification Required

#### 1. Live SERP parsing with proxy

**Test:** Configure a real `PROXY_URL` in `.env`, trigger intent detection for a site with 5+ unclustered keywords via the UI "Запустить анализ" button.
**Expected:** Proposals table populates within ~30 seconds showing commercial/informational/mixed intent per keyword with color-coded confidence percentages.
**Why human:** Requires live Playwright browser, proxy network access, and real Yandex SERP response — cannot verify programmatically without infrastructure.

#### 2. CAPTCHA detection and solving flow

**Test:** Route traffic through a proxy that triggers Yandex CAPTCHA and verify `_solve_captcha` integrates correctly with rucaptcha API.
**Expected:** Captcha solved, SERP results extracted successfully.
**Why human:** Requires real captcha challenge from Yandex + valid ANTICAPTCHA_KEY.

#### 3. Bulk confirm updates cluster intent in UI

**Test:** Run analysis on a site, verify proposals appear, click "Подтвердить все", then navigate to the clusters page.
**Expected:** Cluster intent fields updated from "unknown" to the confirmed values; page auto-reloads after 1.5s delay.
**Why human:** Requires running application with real DB data and browser interaction.

---

## Gaps Summary

No gaps. All five observable truths verified at all four levels (exists, substantive, wired, data-flowing). Commit `aab0567` confirmed in git log. Unit tests pass. Router registered in `main.py`. Celery task registered in `celery_app.py`. Three human verification items are noted above but do not block the phase goal — they require live infrastructure.

---

_Verified: 2026-04-03T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
