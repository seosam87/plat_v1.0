# Feature Research

**Domain:** SEO Management Platform (self-hosted, agency, 20–100 WordPress sites)
**Researched:** 2026-03-31
**Confidence:** HIGH — based on direct knowledge of Ahrefs, Semrush, SE Ranking, Serpstat, Moz, Screaming Frog, Topvisor, Sitechecker, and agency workflow patterns as of mid-2025.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that any credible SEO tool must have. Missing these makes the product feel broken or amateur.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Keyword rank tracking (position history) | Core reason agencies buy any SEO tool; clients ask "where do we rank?" every week | MEDIUM | Daily/weekly polling; geo + device dimensions required. PROJECT.md has this. |
| Google Search Console integration | GSC is free, authoritative, and every serious SEO uses it; not integrating it is a red flag | MEDIUM | OAuth 2.0 flow. PROJECT.md has this. |
| Site crawl (technical audit) | Broken pages, missing metas, 404s — agencies need this to justify retainers | HIGH | Playwright-based crawl. PROJECT.md has this. |
| Page-level SEO field visibility (title, meta, H1, canonical) | Prerequisite for any on-page recommendation; expected in every audit tool | LOW | Side-effect of crawl. PROJECT.md captures this. |
| Multi-site management | Agency tool managing one site is not an agency tool | LOW | Site CRUD with WP connection verification. PROJECT.md has this. |
| Role-based access (admin / manager / client) | Clients must not see other clients' data; managers need scoped access | MEDIUM | Standard RBAC. PROJECT.md has this (Iteration 7). |
| Keyword import (CSV / XLSX) | Agencies build keyword lists in Key Collector, Topvisor, Excel — they will not re-enter manually | LOW | CSV + XLSX parsers. PROJECT.md has this. |
| Keyword → page mapping | The "which URL ranks for this keyword" question is asked constantly | MEDIUM | Requires crawl + positions data joined. PROJECT.md has this. |
| Dashboard / overview screen | First thing every user opens; must show health at a glance without hunting | MEDIUM | PROJECT.md has this (Iteration 6). |
| Position change alerts | Agencies promise clients they will know about drops; this is a contractual expectation | LOW | Telegram/email threshold alerts. PROJECT.md has Telegram. |
| Report export (PDF / Excel) | Clients want to receive a document, not log into a dashboard | MEDIUM | PROJECT.md has this (Iteration 6). |
| 404 / broken page detection | Basic technical SEO hygiene; auto-creating tasks from 404s is minimum expected behaviour | LOW | Side-effect of crawl. PROJECT.md has this. |
| Audit log / change history | Agencies need to know who changed what and when; essential for multi-user trust | LOW | PROJECT.md has `audit_log` from Iteration 1. |
| Scheduled crawls / checks | Manual re-crawl is not viable at 20–100 sites; automation is the product | MEDIUM | Celery Beat. PROJECT.md has this. |

---

### Differentiators (Competitive Advantage)

