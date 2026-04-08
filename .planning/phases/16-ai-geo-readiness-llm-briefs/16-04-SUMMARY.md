# Plan 16-04 Summary — LLM UI Wiring

**Status:** Complete (human-verify checkpoint DEFERRED)
**Completed:** 2026-04-08

## Tasks

| # | Name | Status | Commit |
|---|------|--------|--------|
| 1 | Profile router + template (Anthropic key + Usage tab) | Done | `b071bfa` |
| 2 | LLM brief router + brief detail AI block + HTMX polling + accept | Done | `8994ab5` |
| 3 | End-to-end visual verification against live Claude API | **Deferred** | — |

## Deliverables

- `app/routers/profile.py` — Anthropic key card, Save/Validate/Remove, LLM Usage tab
- `app/routers/llm_briefs.py` — POST `/briefs/{id}/llm-enhance`, GET `/briefs/llm-jobs/{id}` (HTMX polling), POST `/briefs/llm-jobs/{id}/accept`
- `app/templates/analytics/_brief_ai_block.html` — renders "Generate AI brief" button **only when** `current_user.has_anthropic_key`; grey hint otherwise
- `app/templates/analytics/brief_detail.html`, `_llm_job_preview.html`, `_llm_job_accepted.html`
- `app/templates/profile/index.html`, `_usage_tab.html`
- Tests: 7 `test_llm_briefs` + 5 `test_profile_anthropic_key` + 71 smoke — all green

## Deferred Work

Human visual verification against a live Anthropic endpoint is postponed until the user
is ready to connect a real Claude API key. This is tracked as **Phase 999.6: LLM API
Integration & Live Verification** in the backlog.

Until a key is configured in `/profile/`, the UI path is dormant:
- The "Generate AI brief" button is hidden (guarded by `has_anthropic_key`)
- The template brief delivery path is untouched — LLM code is strictly additive
- Celery task `llm.generate_brief_enhancement` is registered but never dispatched
  without an explicit user action

## Invariants Preserved

- [x] Template brief always returned unchanged when Claude API key missing (LLM-03)
- [x] Token caps present: `MAX_INPUT_CHARS`, `MAX_OUTPUT_TOKENS=800` (LLM-04)
- [x] Circuit breaker opens after 3 consecutive permanent failures
- [x] Celery task uses `max_retries=3` with transient/permanent error split per CLAUDE.md
- [x] All requirements covered: LLM-01, LLM-03, LLM-04 (backend, UI guard, caps)
