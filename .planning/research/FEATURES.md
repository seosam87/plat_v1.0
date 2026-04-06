# Feature Research — v2.0 SEO Insights & AI

**Domain:** SEO Management Platform (self-hosted, agency, 20–100 WordPress sites)
**Researched:** 2026-04-06
**Confidence:** HIGH — based on competitor analysis (Sitebulb, Screaming Frog, Ahrefs, SE Ranking, SEMrush), ecosystem search 2025–2026, and direct knowledge of existing v1.0 codebase.
**Scope:** v2.0 milestone only. v1.0 features already built are noted as dependencies, not re-researched.

---

## Executive Summary

v2.0 converts the data v1.0 collects into actionable insights. The platform already has positions, crawl snapshots, keywords, Metrika, content audit, gap analysis, and cannibalization. v2.0 surfaces what to do with that data: quick wins queue, dead content list, error impact scoring, growth opportunity aggregation, GEO/AI readiness checklist, client-facing PDF reports, keyword suggestions, LLM-generated briefs, and security hardening (2FA + notifications).

The nine feature groups split into two tiers:
- **Analytical surfaces (1–5):** Pure SQL/Python logic over existing tables. Fast to build, high signal value.
- **New capabilities (6–9):** Require new external integrations or new UI patterns. Moderately complex.

---

## Feature Group 1: Quick Wins Page

### What It Is

A ranked list of pages that have the highest probability of position improvement with low-effort SEO fixes. The signal set is: position 4–20 (ranking but not top-3) + at least one missing optimization (no TOC, no schema, missing meta description, thin internal links, title length issues).

### How Competitors Present It

**Sitebulb:** Uses "Hints" — 300+ checks, sorted by severity, each with "what / why / how to fix." Colour-coded priority (critical = red, warnings = amber, notices = blue). Users click a Hint to see all affected URLs. This is the gold standard UI pattern for quick wins. Crucially, Sitebulb does NOT combine position data with its hints — it is crawl-only.

**Screaming Frog:** Raw tabular data. No prioritization narrative. Users must export and cross-reference positions themselves. Widely criticized for requiring expert interpretation.

**SE Ranking / Ahrefs:** On-page checker scores each URL 0–100. Ahrefs highlights "positions 11–20 with CTR below site average" as an explicit opportunity signal. SE Ranking's Marketing Plan generates a checklist per site but doesn't rank items by traffic impact.

**Our advantage:** We have positions, Metrika traffic, crawl data, and content audit results in one database. Combining them to rank opportunities by traffic impact is something none of these tools do natively for the WP-agency workflow.

### Table Stakes for This Feature

| Signal | Why Expected | Existing Data Source |
|--------|--------------|---------------------|
| Position 4–20 filter | Universal "low-hanging fruit" framing in all SEO tools | `keyword_positions` table |
| Missing TOC flag | Already detected in content audit | `content_audit` table |
| Missing schema flag | Already detected in content audit | `content_audit` table |
| Missing meta description | Crawl captures this | `crawl_pages` table |
| Thin title (too short/long) | Standard audit check | `crawl_pages` table |
| Page traffic (for sorting) | Metrika visits/sessions per URL | `metrika_pageviews` table |
| Batch fix action | "Fix all" button is table stakes in 2026 | Existing WP content pipeline |

### Differentiators

| Signal | Value | Notes |
|--------|-------|-------|
| Opportunity score = position × traffic weight | Prioritizes pages where a small rank jump means real traffic gain | Requires formula: score = (21 - position) × avg_weekly_sessions |
| Inline fix triggers | Click "Add TOC" inline, not navigate to pipeline | HTMX partial swap over existing pipeline endpoint |
| Filter by site / date / issue type | Power user control | Simple query parameters |
| "Already has fix in pipeline" indicator | Prevent duplicate work | Join against `content_pipeline` table |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Showing ALL audit issues | Defeats the purpose; use the existing content audit page for that |
| Auto-fixing without user confirmation | Violates the existing diff-approval safety contract |
| Position 1–3 in quick wins | These pages don't need fixing — filter out |

### Dependencies on Existing Data

- `keyword_positions` (partitioned monthly) — positions 4–20 filter
- `content_audit` — TOC/schema/internal link status per page
- `crawl_pages` — meta description, title length, canonical
- `metrika_pageviews` — traffic weight for scoring
- `content_pipeline` — "in progress" status to avoid duplicate queuing

### Complexity: LOW-MEDIUM

Pure SQL aggregation + Jinja2 table. The "batch fix" action reuses existing pipeline endpoints. Estimated: 2–3 days implementation.

---

## Feature Group 2: Dead Content Detection

### What It Is

Pages with zero or near-zero traffic over a configurable window (default: 90 days) AND declining or absent positions. These pages consume crawl budget, dilute PageRank, and represent either pruning candidates or refresh opportunities.

### How Competitors Define "Dead"

**Ahrefs / SEMrush content audit:** Combine organic traffic + organic sessions. A page is "underperforming" if it receives < X clicks/month from organic. They recommend: refresh, consolidate, or prune.

**Screaming Frog:** No built-in dead content concept. Users must export URLs and cross-reference with GA/GSC.

