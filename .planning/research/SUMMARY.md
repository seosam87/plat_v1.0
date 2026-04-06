# Project Research Summary

**Project:** SEO Management Platform v2.0 — SEO Insights & AI
**Domain:** Self-hosted SEO management for WordPress agencies (20–100 sites)
**Researched:** 2026-04-06
**Confidence:** HIGH

## Executive Summary

v2.0 is a data-activation milestone, not a data-collection one. The platform already holds positions, crawl snapshots, Metrika traffic, content audit results, gap analysis, and cannibalization data from v1.0. The entire v2.0 feature set converts that existing data into actionable surfaces: Quick Wins, Dead Content, Error Impact Scoring, Growth Opportunities, AI/GEO Readiness, Client PDFs, Keyword Suggest, LLM Briefs, 2FA, and In-App Notifications. Seven of nine feature groups require no new data sources — only new queries and new presentation layers over existing tables.

The recommended approach is additive extension of the existing 35K LOC FastAPI + Celery + PostgreSQL codebase. Four stack additions are needed (anthropic SDK, pyotp, qrcode, sse-starlette); the remaining capabilities are covered by the existing stack. Architecture changes are low-risk: mostly new service files and new router files, with a handful of nullable column additions to existing models. The three highest-risk changes are the `keyword_positions` DISTINCT ON query pattern (requires a `keyword_latest_positions` materialized table from day one), WeasyPrint memory management for PDF generation (requires subprocess-per-PDF isolation), and 2FA login flow changes (must be opt-in with nullable columns, never mandatory in the rollout migration).

The core risk in this milestone is performance, not correctness. All five analytical features (Quick Wins, Dead Content, Impact Scoring, Growth Opportunities, GEO Readiness) query across large, partitioned, or multi-joined tables. Each must be designed with caching or pre-computation from the start — retrofitting later at 100K keywords and 50 sites is a rewrite, not an optimization. If these patterns are established correctly in Phases 1 and 2, the remaining phases are straightforward extensions.

## Key Findings

### Recommended Stack

The v1.0 stack (Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, PostgreSQL 16, Redis 7, Celery 5.4, Playwright 1.47, HTMX 2.0, WeasyPrint 62) is fully validated and unchanged. v2.0 requires four additions:

**New libraries (v2.0 only):**
- `anthropic >= 0.89.0`: Official Anthropic SDK — use sync `Anthropic` client in Celery tasks, `AsyncAnthropic` + `EventSourceResponse` for streaming in FastAPI endpoints; never use `AsyncAnthropic` inside a standard Celery task without `asyncio.run()`
- `pyotp >= 2.9.0`: RFC 6238 TOTP for 2FA — de-facto Python standard, pure Python, no system deps
- `qrcode[pil] >= 8.2`: QR code generation for 2FA setup — `[pil]` extra required for PNG output; Pillow is already a transitive WeasyPrint dep
- `sse-starlette >= 3.3.3`: Production SSE for FastAPI — required only if real-time notification push is chosen over HTMX polling (architecture decision deferred to Phase 6)

**Not needed:** spaCy/NLP (GEO readiness is rule-based DOM inspection), openai SDK (Anthropic covers LLM), WebSockets (SSE or polling is sufficient), serpapi (free autocomplete endpoints work for internal tooling at this scale).

### Expected Features

**Must have (table stakes for v2.0):**
- Quick Wins page — positions 4–20 + missing optimizations, ranked by traffic impact
- Dead Content detection — zero traffic + no ranking for 90+ days + published 180+ days ago
- Error Impact Scoring — audit errors weighted by Metrika traffic percentile of affected pages
- Growth Opportunities — unified aggregation of gap keywords, lost positions, cannibalization
- AI/GEO Readiness checklist — schema, structure, E-E-A-T checks against existing crawl data
- Client Instructions PDF — non-technical, plain-language report for site owners
- Keyword Suggest — Google/Yandex autocomplete with Redis caching and rate limiting
- LLM Briefs (opt-in) — Anthropic-generated content briefs extending existing `ContentBrief` model
- 2FA (TOTP) — opt-in per user; no mandatory rollout
- In-App Notifications — bell icon with per-event notifications from Celery tasks

**Differentiators over competitors:**
- Traffic-weighted opportunity scoring (no competitor natively combines position + Metrika + audit data)
- Inline batch-fix actions that dispatch directly to existing WP content pipeline
- LLM brief generation from structured brief data (not raw HTML) — controlled cost, auditable prompts

**Defer to v3+:**
- White-label theming beyond logo field
- Real-time SERP feature detection (Perplexity/ChatGPT citation monitoring)
- Yandex Wordstat per-user OAuth setup (medium complexity, low priority)
- Backlink opportunity analysis (no backlink data in current stack)
- Auto-send reports without manager review (too risky)

