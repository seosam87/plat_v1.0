# Pitfalls Research

**Domain:** SEO Management Platform v2.0 — Adding 9 features to 35K LOC FastAPI + Celery + PostgreSQL system
**Researched:** 2026-04-06
**Confidence:** HIGH

This document focuses exclusively on pitfalls that arise from *adding* these features to the *existing* system — not generic web development mistakes. Each pitfall is grounded in what the codebase already does and where the integration seams create risk.

---

## Critical Pitfalls

### Pitfall 1: URL Mismatch Between Pages, Metrika, and Positions Ruins Quick Wins / Dead Content Joins

**What goes wrong:**
Quick Wins and Dead Content both require JOINing `pages` (crawl URLs) with `metrika_traffic_pages` (Metrika URL) and `keyword_positions` (ranking URL). All three tables store `page_url` / `url` as raw strings. In production, the same page appears as `https://example.com/blog/` in one table and `https://example.com/blog` (no trailing slash) in another, or `http://` vs `https://`, or with UTM parameters in Metrika. JOINs return zero rows. Developer sees "no Quick Wins found" and assumes the data isn't there — it is, but joins fail silently.

**Why it happens:**
Metrika returns the URL exactly as the user visited it. The crawler stores the canonical URL from the `<link rel="canonical">`. `keyword_positions` stores the ranking URL from XMLProxy or DataForSEO. All three sources use different normalization. The existing code at `audit.py`, `metrika.py`, `change_monitoring.py` all store `page_url` as a raw string with no normalization step — this is fine for those features because they query by `site_id` and filter independently, never JOINing across tables.

**How to avoid:**
- Create a `normalize_url(url: str) -> str` utility function: lowercase scheme and host, strip trailing slash, strip `?utm_*` and `#` fragments, decode percent-encoding.
- Apply normalization on *write* in every service that stores a URL. Add it to `metrika_service.upsert_page_traffic()` immediately — that's the highest-risk callsite.
- For Quick Wins / Dead Content queries, do the join on `normalize_url(p.url) = normalize_url(m.page_url)` or better: store a `normalized_url` computed column in each table and index it.
- Write a test with 5 URL variants of the same page and assert all 5 join correctly.

**Warning signs:**
- Quick Wins returns 0 results for a site with 50+ keywords in positions 4–20.
- Dead Content returns 0 results for a site with Metrika data older than 30 days.
- Manual `SELECT` comparing `pages.url` and `metrika_traffic_pages.page_url` shows format differences for the same logical page.

**Phase to address:**
Phase 1 (Quick Wins / Dead Content) — the normalization utility must be built first, before any JOIN queries are written.

---

### Pitfall 2: DISTINCT ON on Partitioned `keyword_positions` Is Slow Without Partition Pruning

**What goes wrong:**
Quick Wins requires "latest position per keyword". The existing pattern `SELECT DISTINCT ON (kp.keyword_id, kp.engine) ... ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC` works correctly but scans all monthly partitions to find the latest row. With 100K keywords × 12 months of data, this is a full scan of millions of rows. The query goes from 200ms with 2 months of data to 8+ seconds with 12 months. The page times out.

**Why it happens:**
`DISTINCT ON` requires a sort, and PostgreSQL cannot prune partitions when the `WHERE` clause does not filter on `checked_at` (the partition key). The planner must scan all partitions and merge-sort them. The existing code in `report_service.py` and `overview_service.py` uses the same pattern and works because those queries are already filtered by `site_id` and are called once per site, not across all sites simultaneously.

**How to avoid:**
- Add a `WHERE checked_at >= now() - interval '90 days'` filter to all "latest position" queries. This prunes to at most 3 partitions. For Quick Wins, 90 days is appropriate — positions older than that are stale anyway.
- Use a materialized "latest positions" view maintained by the existing position check task: after each position check run, upsert into a `keyword_latest_positions` table (one row per keyword+engine). Quick Wins reads from this flat table, not from the partitioned one. This is the most sustainable approach given the scale.
- Index `keyword_latest_positions` on `(site_id, position, engine)` so the "positions 4–20" filter is instant.

