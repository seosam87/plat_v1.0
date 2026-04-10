# Phase 25: SERP Aggregation Tools - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 25-serp-aggregation-tools
**Areas discussed:** Copywriting Brief Architecture, Playwright Crawling, PAA Parser, Batch Wordstat

---

## Copywriting Brief Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Separate tool | New model + service independent from LLM Brief | |
| Extend LLM Brief | Merge into existing brief_service.py + llm_brief_job.py | :heavy_check_mark: |

**User's choice:** Extend existing LLM Brief — single tool
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Celery chain (4 steps) | XMLProxy -> Playwright -> aggregation -> save as separate tasks | :heavy_check_mark: |
| Single task with stages | One Celery task doing all steps sequentially | |

**User's choice:** Celery chain
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| XLSX export | Excel download | :heavy_check_mark: |
| On-page render | Sections displayed in browser | |
| Both | Page view + XLSX download | |

**User's choice:** XLSX only
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Landing URL required | User must specify target page URL | |
| Landing URL optional | Only phrases + region required | :heavy_check_mark: |

**User's choice:** Landing page URL not required
**Notes:** None

---

## Playwright Crawling

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse crawler_service | Full audit-level crawler for TOP-10 pages | |
| Lightweight crawler | Extract only text, H2, highlights — new service | :heavy_check_mark: |

**User's choice:** Separate lightweight crawler
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Skip and continue | Failed pages silently skipped, job completes | :heavy_check_mark: |
| Mark as partial | Job gets "partial" status on failures | |

**User's choice:** Skip and continue
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| XMLProxy for SERP HTML | No Playwright needed for PAA | :heavy_check_mark: |
| Playwright SERP rendering | JS-render for nested question expansion | |

**User's choice:** XMLProxy
**Notes:** None

---

## PAA Parser

| Option | Description | Selected |
|--------|-------------|----------|
| First level only | Extract visible questions, no expansion | :heavy_check_mark: |
| Recursive expansion | Click each question for nested follow-ups | |

**User's choice:** First level only
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Flat table | PAAResult rows: phrase/question/level | :heavy_check_mark: |
| JSON tree | Nested structure in single JSON field | |

**User's choice:** Flat table
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Both blocks | "Частые вопросы" + "Похожие запросы" | :heavy_check_mark: |
| Only "Частые вопросы" | Main PAA block | |

**User's choice:** Both blocks
**Notes:** None

---

## Batch Wordstat

| Option | Description | Selected |
|--------|-------------|----------|
| Separate service | New batch_wordstat_service.py | :heavy_check_mark: |
| Extend existing | Add batch methods to wordstat_service.py | |

**User's choice:** Separate service
**Notes:** Different concerns: batch 1000 vs single-phrase lookup

| Option | Description | Selected |
|--------|-------------|----------|
| % via HTMX polling | Same polling pattern with progress percentage | :heavy_check_mark: |
| Detailed progress bar | Custom progress component | |

**User's choice:** HTMX polling with percentage
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Separate table | WordstatMonthlyData with result_id FK | :heavy_check_mark: |
| JSON field | Monthly data as JSON in WordstatBatchResult | |

**User's choice:** Separate table
**Notes:** None

---

## Claude's Discretion

- Celery chain error handling strategy
- XLSX layout for Copywriting Brief
- LLM Brief model extension approach
- XMLProxy rate limiting coordination

## Deferred Ideas

None
