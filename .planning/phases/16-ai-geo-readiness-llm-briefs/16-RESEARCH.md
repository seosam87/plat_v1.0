# Phase 16: AI/GEO Readiness & LLM Briefs — Research

**Researched:** 2026-04-08
**Domain:** GEO rule-based DOM checks + Anthropic SDK integration + per-user Fernet-encrypted credential + Celery+HTMX polling job pattern
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Anthropic model**
Use `claude-haiku-4-5-20251001` (Haiku 4.5). Hardcoded in `app/services/llm/config.py` as constant `ANTHROPIC_MODEL`. Code, admin docs, and UI near "Generate AI brief" button MUST show visible note: "Powered by Claude Haiku 4.5 — для апгрейда до Sonnet/Opus отредактируй ANTHROPIC_MODEL и пересобери".

**D-02: API key storage — per-user**
Each user stores their own Anthropic API key in their profile. Stored Fernet-encrypted (same pattern as WP credentials and ServiceCredential). New nullable column `anthropic_api_key_encrypted` in `users` table OR separate `user_credentials` table — researcher decision (see recommendation below). Profile page with "Anthropic API Key" field (masked), "Validate" button (cheap test call), "Remove" button. "Generate AI brief" button shown only when `current_user.has_anthropic_key`.

**D-03: LLM output — 3 AI Suggestion blocks**
Single LLM request returns JSON with all 3 sections: (1) Expanded sections — short content drafts under each H2/H3 from template; (2) FAQ block — 5–8 Q&A from the cluster; (3) Title/Meta variants — 3 title + 3 meta description options. Parsed via Pydantic model `LLMBriefEnhancement`. Three collapsible sections in brief template.

**D-04: UX — async Celery + HTMX polling**
Flow: POST → `LLMBriefJob` (status=pending) → Celery task `generate_llm_brief_enhancement(job_id)` → HTMX polling every 2–3 s → preview block with Accept/Regenerate. Accept: POST merges sections into brief. New model `LLMBriefJob`, new router, HTMX polling pattern from `suggest_jobs`.

**D-05: GEO checklist — 9 rule-based checks, weights summing to 100**
| # | Code | Weight | What |
|---|---|---|---|
| 1 | `geo_faq_schema` | 15 | FAQPage JSON-LD |
| 2 | `geo_article_author` | 15 | Article + Author/Person schema |
| 3 | `geo_breadcrumbs` | 10 | BreadcrumbList schema |
| 4 | `geo_answer_first` | 15 | First paragraph after H1 ≤60 words containing a verb |
| 5 | `geo_update_date` | 10 | `time[datetime]` or `dateModified` in JSON-LD |
| 6 | `geo_h2_questions` | 10 | ≥30% H2s are questions |
| 7 | `geo_external_citations` | 10 | ≥2 outbound links to whitelist authoritative domains |
| 8 | `geo_ai_robots` | 10 | robots.txt/meta does not block GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot, Google-Extended |
| 9 | `geo_summary_block` | 5 | Explicit TL;DR/summary block before first H2 |
No ML/NER. BeautifulSoup + regex only.

**D-06: Token usage tracking**
Table `llm_usage` with columns: id, user_id, brief_id (nullable), job_id, model, input_tokens, output_tokens, cost_usd (numeric 10,6), status (success/failed), error_message, created_at. Pricing constants in `app/services/llm/pricing.py`. Profile "Usage" tab: today/7d/30d totals, success rate, last 20 entries. No hard daily limits in MVP. Circuit breaker per-user: 3 consecutive failures → LLM disabled for 15 min. Redis key `llm:cb:user:{id}` with TTL.

### Claude's Discretion

- Whether `anthropic_api_key_encrypted` column goes on `users` table (simpler) or a new `user_credentials` table (extensible for future per-user integrations). CONTEXT says "researcher decides where cleaner."
- GEO score column storage: `pages.geo_score` int column vs computed on-the-fly from AuditResults — researcher decides.
- Exact GEO score computation function (sum of passed-check weights).
- How `geo_ai_robots` check fetches robots.txt (httpx call at audit time vs stored at crawl time).

### Deferred Ideas (OUT OF SCOPE)