**Warning signs:**
- `EXPLAIN ANALYZE` on Quick Wins query shows "Append" node with 12+ "Seq Scan on keyword_positions_YYYYMM" children.
- Quick Wins endpoint exceeds 3s for a site with 1000+ keywords.
- `pg_stat_statements` shows the DISTINCT ON query consuming >50% of total query time.

**Phase to address:**
Phase 1 (Quick Wins) — design the `keyword_latest_positions` materialized table before writing the first query. Retrofit it in position_tasks.py during the same phase.

---

### Pitfall 3: Impact Scoring Computed on Every Request Becomes Expensive at Scale

**What goes wrong:**
Error Impact Scoring requires aggregating errors (from audit results) weighted by traffic (from Metrika). If this is computed live on each page load, it involves: JOIN `audit_results` × `metrika_traffic_pages` × `pages`, group by error type, order by weighted score. On a site with 500 pages × 20 audit checks = 10K audit rows, joined with Metrika page data, this query takes 1–3 seconds. With 50 sites, the dashboard aggregation becomes unusable.

**Why it happens:**
Scoring feels like a "simple query" during development with 5 test sites. The JOIN fan-out is not visible until real data exists.

**How to avoid:**
- Compute and store scores as a Celery task, not inline in the request. Create an `error_impact_scores` table: `(site_id, check_code, score, computed_at)`. The task runs after each crawl completion and after each Metrika sync.
- Invalidate scores by writing a `score_valid_until` timestamp. The API reads the cached score if `computed_at > (now() - interval '24 hours')`. If stale, it serves the old score and enqueues a background recomputation — never blocks the request.
- The Celery trigger points: hook into the existing `crawl_tasks.py` finalization step and `metrika_tasks.py` sync completion. Both already exist and just need an `enqueue_impact_score_recompute(site_id)` call appended.

**Warning signs:**
- Dashboard endpoint exceeds 3s for any site.
- Database CPU spikes every time the Insights page loads.
- Adding a 6th site causes a 50% response time increase (linear scale = live computation).

**Phase to address:**
Phase 2 (Impact Scoring) — scores must be pre-computed from the start. No live aggregation path should exist in production.

---

### Pitfall 4: WeasyPrint Memory Does Not Release Between Client PDF Calls

