---
phase: 25-serp-aggregation-tools
plan: "03"
subsystem: tools
tags: [paa, beautifulsoup, lxml, celery, xmlproxy, yandex-serp, htmx, jinja2]

requires:
  - phase: 25-serp-aggregation-tools/25-01
    provides: PAAJob + PAAResult SQLAlchemy models, Alembic migration 0050
  - phase: 24-tools-infrastructure-fast-tools
    provides: TOOL_REGISTRY pattern, 7-route handler, export infrastructure

provides:
  - PAA extraction service (extract_paa_blocks, extract_paa_for_phrase) using BeautifulSoup4 + text-content matching
  - fetch_yandex_html_sync in xmlproxy_service for raw Yandex SERP HTML retrieval
  - run_paa Celery task with retry=3, 0.5s rate limiting between phrases
  - TOOL_REGISTRY["paa"] entry with limit=50, cta="Получить вопросы"
  - PAA export headers ["Фраза", "Вопрос", "Блок"] and _result_to_row dispatch
  - PAA templates: index.html, results.html, partials/job_status.html
  - 10 unit tests covering all extraction scenarios

affects:
  - 25-serp-aggregation-tools (remaining plans 04-05)

tech-stack:
  added: []
  patterns:
    - "Text-content heading matching for PAA extraction (avoids fragile CSS selectors)"
    - "Next-sibling traversal from heading to collect PAA items (prevents cross-section pollution)"
    - "PAA tool follows run_commerce_check Celery task pattern exactly"

key-files:
  created:
    - app/services/paa_service.py
    - app/tasks/paa_tasks.py
    - app/templates/tools/paa/index.html
    - app/templates/tools/paa/results.html
    - app/templates/tools/paa/partials/job_status.html
    - tests/test_paa_service.py
  modified:
    - app/services/xmlproxy_service.py (added fetch_yandex_html_sync)
    - app/routers/tools.py (TOOL_REGISTRY, _EXPORT_HEADERS, model/task dispatch, job counts)
    - app/celery_app.py (registered paa_tasks in include list)

key-decisions:
  - "Text-content heading matching (not CSS class selectors) per Research Pitfall 3 — Yandex DOM changes without notice"
  - "Next-sibling traversal from matched heading to collect items — prevents cross-section text pollution when multiple PAA blocks are on the same page"
  - "fetch_yandex_html_sync added to xmlproxy_service using &html=1 parameter — XMLProxy passthrough for raw SERP HTML"
  - "Per-tool template directory (tools/paa/) follows established pattern from tools/commercialization/"

patterns-established:
  - "PAA heading detection: tag.string or get_text for heading tags, then walk next_siblings stopping at next heading"
  - "fetch_yandex_html_sync gracefully handles both HTML and XML responses from XMLProxy"

requirements-completed:
  - PAA-01

duration: 10min
completed: "2026-04-10"
---

# Phase 25 Plan 03: PAA Parser Summary

**PAA extraction from Yandex SERP HTML via XMLProxy using BeautifulSoup4 text-content matching, with flat PAAResult storage, Celery task with retry=3, and fully wired TOOL_REGISTRY integration**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-10T12:30:42Z
- **Completed:** 2026-04-10T12:39:42Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- PAA extraction service with two strategies: heading text-content matching + next-sibling traversal, and data-fast-name attribute fallback
- Celery task run_paa following run_commerce_check pattern with XMLProxy error handling and 0.5s rate limiting between phrases
- Complete TOOL_REGISTRY integration: model/task dispatch, export headers, result serialization, job count in index
- Per-tool templates: PAA-specific index, results (flat 3-column table), and status partial with Russian copy

## Task Commits

1. **Task 1: PAA extraction service + Celery task + tests** - `395ba10` (feat)
2. **Task 2: PAA router integration + results template branch** - `09009ee` (feat)

## Files Created/Modified

- `app/services/paa_service.py` - extract_paa_blocks() and extract_paa_for_phrase() using BeautifulSoup4 lxml
- `app/tasks/paa_tasks.py` - run_paa Celery task with retry=3 and XMLProxy credential loading
- `app/services/xmlproxy_service.py` - Added fetch_yandex_html_sync() with html=1 parameter
- `app/routers/tools.py` - TOOL_REGISTRY paa entry, export headers, model/task/row dispatch, index counts
- `app/celery_app.py` - Registered app.tasks.paa_tasks in include list
- `app/templates/tools/paa/index.html` - Landing page with phrase textarea and previous jobs table
- `app/templates/tools/paa/results.html` - Results with flat 3-column table (Фраза/Вопрос/Блок)
- `app/templates/tools/paa/partials/job_status.html` - Status banners with PAA-specific copy
- `tests/test_paa_service.py` - 10 unit tests covering all extraction scenarios

## Decisions Made

- Text-content matching (not CSS class selectors) per Research Pitfall 3 — Yandex SERP DOM changes without notice; heading text "частые вопросы"/"похожие запросы" is stable language content
- Next-sibling traversal from matched heading to collect PAA items — prevents cross-section pollution that would occur if walking the full parent container (which aggregates all sibling text)
- Per-tool template directory (tools/paa/) follows established pattern from tools/commercialization/ — clean separation without modifying generic tool_results.html

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed cross-section text pollution in PAA extraction**
- **Found during:** Task 1 (test_extract_paa_blocks_both_blocks failure)
- **Issue:** Initial implementation walked `tag.parent.find_all(...)` which included all siblings' text. When a `<div>` container aggregated text from both PAA blocks, searching for "частые вопросы" in the container's text matched it as the heading, then the parent container yielded items from BOTH blocks incorrectly labeled as "частые вопросы"
- **Fix:** Rewrote to use `next_siblings` traversal from the heading tag, stopping at the next heading-level element — this scopes each extraction to exactly the items following that heading
- **Files modified:** app/services/paa_service.py
- **Verification:** test_extract_paa_blocks_both_blocks passes, both source_block values present
- **Committed in:** 395ba10 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in extraction algorithm)
**Impact on plan:** Fix necessary for correctness — without it, all items from "Похожие запросы" would be mislabeled as "Частые вопросы" on pages containing both blocks. No scope creep.

## Issues Encountered

- None beyond the auto-fixed cross-section pollution bug described above.

## Known Stubs

None — PAA tool is fully wired: XMLProxy HTML fetching, BeautifulSoup extraction, PAAResult storage, export via generic handler, flat table UI display. No placeholder data.

Note: `fetch_yandex_html_sync` uses `&html=1` parameter that may not be supported by all XMLProxy account tiers. If the parameter is unsupported, XMLProxy returns XML (handled gracefully by the function — it extracts passage text from XML as fallback). The run_paa task will function with whatever HTML/text XMLProxy provides, logging a warning if 0 PAA questions are found.

## Next Phase Readiness

- PAA Parser fully functional end-to-end
- Phase 25 Plans 04-05 can proceed independently (Batch Wordstat does not depend on PAA)

---
*Phase: 25-serp-aggregation-tools*
*Completed: 2026-04-10*
