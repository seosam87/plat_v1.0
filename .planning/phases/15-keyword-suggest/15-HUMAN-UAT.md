---
status: partial
phase: 15-keyword-suggest
source: [15-VERIFICATION.md]
started: 2026-04-07T00:00:00Z
updated: 2026-04-07T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Yandex Suggest live run with proxy
expected: 200+ deduplicated Yandex Suggest results returned without proxy ban; results table populates with source badges
result: [pending]

### 2. Google Suggest toggle
expected: Combined deduplicated list with Я and G source badges appears
result: [pending]

### 3. Wordstat OAuth + frequency load
expected: Wordstat polling partial appears, then frequency column populates with real numbers
result: [pending]

### 4. Redis cache hit on resubmit (24h)
expected: Status partial immediately shows green 'Из кэша' indicator with no Celery dispatch
result: [pending]

### 5. Rate limit (11 reqs / 60s)
expected: 11th request returns HTTP 429
result: [pending]

### 6. Router test suite in DB-enabled env
expected: tests/test_keyword_suggest_router.py — all 12 tests pass
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
