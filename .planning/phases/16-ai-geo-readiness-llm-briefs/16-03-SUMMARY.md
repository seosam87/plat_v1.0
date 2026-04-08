---
phase: 16-ai-geo-readiness-llm-briefs
plan: 03
subsystem: api
tags: [anthropic, celery, redis, circuit-breaker, llm, encryption, fernet, pydantic]

# Dependency graph
requires:
  - phase: 16-ai-geo-readiness-llm-briefs
    provides: "llm_brief_jobs and llm_usage tables (migration 0041), users.anthropic_api_key_encrypted column, app/services/llm/__init__.py"
provides:
  - "anthropic>=0.39,<1.0 installed and importable"
  - "app/services/llm/config.py: ANTHROPIC_MODEL constant (claude-haiku-4-5-20251001) + INPUT/OUTPUT budgets"
  - "app/services/llm/pricing.py: compute_cost() for Haiku 4.5 pricing"
  - "app/services/llm/llm_service.py: BRIEF_OUTPUT_SCHEMA, LLMBriefEnhancement pydantic model, build_brief_prompt, call_llm_brief_enhance, circuit breaker helpers, log_llm_usage"
  - "app/models/llm_brief_job.py: LLMBriefJob + LLMUsage SQLAlchemy models"
  - "User.has_anthropic_key property + set/get/clear_anthropic_api_key in user_service"
  - "app/tasks/llm_tasks.py: generate_llm_brief_enhancement Celery task"
affects:
  - "16-04: LLM brief enhancement UI (wires Plan 03 task, reads LLMBriefJob.output_json)"

# Tech tracking
tech-stack:
  added:
    - "anthropic>=0.39,<1.0 (AsyncAnthropic, structured JSON output via output_config)"
  patterns:
    - "Circuit breaker: Redis keys llm:cb:user:{id} + llm:cb:fails:{id}, TTL=900s, threshold=3"
    - "Transient vs permanent error split: (APIConnectionError, APITimeoutError, RateLimitError) → retry; (AuthenticationError, PermissionDeniedError, BadRequestError) → fail fast"
    - "_TransientLLMError sentinel: raised inside async body to signal outer sync task wrapper to call self.retry"
    - "_get_async_session/_get_redis injectable functions for test isolation without mocking whole Celery machinery"
    - "TDD: RED commit (test) → GREEN commit (feat) for both tasks"

key-files:
  created:
    - app/services/llm/config.py
    - app/services/llm/pricing.py
    - app/services/llm/llm_service.py
    - app/models/llm_brief_job.py
    - app/tasks/llm_tasks.py
    - tests/test_llm_service.py
    - tests/test_llm_tasks.py
  modified:
    - requirements.txt
    - app/models/__init__.py
    - app/models/user.py
    - app/services/user_service.py
    - app/celery_app.py

key-decisions:
  - "asyncio.new_event_loop().run_until_complete() wraps async body — matches all other async Celery tasks in codebase"
  - "_run_enhance separated from task wrapper to allow direct async testing without full Celery worker"
  - "Circuit breaker NOT incremented on transient retries — only on permanent failure or retry exhaustion"
  - "build_brief_prompt includes all 5 context types (keywords, gaps, geo_score, cannibalization, competitors) even when empty (writes 'нет данных' placeholder per LLM-02)"
  - "User.anthropic_api_key_encrypted added as SQLAlchemy mapped_column on User model to reflect migration 0041 schema"

patterns-established:
  - "Pattern: _get_async_session/_get_redis as module-level injectable functions enables test patching without Celery runner"
  - "Pattern: _TransientLLMError sentinel class decouples retry signaling from exception hierarchy details"

requirements-completed: [LLM-01, LLM-02, LLM-03, LLM-04]

# Metrics
duration: 10min
completed: 2026-04-08
---

# Phase 16 Plan 03: LLM Backend Infrastructure Summary

**Anthropic Claude Haiku 4.5 integration: per-user Fernet-encrypted key storage, structured JSON prompt builder with 5 context types, per-user Redis circuit breaker (3 failures/15 min), and Celery task with transient/permanent error split.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-08T10:28:06Z
- **Completed:** 2026-04-08T10:38:00Z
- **Tasks:** 2 completed (both TDD: RED + GREEN commits)
- **Files modified:** 12

## Accomplishments