**What goes wrong:**
WeasyPrint is confirmed to have a memory leak when called in a loop inside a long-running process (GitHub issue #2130, #1977). Each `HTML(string=html_str).write_pdf()` call in a Celery worker increases RSS by 20–40 MB and this memory is not released until the worker process dies. The existing `report_service.py` already calls WeasyPrint for weekly summary PDFs. Client Instruction PDFs add more calls — potentially 20–100 PDFs per report run. On a 2 GB VPS, the Celery worker hits the OOM killer after 30–50 PDFs.

**Why it happens:**
WeasyPrint uses Pango/Cairo C libraries. Python's garbage collector cannot reclaim memory held by native C extensions. The `write_pdf()` function allocates layout structures in C heap that are not freed until the process exits.

**How to avoid:**
- Run PDF generation in a subprocess per report: `subprocess.run(["python", "-m", "app.pdf_worker", report_id])`. The subprocess exits after the PDF is written, releasing all C memory. Use `asyncio.to_thread()` to call this without blocking the Celery event loop.
- Alternative: use `--max-tasks-per-child=10` on the PDF worker process specifically. After 10 PDFs, the worker process recycles, cleaning all memory. This is already the right pattern for Playwright — apply the same reasoning here.
- Do not generate all 20–100 client PDFs in one task. Use a Celery `group` where each task generates one PDF, so each task in the group benefits from the recycling policy.
- Set `soft_time_limit=120, time_limit=150` per PDF task. A stuck WeasyPrint call (e.g., infinite table pagination) should be killed rather than filling RAM.

**Warning signs:**
- `docker stats` shows the celery-default container's MEM growing during report runs and not recovering.
- Report tasks succeed but subsequent tasks are slower (memory pressure causing swap).
- OOM kill in `dmesg` correlated with a report task completion.

**Phase to address:**
Phase 3 (Client PDF) — subprocess isolation must be the first design decision before any WeasyPrint code is written.

---

### Pitfall 5: Keyword Suggest Triggers IP Bans from Google/Yandex Within Hours

**What goes wrong:**
Google Autocomplete and Yandex Suggest APIs are undocumented and rate-limited aggressively. Direct HTTP calls to `https://suggestqueries.google.com/complete/search` or `https://wordstat.yandex.ru` from a single VPS IP will result in CAPTCHA challenges within minutes of usage and IP bans within hours. The XMLProxy integration (already in the codebase) works because it uses proxy rotation — the same caution applies here.

**Why it happens:**
Developers treat Google Autocomplete as a "free API" because there is no API key required. This is a misread — Google serves it for browser consumption and treats server-to-server calls as scraping.

**How to avoid:**
- Use the XMLProxy API for Yandex Wordstat suggestions if XMLProxy supports it (check their endpoint list). XMLProxy already handles proxy rotation for Yandex — this is the path of least resistance.
- For Google Suggest, use DataForSEO's keyword suggestions API (already integrated in `dataforseo_service.py`) which handles Google's restrictions.
- Cache all suggestions aggressively: Redis with TTL of 7 days minimum. Keyword suggest data does not change meaningfully within a week. Key: `suggest:{engine}:{phrase_hash}`.
- Rate limit the user-facing endpoint in the UI: `slowapi` is already installed. Add a `@limiter.limit("10/minute")` decorator to the suggest endpoint.
- Log every outbound request to Google/Yandex in the audit log with the source IP visible — makes it easy to detect if the VPS IP gets blocked.

**Warning signs:**
- HTTP 429 or CAPTCHA HTML returned from suggest endpoint.
- Suggest results stop updating despite new queries.
- XMLProxy logs show unusually high failure rates for a new endpoint.

**Phase to address:**
Phase 4 (Keyword Suggest) — cache-first design and proxy routing must be decided before any external call is written.

---

### Pitfall 6: LLM API Failures Block Brief Generation with No Fallback

**What goes wrong:**
If the LLM API (OpenAI or Anthropic) is down or returns a 429, the brief generation Celery task fails with an unhandled exception. The user sees a spinner that never resolves, or an opaque "Task failed" error. Since LLM APIs are external dependencies, they can be unavailable at arbitrary times. The existing `retry=3` policy on Celery tasks delays failure by minutes but does not degrade gracefully.

**Why it happens:**
LLM integration feels like a service call but has unique failure modes: rate limits, token limits, content policy blocks, and network timeouts that are more frequent than typical REST APIs. Developers port the existing "retry 3 times" pattern from DataForSEO/GSC calls without accounting for the specific failure scenarios.

**How to avoid:**
- Always return a partial result rather than failing. If the LLM API is unavailable, return the template-based brief (which `brief_service.py` already generates) with a flag `"ai_enhanced": false`. Never block the user's workflow.
- Set `httpx.AsyncClient(timeout=30.0)` for LLM calls — not the default (no timeout). A hung LLM call with no timeout blocks the Celery worker thread indefinitely.
- Implement a circuit breaker: after 3 consecutive LLM failures for a site, set a `redis.setex("llm_circuit_open", 3600, "1")` flag. All subsequent requests return the template brief immediately for 1 hour without attempting the API call.
- Store the raw LLM prompt and response in the DB (`llm_brief_log` table). This enables: debugging hallucinations, cost auditing, and replay without re-billing.
- Cap token usage per brief: max 2000 input tokens (keyword list + page context), max 800 output tokens. Enforce with `max_tokens=800` in the API call. Prevents runaway cost from accidentally sending the full crawl HTML.

**Warning signs:**
- Brief generation tasks in Celery Flower show "RETRY" status for > 5 minutes.
- Monthly LLM API bill increases suddenly (usually means unbounded token usage).
- Users report briefs "hanging" on specific pages — often because those pages have large content being passed to the LLM.

**Phase to address:**
Phase 5 (LLM Briefs) — graceful degradation to template brief must be the default path, with LLM enhancement as opt-in overlay.

---

### Pitfall 7: 2FA Migration Locks Out Existing Users and Has No Recovery Path

**What goes wrong:**
Adding TOTP to the `users` table requires: a new `totp_secret` column (nullable), new `totp_recovery_codes` table, and a modified login flow. If 2FA is made mandatory without a user communication plan, existing users hit the 2FA prompt on their next login and have no way to enroll their authenticator app (they were never shown a QR code). If `totp_secret IS NULL` is not handled as "2FA not yet configured" (instead of "2FA failed"), users are permanently locked out.

**Why it happens:**
The login route is the most-visited endpoint in the app. Any conditional logic change in `auth.py` has a high surface area for regression. Adding `totp_secret` nullable with `if totp_secret IS NOT NULL: verify_totp()` seems correct but the enrollment flow is often not built in the same phase as the verification flow, leaving a gap.

**How to avoid:**
- Add `totp_secret` as `nullable=True` to the `users` table with default NULL. Never make 2FA mandatory in the same migration that adds the column.
- Two-phase rollout: Phase A = users can opt-in (enroll via settings page, generates QR, saves secret); Phase B = (optional, later) admin can force 2FA for specific roles.
- Generate recovery codes during enrollment (8 codes, bcrypt-hashed, stored in `user_recovery_codes` table). Show codes once, immediately after QR scan confirmation. Test the recovery flow in isolation before deploying.
- Test matrix: user with `totp_secret=NULL` + 2FA optional → login works unchanged. User with `totp_secret` set + correct TOTP → login works. User with `totp_secret` set + wrong TOTP → 401. User with `totp_secret` set + recovery code → login works + code invalidated.
- Add `/auth/2fa/disable` endpoint (admin-only) so that if a user loses their device, an admin can set `totp_secret=NULL` and regenerate recovery codes.

**Warning signs:**
- Existing users report "stuck on 2FA screen" after a deploy.
- Test coverage for `auth.py` drops below 70% after adding 2FA conditionals.
- No test exists for the `totp_secret=NULL` path in the login flow.

**Phase to address:**
Phase 6 (2FA) — write the test matrix before writing any auth code changes. The migration must be reviewed by running `alembic upgrade --sql` and inspecting the output before applying to production.

---

### Pitfall 8: Notifications Table Bloat Without Deletion Strategy

**What goes wrong:**
In-app notifications generate 1 row per event per user. With 5 active users × 50 position check completions/week × 20 sites = 5,000 rows/week. After 6 months: ~130,000 rows. PostgreSQL `autovacuum` handles this poorly for high-churn tables because frequent INSERT + soft-deletes (marking `read=True`) generate dead tuple bloat faster than vacuum can clean. The table grows to hundreds of MB, the index bloats, and `SELECT unread notifications WHERE user_id = ?` degrades from microseconds to milliseconds — visible as a slow first-page-load issue.

**Why it happens:**
Notification tables feel like simple tables during development. The churn rate (many inserts, many "soft read" updates) is the worst pattern for PostgreSQL MVCC — every UPDATE writes a new tuple version, leaving the old one as a dead tuple until vacuum runs.

**How to avoid:**
- Implement hard deletion on read: when a user opens notifications, DELETE the displayed rows (or DELETE WHERE created_at < now() - interval '30 days'). Do not use soft delete (`is_read=TRUE`) for notifications — it maximizes bloat.
- Add a Celery Beat task `cleanup_old_notifications` that runs nightly: `DELETE FROM notifications WHERE created_at < now() - interval '30 days'`. This one task prevents bloat indefinitely.
- Set `autovacuum_vacuum_scale_factor = 0.01` on the notifications table specifically (via `ALTER TABLE notifications SET (autovacuum_vacuum_scale_factor = 0.01)`) — this triggers vacuum at 1% dead tuples instead of the default 20%, keeping the table clean on high-churn tables.
- Index only `(user_id, created_at DESC)` — not `(user_id, is_read, created_at)`. Adding `is_read` to the index means every read-mark update invalidates the index entry, doubling write amplification.
- Cap at 100 unread notifications per user in the application layer. Beyond 100 unread, new ones replace the oldest unread. Users with 1000 unread notifications are not reading them — drop them.

**Warning signs:**
- `SELECT pg_size_pretty(pg_total_relation_size('notifications'))` shows >50 MB after a few weeks.
- `pg_stat_user_tables` shows `n_dead_tup` > 10% of `n_live_tup` for the notifications table.
- First-page-load time increases by 50–100ms week over week.

**Phase to address:**
Phase 6 (In-app Notifications) — cleanup strategy must be implemented in the same migration that creates the table.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems specific to this v2.0 milestone.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Live JOIN for Quick Wins instead of `keyword_latest_positions` table | No extra table/migration needed | Degrades to 10s+ queries at 100K keywords; requires rewrite | Never — 100K keywords is known scale from day 1 |
| Computing Impact Scores inline per request | No Celery task needed | Linear slowdown with sites × errors × metrika rows | Never for production use |
| Single WeasyPrint call generating all client PDFs | Simpler task code | OOM kill on report runs for 20+ sites | Never — subprocess per PDF from the start |
| Making 2FA mandatory in the same deploy that adds the feature | Clean code, no "nullable" logic | Locks out all existing users | Never — always two-phase |
| Passing full page HTML to LLM for brief generation | More context = better output | 50–100K token bills; context window errors | Never — always truncate to title + H2s + meta |
| Caching LLM responses with no TTL | Avoids repeated billing | Stale briefs served months later; confused users | Only for briefs explicitly marked "frozen" by user |
| Storing notification `is_read` flag and using soft-delete | Preserves history | Table bloat, index thrash | Never — hard delete on dismiss + nightly cleanup |
| Using the same Celery `default` queue for LLM tasks | No new queue configuration | LLM tasks (slow, expensive) block position checks (fast, time-sensitive) | Never — LLM tasks need their own queue |
| Skipping URL normalization on Metrika join | Faster initial query | Silent zero-result JOIN failures; no error, no warning | Never — normalization must be on write |

---

## Integration Gotchas

Common mistakes when connecting the new v2.0 features to the existing system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Quick Wins + `keyword_positions` (partitioned) | `DISTINCT ON` without partition key filter scans all 12+ partitions | Add `checked_at >= now() - interval '90 days'` to prune; prefer `keyword_latest_positions` flat table |
| Quick Wins + `metrika_traffic_pages` | JOIN on raw `page_url` strings (trailing slash mismatch, http vs https) | Normalize URLs on write; add `normalized_url` computed column and join on that |
| Impact Scoring + Celery triggers | Computing scores in no trigger — stale forever | Hook score recomputation into crawl finalize task and Metrika sync task |
| Impact Scoring + existing `audit_results` | `audit_results` has no `traffic_weight` — JOIN to Metrika requires intermediate aggregation | Aggregate Metrika visits per URL first, then join with audit results as a CTE |
| LLM Briefs + existing `brief_service.py` | Building LLM briefs as a separate service that duplicates template logic | Extend `brief_service.py` with an optional `ai_enhance(brief_dict)` step — template brief is always the base |
| LLM Briefs + Celery queue | Using `default` queue for LLM tasks | Create `llm` queue with `concurrency=2`; LLM calls are I/O-bound but slow (5–30s each) |
| Keyword Suggest + XMLProxy | Creating a new HTTP client for suggest when XMLProxy already handles Yandex proxying | Check XMLProxy suggest endpoint support first; if available, reuse `xmlproxy_service.py` |
| 2FA + existing JWT tokens | Adding 2FA check after JWT issuance means tokens issued before 2FA is enabled are valid without 2FA | Store `totp_verified: bool` in the JWT payload; any token issued without totp_verified=True is rejected if the user has TOTP enabled |
| In-app Notifications + Celery task results | Generating a notification inside every Celery task callback | Create a `notification_service.emit(event_type, site_id, payload)` function; all tasks call this single function — prevents scattered notification logic across 14 task files |
| AI/GEO Readiness + content audit | Building a separate content analysis pipeline when `content_audit_service.py` already parses HTML | Re-use existing `detect_author_block()`, `detect_cta_block()` etc.; add GEO-specific checks to the same detection layer |

---

## Performance Traps

Patterns that work at small scale but fail at real data volumes.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `DISTINCT ON keyword_positions` without time window | 8–15s query for latest position per keyword | Filter on `checked_at >= now() - interval '90 days'`; use `keyword_latest_positions` table | At ~3 months of data for 100K keywords (i.e., now) |
| Live Impact Score aggregation per request | Dashboard exceeds 3s for any site | Pre-compute in Celery, store in `error_impact_scores` table | At 50+ audit checks × 200+ pages per site |
| WeasyPrint in long-running Celery worker without subprocess isolation | Worker OOM after 30–50 PDFs | Subprocess-per-PDF or `--max-tasks-per-child=10` for PDF worker | After ~20 PDFs in one worker process lifetime |
| In-app notification soft-delete (mark read, keep row) | Page load slows 10ms/week as table bloats | Hard delete on dismiss + nightly cleanup | After ~3 months of active use with 5+ users |
| LLM API call without token cap | Runaway cost; context window errors | `max_tokens=800` output; truncate input to 2000 tokens | When any page's content is >8K tokens (common for content-heavy pages) |
| Suggesting keywords by calling Google/Yandex directly from VPS | IP banned within hours | Cache 7 days in Redis; route via DataForSEO or XMLProxy | First day of production use |
| Passing `site_id` as string vs UUID in new JOIN queries | `TypeError: invalid input for query argument $1` at runtime | Use `uuid.UUID(str(site_id))` cast at service boundary; add UUID type test | Immediately in dev if not caught by type checker |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing raw TOTP secret unencrypted in `users.totp_secret` | DB dump exposes all TOTP secrets; attacker can generate valid codes | Encrypt with Fernet (already used for WP credentials in `crypto_service.py`) before storing |
| Recovery codes stored as plaintext | Same as above — one DB read = full account takeover | bcrypt-hash recovery codes before storage; verify with `bcrypt.verify()` at login |
| LLM prompt includes full WP page HTML with client data | Client PII (names, emails from contact forms) sent to third-party LLM API | Strip all user-submitted content from pages before building prompts; send only SEO metadata (title, H1–H3, meta description) |
| Keyword Suggest endpoint without rate limiting | A single user can exhaust the daily XMLProxy/DataForSEO API quota in minutes | `@limiter.limit("10/minute")` on the suggest endpoint (slowapi already installed) |
| Client PDF accessible via predictable URL | Client A can access Client B's PDF by guessing the filename | Store PDFs in a path with UUID filename; check `site_id` ownership on every PDF download request |
| 2FA bypass via password reset flow | If password reset does not require 2FA, it becomes a bypass vector | After password reset, invalidate `totp_secret` and require re-enrollment; or require current TOTP code to initiate password reset |
| LLM API key in environment variable without rotation strategy | Leaked key = unlimited billing | Store in `service_credential` table (already Fernet-encrypted); rotate monthly; set billing limits in OpenAI/Anthropic dashboard |

---

## UX Pitfalls

Common user experience mistakes for these specific features.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Quick Wins shows pages in positions 4–20 without filtering out pages already in the WP pipeline | Users see pages already being optimized as "Quick Wins" — redundant work | Cross-reference with active `wp_content_job` records; exclude pages with pending pipeline jobs |
| Dead Content shows pages with 0 visits but only because Metrika isn't connected for that site | "Dead content" alert for a site with no Metrika — confusing | Show "Metrika not connected" banner instead of Dead Content tab when `metrika_traffic_pages` is empty for the site |
| Impact Score shown without "last computed" timestamp | User doesn't know if score reflects today's crawl or last week's | Always show `score_computed_at` next to every score |
| 2FA QR code shown but no "test code before saving" step | User scans QR, saves secret to DB, but their phone's clock is wrong — they can never log in | Require user to enter a valid TOTP code before the secret is saved; only then mark 2FA as enabled |
| LLM Brief button active for pages that haven't been crawled | LLM has no content to work with; returns generic brief | Disable LLM Brief button if `pages.last_crawled_at IS NULL` for the target page |
| Notification bell shows total count including notifications from 30+ days ago | "47 notifications" looks alarming; user dismisses all without reading | Show unread count capped at last 7 days; "and X older" link for the rest |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Quick Wins:** URL normalization applied — verify by comparing `pages.url` with `metrika_traffic_pages.page_url` for a site with known data. Missing normalization = silent zero results.
- [ ] **Quick Wins:** Excludes pages already in active WP pipeline (`wp_content_job.status IN ('pending', 'in_progress')`) — verify with test that has an active job.
- [ ] **Impact Scoring:** Score is pre-computed (check `error_impact_scores` table exists and has rows after crawl finalization) — not live-computed per request.
- [ ] **Impact Scoring:** Recomputation is triggered by *both* crawl finalize AND Metrika sync — verify by running each independently and checking `score_computed_at` updates.
- [ ] **Client PDF:** Generated in subprocess or isolated worker — verify with `docker stats` that the PDF worker container memory returns to baseline after a 10-site report run.
- [ ] **Keyword Suggest:** Results are cached in Redis — verify by calling the endpoint twice for the same keyword and checking Redis key exists with TTL > 0.
- [ ] **Keyword Suggest:** Rate limit header returned in response — verify with `curl -I` that `X-RateLimit-*` headers appear.
- [ ] **LLM Briefs:** Graceful fallback to template brief on API failure — verify by temporarily setting an invalid API key and checking the brief endpoint still returns a result.
- [ ] **LLM Briefs:** Token cap enforced — verify by passing a 20K-character page and checking that the API call uses < 2500 total tokens.
- [ ] **2FA:** `totp_secret=NULL` path (not enrolled) still lets user log in — verify with a test user that has no 2FA set up.
- [ ] **2FA:** Recovery code is invalidated after single use — verify by using a recovery code twice; second use should return 401.
- [ ] **2FA:** Admin can reset 2FA for a user — verify via admin UI or admin API endpoint.
- [ ] **Notifications:** Nightly cleanup task is registered in Celery Beat — verify in Flower that the task appears in the schedule.
- [ ] **Notifications:** Table size does not grow unboundedly — verify after 1 week that row count stays below 10K.
- [ ] **AI/GEO Readiness:** Reuses existing `content_audit_service.py` detection functions — no duplicate regex patterns for the same checks.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| URL mismatch causing zero JOIN results | MEDIUM | Run one-time normalization UPDATE across `pages`, `metrika_traffic_pages`, `audit_results`; add normalized_url column; rebuild indexes |
| DISTINCT ON query causing timeouts | LOW | Add `checked_at` filter immediately; schedule backfill of `keyword_latest_positions` table as Celery task |
| WeasyPrint OOM killing Celery worker | LOW | Restart the celery-default container; add `--max-tasks-per-child=10` to the worker command in `docker-compose.yml` |
| IP ban from Google/Yandex suggest | LOW-MEDIUM | Switch to DataForSEO/XMLProxy routing; wait 24–48h for IP ban to lift; add Redis cache immediately |
| LLM API cost spike | LOW | Set billing alert in provider dashboard; cap `max_tokens` in code; enable circuit breaker |
| 2FA lockout of users | HIGH | Admin runs `UPDATE users SET totp_secret = NULL WHERE id = ?`; user re-enrolls on next login; add admin recovery endpoint proactively |
| Notifications table bloat | MEDIUM | Run `DELETE FROM notifications WHERE created_at < now() - interval '30 days'`; expect VACUUM to run after; set autovacuum tuning |
| Alembic multiple heads from adding 9 migrations | LOW | `alembic merge heads -m "merge_v2_heads"`; review generated migration; apply |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| URL mismatch on JOIN | Phase 1 (Quick Wins) — build `normalize_url()` first | Test: 5 URL variants of same page all JOIN correctly |
| DISTINCT ON partition scan | Phase 1 (Quick Wins) — create `keyword_latest_positions` table | EXPLAIN ANALYZE shows max 3 partition scans |
| Impact Score staleness | Phase 2 (Impact Scoring) — pre-compute in Celery from day 1 | `error_impact_scores` has rows; `score_computed_at` updates on crawl finalize |
| WeasyPrint OOM | Phase 3 (Client PDF) — subprocess isolation before first PDF call | docker stats stable after 20-site report run |
| Keyword Suggest IP ban | Phase 4 (Keyword Suggest) — cache + proxy routing from first call | Redis key present after first suggest call |
| LLM fallback missing | Phase 5 (LLM Briefs) — template fallback is the default path | Invalid API key → template brief returned, no 500 error |
| 2FA lockout | Phase 6 (2FA) — migration adds nullable column; 2FA optional by default | Existing user with NULL totp_secret can still login |
| Notification bloat | Phase 6 (Notifications) — cleanup task in same PR as table creation | Nightly cleanup appears in Flower schedule |
| Alembic multiple heads | Every phase — single head verified in CI | `alembic heads` returns exactly 1 head in CI |
| Test coverage regression | Every phase — new service code requires tests before merge | `pytest --cov-fail-under=60` passes in CI |

---

## Sources

- WeasyPrint memory leak issues: [GitHub #2130](https://github.com/Kozea/WeasyPrint/issues/2130), [GitHub #1977](https://github.com/Kozea/WeasyPrint/issues/1977), [GitHub #1104](https://github.com/Kozea/WeasyPrint/issues/1104)
- PostgreSQL DISTINCT ON performance: [CYBERTEC: Killing performance with partitioning](https://www.cybertec-postgresql.com/en/killing-performance-with-postgresql-partitioning/), [Tiger Data: DISTINCT 8000x faster](https://www.tigerdata.com/blog/how-we-made-distinct-queries-up-to-8000x-faster-on-postgresql)
- PostgreSQL table bloat and partitioning as TTL: [Simple Thread: Drop Partitions Not Performance](https://www.simplethread.com/beyond-delete/), [Medium: Partitioning to avoid bloat](https://medium.com/@achakrab01/using-partitioning-in-postgresql-to-avoid-table-bloat-and-implement-ttl-like-feature-b217572e9f0a)
- OpenAI rate limiting and cost control: [OpenAI Cookbook: Handle rate limits](https://cookbook.openai.com/examples/how_to_handle_rate_limits), [Skywork: AI API cost management 2025](https://skywork.ai/blog/ai-api-cost-throughput-pricing-token-math-budgets-2025/)
- Alembic multiple heads: [GitHub Discussion #1543](https://github.com/sqlalchemy/alembic/discussions/1543), [Jerry Codes: Multiple heads in Alembic](https://blog.jerrycodes.com/multiple-heads-in-alembic-migrations/)
- TOTP/2FA implementation: [PyOTP docs](https://pyauth.github.io/pyotp/), [FastAPI 2FA guide](https://codevoweb.com/two-factor-authentication-2fa-in-fastapi-and-python/)
- Prompt injection risks in LLM tools: [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), [LLM Safety for SEOs](https://t-ranks.com/aeo/llm-safety-prompt-injection-seo/)
- Yandex Wordstat API and IP protection: [Yandex Wordstat API docs](https://yandex.com/support2/wordstat/en/content/api-structure), [Yandex Autocomplete scraping](https://brightdata.com/products/serp-api/yandex-search/autocomplete)
- Redis materialized view tradeoffs: [Leapcell: Postgres Materialized Views vs Redis](https://leapcell.io/blog/choosing-between-postgres-materialized-views-and-redis-application-caching)
- Codebase: existing `content_audit_service.py` regex patterns, `position.py` partition model, `metrika.py` page_url storage, `report_service.py` WeasyPrint usage, `user.py` auth model, `xmlproxy_service.py` proxy patterns

---
*Pitfalls research for: SEO Management Platform v2.0 (adding to 35K LOC existing system)*
*Researched: 2026-04-06*