- GEO checks beyond MVP-9: `geo_statistics`, `geo_quotations`, `geo_named_entities`, `geo_published_modified`, `geo_lang_attr`, `geo_canonical_self`, `geo_word_count`, `geo_definition_lists`, `geo_llms_txt`
- LLM generation of full page content
- Hard daily/monthly per-user token limits
- Admin UI model override
- Multiple LLM providers (OpenAI/Gemini/Mistral)
- Streaming/SSE for preview
- `/llms.txt` site-level file
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GEO-01 | Every page gets GEO score 0–100 from rule-based DOM checks (FAQPage, Article/Author, BreadcrumbList, answer-first, update date) | D-05 defines 9 checks + weights; BS4+lxml pattern in codebase; score stored as column or computed from AuditResults |
| GEO-02 | GEO checks added to existing `audit_check_definitions` system as `geo_*` codes | `AuditCheckDefinition` model accepts any `code` string; Alembic migration inserts rows; `run_checks_for_page` dispatches via `_CHECK_RUNNERS` dict |
| GEO-03 | GEO readiness visible in audit table with filter by score range and check type | Existing `/audit/{site_id}` route + template extended with geo_score column + filter controls |
| LLM-01 | AI brief generation via Claude API, opt-in, button visible only when API key configured | D-02 per-user key; D-04 Celery+HTMX flow; Anthropic SDK `AsyncAnthropic.messages.create()` |
| LLM-02 | AI brief context includes positions, gap keywords, GEO score, cannibalization, competitors | `ContentBrief` model + `AnalysisSession` already carry keyword/competitor data; GEO score from Phase 16 `pages.geo_score` or AuditResult aggregation |
| LLM-03 | Template brief always generated as fallback; AI brief enhances, never replaces | Template brief path unchanged; `LLMBriefJob` is additive — `generate_brief()` in `brief_service.py` not modified |
| LLM-04 | Hard token cap (input ~2000, output ~800) + circuit breaker on API unavailability | `max_tokens=800` in SDK call; input truncation in prompt builder; Redis circuit breaker key `llm:cb:user:{id}` TTL 900 s |
</phase_requirements>

---

## Summary

Phase 16 has two independent sub-systems that share a single dependency: BeautifulSoup + lxml HTML parsing (already installed). The GEO sub-system extends the existing `audit_check_definitions` / `AuditResult` infrastructure with 9 new `geo_*` check runners and a numeric GEO score computed from check weights. The LLM sub-system introduces the Anthropic Python SDK (`anthropic>=0.39`) for the first time — a new Python package that is NOT yet in `requirements.txt`.

Key facts confirmed against official sources (April 2026):
- Model ID `claude-haiku-4-5-20251001` is valid and current — confirmed from the official Anthropic models overview page.
- Haiku 4.5 pricing: $1.00/MTok input, $5.00/MTok output — confirmed from official pricing page.
- Structured outputs (native JSON schema via `output_config.format`) are **generally available** on Haiku 4.5 — no beta header required as of the current API. Use `output_config={"format": {"type": "json_schema", "schema": ...}}` in `messages.create()`.
- The `anthropic` PyPI package is currently at version 0.49.x (verified from PyPI) — pin `anthropic>=0.39,<1.0` for stability.
- The GEO check `geo_ai_robots` must use updated AI bot user-agent strings confirmed from current crawler documentation (April 2026).

**Primary recommendation:** Structure the phase as 4 plans — (1) GEO check runners + migration + score column, (2) GEO audit table UI + filters, (3) LLM infrastructure (SDK install, model, per-user key, job model, Celery task, circuit breaker), (4) LLM brief UI (button, polling, accept/regenerate, usage tab).

---

## Standard Stack

### Core (already in requirements.txt)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| beautifulsoup4 | >=4.12 | HTML DOM parsing for all 9 GEO checks | Already installed |
| lxml | >=5.0 | BS4 parser backend (faster than html.parser) | Already installed |
| cryptography | >=42.0 | Fernet encryption for API key storage | Already installed, `crypto_service.py` ready |
| redis | >=5.0 | Circuit breaker state storage (TTL key) | Already installed |
| celery | >=5.4 | LLM brief generation job | Already installed |
| httpx | >=0.27 | Fetch `robots.txt` for `geo_ai_robots` check | Already installed |
| pydantic | >=2.7 | `LLMBriefEnhancement` model for JSON parse | Already installed |

### New (must be added)
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| anthropic | >=0.39,<1.0 | Anthropic Messages API client | `AsyncAnthropic` for async Celery tasks; structured JSON output via `output_config` |