### Architecture Approach

All nine features integrate as additive extensions to the existing architecture. No existing services are refactored; no existing models have destructive changes. The pattern is: new `routers/`, new `services/`, new `tasks/`, and nullable column additions via Alembic migrations. The most architecturally significant decision is whether in-app notifications use HTMX polling (30s interval, simpler) or SSE push via Redis pub/sub (real-time, requires `sse-starlette`). Architecture research recommends polling for this user scale (< 20 users), deferring SSE unless real-time delivery is explicitly required.

**Major components and responsibilities:**
1. `app/services/insights_service.py` (new) — cross-cutting Quick Wins / Dead Content / Opportunities queries joining positions + audit + Metrika
2. `app/services/impact_scoring_service.py` (new) — audit error prioritization; pre-computes to `error_impact_scores` table via Celery, never live per request
3. `app/services/suggest_service.py` (new) — keyword autocomplete fetching + Redis caching; external calls isolated in Celery tasks
4. `app/services/notification_service.py` (new) — single `emit()` entrypoint called from all Celery tasks; prevents scattered notification logic across 14 task files
5. `app/models/notification.py` (new) — notification storage with 30-day cleanup via Celery Beat
6. `app/routers/insights.py` (new) — `/insights/{site_id}/quick-wins`, `/dead-content`, `/impact-scores`, `/opportunities`
7. `AuditCheckDefinition` extension — `geo_*` check codes seeded via Alembic data migration; no schema change
8. `ContentBrief` model extension — nullable `llm_brief_text`, `llm_generated_at`, `llm_*_tokens` columns
9. `User` model extension — nullable `totp_secret` (Fernet-encrypted), `totp_enabled`, `totp_backup_codes`

**Critical architectural invariant:** `keyword_latest_positions` materialized table must be built in Phase 1. The existing `DISTINCT ON (keyword_id, engine) ORDER BY checked_at DESC` pattern degrades to 8–15 second full partition scans at 100K keywords x 12 months. This table is the foundation for Quick Wins, Dead Content, and Growth Opportunities.

### Critical Pitfalls

1. **URL mismatch ruins JOIN queries (Phase 1)** — `pages.url`, `metrika_traffic_pages.page_url`, and `keyword_positions.url` use different normalization (trailing slashes, http vs https, UTM params). JOINs silently return zero rows. Build `normalize_url()` utility and apply on write before any JOIN query is written. Test with 5 URL variants of the same page.

2. **DISTINCT ON on partitioned `keyword_positions` causes timeout at scale (Phase 1)** — Full partition scans at 100K keywords take 8–15 seconds. Create `keyword_latest_positions` flat table (one row per keyword+engine, updated after each position check) and query that instead. Add `WHERE checked_at >= now() - interval '90 days'` as minimum mitigation.