**Clearscope / ContentKing:** Content decay = gradual CTR/click decline over 3–6 months. They track "first seen below threshold" date.

**Industry consensus (2025):** "Dead" requires multiple signals — a page with zero traffic but high conversion (product landing page) is not dead. The definition must combine traffic + positions + page type.

### Recommended Scoring Model

A page is dead if ALL of:
1. Zero Metrika sessions in the last 90 days (configurable)
2. No tracked keyword ranking in positions 1–50 (or all tracked keywords dropped out of top 50)
3. Published more than 180 days ago (to exclude new content)

Optionally: declining trend = positions dropped > 10 places in last 60 days.

### Table Stakes

| Metric | Source | Notes |
|--------|--------|-------|
| Sessions = 0 last N days | `metrika_pageviews` | Configurable window |
| No position in top 50 | `keyword_positions` | Aggregated per URL |
| Page age > 180 days | `crawl_pages.first_seen` | Exclude new content |
| Page type (blog/landing/product) | `content_audit.page_type` | Weight differently by type |

### Differentiators

| Feature | Value |
|---------|-------|
| "Action" column: Refresh / Consolidate / Prune | Reduce decision friction for the analyst |
| Merge suggestion: "Similar to [other URL]" | Detect consolidation candidates using title + keyword overlap |
| "Last meaningful traffic" date | More useful than "zero traffic" — shows how long it's been dead |
| Batch noindex action | For pages decided as prunable; triggers task creation |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Auto-pruning (noindexing) without review | High-risk irreversible action; must require manual confirmation |
| Treating 404 pages as "dead content" | Those belong in the crawl error queue, not dead content |
| Ignoring page type context | A "Contact" page with zero organic traffic is NOT dead |

### Dependencies

- `metrika_pageviews` — traffic per URL
- `keyword_positions` — position history per URL
- `crawl_pages` — URL inventory, first_seen, page_type
- `content_audit` — page type classification

### Complexity: LOW

Mostly a SQL query with configurable thresholds. UI is a sortable table with action column. Estimated: 1–2 days.

---

## Feature Group 3: Error Impact Scoring

### What It Is

A prioritized queue of SEO errors where each error is weighted by the traffic/potential of the affected page. "Missing meta description on 10 pages" means different things if those 10 pages are your top-traffic URLs vs. uncrawled orphan pages.

### How Competitors Handle It

**Screaming Frog / Sitebulb:** Pure error counts, no traffic weighting. Sitebulb at least sorts by severity (critical > warning > notice) but all pages of the same error type are equal.

**SEMrush Site Audit:** Score 0–100 based on error count and type. Traffic weighting is not native — users manually cross-reference with Position Tracking.

**Ahrefs Site Audit:** Similar. Error list with severity levels. No traffic weight.

**Industry gap:** No mainstream tool natively combines crawl errors with traffic data for prioritization. This is genuinely differentiated.

### Recommended Scoring Formula

```
impact_score = severity_weight × page_traffic_percentile
```

Where:
- `severity_weight`: Critical=3, Warning=2, Notice=1
- `page_traffic_percentile`: Metrika sessions for URL normalized 0–1 across site

Result: A critical error on a page in the top 10% of site traffic scores 3.0. A notice on a zero-traffic page scores 0.0.

### Error Categories (from existing crawl + audit data)

| Error Type | Severity | Source Table |
|------------|----------|-------------|
| 404 broken links (inbound) | Critical | `crawl_pages` |
| Noindex on indexed page | Critical | `crawl_pages` |
| Duplicate title/meta | Warning | `crawl_pages` |
| Missing meta description | Warning | `crawl_pages` |
| Missing H1 or duplicate H1 | Warning | `crawl_pages` |
| Missing schema (where expected) | Warning | `content_audit` |
| Missing TOC (where expected) | Notice | `content_audit` |
| Thin content (< 300 words) | Notice | `crawl_pages` |
| Canonical mismatch | Warning | `crawl_pages` |
| Slow page (from Metrika bounce/time data) | Notice | `metrika_pageviews` |

### Table Stakes

| Feature | Notes |
|---------|-------|
| Combined error + traffic table | The core value — must be on first view |
| Sort by impact score | Default sort |
| Filter by error type, severity, site | Standard controls |
| "Fix" action linking to appropriate workflow | 404 → crawl tasks; meta → content pipeline |

### Differentiators

| Feature | Value |
|---------|-------|
| Traffic tier badges on rows (Top 10%, Top 25%, etc.) | Visual context without requiring users to calculate |
| "Expected traffic gain" estimate | Show: if you fix meta + schema on page X, estimated +N sessions/month based on CTR improvement models |
| Error trend: new vs. existing | Flag errors that appeared since last crawl vs. long-standing issues |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Scoring formula too complex to explain | Users won't trust a black box; show the formula |
| Mixing crawl errors with position opportunities | These are different queues; keep them separate |

### Dependencies

- `crawl_pages` — all error types
- `content_audit` — schema/TOC status
- `metrika_pageviews` — traffic weight
- `keyword_positions` — positions for CTR model

### Complexity: LOW-MEDIUM

SQL aggregation with scoring formula. New table or materialized view: `error_impact_scores`. Estimated: 2 days.

