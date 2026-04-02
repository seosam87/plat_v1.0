---
created: 2026-04-02T20:19:26.011Z
title: Fix position check ignores keyword engine preference
area: api
files:
  - app/tasks/position_tasks.py:113
  - app/tasks/position_tasks.py:154
  - app/models/keyword.py:67-69
  - app/templates/positions/index.html:104
---

## Problem

Keywords imported from KeyCollector have `engine="yandex"` in the Keyword model,
but `check_positions` task hardcodes `"google"` when writing positions:

- Line 113: `write_position_sync(db, kw.id, ..., "google", position, url=url)`
- Line 154: `write_position_sync(db, kw.id, ..., "google", position, url=url)`

Result: all keywords show "google" badge in positions UI regardless of actual engine.
The `Keyword.engine` field is stored but never consulted during position checks.

## Solution

1. Read `kw.engine` (default to "google" if None) in `_check_via_dataforseo` and `_check_via_serp_parser`
2. Pass correct engine to `write_position_sync()`
3. Route Yandex keywords to XMLProxy service (when integrated), Google to Playwright
4. Group keywords by engine before processing to avoid mixing API calls