3. **WeasyPrint memory leak kills Celery workers (Phase 3)** — Each `write_pdf()` call adds 20–40 MB RSS that is never released (GitHub issues #2130, #1977). Run PDF generation in a subprocess per report, or set `--max-tasks-per-child=10` on the PDF worker. Never generate all client PDFs in a single long-running task.

4. **Keyword Suggest triggers IP ban within hours (Phase 4)** — Google and Yandex treat server-to-server autocomplete calls as scraping. Route through DataForSEO or XMLProxy (already in stack); cache all suggest results in Redis with 7-day TTL; apply `@limiter.limit("10/minute")` on the endpoint.

5. **LLM API failures must degrade gracefully (Phase 5)** — The template-based brief (already generated by `brief_service.py`) must always be returned, with LLM enhancement as an optional overlay. Implement a circuit breaker after 3 consecutive failures. Cap input at 2000 tokens and output at 800 tokens to prevent runaway cost.

6. **2FA migration locks out existing users (Phase 6)** — Add `totp_secret` as nullable with default NULL. Never make 2FA mandatory in the same migration that adds the column. Two-phase rollout: opt-in first, then optional forced enforcement later.

7. **Notifications table bloat (Phase 6)** — Soft-delete (mark-as-read) generates dead tuple churn that defeats PostgreSQL autovacuum. Use hard DELETE on dismiss, nightly cleanup task, and set `autovacuum_vacuum_scale_factor = 0.01` on the notifications table in the same migration that creates it.

## Implications for Roadmap

Based on research, features split into dependency tiers that suggest a natural phase order.

### Phase 1: Analytical Foundations (Quick Wins + Dead Content)

**Rationale:** Both features depend on the same infrastructure prerequisite — URL normalization and `keyword_latest_positions` materialized table. Building both together amortizes the setup cost. These are the highest-value, lowest-complexity features (pure SQL over existing data). They demonstrate v2.0 value immediately.

**Delivers:** Quick Wins page, Dead Content page, `normalize_url()` utility, `keyword_latest_positions` table, `insights_service.py` foundation, `routers/insights.py`

**Addresses:** Feature Groups 1 and 2 from FEATURES.md

**Avoids:** URL mismatch pitfall and DISTINCT ON partition scan pitfall — both must be addressed before any JOIN query is written

**Research flag:** Standard patterns — skip phase research. Pure SQL analytics, well-understood PostgreSQL optimization.

### Phase 2: Impact Scoring + Growth Opportunities

**Rationale:** Depends on Phase 1 infrastructure (`normalize_url`, `keyword_latest_positions`, `insights_service.py`). Both features add aggregation layers over existing data. Impact Scoring requires the `error_impact_scores` pre-computation table and Celery trigger hooks. Growth Opportunities reuses Phase 1's `insights_service.py`.

**Delivers:** Error Impact Scoring (pre-computed, Celery-triggered), Growth Opportunities page, `impact_scoring_service.py`, `opportunities_service.py`

**Addresses:** Feature Groups 3 and 4 from FEATURES.md

**Avoids:** Live aggregation performance trap — `error_impact_scores` must be pre-computed from day one

**Research flag:** Standard patterns — skip phase research.

### Phase 3: Client PDF Reports

**Rationale:** Depends on existing `report_service.py` and WeasyPrint (already working for internal reports). Largely self-contained — new Jinja2 template + one new aggregation function. Isolated early because it has its own critical pitfall (WeasyPrint OOM) that must be solved in isolation before it contaminates the PDF worker shared with existing reports.

**Delivers:** Client Instructions PDF template, `client_report_data()` aggregator, `GET /reports/{site_id}/client-instructions/pdf`, subprocess-isolated PDF generation

**Addresses:** Feature Group 6 from FEATURES.md

**Avoids:** WeasyPrint OOM by establishing subprocess-per-PDF pattern before any PDF code is written

**Research flag:** Standard patterns — skip phase research.

### Phase 4: Keyword Suggest

**Rationale:** Externally-dependent feature with its own risk profile (IP bans, rate limits). Isolated in its own phase so its failure modes do not block other work. Requires new `suggest_service.py` and `suggest_tasks.py` but no changes to existing services.

**Delivers:** Keyword suggest UI (inline in keyword add flow), `suggest_service.py`, `suggest_tasks.py`, Redis suggest cache, rate limiting on suggest endpoint

**Addresses:** Feature Group 7 from FEATURES.md

**Avoids:** IP ban pitfall — cache-first + proxy routing must be the first design decision

**Research flag:** May benefit from research into XMLProxy suggest endpoint availability before implementation begins.

### Phase 5: LLM Briefs + AI/GEO Readiness

**Rationale:** These two features share the same dependency (existing crawl + content audit data) and the same architectural pattern (extend existing services, add new detection functions). LLM Briefs extend `ContentBrief` + `brief_service.py`. GEO Readiness extends `AuditCheckDefinition` + `content_audit_service.py`. Grouped together as the "AI features" phase with `anthropic` SDK introduction.

**Delivers:** LLM-generated brief enhancement (opt-in), `generate_llm_brief` Celery task, GEO Readiness checklist (6 new `geo_*` audit check codes), `anthropic` SDK integration, graceful fallback to template brief

**Addresses:** Feature Groups 5 and 8 from FEATURES.md

**Avoids:** LLM failure blocking brief delivery — template brief is always the base; LLM is enhancement only. Token cap enforced at 2000 input / 800 output.

**Research flag:** Standard patterns for GEO checks. LLM integration patterns documented in STACK.md. No additional research needed.

### Phase 6: Security Hardening (2FA + Notifications)

**Rationale:** Both features touch the auth layer and global UI chrome (header). Grouped together as they share Alembic migrations on the `users` table and require careful regression testing of the login flow. Notifications are prerequisite for 2FA (users need a channel to confirm setup completion).

**Delivers:** TOTP 2FA (opt-in enrollment, backup codes, admin reset endpoint), In-App Notification bell (HTMX polling, 30s interval), nightly notification cleanup task, `notification_service.py`, `routers/security.py`, user model columns for TOTP

**Addresses:** Feature Groups 9 and 10 from FEATURES.md

**Avoids:** 2FA lockout (nullable columns, opt-in only); notification table bloat (hard delete + nightly cleanup + autovacuum tuning in same migration)

**Research flag:** 2FA auth flow changes are the highest-risk code changes in this milestone. Write the 4-path test matrix (no 2FA / 2FA correct / 2FA wrong / recovery code) before any auth code changes. Run `alembic upgrade --sql` and review output before applying migration.

### Phase Ordering Rationale

- Phases 1–2 establish the URL normalization and `keyword_latest_positions` infrastructure that all other analytical queries depend on
- Phase 3 (PDF) isolated early because its OOM pitfall is self-contained and the subprocess pattern established here protects all future PDF work
- Phase 4 (Suggest) isolated because IP ban risk is entirely separate from other work and should not block analytical features
- Phase 5 (AI) after core analytics because LLM briefs extend `ContentBrief` (existing) and GEO checks extend `AuditCheckDefinition` (existing) — these integrations are cleaner after the analytical layer is stable
- Phase 6 (Security) last because it touches the most sensitive existing code (auth) and benefits from having all feature surfaces finalized before adding security controls to them

### Research Flags

**Needs `/gsd:research-phase` before planning:**
- Phase 4: XMLProxy suggest endpoint availability — determine before designing the routing strategy
- Phase 6: Write test matrix for 2FA auth flow changes before any implementation

**Standard patterns (skip research-phase):**
- Phase 1: PostgreSQL window functions, HTMX partial tables — well-documented
- Phase 2: Celery task triggers and Redis caching — established project patterns
- Phase 3: WeasyPrint subprocess isolation — solution documented in PITFALLS.md
- Phase 5: Anthropic SDK sync/async patterns — fully documented in STACK.md

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing stack is production-validated; 4 new additions confirmed with version compatibility matrix |
| Features | HIGH | Based on competitor analysis of Sitebulb, Ahrefs, SE Ranking, SEMrush + direct knowledge of v1.0 feature set |
| Architecture | HIGH | Based on direct codebase inspection (35,402 LOC); all integration points identified with specific file paths and model field names |
| Pitfalls | HIGH | All critical pitfalls grounded in specific existing codebase patterns; WeasyPrint pitfall backed by confirmed GitHub issue numbers |

**Overall confidence:** HIGH

### Gaps to Address

- **XMLProxy suggest endpoint:** PITFALLS.md flags that XMLProxy may support Yandex suggest (reducing IP ban risk) but this is unconfirmed. Verify `xmlproxy_service.py` endpoint list before finalizing Phase 4 design. If unavailable, fallback is DataForSEO keyword suggestions (already integrated).

- **Notifications polling vs SSE decision:** Architecture research recommends HTMX polling (30s) over Redis pub/sub SSE for this user scale. Validate with user before Phase 6 planning — if real-time delivery is required, `sse-starlette` is already in the stack additions and the SSE pattern is documented in STACK.md.

- **LLM model selection:** STACK.md uses `claude-3-5-haiku-20241022` as the default brief model; ARCHITECTURE.md references `claude-opus-4-6`. Confirm before Phase 5 — Haiku is 10-20x cheaper and appropriate for structured brief generation; Opus is higher quality but cost-prohibitive for batch runs across 50 sites.

- **Alembic head management:** With 9 features across 6 phases, each adding at least one migration, there is risk of multiple heads if phases are executed with parallel tasks. Enforce single-head constraint in CI (`alembic heads` must return exactly 1) from Phase 1 onwards.

## Sources

### Primary (HIGH confidence)

- Existing codebase direct inspection — `app/models/`, `app/services/`, `app/tasks/`, `app/routers/` (35,402 LOC)
- Anthropic Python SDK GitHub (anthropics/anthropic-sdk-python) v0.89.0, April 3, 2026
- pyotp PyPI v2.9.0 documentation
- sse-starlette v3.3.3 (March 2026)
- WeasyPrint GitHub issues #2130, #1977 (confirmed memory leak, native C heap not freed)
- PostgreSQL DISTINCT ON partition performance: CYBERTEC blog, TigerData blog

### Secondary (MEDIUM confidence)

- Competitor analysis: Sitebulb, Screaming Frog, SE Ranking, Ahrefs, SEMrush feature sets (knowledge base through Aug 2025)
- GEO/AI readiness signals: Onely, Frase, SearchEngineLand 2025–2026 (FAQPage 3.2x citation lift is industry data, not Google-confirmed)
- Google Autocomplete undocumented endpoint stability — confirmed stable for internal tooling at low volume; IP ban threshold undefined

### Tertiary (LOW confidence)

- Yandex Wordstat OAuth token setup complexity — described as MEDIUM but not directly tested in this codebase
- Chart rendering strategy for WeasyPrint client PDFs — SVG vs Chart.js server-side both viable; final approach depends on implementation testing

---
*Research completed: 2026-04-06*
*Ready for roadmap: yes*