---

## Feature Group 4: Growth Opportunities

### What It Is

An aggregated view of "where this site can grow organically." Combines three existing signals that are currently surfaced in separate pages:
1. **Gap keywords** — keywords site doesn't rank for but competitors do (from gap analysis)
2. **Lost positions** — keywords that dropped in the last 30/60/90 days
3. **Cannibalization candidates** — keywords with multiple ranking URLs eating each other

Currently these live in separate pages (Gap Analysis, Position Tracking filters, Cannibalization Detector). Growth Opportunities consolidates them into a single prioritized list.

### How Competitors Handle It

**Ahrefs Opportunities:** "Positions 11–20 for keywords you already rank" + keyword gap against specified competitors. Separate tabs, not unified scoring.

**SEMrush Keyword Gap + Position Changes:** Similarly siloed — gap analysis and position changes are different tools.

**SE Ranking:** Has a "Marketing Plan" that generates checklist items from multiple signals but it's audit-style (text steps), not a data-driven ranked list.

**Our advantage:** We already have all three signal sources. The work is aggregation and unified presentation, not new data collection.

### Recommended Signal Aggregation

| Signal | Source | Score Weight |
|--------|--------|-------------|
| Keyword gap (competitor ranks, we don't) | `gap_analysis` table | Volume × gap_score |
| Position 11–20 (ranking, not page 1) | `keyword_positions` | Volume × (21 - position) |
| Position dropped > 5 in 30 days | `keyword_positions` delta | Volume × drop_magnitude |
| Cannibalization pair | `cannibalization` table | Combined traffic of both pages |
| Missing featured snippet (answer-box) | `keyword_positions.serp_features` | Volume × 0.5 (lower confidence) |

### Table Stakes

| Feature | Notes |
|---------|-------|
| Unified list sorted by opportunity score | Headline feature |
| Type badge (Gap / Lost / Cannibalization) | Visual signal type differentiation |
| One-click: "Create task for this opportunity" | Converts insight to action |
| Filter by site, signal type, keyword volume | Standard controls |

### Differentiators

| Feature | Value |
|---------|-------|
| "Effort" classification: Quick / Medium / Major | Gap keyword = Major (need new content); Position 11-20 = Quick (needs on-page tweak); Cannibalization = Medium (URL consolidation or redirect) |
| Trend arrow on lost positions | Was it 1 drop or a sustained slide? |
| Link to relevant tool for each type | Lost position → Position Tracker; Cannibalization → Cannibalization Detector; Gap → Content Plan |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Duplicating gap analysis or cannibalization pages | This is a summary/aggregator, not a replacement |
| Including backlink opportunities | We don't have backlink data; don't fake it |

### Dependencies

- `keyword_positions` — positions + history
- `gap_analysis` table (v1.0)
- `cannibalization` table (v1.0)
- `keywords` — volume data

### Complexity: MEDIUM

Requires a new aggregation query joining three existing tables with scoring formula. UI is a table with type badges and action buttons. Estimated: 2–3 days.

---

## Feature Group 5: AI/GEO Readiness Checklist

### What It Is

A per-page and per-site checklist assessing how well content is optimized for AI-powered search engines (Google AI Overviews, Perplexity, ChatGPT Search, Yandex AI). GEO = Generative Engine Optimization.

### What GEO Readiness Means in 2026 (Research Verified)

Based on multiple authoritative sources (Onely, Frase, Geoptie, SearchEngineLand 2025-2026):

**Confirmed signals that increase AI citation probability:**
- FAQPage schema markup — pages with FAQPage markup are 3.2× more likely to appear in Google AI Overviews (MEDIUM confidence — industry data, not Google-confirmed)
- Answer-first structure — question in H2, direct 2–4 sentence answer immediately following, no preamble
- Article/Organization/Author schema — establishes E-E-A-T identity
- Author bio section with credentials/credentials (E-E-A-T)
- Structured data coverage: at minimum Article + BreadcrumbList + FAQPage
- Content under 600 words that directly answers a single question (for featured snippet / AI snippet targeting)
- HowTo schema for procedural content
- Clear H1/H2/H3 hierarchy that mirrors question→answer structure
- Canonical URL (no duplicate content risk for AI crawlers)

**Signals that are widely cited but less confirmed:**
- Citation of authoritative external sources
- "Last updated" date visible to users (freshness signal)
- Original data or statistics on the page

### Checklist Items by Category

| Category | Check | Source | Confidence |
|----------|-------|--------|------------|
| Schema | FAQPage schema present | `content_audit.schema_types` | HIGH |
| Schema | Article/BlogPosting schema | `content_audit.schema_types` | HIGH |
| Schema | Author schema or Organization | `content_audit.schema_types` | HIGH |
| Schema | BreadcrumbList schema | `content_audit.schema_types` | HIGH |
| Structure | H2 headings that are questions | `crawl_pages.headings` (detect `?`) | MEDIUM |
| Structure | H1 present and unique | `crawl_pages` | HIGH |
| Content | FAQ section present (question+answer pairs) | Text analysis of crawled content | MEDIUM |
| E-E-A-T | Author byline on page | `crawl_pages` (meta author or byline element) | MEDIUM |
| E-E-A-T | "Last updated" date visible | `crawl_pages` (dateModified in schema or visible) | MEDIUM |
| Technical | Canonical set | `crawl_pages.canonical` | HIGH |
| Technical | Page indexed (not noindex) | `crawl_pages.noindex` | HIGH |
| Content | Word count 300–2000 (optimal range) | `crawl_pages.word_count` | LOW |

### Table Stakes

| Feature | Notes |
|---------|-------|
| Score 0–100 per page | Percentage of checks passing |
| Site-level aggregate GEO score | Average or median across pages |
| Grouped by check category (Schema / Structure / E-E-A-T / Technical) | Standard audit grouping |
| "Fix" links to appropriate pipeline action | Schema missing → WP content pipeline |

### Differentiators

| Feature | Value |
|---------|-------|
| Per-content-type thresholds | Blog post GEO requirements differ from product/service pages |
| "AI snippet detected" flag | If Yandex or Google is already pulling an AI snippet from this page, show it |
| GEO trend over time | Did GEO score improve after last pipeline run? |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Claiming to predict AI citation | No tool can reliably do this; present as "readiness signals," not guarantees |
| Requiring new data sources | All checks should use existing crawl + content audit data |
| Checking for Perplexity/ChatGPT citations in real-time | Rate-limited, fragile, slow; out of scope |

### Dependencies

- `content_audit` — schema types, TOC, structure signals
- `crawl_pages` — H1/H2 headings, canonical, noindex, word_count
- No new data required — checklist is computed from existing crawl data

### Complexity: LOW-MEDIUM

Checklist computation is pure Python/SQL against existing data. UI is a scored checklist. The FAQ section detection (parsing crawled HTML for question patterns) is the only mildly complex check. Estimated: 2–3 days.

---

## Feature Group 6: Client Instructions PDF

### What It Is

A generated PDF document for the site owner (not the SEO manager) explaining what SEO work was done, what was found, and what actions they should take. Different from the existing internal PDF reports — these are client-facing, plain-language, and action-oriented.

### What Makes a Good Client SEO Report (Research Verified)

Based on SEOptimer, Databox, Reportr, ReportGarden 2025:

**Structure (consensus across sources):**
1. Executive summary: 3–5 bullet points of the most important findings
2. Positions section: where you rank, changes since last report, top movers
3. Traffic section: sessions, top pages, trend (from Metrika)
4. Technical health: critical errors count and status
5. Work done this period: tasks completed, content pipeline runs
6. Recommended actions: top 3 things the client should do or approve
7. Next period plan: what the agency will do next

**Language guidelines:**
- No jargon: "search engine positions" not "SERP rankings"; "website errors" not "crawl errors"
- Explain every number: "Your site appeared X times in search results" not "X impressions"
- Max 9 metrics per report (industry best practice — cognitive load threshold)
- Each finding paired with an action
- Avoid automated reports without human annotation — always include a "Summary note" field the manager fills in

**Format:**
- PDF with site logo
- 2–4 pages optimal for client attention
- Visualizations: position trend chart (Chart.js → PNG via WeasyPrint), traffic chart
- Russian-language primary (team context); bilingual toggle is a future nice-to-have

### Table Stakes

| Feature | Notes |
|---------|-------|
| Predefined section template (per above) | Jinja2 template rendered to WeasyPrint PDF |
| Manager annotation field | Free-text "Summary note" per section |
| Logo field (per site) | Already exists in site management |
| Date range selector | Monthly default |
| Position trend chart image | Chart.js renders server-side or SVG in WeasyPrint |
| Delivery via Telegram/email | Reuse existing delivery infrastructure |

### Differentiators

| Feature | Value |
|---------|-------|
| "Traffic change explained in plain Russian" block | Auto-generated sentence: "Your site received N visits this month, which is X% more/less than last month" |
| Quick wins carried into report | "We found 5 pages that could be improved easily — see page 3" |
| WP pipeline actions included | "We added table of contents to 12 articles; here's what changed" |
| "Approve actions" section | Client can see what's pending their approval; reduces email back-and-forth |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Full technical audit dump | Clients don't understand it; creates support burden |
| All keywords listed | Pick top 10–20 by traffic; rest goes in appendix or separate internal report |
| Auto-send without manager review | Dangerous; a bad month needs human framing first |
| White-label theming system | Full theming is out of scope (v1.0 decision); logo field is sufficient |

### Dependencies

- `keyword_positions` — position data
- `metrika_pageviews` — traffic data
- `crawl_pages` — error counts
- `tasks` / `projects` — work done this period
- `content_pipeline` — pipeline runs
- `sites.logo_url` — client branding
- WeasyPrint (already in stack)

### Complexity: MEDIUM

New Jinja2 template + manager annotation form + PDF generation endpoint. Chart rendering to images for WeasyPrint is the trickiest part (needs Chart.js server-side or SVG charts). Estimated: 3–4 days.

---

## Feature Group 7: Keyword Suggest

### What It Is

Given a seed keyword or URL, return suggested related keywords from Google Autocomplete, Yandex Suggest, and optionally Yandex Wordstat. Users can select suggestions and add them to the keyword tracking list.

### API Options (Research Verified)

**Google Suggest (Autocomplete):**
- URL: `https://suggestqueries.google.com/complete/search?output=json&q={query}&hl=ru`
- No API key required (undocumented but stable)
- Returns 10 suggestions per query
- For more coverage: alphabet soup method — append a–z to seed keyword and collect all variations
- Rate limit: informal; 1 req/sec is safe; use asyncio for parallel letters
- Returns JSON with suggestions list

**Yandex Suggest:**
- URL: `https://suggest.yandex.ru/suggest-ya.cgi?v=4&part={query}&uil=ru`
- No API key required
- Returns similar autocomplete suggestions
- Yandex-specific; essential for RU-market keywords

**Yandex Wordstat API:**
- Official REST API at `https://api.wordstat.yandex.net`
- Requires OAuth token (Yandex Direct account + API access request to Yandex support)
- Returns search frequency data for phrases
- Rate limited by quota; HTTP 429 on excess
- Best for volume data on specific keywords, not broad discovery
- Authentication complexity: MEDIUM (OAuth token, not trivial to set up per-user)

**DataForSEO Keywords Suggestions:**
- `/dataforseo_labs/google/keyword_suggestions/live` endpoint
- Already in stack; returns volume, CPC, difficulty alongside suggestions
- More reliable than scraping Google Suggest; costs per request
- Recommended for enrichment after initial suggestions collected

### Recommended Implementation

1. Primary discovery: Google Suggest + Yandex Suggest (no auth, fast, covers 90% of use cases)
2. Alphabet soup expansion: async parallel requests for "{seed} a", "{seed} b", etc.
3. Deduplication + frequency ranking by appearance count across alphabet
4. Optional enrichment: DataForSEO for volume/difficulty on selected keywords
5. Yandex Wordstat: integrate only if user has token configured; show as "optional enrichment"

### Table Stakes

| Feature | Notes |
|---------|-------|
| Input: seed keyword | Free text |
| Input: target engine (Google / Yandex / Both) | Default: Yandex (project constraint) |
| Suggestions list with "Add to tracking" checkbox | Core action |
| Deduplicated results | Avoid noise |
| Async fetch with loading indicator | HTMX + Celery or inline async |

### Differentiators

| Feature | Value |
|---------|-------|
| Alphabet soup auto-expansion toggle | Generates 200+ suggestions from a single seed |
| Volume enrichment via DataForSEO (opt-in) | Adds volume/difficulty to suggestions before adding to tracking |
| "Already tracked" indicator | Shows if a suggestion is already in the keyword DB for this site |
| Input: URL → extract keywords from page content | Seed from existing content, not just manual input |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Yandex Wordstat as required integration | OAuth setup is a barrier; make it opt-in |
| Building a keyword database/index | We collect keywords from external sources, not our own index |
| Bulk add without volume check | Users will add 500 keywords they'll never use; encourage selection |

### Dependencies

- `keywords` table — for "already tracked" check and adding new keywords
- `sites` — for region/language context
- External: Google Suggest API (no auth), Yandex Suggest API (no auth)
- Optional external: DataForSEO (already configured), Yandex Wordstat (OAuth required)

### Complexity: MEDIUM

Two undocumented APIs (Google + Yandex Suggest) + async parallelism for alphabet soup + optional DataForSEO enrichment. The main risk is rate limiting on Suggest APIs — implement backoff. Estimated: 3 days.

---

## Feature Group 8: LLM Briefs

### What It Is

AI-generated content briefs using an LLM (Claude API or OpenAI API) as an opt-in enhancement to the existing template-based brief system. The existing briefs are template-generated (H1–H3 structure + keywords). LLM Briefs add: competitive angle, differentiated angle suggestions, opening paragraph draft, FAQ suggestions for GEO.

### Why This Is Now Feasible

v1.0 deliberately deferred LLM integration ("deterministic output preferred"). v2.0 context: the platform now has rich data (positions, gap keywords, competitor signals, content audit results, Metrika traffic). Passing this context to an LLM produces significantly better briefs than prompting a blank LLM manually. The work is context assembly, not prompt magic.

### What Context to Pass

Based on SEO brief generation patterns (research 2025):

```
System: You are a senior SEO content strategist for a Russian-language website in the {niche} space.

Context provided:
- Target keyword: {primary_keyword} (Yandex position: {position}, search volume: {volume})
- Secondary keywords from cluster: {keyword_cluster}
- Gap keywords (competitors rank, we don't): {gap_keywords}
- Current page URL (if refresh brief): {url}
- Current page title and H1: {title}, {h1}
- Cannibalization risk: {cannibal_url} also ranks for this keyword
- Top 3 Yandex results for this keyword: {serp_titles}
- GEO readiness score: {geo_score}/100 (missing: {missing_checks})
- Metrika sessions last 30 days: {sessions}

Generate:
1. Recommended H1 (2 variants)
2. Meta description (155 chars)
3. Article structure (H2/H3 outline, 6-8 sections)
4. 3 FAQ questions with short answers (for FAQPage schema)
5. Differentiating angle (what this article should say that the top 3 don't)
6. Suggested internal links (from: {top_internal_link_candidates})
```

### API Integration Pattern

- Model: Claude 3.5 Haiku (fast, cheap) as default; Claude 3.5 Sonnet as premium option
- Fallback: OpenAI GPT-4o-mini
- Config: API key stored in site settings / env; configurable per-user
- Cost guard: show estimated token cost before generation; require user confirmation
- Async via Celery task (brief generation can take 5–15 seconds)
- Output stored in `content_briefs` table alongside template-generated fields
- Diff view: show LLM-generated sections alongside template-generated sections

### Table Stakes

| Feature | Notes |
|---------|-------|
| Opt-in button on existing brief page | "Enhance with AI" CTA |
| API key configuration in settings | Per-site or global key |
| Loading state (Celery async) | Brief generation is not instant |
| LLM output sections clearly labeled as AI-generated | Trust/transparency |
| Save to brief / discard options | User controls what gets kept |

### Differentiators

| Feature | Value |
|---------|-------|
| Context-aware: uses positions, gap keywords, GEO score | This is the actual differentiator — not just "ask Claude to write a brief" |
| FAQ section output → one-click add to FAQPage schema | Closes the GEO readiness loop |
| "Differentiation angle" section | Most tools don't do this; helps writers actually add value vs. competitors |
| Brief version history | Track template vs. LLM version; rollback if needed |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Auto-publishing LLM output | This was explicitly ruled out in v1.0; LLM output is input to humans, not to WP |
| Building prompt UI for users to customize system prompts | Complexity trap; maintain the prompt server-side |
| Multiple LLM providers with UI switching | Config per deployment is sufficient; users don't need to choose models |
| Generating full articles | Out of scope; briefs only |

### Dependencies

- `content_briefs` table (existing)
- `keyword_positions` — position context
- `gap_analysis` — gap keyword context
- `cannibalization` — cannibal risk context
- `crawl_pages` — current page title/H1
- `geo_readiness_scores` (new, from Feature Group 5)
- External: Anthropic Claude API or OpenAI API (new dependency)
- `app_settings` — LLM API key storage (encrypted, Fernet)

### Complexity: MEDIUM-HIGH

Context assembly query (joining 5+ tables), Celery task for async generation, streaming response handling (or poll-based), output storage and diff UI. The hardest part is making the context assembly robust for edge cases (page with no position data, no gap keywords, etc.). Estimated: 4–5 days.

---

## Feature Group 9: 2FA (TOTP) + In-App Notifications

### 9A: TOTP Two-Factor Authentication

### What It Is

Per-user opt-in TOTP (Time-based One-Time Password) 2FA using an authenticator app (Google Authenticator, Authy, etc.). Standard RFC 6238 implementation.

### Standard Pattern (Research Verified)

**Library:** `pyotp` (pyauth/pyotp) — the Python standard for TOTP. Actively maintained. Works with all authenticator apps.

**Supporting library:** `qrcode[pil]` — generates QR codes for the provisioning URI.

**User model changes required:**
```
users table additions:
  totp_secret      VARCHAR(32) NULL  -- base32 TOTP secret, Fernet-encrypted at rest
  totp_enabled     BOOLEAN DEFAULT FALSE
  totp_verified_at TIMESTAMP NULL
  backup_codes     TEXT[] NULL  -- hashed backup codes (10 codes)
```

**Flow:**
1. User navigates to Security settings
2. Platform generates `pyotp.random_base32()` secret (stored encrypted, not yet active)
3. QR code rendered (provisioning URI) for user to scan
4. User enters 6-digit code from authenticator app to confirm setup
5. `totp_enabled = TRUE` on successful verification
6. On login: after password check, if `totp_enabled`, show TOTP code input before issuing JWT
7. JWT flow unchanged after TOTP verification

**Backup codes:** Generate 10 single-use backup codes at setup. Hash with bcrypt. Store in DB. Invalidate on use.

**JWT impact:** Minimal — add `mfa_verified: true` claim to JWT. Gate-check on sensitive endpoints if needed.

### Table Stakes

| Feature | Notes |
|---------|-------|
| Enable/disable 2FA in profile settings | Per-user opt-in |
| QR code display + manual secret key | For users who can't scan |
| Verify code before enabling | Prevent lockout from misconfigured setup |
| TOTP prompt on login | After password, before JWT issuance |
| 10 backup codes, downloadable | Recovery path |
| Disable 2FA requires current TOTP code | Prevent accidental disabling |

### Differentiators

None needed — 2FA is a security hygiene feature, not a product differentiator. The value is "it exists and works correctly."

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| SMS-based 2FA | TOTP is simpler, free, and more secure (no SMS hijacking) |
| Forcing 2FA for all users | This is an internal tool; opt-in is correct for initial rollout |
| Hardware key (FIDO2/WebAuthn) | Overcomplicated for this use case and user base |

### Dependencies

- `users` table (Alembic migration required)
- `pyotp` library (new, lightweight)
- `qrcode[pil]` library (new)
- JWT issuance logic in auth service

### Complexity: MEDIUM

Well-documented pattern, multiple reference implementations exist on GitHub with FastAPI + SQLAlchemy. Estimated: 2–3 days.

---

### 9B: In-App Notification Feed

### What It Is

A bell icon in the nav bar showing unread notification count, with a dropdown or panel listing recent system notifications. Notifications include: position drop alerts, crawl errors detected, pipeline completions, task assignments, report delivered.

### Standard Pattern (Research Verified)

**Delivery mechanism choice:**
- **HTMX polling** (`hx-trigger="every 30s"`) — simplest; polling endpoint returns notification count badge and feed fragment. Works with existing HTMX architecture. No WebSocket complexity.
- **SSE (Server-Sent Events)** — push-based, lower latency; HTMX 2.0 has SSE extension. More complex server infrastructure (requires persistent connections, Redis pub/sub as broker per worker).

**Recommendation:** Start with HTMX polling every 30 seconds. The user base is small (< 20 users), event frequency is low (not a trading platform), and polling at 30s is indistinguishable from SSE for SEO alerts. Migrate to SSE only if needed.

**Notification table:**
```
notifications:
  id             UUID PK
  user_id        UUID FK users.id
  type           VARCHAR(50)  -- position_drop, crawl_error, pipeline_done, task_assigned, report_sent
  title          VARCHAR(255)
  body           TEXT NULL
  link_url       VARCHAR(500) NULL  -- deep link to relevant page
  is_read        BOOLEAN DEFAULT FALSE
  created_at     TIMESTAMP
  site_id        UUID FK NULL  -- for site-scoped notifications
```

**Generation:** Celery tasks that currently send Telegram/email alerts also write to `notifications` table. No new Celery tasks needed — add `notification_service.create(user_id, type, title, body, link_url)` call to existing alert points.

**UI:** Bell icon in nav with `<span class="badge">N</span>`. Click opens HTMX-driven dropdown with notification list. Mark read on open (or on individual item click). "Mark all read" action.

### Table Stakes

| Feature | Notes |
|---------|-------|
| Unread count badge on bell icon | Core visibility signal |
| Notification feed (last 50 notifications) | Date, type icon, title, link |
| Mark read on click / mark all read | Standard UX |
| Type icons (position drop vs crawl error vs task) | Visual differentiation |
| Notification retention: 90 days | Configurable; prune via Celery Beat task |

### Differentiators

| Feature | Value |
|---------|-------|
| Deep links from notifications | Click "Position drop on site X" goes directly to that keyword's chart |
| Site filter on notification feed | Managers with multi-site view need to filter by site |
| Notification preferences per user | Toggle which event types trigger in-app vs Telegram vs email |

### Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| WebSocket implementation | Overkill for this scale and event frequency |
| Real-time push for every Celery task completion | Noise; only notify on user-relevant events |
| Browser push notifications | Requires service worker; complexity not justified for internal tool |

### Dependencies

- `notifications` table (new, Alembic migration)
- `users` — FK for per-user notifications
- `sites` — FK for site-scoped notifications
- Existing Celery alert points (position drop alerts, pipeline completion, crawl errors)
- Existing nav template — add bell icon with HTMX polling

### Complexity: LOW-MEDIUM

New DB table + notification service helper + HTMX polling endpoint + nav template update. The integration work (wiring existing Celery tasks to write notifications) is the most time-consuming part but is purely additive. Estimated: 2–3 days.

---

## Feature Dependencies (v2.0)

```
[Existing: keyword_positions + crawl_pages + content_audit + metrika_pageviews]
    └──powers──> [Quick Wins Page]           # Group 1 — SQL aggregation
    └──powers──> [Dead Content Detection]     # Group 2 — SQL aggregation
    └──powers──> [Error Impact Scoring]       # Group 3 — SQL aggregation
    └──powers──> [AI/GEO Readiness]           # Group 5 — rule-based checks

[Existing: gap_analysis + cannibalization + keyword_positions]
    └──powers──> [Growth Opportunities]       # Group 4 — aggregation of existing outputs

[Group 5: geo_readiness_scores]
    └──enriches──> [LLM Briefs]              # Group 8 — context input

[Existing: content_briefs + content pipeline]
    └──extends──> [LLM Briefs]               # Group 8 — enhancement layer

[Existing: WeasyPrint + report templates]
    └──extends──> [Client Instructions PDF]   # Group 6 — new Jinja2 template

[External: Google Suggest API + Yandex Suggest API]
    └──feeds──> [Keyword Suggest]             # Group 7 — new external calls

[Existing: users table + JWT auth]
    └──extends──> [2FA TOTP]                  # Group 9A — auth layer addition

[Existing: Celery alert tasks + nav template]
    └──extends──> [In-App Notifications]      # Group 9B — additive to existing alerts

[Group 9B: notifications]
    └──can link to──> [Quick Wins, Error Impact, Growth Opportunities]
```

---

## Table Stakes vs Differentiators vs Anti-Features Summary

### Table Stakes (Expected by Users for These Feature Types)

| Feature | Minimum Viable Form |
|---------|-------------------|
| Quick Wins | Filtered list of pages with position 4–20 + at least one issue; sortable by something meaningful |
| Dead Content | Pages with zero traffic + no position; age filter; action column |
| Error Impact | Error list with severity + page traffic context |
| Growth Opportunities | Combined gap/lost/cannibalization list |
| GEO Readiness | Scored checklist per page with pass/fail per check |
| Client PDF | Clean PDF with positions + traffic + work done + next steps |
| Keyword Suggest | Autocomplete suggestions from Google/Yandex; add to tracking |
| LLM Briefs | AI button on existing brief that produces structured output |
| 2FA | TOTP via authenticator app; setup + login verification flow |
| Notifications | Unread badge + feed with mark-read |

### Differentiators (What Makes Our Implementation Better)

| Feature | Our Differentiator |
|---------|-------------------|
| Quick Wins | Traffic-weighted opportunity score; combines position + content audit in one query |
| Dead Content | "Last meaningful traffic" date; merge suggestions; actionable not just diagnostic |
| Error Impact | Native traffic weighting — no other tool does this natively |
| Growth Opportunities | Unified scoring across three previously-siloed signal sources |
| GEO Readiness | Auto-computed from existing crawl data; no manual checklist |
| Client PDF | Manager annotation + "approve actions" section; plain-Russian auto-sentences |
| Keyword Suggest | Alphabet soup expansion; "already tracked" indicator; DataForSEO enrichment opt-in |
| LLM Briefs | Context assembly from 5+ existing data sources (not a blank-slate LLM prompt) |
| 2FA | Tight integration with existing JWT flow; no external auth service dependency |
| Notifications | Deep links to relevant platform pages; site-scoped filtering |

### Anti-Features (Explicitly Avoid)

| Anti-Feature | Reason |
|--------------|--------|
| Auto-fixing without diff approval | Violates existing safety contract; would break user trust |
| Auto-pruning dead content | Irreversible SEO damage; must be human-approved |
| Claiming AI citation prediction for GEO | Unverifiable; causes trust erosion when it's wrong |
| Full-article LLM generation | Out of scope; tool generates briefs, humans write articles |
| Yandex Wordstat as required dependency | OAuth setup barrier; makes Keyword Suggest unusable for users without Direct account |
| WebSockets for notifications | Overkill for this scale; polling is sufficient |
| Forced 2FA for all users | Internal tool; opt-in is correct |
| White-label PDF | Full theming system is out of scope (v1.0 decision) |

---

## MVP for v2.0 Milestone

### Phase 1 (pure data surfaces, no new external deps)

1. **Error Impact Scoring** — highest ROI, pure SQL, immediate user value
2. **Quick Wins Page** — pure SQL + HTMX, reuses pipeline endpoints
3. **Dead Content Detection** — pure SQL, low complexity
4. **Growth Opportunities** — SQL aggregation, reuses existing page data
5. **AI/GEO Readiness** — rule-based checks against existing crawl data

### Phase 2 (new integrations and capabilities)

6. **Client Instructions PDF** — new Jinja2 template + WeasyPrint (already in stack)
7. **Keyword Suggest** — Google/Yandex Suggest APIs (no auth required path first)
8. **In-App Notifications** — HTMX polling, additive to existing Celery alerts
9. **2FA TOTP** — pyotp + qrcode, self-contained auth addition
10. **LLM Briefs** — most complex; depends on Phase 1 GEO readiness data; add last

### Defer

| Feature | Reason |
|---------|--------|
| Yandex Wordstat integration | OAuth complexity; alphabet soup + Yandex Suggest covers discovery needs |
| SSE for notifications | Polling at 30s is sufficient; revisit if user base grows |
| Multi-language client reports | Russian-first is correct; bilingual is v3.0 |
| LLM model switching UI | Config-only is sufficient for internal tool |

---

## Sources

- Sitebulb audit interface and "Hints" system — knowledge base mid-2025
- Screaming Frog vs. Sitebulb comparison analysis — WebSearch 2026-04-06
- Ahrefs quick wins methodology ("positions 11–20 with below-average CTR") — knowledge base
- SE Ranking Marketing Plan feature — knowledge base
- Content decay / dead content detection patterns — SearchEngineLand, Clearscope, Ahrefs 2025
- GEO readiness criteria — Onely GEO checklist, Frase FAQ schema study, Geoptie.com, SearchEngineLand 2025-2026
- FAQPage schema citation rate (3.2×) — Frase.io study, industry data, MEDIUM confidence
- Client SEO report structure — SEOptimer, Databox, ReportGarden, Reportr 2025
- Google Suggest API — importsem.com, charlieojackson.co.uk, unofficial endpoint documentation
- Yandex Suggest API — undocumented stable endpoint, community knowledge
- Yandex Wordstat official API — yandex.ru/support2/wordstat/en, yandex.cloud/en/docs/search-api
- FastAPI TOTP 2FA — codevoweb.com 2026, github.com/josiemundi/fastapi-twofactor
- pyotp library — pyauth.github.io/pyotp
- HTMX SSE/polling for notifications — HTMX 2.0 docs, vlcinsky/fastapi-sse-htmx, Medium 2025
- LLM SEO brief generation context patterns — SEOmonitor, thruuu.com, almcorp.com 2025
- Error impact scoring formula — gracker.ai technical SEO audit prioritization, searchengineland.com 2025

---
*Feature research for: SEO Management Platform v2.0 — SEO Insights & AI milestone*
*Researched: 2026-04-06*