Features that go beyond expectations and create genuine lock-in or workflow advantages. For a self-hosted agency tool these matter more than feature breadth.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Automated TOC injection into WP | Saves 15–30 min per article; bulk-processed across sites is a major time multiplier | HIGH | Core unique value. PROJECT.md has this (Iteration 4). |
| Automated schema.org injection (Article JSON-LD) | Schema markup is error-prone manually; automation at scale eliminates a recurring task | HIGH | Part of WP content pipeline. PROJECT.md has this. |
| Automated internal linking suggestions + injection | Internal linking is universally under-done; auto-insertion from keyword DB is genuinely rare in tools at this price point | HIGH | Most SaaS tools suggest; few auto-inject. PROJECT.md goes further. |
| WP content pipeline with mandatory diff preview + rollback | Agencies are terrified of breaking client sites; preview + rollback converts sceptics | HIGH | This safety layer is the differentiator, not the automation itself. PROJECT.md has this. |
| SERP-intersection keyword clustering | Group keywords by ranking URL overlap — more reliable than semantic clustering alone | MEDIUM | PROJECT.md has both manual + auto clustering. |
| Cannibalization detection | "Two pages fighting for the same keyword" is a common agency finding; auto-detection saves hours of analysis | MEDIUM | Requires positions + page mapping. PROJECT.md has this. |
| Content plan → WP draft in one click | Closes the loop from keyword research to published post without leaving the tool | MEDIUM | Direct WP REST API integration. PROJECT.md has this. |
| Page brief generation (template-based, H1–H3 + keywords) | Briefs are a deliverable agencies charge for; automation makes them instant | MEDIUM | PROJECT.md deliberately keeps this LLM-free for determinism. Good call. |
| Auto-task creation from SEO findings | Converting crawl findings into actionable tasks without manual triage is a real time-saver | MEDIUM | 404 → task, cannibalization → task, missing schema → task. PROJECT.md has this. |
| Yandex Webmaster integration | Critical for Russian-market agencies; virtually no Western SaaS supports this well | MEDIUM | PROJECT.md has this. Genuine niche advantage. |
| Kanban project board tied to SEO data | Most tools show data but leave task management to Trello/Jira; integration removes context-switching | MEDIUM | PROJECT.md has this (Iteration 5). |
| Per-page snapshot diff with change feed | "What changed on this page between crawls?" is asked constantly after rankings move; few tools answer it well | HIGH | JSON diffs per crawl. PROJECT.md has this. |
| Yoast/RankMath meta field write-back via REST API | Pushing SEO fields from the platform back to WP eliminates copy-paste; unique to WP-native tools | MEDIUM | PROJECT.md has this. |
| Ad traffic period comparison (before/after) | Agencies need to show ROI across campaign periods; simple CSV upload + delta table is more useful than complex integrations | LOW | PROJECT.md has this with good scope (CSV upload only). |
| Self-hosted / no SaaS fees | At 50+ sites, Semrush or Ahrefs fees are $500–$2000/month; self-hosted amortises to near-zero | N/A (deployment) | This is a structural differentiator, not a feature. Worth naming explicitly to users. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that get requested constantly but create disproportionate cost or maintenance burden.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| LLM-generated article content | "AI writes the content for us" is appealing | Hallucinations break briefs; output quality varies wildly; clients blame the tool; adds inference cost and latency; turns an SEO tool into a writing tool (different product) | Template-based briefs (PROJECT.md's approach) deliver deterministic, auditable output. Add LLM as opt-in enrichment later if genuinely demanded. |
| Real-time rank tracking (live SERP polling) | "I want to see position changes the moment they happen" | Google SERPs are personalised; real-time polling triggers bans even with rotation; results vary by DC; costs are enormous at scale; daily is sufficient for agency reporting | Daily scheduled checks with Celery Beat + DataForSEO fallback. PROJECT.md has this correctly. |
| Backlink database (crawled) | Ahrefs-style link index is expected by SEO pros | Building a web-scale backlink crawler is a multi-year infrastructure project; it's not a feature, it's a separate company | GSC provides backlink data for owned sites. DataForSEO API can supply third-party backlink data on demand if needed. |
| Direct Google Ads / Yandex Direct API integration | "Pull ad spend automatically" | OAuth per-client, token refresh, rate limits, schema changes on Google's side, scopes differ by account type — ongoing maintenance indefinitely | CSV upload covers 90% of the use case. PROJECT.md correctly scoped this out. |
| SPA/React frontend | "Modern UI, better UX" | Adds build toolchain, API versioning discipline, hydration complexity, JS bundle management — doubles frontend scope for marginal UX gain in an internal tool | Jinja2 + HTMX covers all required interactions (modals, inline updates, live tables). PROJECT.md correctly chose this. |
| White-label per-client branding | Agencies ask to send reports with their own logo/colours | Theming system is a non-trivial frontend feature; clients interact minimally with the tool; PDF/Excel exports can be styled far more cheaply | Logo field on reports + CSS variable override is sufficient. Full white-label is a SaaS product pivot. |
| Mobile app | "I want to check rankings on my phone" | Doubles platform surface; PWA is more maintainable | Responsive web design + PWA manifest is sufficient for mobile use. |
| Competitor keyword gap analysis (organic) | Standard Semrush/Ahrefs feature | Requires a crawled index of competitor rankings — same problem as backlink database. Can't be done without third-party data | DataForSEO organic positions endpoint can be called on-demand for specific competitors; scope tightly. |
| Automated penalty detection | "Tell me if Google penalised a site" | Penalty signals don't exist as an API; heuristic traffic drop detection requires stable baseline + attribution logic that generates false positives | Alert on significant GSC impression/click drops instead. |
| Multi-language SERP support beyond RU/EN | "We need DE/FR/ES markets too" | Each engine/locale adds geo-specific parser rules and testing surface; User-Agent pools must grow | Scope Yandex (RU) + Google (configurable geo) first. Locale expansion is a later iteration with no architectural changes needed. |

---

## Feature Dependencies

```
[Site Management (WP REST connection)]
    └──requires──> [Crawl Engine]
                       └──requires──> [Page Snapshot Store]
                                          └──requires──> [Change Feed UI]
                                          └──requires──> [Diff Engine]

[Keyword Import]
    └──enables──> [Position Tracking]
                      └──requires──> [SERP Poller / DataForSEO]
                      └──enables──> [Keyword → Page Mapping]
                                        └──enables──> [Cannibalization Detection]
                                        └──enables──> [Missing Page Detection → Task]

[GSC Integration]
    └──enhances──> [Position Tracking] (authoritative click/impression data alongside rank data)
    └──enhances──> [Backlink visibility] (limited, but free)

[Crawl Engine]
    └──enables──> [Technical Audit (404, noindex, missing meta)]
    └──enables──> [TOC / Schema Detection]
    └──enables──> [WP Content Pipeline trigger]
    └──enables──> [Auto-task creation from findings]

[WP Content Pipeline]
    └──requires──> [Site Management (WP REST connection)]
    └──requires──> [Crawl Engine] (source of pages to process)
    └──requires──> [Keyword DB] (for internal linking relevance)
    └──requires──> [Diff Preview UI] (mandatory gate before push)
    └──enables──> [TOC injection]
    └──enables──> [Schema injection]
    └──enables──> [Internal linking injection]
    └──enables──> [Yoast/RankMath write-back]

[Project / Task Board]
    └──requires──> [Site Management]
    └──enhanced by──> [Auto-task creation] (crawl findings, position drops, cannibalization)
    └──enhanced by──> [Content Plan] (tasks linked to content rows)

[Content Plan]
    └──requires──> [Keyword DB]
    └──requires──> [Site Management (WP REST)] (for one-click draft creation)
    └──enables──> [Page Brief generation]

[Reporting]
    └──requires──> [Position Tracking] (trends)
    └──requires──> [Project / Task Board] (task progress)
    └──requires──> [Crawl Engine] (site change data)
    └──enhanced by──> [Ad Traffic module] (holistic SEO+paid view)

[Auth / RBAC]
    └──required by──> everything (foundation, must be first)

[Celery + Redis]
    └──required by──> [Crawl Engine] (async, scheduled)
    └──required by──> [Position Tracking] (async, scheduled)
    └──required by──> [WP Content Pipeline] (async batch)
    └──required by──> [Report delivery] (scheduled email/Telegram)
```

### Dependency Notes

- **Auth requires nothing but must be first:** Every subsequent feature requires a user context and role enforcement. A working auth layer unblocks all parallel development.
- **Crawl Engine unlocks the most downstream features:** TOC/schema detection, change feed, content pipeline triggers, and auto-task creation all depend on it. It is the highest-leverage early investment.
- **Position Tracking requires Keyword Import:** You cannot track positions without keywords. The import UX must exist before the tracking loop can be validated.
- **WP Content Pipeline requires Crawl + Keyword DB:** The pipeline needs to know which pages exist (crawl) and which keywords are relevant (keyword DB) to generate meaningful internal links. Building it without these foundations produces a fragile one-shot tool.
- **Reporting is a terminal consumer:** It reads from every other subsystem but writes to none. It should be built last. A premature reporting module blocks nothing but wastes effort if upstream schemas change.
- **Content Plan enhances but does not block Position Tracking:** These can be developed in parallel once Site Management and Keyword Import exist.
- **GSC OAuth and Yandex integrations are additive:** They enrich position data but are not required for the SERP polling path to function. They can be added without restructuring position storage.

---

## MVP Definition

### Launch With (v1)

Minimum needed for an SEO agency to replace their current workflow (GSC + spreadsheets + WP admin).

- [ ] Auth + RBAC (admin/manager/client) — nothing works without identity and access control
- [ ] Site management (add/verify WP sites) — the unit of work is a site; must exist before everything else
- [ ] Keyword import (CSV/XLSX) + manual entry — agencies have existing keyword lists; no import = no adoption
- [ ] Position tracking with history (Google, configurable geo/device) — the primary reason anyone opens the tool
- [ ] GSC integration — authoritative data; builds trust immediately; low implementation cost relative to value
- [ ] Site crawler (URL, title, H1, meta, status, depth) with scheduled runs — replaces Screaming Frog for basic audit
- [ ] Change feed (what changed on each page since last crawl) — answers the "something moved, what changed?" question
- [ ] Keyword → page mapping + cannibalization detection — core analysis output agencies deliver to clients
- [ ] Dashboard (positions, tasks, recent changes across all projects) — first screen every session
- [ ] Basic task board (manual task creation + status) — replaces spreadsheet task tracking
- [ ] Report export (PDF + Excel) — client deliverable; without this, the tool has no external output

### Add After Validation (v1.x)

Add once the core ranking + crawl + reporting loop is working and users are in the tool daily.

- [ ] Auto-task creation from crawl findings (404 → task, cannibalization → task) — trigger: users are manually creating these tasks and complaining
- [ ] Position drop Telegram alerts — trigger: users report they missed a drop they should have caught
- [ ] WP Content Pipeline (TOC, schema, internal links) with diff preview + rollback — trigger: users ask "can it actually fix things, not just report them?"
- [ ] Content plan + one-click WP draft creation — trigger: content workflow is being managed in a separate spreadsheet
- [ ] Page brief generation — trigger: agency is producing briefs manually and wants automation
- [ ] Yandex Webmaster integration — trigger: team manages significant Yandex-traffic sites
- [ ] Scheduled report delivery (Telegram/SMTP) — trigger: managers are manually exporting and sending reports

### Future Consideration (v2+)

Defer until core product-market fit is established (team uses it daily and prefers it over alternatives).

- [ ] LLM-assisted brief enrichment — defer until template-based briefs are validated as useful; then LLM is an optional enhancement, not a dependency
- [ ] SERP-intersection clustering (automated) — defer until keyword volumes are large enough (500+ keywords per site) to make clustering valuable
- [ ] Ad traffic module — defer until SEO data loop is proven; ad data is a nice-to-have extension
- [ ] Competitor on-demand position lookup (via DataForSEO) — defer until core own-site tracking is rock-solid
- [ ] Celery Flower / task queue UI — defer until queue debugging becomes a real operational pain point
- [ ] Client invite links + self-registration — defer until there are enough clients actively requesting dashboard access

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Auth + RBAC | HIGH | LOW | P1 |
| Site management (WP connection) | HIGH | LOW | P1 |
| Keyword import (CSV/XLSX) | HIGH | LOW | P1 |
| Position tracking + history | HIGH | MEDIUM | P1 |
| GSC integration | HIGH | MEDIUM | P1 |
| Site crawler (basic audit fields) | HIGH | HIGH | P1 |
| Change feed UI | HIGH | MEDIUM | P1 |
| Keyword → page mapping | HIGH | MEDIUM | P1 |
| Cannibalization detection | HIGH | LOW | P1 |
| Dashboard overview | HIGH | MEDIUM | P1 |
| Report export (PDF + Excel) | HIGH | MEDIUM | P1 |
| Task board (Kanban) | MEDIUM | MEDIUM | P2 |
| Position alerts (Telegram) | MEDIUM | LOW | P2 |
| Auto-task creation from findings | MEDIUM | LOW | P2 |
| WP Content Pipeline (TOC + schema + links) | HIGH | HIGH | P2 |
| Diff preview + rollback for WP pipeline | HIGH | MEDIUM | P2 |
| Content plan + WP draft creation | MEDIUM | MEDIUM | P2 |
| Page brief generation | MEDIUM | LOW | P2 |
| Yandex Webmaster integration | MEDIUM | MEDIUM | P2 |
| Scheduled report delivery | MEDIUM | LOW | P2 |
| Page snapshot diffs (JSON) | MEDIUM | MEDIUM | P2 |
| SERP-intersection clustering | MEDIUM | HIGH | P3 |
| Ad traffic CSV module | LOW | LOW | P3 |
| Celery Flower / task queue UI | LOW | LOW | P3 |
| Client invite link self-registration | LOW | LOW | P3 |
| LLM brief enrichment | LOW | MEDIUM | P3 |
| Competitor position lookup (DataForSEO) | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch — without this, the tool does not replace existing workflow
- P2: Should have — adds significant value, add when core is stable
- P3: Nice to have — future consideration after product-market fit

---

## Competitor Feature Analysis

| Feature | Semrush / Ahrefs | SE Ranking / Serpstat | Our Approach |
|---------|------------------|-----------------------|--------------|
| Rank tracking | Daily, any engine, any geo, device split, SERP features | Daily, configurable schedule, cheaper at high keyword volume | Playwright SERP poller + DataForSEO fallback; geo/device configurable. No SERP feature data (not needed for agency workflow). |
| Site crawl | Deep crawls, JS rendering, 200+ checks, log file analysis | Lighter crawls, fewer checks | Playwright-based (handles JS); focused on fields that drive agency actions (title, H1, meta, schema, TOC, noindex, status). Depth-first, not breadth-first. |
| Keyword research (own index) | Massive crawled keyword databases with volume/difficulty | Smaller indices, SERP-derived | NOT building a keyword index. Import from Key Collector / Topvisor / manual. This is not a gap — it is a deliberate scope boundary. |
| Backlink analysis | Multi-billion URL indices; DR/UR metrics | Smaller indices | NOT building. GSC provides owned-site backlink data. DataForSEO can fill gaps on demand. |
| Content optimisation | Semrush Writing Assistant (NLP-based); Ahrefs has limited on-page tooling | SE Ranking has on-page checker | WP-native pipeline is stronger: actual injection, not just recommendations. Unique advantage. |
| Internal tool integration | None (SaaS, no WP write-back) | SE Ranking has WP plugin (read-focused) | Direct WP REST API write-back (Yoast/RankMath meta, content injection). Genuine differentiator. |
| Project / task management | Semrush has basic Projects; Ahrefs has none | SE Ranking has basic task module | Kanban board tied to SEO findings + auto-task creation. More integrated than any SaaS competitor. |
| Client access / reporting | Client portals, white-label PDFs, scheduled emails | Similar; SE Ranking has strong white-label | PDF/Excel export + Telegram delivery. No white-label (scoped out). Sufficient for internal agency use. |
| Pricing model | $100–$500+/month for agency plans | $100–$300/month | Self-hosted: VPS cost only (~$20–$80/month). Structural cost advantage at scale. |
| Yandex support | Minimal to none | Serpstat has some Yandex data | Yandex Webmaster native integration + Playwright Yandex SERP parsing. Clear advantage for RU market. |
| Multi-site management | Project-based, not WordPress-native | Similar | WP REST API native; credentials encrypted per site; bulk operations via Celery. Purpose-built for WP agency. |

---

## Gap Analysis: PROJECT.md vs Industry Standards

### What PROJECT.md Has Right

- Crawler with Playwright (handles JS, which Screaming Frog misses on dynamic sites)
- Positions + GSC + Yandex in one place (no comparable self-hosted tool does this)
- WP content pipeline with diff/rollback (unique, high value, correctly scoped)
- Template-based briefs without LLM (correct deferral — determinism matters for client-facing deliverables)
- CSV-only ad traffic (correct scoping — API integrations are a maintenance trap)
- Jinja2 + HTMX over SPA (correct — eliminates entire frontend build complexity)
- Celery Beat for scheduling (correct — avoids APScheduler's single-process limitation)
- DataForSEO as safe SERP fallback (correct risk management for Playwright bans)

### What Is Missing or Under-Specified

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| No keyword volume / difficulty data source | MEDIUM | Agencies need volume estimates to prioritise keywords. PROJECT.md mentions "volume estimate" in brief generation but no volume data source is specified. DataForSEO Keywords Data endpoint can provide this cheaply on-demand. Add to Iteration 3 scope or brief generation context. |
| No SERP feature tracking (featured snippets, PAA, local pack) | LOW | Table stakes in premium tools; not required for agency workflow but clients ask about it. DataForSEO returns SERP features alongside positions — capture and store even if not yet surfaced in UI. Costs nothing extra. |
| No page indexation status check beyond noindex tag | MEDIUM | A page can be noindexed in GSC (coverage report) despite having no noindex tag. GSC URL Inspection API can verify indexation status per URL. Worth adding as an optional enrichment in Iteration 3. |
| Scheduled report delivery (Telegram/SMTP) is in Iteration 6 | LOW | For an agency managing 50+ sites, automated weekly summaries should arrive earlier (Iteration 5 or alongside the reporting module). Not a blocking gap, but re-order consideration. |
| No sitemap.xml parsing in crawler | LOW | Sitemaps give the crawler a faster, more complete URL list than link-following alone. Especially important for large sites with deep navigation. Add as crawler enhancement in Iteration 2. |
| Content plan lacks priority/effort fields | LOW | Without effort estimation, the content plan is just a list. Adding story-point-style effort and priority columns converts it into a planning tool. Low complexity addition. |
| No page speed / Core Web Vitals data | LOW | CWV affects rankings; clients ask about it. Not worth building a measurement system — Google PageSpeed Insights API is free and simple. Optional future addition, not a gap that blocks launch. |

### What Is Excessive or Should Be Simplified

| Item | Assessment |
|------|------------|
| Playwright SERP parser as primary rank tracking | Risky as primary mechanism. Playwright SERP parsing for 1,000+ keywords across 50 sites is operationally fragile (ban risk, IP rotation cost, result variance). DataForSEO should be primary; Playwright should be the fallback or supplement, not the other way around. Reconsider the primacy in Iteration 3. |
| Page type detection (category/article/landing/product) | Useful but the classifier logic will need maintenance as site structures vary. Start with URL pattern matching + meta heuristics; defer ML-based classification. |
| Celery Flower in Iteration 7 | Correct placement. Flower is a debugging tool, not a user-facing feature. Could be replaced with a minimal custom task status page at lower complexity cost if full Flower is overkill. |

---

## Sources

- Ahrefs feature set (Site Explorer, Keywords Explorer, Site Audit, Rank Tracker, Content Explorer) — knowledge as of mid-2025
- Semrush feature set (Position Tracking, Site Audit, On-Page SEO Checker, Content Writing Assistant, Projects, Agency toolkit) — knowledge as of mid-2025
- SE Ranking feature set (Rank Tracker, Website Audit, On-Page Checker, Backlink Monitor, Content Editor, Marketing Plan) — knowledge as of mid-2025
- Serpstat feature set (Rank Tracker, Site Audit, Keyword Research, Backlink Analysis, Cluster Research) — knowledge as of mid-2025
- Screaming Frog SEO Spider feature set (technical audit reference)
- Topvisor (rank tracking, keyword grouping — relevant as source format for keyword import)
- DataForSEO API documentation (SERP, Keywords Data, Backlinks endpoints)
- Google Search Console API (Search Analytics, URL Inspection)
- Yandex Webmaster API
- Agency SEO workflow patterns: standard deliverables (rank reports, technical audits, content briefs, content plans)

---
*Feature research for: SEO Management Platform (self-hosted, WordPress-agency, 20–100 sites)*
*Researched: 2026-03-31*
