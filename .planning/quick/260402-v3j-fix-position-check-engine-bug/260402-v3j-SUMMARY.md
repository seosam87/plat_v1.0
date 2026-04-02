---
phase: quick
plan: 260402-v3j
subsystem: position-tasks
tags: [bugfix, engine, yandex, position-check]
dependency_graph:
  requires: []
  provides: [engine-aware-position-writing]
  affects: [keyword_positions, serp_parser_service, dataforseo_service]
tech_stack:
  added: []
  patterns: [kw.engine.value fallback pattern]
key_files:
  created:
    - tests/test_position_tasks_engine.py
  modified:
    - app/tasks/position_tasks.py
decisions:
  - Engine string derived from kw.engine.value with "google" as fallback (not None)
metrics:
  duration: ~8 min
  completed: 2026-04-02
  tasks: 1
  files: 2
---

# Quick Fix 260402-v3j: Fix Hardcoded Engine in Position Check Tasks

**One-liner:** Replace hardcoded `"google"` engine string in `_check_via_dataforseo` and `_check_via_serp_parser` with `kw.engine.value if kw.engine else "google"` so Yandex keywords store positions with engine='yandex'.

## What Was Fixed

`app/tasks/position_tasks.py` had two functions that always wrote `engine="google"` to `keyword_positions`, regardless of the keyword's actual engine field. Keywords imported from KeyCollector have `engine=SearchEngine.yandex`, so their positions were mislabelled as Google results.

### Changes in `app/tasks/position_tasks.py`

**`_check_via_dataforseo` (line 112):**
```python
# Before
write_position_sync(db, kw.id, uuid.UUID(site_id), "google", position, url=url)

# After
engine_str = kw.engine.value if kw.engine else "google"
write_position_sync(db, kw.id, uuid.UUID(site_id), engine_str, position, url=url)
```

**`_check_via_serp_parser` (lines 143-154):**
```python
# Before
serp_data = parse_serp_sync(kw.phrase, engine="google")
...
write_position_sync(db, kw.id, uuid.UUID(site_id), "google", position, url=url)

# After
engine_str = kw.engine.value if kw.engine else "google"
serp_data = parse_serp_sync(kw.phrase, engine=engine_str)
...
write_position_sync(db, kw.id, uuid.UUID(site_id), engine_str, position, url=url)
```

## Tests Added

`tests/test_position_tasks_engine.py` — 6 unit tests using `unittest.mock.patch` targeting the correct module paths for locally-imported functions:

| Test | Covers |
|------|--------|
| `test_yandex_keyword_writes_yandex_engine` (dataforseo) | engine='yandex' propagated to write_position_sync |
| `test_none_engine_defaults_to_google` (dataforseo) | engine=None defaults to 'google' |
| `test_yandex_keyword_calls_parse_with_yandex_engine` | engine='yandex' passed to parse_serp_sync |
| `test_yandex_keyword_writes_yandex_engine` (serp_parser) | engine='yandex' propagated to write_position_sync |
| `test_none_engine_parse_defaults_to_google` | engine=None defaults parse to 'google' |
| `test_none_engine_write_defaults_to_google` | engine=None defaults write to 'google' |

All 6 passed.

## Commits

| Hash | Message |
|------|---------|
| 8e45946 | test(quick-260402-v3j): add failing tests for engine propagation in position tasks |
| 23e77f6 | fix(quick-260402-v3j): use kw.engine instead of hardcoded 'google' in position tasks |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `app/tasks/position_tasks.py` — modified and committed (23e77f6)
- `tests/test_position_tasks_engine.py` — created and committed (8e45946)
- All 6 tests pass: `python -m pytest tests/test_position_tasks_engine.py -x -v`
- No hardcoded `"google"` remains as a direct argument to `write_position_sync` or `parse_serp_sync`