**Installation:**
```bash
# Add to requirements.txt:
anthropic>=0.39,<1.0
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native Anthropic structured output | `instructor` library | `instructor` adds a dependency and abstraction layer; native `output_config` is supported on Haiku 4.5 and requires zero extra deps |
| Redis circuit breaker key | DB column `llm_circuit_open_until` | DB requires migration and DB round-trip; Redis TTL key is 1 line of code and auto-expires |
| Column `geo_score` on `pages` | Computed on-the-fly from AuditResults | Computed approach requires aggregation on every page load; column is simpler and matches how `has_toc`/`has_schema` flags are stored |

---

## Architecture Patterns

### Recommended Project Structure (new files)
```
app/
├── services/llm/
│   ├── __init__.py
│   ├── config.py           # ANTHROPIC_MODEL constant
│   ├── pricing.py          # Haiku 4.5 $/MTok constants + compute_cost()
│   ├── geo_checks.py       # 9 pure check functions (no DB, testable)
│   └── llm_service.py      # AsyncAnthropic call, prompt builder, circuit breaker
├── models/
│   └── llm_brief_job.py    # LLMBriefJob + LLMUsage models
├── tasks/
│   └── llm_tasks.py        # generate_llm_brief_enhancement Celery task
└── routers/
    └── llm_briefs.py       # POST /briefs/{brief_id}/llm-enhance, GET polling, POST accept

alembic/versions/
└── 0041_add_geo_score_and_llm_tables.py   # geo_score col + llm_brief_jobs + llm_usage + anthropic_api_key_encrypted

app/templates/
├── analytics/              # extend brief template with AI block
└── profile/
    └── index.html          # Profile page with key input + Usage tab
```

### Pattern 1: GEO Check Runner Extension
**What:** Add 9 new runners to `_CHECK_RUNNERS` dict in `content_audit_service.py` with `geo_*` prefix codes. Each runner takes `(html: str, page_data: dict) -> bool`. GEO score computed as sum of weights for passed checks.
**When to use:** Triggered from existing `run_site_audit` Celery task and as a separate `run_geo_audit(site_id)` task that can be triggered standalone.

```python
# Source: existing content_audit_service.py pattern
# app/services/llm/geo_checks.py

import json, re
from bs4 import BeautifulSoup

