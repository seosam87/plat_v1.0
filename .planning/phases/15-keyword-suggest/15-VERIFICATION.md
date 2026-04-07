---
phase: 15-keyword-suggest
verified: 2026-04-07T00:00:00Z
status: human_needed
score: 5/5 success criteria verified (code-level); live external API behavior requires human verification
re_verification: false
human_verification:
  - test: "Run /ui/keyword-suggest/ in a browser, enter a Russian seed (e.g. 'купить диван'), submit, wait for completion"
    expected: "200+ deduplicated Yandex Suggest results returned without proxy ban; results table populates with source badges"
    why_human: "Requires live Yandex Suggest endpoint, configured proxy pool, and visual UI confirmation; cannot be exercised in CI"
  - test: "Toggle 'Add Google Suggest' checkbox and resubmit"
    expected: "Combined deduplicated list with Я and G source badges appears"
    why_human: "Requires live Google Suggest endpoint and visual UI"
  - test: "Configure Yandex Direct OAuth token in Settings, then click 'Загрузить частотность' on a completed job"
    expected: "Wordstat polling partial appears, then frequency column populates with real numbers"
    why_human: "Requires valid OAuth token + live Yandex Wordstat API quota"
  - test: "Resubmit the same seed within 24h"
    expected: "Status partial immediately shows green 'Из кэша' indicator with no Celery dispatch"
    why_human: "Requires live Redis instance with prior cached entry"
  - test: "Submit 11 search requests in under 60 seconds from same IP"
    expected: "11th request returns HTTP 429"
    why_human: "Rate-limit middleware behavior depends on running app + slowapi storage backend"
  - test: "tests/test_keyword_suggest_router.py — DB-backed router suite"
    expected: "All 12 tests pass"
    why_human: "Test suite errors with socket.gaierror in this environment (no DB host); same issue affects pre-existing tests/test_client_reports_router.py — environmental, not a code defect"
---

# Phase 15: Keyword Suggest Verification Report

**Phase Goal:** Users can retrieve 200+ keyword suggestions by seed keyword from Yandex (primary) and Google (secondary) with results cached in Redis so repeat queries need no external calls.

**Verified:** 2026-04-07
**Status:** human_needed (all code-level checks pass; live external/API behavior requires human verification)

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Seed → 200+ Yandex Suggest results via alphabetic expansion routed through proxy pool | ✓ VERIFIED (code) / ? human (live) | `app/tasks/suggest_tasks.py` iterates `RU_ALPHABET` (33 letters), uses `get_active_proxy_urls_sync()` rotation, 30s pause on ban, partial-results path (lines 58–170) |
| 2 | Google Suggest toggle → combined deduplicated results | ✓ VERIFIED | `include_google` branch in `fetch_suggest_keywords` calls `fetch_google_suggest_sync` per letter; `deduplicate_suggestions()` merges with source tags |
| 3 | Wordstat opt-in: token configured → frequency column visible | ✓ VERIFIED | `app/services/wordstat_service.py::fetch_wordstat_frequency_sync` (Bearer token); `fetch_wordstat_frequency` Celery task in `suggest_tasks.py:183`; UI conditional `has_wordstat_token` in router lines 98/222; `"yandex_direct": ["token"]` in `service_credential_service.py:22` |
| 4 | Cache hit on repeat seed → instant return, no external call | ✓ VERIFIED | `suggest_tasks.py:58` reads `r.get(cache_key_val)` first; on hit sets `cache_hit=True`, status=complete and returns; cache write at `r.set(..., ex=SUGGEST_CACHE_TTL)` with `SUGGEST_CACHE_TTL = 86400` |
| 5 | Rate limit 10/min on suggest endpoint; external calls inside Celery with retry=3 | ✓ VERIFIED | `@limiter.limit("10/minute")` at `keyword_suggest.py:116`; both Celery tasks declared with `max_retries=3`; HTTP fetches only inside task body |

**Score:** 5/5 truths verified at code level. Items 1, 3 also flagged for human run-time confirmation.

### Required Artifacts (all three plans)

| Artifact | Status | Notes |
|---|---|---|
| `app/models/suggest_job.py` | ✓ VERIFIED | `class SuggestJob` with status lifecycle, cache_key, cache_hit, result_count, expected_count |
| `app/services/suggest_service.py` | ✓ VERIFIED | `fetch_yandex_suggest_sync`, `fetch_google_suggest_sync`, `suggest_cache_key`, `deduplicate_suggestions`, `RU_ALPHABET`, `SUGGEST_CACHE_TTL=86400` |
| `app/tasks/suggest_tasks.py` | ✓ VERIFIED | `fetch_suggest_keywords` + `fetch_wordstat_frequency` tasks, both `max_retries=3` |
| `alembic/versions/0040_add_suggest_jobs.py` | ✓ VERIFIED | Creates `suggest_jobs` table |
| `app/services/wordstat_service.py` | ✓ VERIFIED | `fetch_wordstat_frequency_sync` with Bearer auth |
| `app/services/service_credential_service.py` | ✓ VERIFIED | `"yandex_direct": ["token"]` in ENCRYPTED_FIELDS |
| `app/routers/keyword_suggest.py` | ✓ VERIFIED | All 6 endpoints (index, search, status, export, wordstat dispatch, wordstat-status); rate limiter, StreamingResponse, UTF-8 BOM CSV |
| `app/templates/keyword_suggest/index.html` | ✓ VERIFIED | hx-post search form |
| `app/templates/keyword_suggest/partials/suggest_status.html` | ✓ VERIFIED | hx-trigger polling |
| `app/templates/keyword_suggest/partials/suggest_results.html` | ✓ VERIFIED | filter, sort, CSV link, Wordstat hx-post button |
| `app/navigation.py` | ✓ VERIFIED | "keyword-suggest" section with child entry (lines 87–93) |
| `tests/test_suggest_service.py` | ✓ VERIFIED | 11 tests pass |
| `tests/test_suggest_tasks.py` | ✓ VERIFIED | tests pass |
| `tests/test_wordstat_service.py` | ✓ VERIFIED | tests pass |
| `tests/test_position_engine_fix.py` | ✓ VERIFIED | tests pass |
| `tests/test_keyword_suggest_router.py` | ⚠️ PRESENT, untested in env | 12 test functions defined; collection errors with socket.gaierror — same env issue affects existing `test_client_reports_router.py` |

