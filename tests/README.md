# Tests

## UI Smoke Crawler (Phase 15.1)

`tests/test_ui_smoke.py` parametrizes over every UI GET route discovered from `app.routes` and asserts each renders without Jinja errors. The smoke gate runs in default `pytest` invocation and blocks CI merge.

### Adding a new route to smoke coverage

A new UI GET route is automatically picked up — no test code changes needed — IF its path parameters are already in `PARAM_MAP`.

1. **Path uses only known params** (`site_id`, `keyword_id`, `module`, etc.): nothing to do. Run `pytest tests/test_ui_smoke.py -k <your_route>` to confirm.

2. **Path uses a NEW param name** (e.g. `{cluster_id}`):
   - Add the entity to `tests/fixtures/smoke_seed.py` (create one row in the seed)
   - Add the UUID to `SMOKE_IDS` dict
   - The helper's `build_param_map` will pick it up automatically

3. **Route cannot be smoke-tested** (file download, external redirect, websocket, destructive side-effect):
   - Add path to `SMOKE_SKIP` dict in `tests/_smoke_helpers.py` with a reason comment

4. **Route is a partial** (path contains `/tabs/`, `/partials/`, `/detail/`):
   - Picked up automatically; structural HTML check is relaxed (no `<title>` requirement)

### Non-HTML endpoints under UI prefixes

The smoke gate auto-skips JSON / CSV / file endpoints discovered under
UI prefixes. `discover_routes` classifies routes via three tiers:

1. Explicit `response_class=HTMLResponse` → tested.
   Explicit `response_class=JSONResponse / FileResponse / StreamingResponse / PlainTextResponse` → skipped.
2. Return annotation `-> HTMLResponse` → tested.
   Return annotation `-> list[dict]`, `-> dict`, `-> SomeBaseModel` → skipped.
3. No signal → tested (conservative fallback).

**If your endpoint returns JSON / CSV / binary**: declare `response_class=`
on the route OR add a return-type annotation. You should NEVER need to
add an entry to `SMOKE_SKIP` for non-HTML endpoints — that list is
reserved for HTML endpoints that are deliberately untestable (auth
redirects, ambiguous path-param collisions, etc.).

### Common failures and fixes

| Failure | Cause | Fix |
|---|---|---|
| `UnknownParamError: Unknown path param 'foo'` | New param name | Add to PARAM_MAP via SMOKE_IDS |
| `response body contains error marker 'builtin_function_or_method'` | Jinja attr/key collision (e.g. `data.items` resolved to dict.items method) | Rename context var or use `data['items']` |
| `response body contains error marker 'UndefinedError'` | Template references undefined variable | Add var to route context |
| `full page missing <title>` | Template not extending base layout | Use `{% extends "base.html" %}` |

### Running locally

```bash
pytest tests/test_ui_smoke.py -x          # full smoke suite
pytest tests/test_ui_smoke.py -k opp      # only opportunities routes
python -m tests.smoke_test                # standalone CLI (in-process)
python -m tests.smoke_test --url http://localhost:8000  # against live server
```