def check_geo_faq_schema(html: str, page_data: dict) -> bool:
    """FAQPage JSON-LD present in page."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            if isinstance(data, list):
                data = data[0]
            if data.get("@type") in ("FAQPage",):
                return True
            # Also check @graph
            for item in data.get("@graph", []):
                if item.get("@type") == "FAQPage":
                    return True
        except (json.JSONDecodeError, AttributeError):
            continue
    return False

def check_geo_answer_first(html: str, page_data: dict) -> bool:
    """First paragraph after H1 is ≤60 words and contains a verb."""
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if not h1:
        return False
    # Find first <p> after H1
    el = h1.find_next_sibling()
    while el and el.name not in ("p", "h2", "h3"):
        el = el.find_next_sibling()
    if not el or el.name != "p":
        return False
    text = el.get_text(strip=True)
    words = text.split()
    if len(words) > 60:
        return False
    # Russian + English verb heuristic: contains common verb patterns
    verb_re = re.compile(
        r"\b(является|позволяет|помогает|обеспечивает|представляет|"
        r"is|are|was|were|can|will|has|have|provides|helps|allows)\b",
        re.IGNORECASE,
    )
    return bool(verb_re.search(text))
```

### Pattern 2: GEO Score Column + Upsert
**What:** New nullable `geo_score` int column on `pages` table. Updated after each audit run. Score = sum of weights for `geo_*` check codes with status `pass`.
**Why column not computed:** Matches existing `has_toc`, `has_schema` pattern; avoids aggregation JOIN on audit table in the UI query.

```python
# Alembic migration fragment (0041_...)
op.add_column("pages", sa.Column("geo_score", sa.Integer(), nullable=True))

# Score computation in geo_checks.py
GEO_WEIGHTS = {
    "geo_faq_schema": 15,
    "geo_article_author": 15,
    "geo_breadcrumbs": 10,
    "geo_answer_first": 15,
    "geo_update_date": 10,
    "geo_h2_questions": 10,
    "geo_external_citations": 10,
    "geo_ai_robots": 10,
    "geo_summary_block": 5,
}

def compute_geo_score(results: list[dict]) -> int:
    """Sum weights of passed geo_* checks. Returns 0–100."""
    return sum(
        GEO_WEIGHTS.get(r["check_code"], 0)
        for r in results
        if r["check_code"].startswith("geo_") and r["status"] == "pass"
    )
```

### Pattern 3: Anthropic SDK — Async Celery Task
**What:** Celery task calls `AsyncAnthropic.messages.create()` with `output_config` for guaranteed JSON output. Uses `asyncio.new_event_loop().run_until_complete()` pattern (same as all other async Celery tasks in this codebase).

```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
# app/services/llm/llm_service.py

from anthropic import AsyncAnthropic
import asyncio, json

BRIEF_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "expanded_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["heading", "content"],
                "additionalProperties": False,
            },
        },
        "faq_block": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
                "additionalProperties": False,
            },
        },
        "title_variants": {
            "type": "array",
            "items": {"type": "string"},
        },
        "meta_variants": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["expanded_sections", "faq_block", "title_variants", "meta_variants"],
    "additionalProperties": False,
}

async def call_llm_brief_enhance(api_key: str, prompt: str) -> dict:
    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",   # ANTHROPIC_MODEL constant
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": BRIEF_OUTPUT_SCHEMA,
            }
        },
    )
    return json.loads(response.content[0].text)
```

### Pattern 4: Circuit Breaker (Redis TTL)
**What:** Per-user circuit breaker using Redis key `llm:cb:user:{user_id}` with TTL 900 seconds (15 min). Incremented on each failure; checked before allowing LLM call; reset on success.

```python
# app/services/llm/llm_service.py
import redis as sync_redis

CB_KEY_PREFIX = "llm:cb:user:"
CB_THRESHOLD = 3
CB_TTL_SECONDS = 900

def check_circuit_breaker(r: sync_redis.Redis, user_id: str) -> bool:
    """Returns True if circuit is OPEN (user blocked)."""
    key = f"{CB_KEY_PREFIX}{user_id}"
    val = r.get(key)
    return val is not None and int(val) >= CB_THRESHOLD

def record_cb_failure(r: sync_redis.Redis, user_id: str) -> int:
    """Increment failure count. Returns new count."""
    key = f"{CB_KEY_PREFIX}{user_id}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, CB_TTL_SECONDS)
    return count

def reset_circuit_breaker(r: sync_redis.Redis, user_id: str) -> None:
    r.delete(f"{CB_KEY_PREFIX}{user_id}")
```

### Pattern 5: HTMX Polling for LLM Job
**What:** Copy the `generation_status.html` partial pattern from `client_reports/partials/`. Use `hx-trigger="load delay:3s"` + `hx-swap="outerHTML"` to replace status div every 3 s until done/failed.

```html
<!-- app/templates/briefs/partials/llm_job_status.html -->
{% if status in ('pending', 'running') %}
<div
  hx-get="/ui/briefs/llm-jobs/{{ job_id }}"
  hx-trigger="load delay:3s"
  hx-swap="outerHTML"
  class="...">
  <span>Генерация AI-блоков...</span>
</div>
{% elif status == 'done' %}
  <!-- preview block with expanded_sections, faq_block, title/meta variants -->
  <!-- Accept button: hx-post="/ui/briefs/llm-jobs/{{ job_id }}/accept" -->
  <!-- Regenerate button: hx-post="/briefs/{{ brief_id }}/llm-enhance" -->
{% elif status == 'failed' %}
  <div class="...">Ошибка генерации. {{ error_message }}</div>
{% endif %}
```

### Pattern 6: Per-User API Key Storage
**Recommendation (D-02 discretion):** Add `anthropic_api_key_encrypted` as nullable column to `users` table. Rationale: the codebase has only one type of per-user external credential (Anthropic). A `user_credentials` table would be more extensible but adds an extra table, extra JOIN, and extra model for no immediate gain. If future phases add Yandex Direct per-user tokens or other user credentials, the table can be extracted then via a migration. This matches the existing pattern where `ServiceCredential` is a shared table and WP credentials use a site-level field.

Property `has_anthropic_key` added as a Python `@property` on `User` model:
```python
@property
def has_anthropic_key(self) -> bool:
    return bool(self.anthropic_api_key_encrypted)
```

### Anti-Patterns to Avoid
- **Running GEO checks inline in the request handler:** All HTML fetching + BS4 parsing is slow — always run in a Celery task.
- **Storing Anthropic API key in plaintext:** Must use `crypto_service.encrypt()` / `crypto_service.decrypt()` — same pattern as WP passwords.
- **Calling `Anthropic()` (sync) inside an async context:** Use `AsyncAnthropic` to avoid blocking the event loop. Celery tasks already use the `asyncio.new_event_loop()` pattern — follow that.
- **Using `json_mode` (deprecated):** The old `output_format` beta header is superseded by `output_config.format`. Use the current GA API shape.
- **Mixing GEO score computation with audit result save:** Keep `compute_geo_score(results)` as a pure function; call it after `save_audit_results()`, then `UPDATE pages SET geo_score = X WHERE url = Y`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-LD extraction | Custom regex | `json.loads()` on `<script type="application/ld+json">` tags found via BS4 | Regex breaks on nested/escaped JSON; BS4 tag finder is reliable |
| JSON schema enforcement on LLM output | Try/except JSON parse with retries | `output_config.format.json_schema` in messages.create | Native constrained decoding — no parse errors, no retries needed on Haiku 4.5 |
| HTTP robots.txt fetch timeout handling | Custom timeout loop | `httpx.AsyncClient(timeout=5.0).get(robots_url)` with `.raise_for_status()` catch | httpx already handles timeouts and retries; CONTEXT says httpx is the stack HTTP client |
| Circuit breaker with rolling window | Custom counter list in Redis | Simple `INCR` + `EXPIRE` pattern | Rolling window adds complexity with no benefit for a 3-strike rule; TTL reset is equivalent |
| Async SDK client lifecycle in Celery | Manual client pool | `AsyncAnthropic(api_key=...)` per task call | Celery tasks are separate processes; client is cheap to construct per task |

---

## GEO Check Implementation Details

### AI Robot User-Agent Strings (confirmed April 2026)

The `geo_ai_robots` check must look for these exact tokens in `robots.txt`:

| Bot | User-Agent token | Owner |
|-----|-----------------|-------|
| GPTBot | `GPTBot` | OpenAI (training) |
| OAI-SearchBot | `OAI-SearchBot` | OpenAI (search features) |
| ChatGPT-User | `ChatGPT-User` | OpenAI (on-demand) |
| anthropic-ai | `anthropic-ai` | Anthropic (training) |
| ClaudeBot | `ClaudeBot` | Anthropic (citations) |
| Claude-SearchBot | `Claude-SearchBot` | Anthropic (search, new 2025) |
| PerplexityBot | `PerplexityBot` | Perplexity |
| Google-Extended | `Google-Extended` | Google (Gemini training) |

**Check logic:** fetch `https://{site_domain}/robots.txt` via httpx (timeout 5 s, fail-open). Look for `Disallow: /` under any of the above `User-agent:` lines. If any of the 8 bots has a blanket disallow, return False (page/site is blocking AI crawlers). If robots.txt is unreachable, return True (fail-open — assume not blocked).

**Important:** The check runs at the site level (robots.txt is site-wide), not per-page. Cache the robots.txt fetch result per site_id per audit run (in-memory dict within the Celery task scope) to avoid 8 fetches per page.

### GEO Check: External Citations Whitelist

For `geo_external_citations` (≥2 outbound links to authoritative domains), use a hardcoded whitelist of patterns:

```python
CITATION_DOMAINS = {
    # Russian authoritative
    "wikipedia.org", "rospotrebnadzor.ru", "government.ru", "kremlin.ru",
    "mos.ru", "rosstat.gov.ru", "cbr.ru", "минздрав.рф", "minobrnauki.gov.ru",
    # International authoritative
    "who.int", "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov",
    "scholar.google.com", "nih.gov", "cdc.gov",
    # Education (TLD patterns)
    # Any .edu, .gov, .ac.uk domain counts
}
CITATION_TLD_PATTERNS = (".edu", ".gov", ".ac.uk", ".gov.ru", ".edu.ru")
```

Function checks: does each outbound link's domain end with an authoritative TLD, OR is its hostname in `CITATION_DOMAINS`?

### GEO Score Storage Recommendation

**Store `geo_score` as column on `pages` table.** Reasons:
1. Consistent with existing boolean flags (`has_toc`, `has_schema`) — same pattern.
2. Enables direct `ORDER BY geo_score` in audit table without a subquery.
3. Filter by score range (`WHERE geo_score < 50`) is a simple indexed comparison.
4. Score is updated on each audit run alongside `AuditResult` upserts.

Alternative (on-the-fly from AuditResults) requires a complex aggregation JOIN with CASE WHEN per check code — significantly more query complexity for the audit table.

---

## Common Pitfalls

### Pitfall 1: GEO checks called without HTML
**What goes wrong:** The existing audit task tries to fetch HTML from WP (`_fetch_wp_content`) — this can return an empty string if WP is unreachable. GEO BS4 checks on `""` will return False for all checks, giving a score of 0 incorrectly.
**Why it happens:** Same root cause as existing audit — crawl stores metadata but not raw HTML.
**How to avoid:** In the GEO check runner, if `html == ""`, emit all 9 GEO checks as `status="skip"` (new status value) rather than `"fail"`, and set `geo_score = None` instead of 0. This keeps the audit table accurate and distinguishes "couldn't fetch" from "checked and failed".
**Warning signs:** All pages showing geo_score = 0 after audit run.

### Pitfall 2: Anthropic structured outputs beta vs GA confusion
**What goes wrong:** Code uses the deprecated `output_format` parameter or the `anthropic-beta: structured-outputs-2025-11-13` header — works but is marked for eventual removal.
**Why it happens:** Older tutorials and Stack Overflow answers still show the beta API shape.
**How to avoid:** Use `output_config={"format": {"type": "json_schema", "schema": ...}}` — the GA shape confirmed from official docs (April 2026). The old beta header still works as a transition but do not write new code against it.

### Pitfall 3: Celery task with sync `Anthropic()` client
**What goes wrong:** Using `anthropic.Anthropic()` (synchronous) inside a Celery task that wraps an async event loop. The sync client makes blocking HTTP calls but won't deadlock in this pattern — however it bypasses asyncio entirely and is inconsistent with the rest of the codebase.
**How to avoid:** Use `asyncio.new_event_loop().run_until_complete(async_fn())` with `AsyncAnthropic` — same pattern as all other async Celery tasks (`suggest_tasks.py`, `audit_tasks.py`).

### Pitfall 4: JSON-LD extraction missing `@graph` wrapper
**What goes wrong:** Many WordPress SEO plugins (Yoast, RankMath) wrap all schema in a single `@graph` array: `{"@context": "...", "@graph": [{"@type": "FAQPage", ...}]}`. Checking only `data["@type"]` misses this pattern.
**How to avoid:** In each JSON-LD checker, check both `data.get("@type")` and iterate `data.get("@graph", [])`.

### Pitfall 5: Per-user circuit breaker not isolated
**What goes wrong:** If the circuit breaker key is global (not per-user), one user with an invalid key blocks LLM access for all users.
**How to avoid:** Key format is `llm:cb:user:{user_id}` — `user_id` is the UUID string. Never use a global `llm:cb:global` key.

### Pitfall 6: robots.txt check blocks entire audit on timeout
**What goes wrong:** `geo_ai_robots` makes an HTTP request to the site's `robots.txt`. If the site is slow or the domain is unreachable, this times out and stalls the audit task.
**How to avoid:** Use `httpx.get(url, timeout=5.0)` with a broad exception catch that returns `True` (fail-open) on any error. Cache the result in a local dict for the duration of the Celery task to avoid repeated fetches.

### Pitfall 7: Alembic migration order
**What goes wrong:** Adding `geo_score` column to `pages` and inserting `geo_*` rows into `audit_check_definitions` in the same migration causes FK issues if run out of order with the existing sequence.
**How to avoid:** Use a single migration file `0041_add_geo_score_and_llm_tables.py` that: (1) adds column `pages.geo_score`, (2) adds column `users.anthropic_api_key_encrypted`, (3) creates `llm_brief_jobs` table, (4) creates `llm_usage` table, (5) inserts 9 `audit_check_definitions` rows for `geo_*` codes.

---

## Code Examples

### Anthropic SDK basic async call (GA structured output)
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from anthropic import AsyncAnthropic
import json

async def call_anthropic(api_key: str, prompt: str, schema: dict, max_tokens: int = 800) -> dict:
    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )
    # response.usage.input_tokens, response.usage.output_tokens available
    return json.loads(response.content[0].text), response.usage
```

### Fernet encryption of API key (existing pattern)
```python
# Source: app/services/crypto_service.py (existing)
from app.services.crypto_service import encrypt, decrypt

# Store:
user.anthropic_api_key_encrypted = encrypt(raw_api_key)
# Retrieve:
raw_key = decrypt(user.anthropic_api_key_encrypted)
```

### GEO score computation
```python
# app/services/llm/geo_checks.py
GEO_WEIGHTS: dict[str, int] = {
    "geo_faq_schema": 15,
    "geo_article_author": 15,
    "geo_breadcrumbs": 10,
    "geo_answer_first": 15,
    "geo_update_date": 10,
    "geo_h2_questions": 10,
    "geo_external_citations": 10,
    "geo_ai_robots": 10,
    "geo_summary_block": 5,
}  # sum = 100

def compute_geo_score(audit_results: list[dict]) -> int:
    return sum(
        GEO_WEIGHTS[r["check_code"]]
        for r in audit_results
        if r["check_code"] in GEO_WEIGHTS and r["status"] == "pass"
    )
```

### Prompt builder (input token budget ~2000)
```python
def build_brief_enhancement_prompt(brief: ContentBrief, geo_score: int | None) -> str:
    keywords = [k["phrase"] for k in (brief.keywords_json or [])[:20]]
    headings = [
        f"H{h['level']}: {h['text']}"
        for h in (brief.headings_json or [])[:10]
    ]
    prompt = f"""Ты SEO-копирайтер. Расширь шаблонное ТЗ для страницы.

