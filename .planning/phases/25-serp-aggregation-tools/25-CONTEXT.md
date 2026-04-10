# Phase 25: SERP Aggregation Tools - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Three advanced SERP tools requiring multi-step crawling and aggregation — Copywriting Brief generator (TOP-10 analysis), PAA parser, and Batch Wordstat frequency tool. All follow the Job+Result architecture from Phase 24, appear in the existing Tools sidebar section.

</domain>

<decisions>
## Implementation Decisions

### Copywriting Brief Architecture
- **D-01:** Copywriting Brief is an EXTENSION of the existing LLM Brief (Phase 16), not a separate tool. Merge into `app/services/brief_service.py` and `app/models/llm_brief_job.py` — add TOP-10 analysis sections alongside existing LLM-generated content.
- **D-02:** Pipeline runs as a Celery chain of 4 steps: (1) XMLProxy TOP-10 URLs → (2) Playwright crawl each page → (3) aggregation/frequency computation → (4) DB write + status update.
- **D-03:** Output format is XLSX export only (no PDF, no on-page rendered brief).
- **D-04:** Landing page URL is optional input — user submits phrases + region, URL посадочной not required.

### Playwright Crawling
- **D-05:** Separate lightweight crawler for TOP-10 pages — extract only visible text, H2 headings, and highlights. Do NOT reuse the full `crawler_service.py` (which does site audit-level crawling).
- **D-06:** If a TOP-10 page fails (timeout, 403, captcha) — skip it silently and continue with remaining pages. Job completes with whatever data was collected, no partial status.

### PAA Parser
- **D-07:** Use XMLProxy to fetch Yandex SERP HTML for PAA extraction (no Playwright needed — XMLProxy returns rendered HTML).
- **D-08:** First level only — do not attempt to expand nested questions (no recursive XMLProxy calls).
- **D-09:** Storage as flat table: PAAResult rows with columns (phrase, question, level, source_block). No JSON tree.
- **D-10:** Extract BOTH "Частые вопросы" and "Похожие запросы" blocks from Yandex SERP.

### Batch Wordstat
- **D-11:** Separate service (`batch_wordstat_service.py`), NOT extending existing `wordstat_service.py`. Different concerns: batch processing up to 1000 phrases vs single-phrase lookup.
- **D-12:** Progress shown as % completion via HTMX polling (same pattern as other tools — `partials/job_status.html` with progress percentage).
- **D-13:** Monthly dynamics stored in a separate table (`WordstatMonthlyData` or similar) linked to WordstatBatchResult, NOT as JSON field. Columns: result_id FK, year_month, frequency.

### Claude's Discretion
- Celery chain error handling strategy (which step failures are retryable)
- XLSX template layout and column ordering for Copywriting Brief
- How to merge new Copywriting Brief sections with existing LLM Brief model structure
- XMLProxy rate limiting coordination across concurrent tool jobs

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 24 Infrastructure (base patterns)
- `app/routers/tools.py` — TOOL_REGISTRY dispatch pattern, all 7 route handlers
- `app/models/commerce_check_job.py` — Job+Result model pattern to follow
- `app/templates/tools/tool_landing.html` — Shared input form template
- `app/templates/tools/tool_results.html` — Shared results rendering template
- `app/templates/tools/partials/job_status.html` — HTMX polling partial

### Existing services to integrate with
- `app/services/brief_service.py` — LLM Brief service (Phase 16), extend for Copywriting Brief
- `app/models/llm_brief_job.py` — LLM Brief model, extend with TOP-10 sections
- `app/services/wordstat_service.py` — Existing sync Wordstat API client (Phase 15.3)
- `app/services/xmlproxy_service.py` — XMLProxy SERP fetching
- `app/services/crawler_service.py` — Full Playwright crawler (reference only, do NOT reuse for TOP-10)

### ROADMAP success criteria
- `.planning/ROADMAP.md` §Phase 25 — 5 success criteria defining acceptance

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TOOL_REGISTRY` in `app/routers/tools.py` — add 3 new tool slugs (brief, paa, wordstat-batch)
- `tool_landing.html` / `tool_results.html` — shared templates, extend for new tools
- `partials/job_status.html` — HTMX polling, add progress % display for Wordstat batch
- `app/services/xmlproxy_service.py` — XMLProxy client for SERP fetching (used by PAA + Brief)

### Established Patterns
- Job model: `id (UUID), user_id FK, status (pending/running/complete/partial/error), input_*, created_at, completed_at`
- Result model: `id (int), job_id FK, per-row data columns`
- Celery task: `@celery_app.task(bind=True, max_retries=3)`, asyncio.run() bridge for async services
- Router: slug-based dispatch through TOOL_REGISTRY, generic handlers

### Integration Points
- `TOOL_REGISTRY` dict — add entries for "brief", "paa", "wordstat-batch"
- `app/celery_app.py` — register new task modules
- Navigation sidebar — already has Tools section from Phase 24
- `_EXPORT_HEADERS` dict in router — add export column definitions

</code_context>

<specifics>
## Specific Ideas

- Copywriting Brief extends existing LLM Brief model — single tool with both template-based and LLM-enhanced sections
- PAA extracts from both Yandex SERP blocks ("Частые вопросы" + "Похожие запросы")
- Batch Wordstat needs separate monthly dynamics table for proper querying/charting
- Lightweight TOP-10 crawler is intentionally separate from full site crawler

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 25-serp-aggregation-tools*
*Context gathered: 2026-04-10*
