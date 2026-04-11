---
status: diagnosed
trigger: "UAT Test 2 (Phase 999.8): Фильтрация по категориям не работает на /ui/playbooks/blocks — форма создания блока работает, карточка появляется в сетке, но при выборе категории список не сужается"
created: 2026-04-11T21:00:00Z
updated: 2026-04-11T21:05:00Z
---

## Current Focus

hypothesis: FastAPI route ui_playbook_blocks declares category_id and expert_source_id as `uuid.UUID | None = None`; HTMX hx-include sends the empty string for whichever select is set to "Все ...", FastAPI 422s on empty-string→UUID parsing, the filter never reaches the service layer, the grid is replaced with a JSON error (or stays visually unchanged), user perceives "filter doesn't work"
test: Live in-process AsyncClient reproduction against the running api container
expecting: 422 on requests mimicking the real HTMX payload, 200 on requests without the empty companion param
next_action: Return diagnosis to planner

## Symptoms

expected: |
  User opens /ui/playbooks/blocks, selects a category from the dropdown,
  HTMX fires hx-get to /ui/playbooks/blocks?category_id=<uuid>&expert_source_id=<whatever>,
  server returns filtered _block_card_grid.html partial, innerHTML of #blocks-grid
  swaps to show only blocks in that category.
actual: |
  Clicking a category in the dropdown does not narrow the grid — the list stays
  the same (or displays garbage). No visible filter effect.
errors: |
  Hidden 422 Unprocessable Entity from the /ui/playbooks/blocks endpoint on
  every filter-change event (not visible in UI because HTMX innerHTML-swaps
  the response body into #blocks-grid or silently ignores non-2xx depending
  on HTMX config).
reproduction: |
  1. Log in as admin
  2. Go to /ui/playbooks/blocks (seed has at least 6 demo blocks across categories)
  3. Click the "Все категории" dropdown and select any category
  4. Observe: grid does not narrow
started: Plan 02 commit b2a1f68 (Phase 999.8, 2026-04-11) — introduced in the initial implementation

## Eliminated

- hypothesis: Service list_blocks ignores category_id param
  evidence: |
    app/services/playbook_service.py:248 `if category_id is not None: stmt = stmt.where(PlaybookBlock.category_id == category_id)` — correct.
    Plan 02 SUMMARY line 148 confirms in-process smoke test `Filtered list ?category_id=… Returns new block in body` passed.
  timestamp: 2026-04-11T21:03:00Z

- hypothesis: Parameter name mismatch (slug vs id) between template and router
  evidence: |
    Template uses name="category_id" (app/templates/playbooks/blocks.html:16),
    route signature uses `category_id: uuid.UUID | None = None` (app/routers/playbooks.py:66).
    Names match.
  timestamp: 2026-04-11T21:03:00Z

- hypothesis: hx-target wrong / swap wrapper missing
  evidence: |
    Template has `<div id="blocks-grid">` on line 44 and dropdown uses
    `hx-target="#blocks-grid"` with `hx-swap="innerHTML"` — correct wiring.
  timestamp: 2026-04-11T21:03:00Z

## Evidence

- timestamp: 2026-04-11T21:02:30Z
  checked: app/templates/playbooks/blocks.html lines 15–42
  found: |
    Category <select name="category_id"> has
      hx-get="/ui/playbooks/blocks"
      hx-include="[name='expert_source_id']"
    Expert <select name="expert_source_id"> has symmetric
      hx-include="[name='category_id']"
    BOTH selects have `<option value="">Все ...</option>` as their default/first option.
  implication: |
    When user picks a category, HTMX submits both category_id=<uuid> AND
    expert_source_id="" (empty string from the default "Все эксперты" option).
    Same in reverse for expert selection.

- timestamp: 2026-04-11T21:02:35Z
  checked: app/routers/playbooks.py lines 63–92 (ui_playbook_blocks)
  found: |
    Route signature:
      async def ui_playbook_blocks(
          request: Request,
          category_id: uuid.UUID | None = None,
          expert_source_id: uuid.UUID | None = None,
          ...
      )
    No pre-parsing, no Query() with custom converter, no empty-string coercion.
  implication: |
    FastAPI/Pydantic v2 treats a present-but-empty query param as a
    validation failure, not as absent. `?expert_source_id=` is NOT equivalent
    to omitting the parameter — it's `""` which fails UUID parsing.

- timestamp: 2026-04-11T21:03:13Z
  checked: Live reproduction via in-process AsyncClient against running api container (seo-platform-api-1)
  found: |
    [1] GET /ui/playbooks/blocks                                              → 200 (plain grid)
    [2] GET /ui/playbooks/blocks?category_id=<uuid>&expert_source_id=         → 422
        detail: {"type":"uuid_parsing","loc":["query","expert_source_id"],
                 "msg":"Input should be a valid UUID, invalid length:
                       expected length 32 for simple format, found 0",
                 "input":""}
    [3] GET /ui/playbooks/blocks?category_id=&expert_source_id=               → 422
        (both params flagged as invalid UUID)
    [4] GET /ui/playbooks/blocks?category_id=<uuid>                           → 200
        (works — proves service layer is fine, only the empty-string companion param kills it)
  implication: |
    Bug is 100% reproduced. FastAPI rejects the exact payload HTMX generates
    on every filter change. The service layer and template targets are
    healthy; the sole defect is the route signature accepting UUID instead of
    handling empty string as "no filter".

## Resolution

root_cause: |
  Route ui_playbook_blocks at app/routers/playbooks.py:63-76 declares
  category_id and expert_source_id as `uuid.UUID | None = None`, but the
  HTMX filter dropdowns in app/templates/playbooks/blocks.html send the
  empty string for whichever select is currently on "Все ..." (via
  hx-include of the sibling select). FastAPI's Pydantic v2 query
  validation rejects `""` as an invalid UUID and returns 422 instead of
  treating it as absent. Every filter change therefore short-circuits
  before the service layer is reached, and HTMX swaps the JSON error
  (or nothing) into #blocks-grid.

fix: ""
verification: ""
files_changed: []