Тема: {brief.title}
URL: {brief.target_url or '—'}
GEO-score: {geo_score if geo_score is not None else 'н/д'} / 100
Ключевые слова: {', '.join(keywords)}
Структура заголовков:
{chr(10).join(headings)}

Верни JSON согласно схеме. Для каждого H2/H3 напиши 2–3 предложения (expanded_sections).
Добавь 5–7 вопросов FAQ (faq_block). Предложи 3 варианта title и 3 meta description.
Пиши на русском языке, стиль — профессиональный SEO."""
    # Truncate if needed (rough token estimate: 4 chars ≈ 1 token, target <2000 tokens → <8000 chars)
    if len(prompt) > 7500:
        prompt = prompt[:7500] + "\n[обрезано]"
    return prompt
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Anthropic beta structured outputs (`output_format` + beta header) | GA `output_config.format.json_schema` — no beta header | Late 2025 (GA release) | Write new code against GA shape; old beta shape still works as transition |
| `claude-3-5-haiku-20241022` (Haiku 3.5 — deprecated) | `claude-haiku-4-5-20251001` (Haiku 4.5) | Oct 2025 | Haiku 3 deprecated April 19, 2026 — do not use |
| Per-site service credentials (global) | Per-user API keys (Fernet encrypted on `users` table) | Phase 16 introduces | Billing isolated per user |

**Deprecated/outdated:**
- `claude-3-haiku-20240307`: deprecated, retires April 19, 2026 — must not be used.
- `output_format` beta header: still works but superseded by `output_config.format`.

---

## Open Questions

1. **`geo_ai_robots` — per-page check or per-site check?**
   - What we know: robots.txt is served at the domain root and applies site-wide; there are no per-page robots.txt files.
   - What's unclear: Should each page row in `audit_results` get an individual `geo_ai_robots` result, or should the check be run once and applied to all pages?
   - Recommendation: Run once per audit run (fetch robots.txt once, cache in task scope), but write one `AuditResult` row per page so the existing filter/score system works uniformly. This is consistent — the check result is the same value for all pages of a site.

2. **`geo_answer_first` verb detection — Russian coverage**
   - What we know: A regex list of common Russian verbs is feasible but incomplete.
   - What's unclear: Whether a naive regex catches enough cases without too many false positives.
   - Recommendation: Use a whitelist of ~20 high-frequency Russian verbs + common English verbs. Mark as best-effort; the spec says "contains a verb" not "parse morphology." This is intentionally approximate — no NER/spaCy.

3. **LLMBriefJob model location**
   - What we know: `ContentBrief` lives in `app/models/analytics.py`.
   - Recommendation: Create `app/models/llm_brief_job.py` as a standalone file (parallel to `suggest_job.py`) to keep the LLM models isolated and easy to find.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` Python package | LLM Briefs | Not installed | — | Must add to `requirements.txt` before any LLM code is written |
| Redis | Circuit breaker + Celery | Available | 5.0.x (in requirements.txt) | — |
| beautifulsoup4 | GEO DOM checks | Available | >=4.12 (in requirements.txt) | — |
| lxml | GEO check BS4 parser | Available | >=5.0 (in requirements.txt) | — |
| httpx | robots.txt fetch | Available | >=0.27 (in requirements.txt) | — |
| cryptography (Fernet) | API key encryption | Available | >=42.0 (in requirements.txt) | — |
| PostgreSQL | DB migrations | Available | 16.x (Docker Compose) | — |

**Missing dependencies with no fallback:**
- `anthropic>=0.39,<1.0` — must be added to `requirements.txt` in Wave 0 (Plan 1, Task 1).

**Missing dependencies with fallback:**
- None.

---

## Project Constraints (from CLAUDE.md)

| Constraint | Impact on Phase 16 |
|------------|-------------------|
| FastAPI 0.115 + Pydantic v2 | Use `@field_validator`, not `@validator`; use Pydantic v2 for `LLMBriefEnhancement` model |
| SQLAlchemy 2.0 async + `AsyncSession` | All new DB functions use `async_session_factory()` pattern |
| Celery 5.4 | New `llm_tasks.py` uses `@celery_app.task(bind=True, max_retries=3, ...)` |
| Alembic for all schema changes | Migration `0041_...` required before any `geo_score` or `llm_brief_jobs` references in code |
| Fernet encryption for credentials | `crypto_service.encrypt()`/`decrypt()` for `anthropic_api_key_encrypted` |
| loguru for logging | Use `logger.info/error/warning` from loguru in all new services |
| pytest + pytest-asyncio | Tests in `tests/test_geo_checks.py`, `tests/test_llm_service.py` — pure function tests |
| service layer coverage > 60% | GEO check pure functions are trivially testable; cover all 9 checkers |
| UI pages < 3 s | GEO score is pre-computed column, not live aggregation; audit table loads fast |
| LLM long operations are always async via Celery | "Generate AI brief" POST dispatches Celery task immediately; never blocks request handler |
| HTMX 2.0 | Polling uses `hx-trigger="load delay:3s"` — valid HTMX 2.0 syntax (same as existing client_reports pattern) |
| No `on_event` startup/shutdown | Any startup code (e.g., loading pricing constants) uses `lifespan=` parameter pattern |

---

## Sources

### Primary (HIGH confidence)
- [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview) — confirmed `claude-haiku-4-5-20251001` model ID, pricing $1/$5 per MTok, context window 200k
- [Anthropic Structured Outputs (GA)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — confirmed `output_config.format.json_schema` GA syntax for Haiku 4.5; beta header superseded
- `app/services/content_audit_service.py` — existing `_CHECK_RUNNERS` dict pattern; `save_audit_results()` upsert pattern
- `app/services/crypto_service.py` — Fernet encrypt/decrypt pattern for API key storage
- `app/models/audit.py` — `AuditCheckDefinition` schema (code, weight not stored in model — stored as migration-seeded rows)
- `app/tasks/audit_tasks.py` — `asyncio.new_event_loop()` Celery task pattern to follow
- `app/templates/client_reports/partials/generation_status.html` — HTMX polling `hx-trigger="load delay:3s"` template pattern

### Secondary (MEDIUM confidence)
- [Momentic: AI Search Crawlers (2025)](https://momenticmarketing.com/blog/ai-search-crawlers-bots) — AI bot user-agent strings (verified against ALM Corp Anthropic bots article)
- [ALM Corp: Anthropic Three-Bot Framework](https://almcorp.com/blog/anthropic-claude-bots-robots-txt-strategy/) — Claude-SearchBot as third Anthropic bot
- [PyPI anthropic package](https://pypi.org/project/anthropic/) — current version 0.49.x; pin `>=0.39,<1.0`

### Tertiary (LOW confidence)
- Princeton GEO study (Aggarwal et al., 2024) — theoretical basis for `external_citations` check weight; arxiv URL not confirmed; CONTEXT.md cites it as motivation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing packages verified in requirements.txt; Anthropic SDK version confirmed on PyPI
- Architecture patterns: HIGH — GEO check pattern directly mirrors existing `_CHECK_RUNNERS` dict; LLM Celery pattern mirrors `suggest_tasks.py`; HTMX polling pattern mirrors `generation_status.html`
- Anthropic API: HIGH — model ID, pricing, and structured output syntax confirmed from official docs (April 2026)
- AI bot user-agents: MEDIUM — confirmed from multiple 2025 sources; Claude-SearchBot is new (2025) and may evolve
- GEO check heuristics (answer_first verb regex, citation domain whitelist): MEDIUM — implementable but intentionally approximate per spec

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (Anthropic model IDs and pricing stable for ~30 days; AI bot user-agents may evolve faster)