- Anthropic SDK (v0.91.0) installed and importable in api container; `call_llm_brief_enhance` uses `AsyncAnthropic` with `output_config` for guaranteed JSON structured output
- Per-user circuit breaker via Redis: 3 consecutive permanent failures → 15-min lockout; transient retries do NOT increment counter (prevents single network blip from opening circuit)
- 20 unit tests pass (14 service tests + 6 task tests) with zero real API calls

## Task Commits

Each task was committed atomically (TDD — RED then GREEN):

1. **Task 1 RED: LLM service tests** - `e7b8df5` (test)
2. **Task 1 GREEN: SDK install + service module + key storage** - `579a950` (feat)
3. **Task 2 RED: Celery task tests** - `cbf3c6c` (test)
4. **Task 2 GREEN: generate_llm_brief_enhancement task** - `56f7e2e` (feat)

## Files Created/Modified

- `requirements.txt` - Added `anthropic>=0.39,<1.0`
- `app/services/llm/config.py` - ANTHROPIC_MODEL constant, token budgets, circuit breaker constants
- `app/services/llm/pricing.py` - Haiku 4.5 pricing (input $1/MTok, output $5/MTok), compute_cost()
- `app/services/llm/llm_service.py` - BRIEF_OUTPUT_SCHEMA, LLMBriefEnhancement pydantic model, build_brief_prompt (all 5 context types + hard truncation), call_llm_brief_enhance, is_circuit_open/record_llm_failure/record_llm_success, log_llm_usage
- `app/models/llm_brief_job.py` - LLMBriefJob + LLMUsage SQLAlchemy 2.0 models
- `app/models/__init__.py` - Registered LLMBriefJob, LLMUsage
- `app/models/user.py` - Added anthropic_api_key_encrypted column + has_anthropic_key property
- `app/services/user_service.py` - set/get/clear_anthropic_api_key using crypto_service.encrypt/decrypt
- `app/tasks/llm_tasks.py` - generate_llm_brief_enhancement Celery task + _run_enhance + _mark_failed + _TransientLLMError
- `app/celery_app.py` - Registered app.tasks.llm_tasks in include list
- `tests/test_llm_service.py` - 14 unit tests for service module
- `tests/test_llm_tasks.py` - 6 unit tests for Celery task

## Decisions Made

- `_run_enhance` separated from Celery task wrapper to allow direct async testing — same pattern as impact_tasks/audit_tasks in this codebase
- `_TransientLLMError` sentinel avoids importing Celery in tests and cleanly separates "should retry" from "should fail fast"
- Circuit breaker only fires on permanent failure OR transient retry exhaustion — one network blip does not lock the user out
- `_get_async_session` and `_get_redis` are injectable module-level functions rather than globals, making tests clean without mocking the whole DB engine

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added User.anthropic_api_key_encrypted to SQLAlchemy model**
- **Found during:** Task 1 — implementing user_service key functions
- **Issue:** Migration 0041 added the column to PostgreSQL, but the User SQLAlchemy model had no corresponding `Mapped[str | None]` column — ORM writes would fail silently or error
- **Fix:** Added `anthropic_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)` and `has_anthropic_key` property to `app/models/user.py`
- **Files modified:** `app/models/user.py`
- **Commit:** 579a950 (Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (Rule 2 missing critical ORM column)
**Impact on plan:** Essential for ORM writes to the encrypted key column. No scope creep.

## Issues Encountered

- Anthropic package not pre-installed in Docker image — had to rebuild (`docker compose build api`) after adding to requirements.txt. First two test runs used ephemeral pip install that did not persist.

## Next Phase Readiness

- `generate_llm_brief_enhancement(job_id)` is ready for Plan 04 to invoke after template brief creation
- LLMBriefJob model ready for Plan 04 to create rows and poll status
- `has_anthropic_key` property ready for Plan 04 template conditionals (D-02)
- No blockers for Plan 04 UI wiring

## Self-Check: PASSED

All created files verified present:
- FOUND: app/services/llm/config.py
- FOUND: app/services/llm/pricing.py
- FOUND: app/services/llm/llm_service.py
- FOUND: app/models/llm_brief_job.py
- FOUND: app/tasks/llm_tasks.py
- FOUND: tests/test_llm_service.py
- FOUND: tests/test_llm_tasks.py

All commits verified:
- e7b8df5: test(16-03) RED Task 1
- 579a950: feat(16-03) GREEN Task 1
- cbf3c6c: test(16-03) RED Task 2
- 56f7e2e: feat(16-03) GREEN Task 2
- 097e8be: docs(16-03) final commit

---
*Phase: 16-ai-geo-readiness-llm-briefs*
*Completed: 2026-04-08*