### Key Link Verification (manual after gsd-tools regex misses)

| From | To | Status | Evidence |
|---|---|---|---|
| `suggest_tasks.py` → `suggest_service.py` | ✓ WIRED | `from app.services.suggest_service import (...)` line 22 (multi-line import — gsd-tools regex missed it) |
| `suggest_tasks.py` → redis | ✓ WIRED | `import redis as sync_redis` line 15; `sync_redis.from_url(...)` lines 58, 192 |
| `suggest_tasks.py` → `SuggestJob` | ✓ WIRED | Pattern found |
| `keyword_suggest.py` → `suggest_tasks` (delay) | ✓ WIRED | `fetch_suggest_keywords.delay(...)` line 174; lazy import + `fetch_wordstat_frequency.delay(...)` lines 320/330 |
| `keyword_suggest.py` → redis async | ✓ WIRED | `import redis.asyncio as aioredis` line 19; `aioredis.from_url(...)` line 67 |
| `suggest_status.html` → router | ✓ WIRED | hx-get to `/ui/keyword-suggest/status/...` |
| `suggest_results.html` → router | ✓ WIRED | hx-post to `/ui/keyword-suggest/{job}/wordstat` |
| `main.py` → `keyword_suggest_router` | ✓ WIRED | `app.include_router(keyword_suggest_router)` |
| `suggest_tasks.py` → `wordstat_service` | ✓ WIRED | Lazy import inside `fetch_wordstat_frequency`: `from app.services.wordstat_service import fetch_wordstat_frequency_sync` line 190 |
| `wordstat_service.py` → `service_credential_service` (yandex_direct) | ⚠️ DESIGN VARIANT | Plan stipulated `wordstat_service` looks up the credential, but actual implementation has `wordstat_service` accept `oauth_token` as a parameter and the credential lookup happens in `suggest_tasks.py::fetch_wordstat_frequency` (`get_credential_sync(db, "yandex_direct")`). Cleaner separation; functionally equivalent. Not a defect. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Service unit tests | `pytest tests/test_suggest_service.py tests/test_suggest_tasks.py tests/test_wordstat_service.py tests/test_position_engine_fix.py` | 43 passed | ✓ PASS |
| Position engine default fix | `grep 'else "yandex"' app/tasks/position_tasks.py` | Found at lines 268, 298; no `else "google"` remains | ✓ PASS |
| Router import collection | `pytest tests/test_keyword_suggest_router.py` | socket.gaierror at conftest DB connect | ? SKIP (environmental — also blocks pre-existing router tests) |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| SUG-01 | 15-01, 15-02 | Yandex Suggest via alphabetic expansion (200+) | ✓ SATISFIED (code) / ? human (live ban-free run) | RU_ALPHABET loop + proxy rotation in `suggest_tasks.py` |
| SUG-02 | 15-01, 15-02 | Google Suggest as additional source | ✓ SATISFIED | `fetch_google_suggest_sync` + include_google branch + dedup |
| SUG-03 | 15-02, 15-03 | Wordstat API integration (opt-in OAuth) | ✓ SATISFIED (code) / ? human (live API) | `wordstat_service.py`, `fetch_wordstat_frequency` task, encrypted token, UI gating |
| SUG-04 | 15-01, 15-02 | Redis cache TTL 24h, no external call on hit | ✓ SATISFIED | `SUGGEST_CACHE_TTL = 86400`, cache-first read in task |

No orphaned requirements: REQUIREMENTS.md maps SUG-01..SUG-04 to Phase 15; all four are claimed by at least one plan's `requirements:` frontmatter. All marked Complete in REQUIREMENTS.md status table.

### Anti-Patterns Found

None detected. No TODO/FIXME placeholders, no empty handlers, no hardcoded empty returns in production code paths. The proxy-exhaustion fallback (`proxy_url=None`) is intentional and documented.

### Human Verification Required

See frontmatter `human_verification` block for the 6 items requiring live runtime confirmation (proxy/external API behavior, rate limit middleware, cache behavior with real Redis, and the router test suite which is blocked by an environmental DB host issue affecting all router tests in this checkout).

### Gaps Summary

No code-level gaps. Phase 15 implements all four success criteria correctly:

1. The Yandex alphabetic expansion + proxy rotation is structurally complete and matches D-05/D-06/D-17 from CONTEXT.
2. Google Suggest path and dedup are implemented and unit-tested.
3. Wordstat opt-in chain works end-to-end at the code level (encrypted credential → router gating → Celery task → cache update → UI re-render).
4. Redis caching with 24h TTL is implemented in both write and read paths, with cache-hit short-circuit.
5. Rate limiting (10/min) and Celery offloading with retry=3 are in place.

The only gsd-tools "failures" were regex misses against multi-line and lazy imports — manual verification confirms all key links are wired. One design variant in 15-03 (credential lookup moved from `wordstat_service` into the Celery task) is functionally equivalent and arguably cleaner.

Phase 15 is ready for human runtime verification. No replanning needed.

---

_Verified: 2026-04-07_
_Verifier: Claude (gsd-verifier)_
