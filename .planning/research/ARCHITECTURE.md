# Architecture: v2.0 Integration Design

**Domain:** SEO Management Platform — v2.0 feature integration with existing FastAPI + Celery + PostgreSQL stack
**Researched:** 2026-04-06
**Confidence:** HIGH — based on direct inspection of the existing codebase (35,402 LOC)

---

## Context: Existing Architecture Snapshot

Before detailing integrations, the key existing components to preserve and extend:

```
app/
├── models/         31 model files (audit.py, gap.py, keyword.py, position.py, analytics.py, user.py, ...)
├── services/       55 service files (brief_service.py, report_service.py, gap_service.py, ...)
├── routers/        25 router files
├── tasks/          12 Celery task modules (3 queues: crawl, wp, default)
├── templates/      16 template directories + base.html, login.html
├── auth/           jwt.py, password.py, dependencies.py
├── navigation.py   NAV_SECTIONS — 6 sidebar sections, pattern-based active state
└── config.py       Pydantic Settings — 30+ env vars
```

**Critical invariants to preserve:**
- Celery uses sync SQLAlchemy (`get_sync_db()`); FastAPI uses async SQLAlchemy (`AsyncSession`)
- All schema changes via Alembic migrations — never direct DB edits
- Service layer receives a `db` session — it does not own session lifecycle
- `AuditCheckDefinition` drives configurable content audit checks
- `keyword_positions` is monthly range-partitioned — any aggregate query must use the correct pattern
- `navigation.py` `NAV_SECTIONS` is the single source of truth for sidebar links

---

## Feature Integration Analysis

### 1. Quick Wins / Dead Content / Impact Scoring / Growth Opportunities

**Classification: Views over existing tables, not new storage**

All four features are analytics views computed from data that already exists:
- `keyword_positions` — position history, delta, position ranges
- `audit_results` + `audit_check_definitions` — per-page check failures
- `crawl_pages` — traffic-bearing page inventory (via Metrika integration)
- `gap_keywords` — competitor gap data with `potential_score`
- `cannibalization` records — existing cannibalization detection output
- Metrika sessions data (already in `metrika` tables from Phase 4)

**New models needed:** None for core logic. One optional model per feature for persisting computed scores if caching across sessions is required (see below).

**New services needed:**

| Service | What it does | Extends or new? |
|---------|-------------|-----------------|
| `insights_service.py` | Cross-cutting queries: join positions + audit_results + metrika sessions for Quick Wins | **New** — aggregates across 3+ services |
| `dead_content_service.py` | Pages with 0 Metrika sessions AND declining positions | **New** — extend `metrika_service.py` + `position_service.py` logic |
| `impact_scoring_service.py` | Rank audit errors by (frequency of occurrence × traffic weight of affected pages) | **New** — extend `audit_service.py` |
| `opportunities_service.py` | Aggregate: gap keywords + position 11–30 + cannibalization victims | **New** — thin orchestrator over existing services |

**Data queries pattern (no new tables):**

Quick Wins query:
```sql
-- Pages in positions 4–20 AND missing TOC/schema/links
SELECT k.phrase, k.target_url, kp.position, ar.check_code
FROM keywords k
JOIN keyword_positions kp ON kp.keyword_id = k.id
JOIN audit_results ar ON ar.page_url = kp.url AND ar.site_id = k.site_id
WHERE k.site_id = :sid
  AND kp.position BETWEEN 4 AND 20
  AND ar.status = 'fail'
  AND ar.check_code IN ('toc_present', 'schema_present', 'internal_links_ok')
ORDER BY kp.position ASC
```

Dead Content query joins `metrika_sessions` aggregates with `keyword_positions` latest check.

Impact Scoring: `audit_results` failures grouped by `check_code`, each URL weighted by its Metrika session count.

**Optional caching model** (if recalculation is too slow at 100 sites):
```python
class InsightCache(Base):
    __tablename__ = "insight_cache"
    site_id / insight_type / computed_at / payload (JSON) / expires_at
```
Use Redis instead if TTL-based invalidation is sufficient (preferred — avoids another migration).

**Redis cache pattern for insight results:**
```python
CACHE_KEY = "insights:{site_id}:{insight_type}"
TTL = 3600  # 1 hour; invalidate on new position check or crawl completion
```

**Router placement:** New router `routers/insights.py` with routes:
- `GET /insights/{site_id}/quick-wins`
- `GET /insights/{site_id}/dead-content`
- `GET /insights/{site_id}/impact-scores`
- `GET /insights/{site_id}/opportunities`

All return HTMX fragments; heavy queries run in < 3s with proper indexes (positions already indexed).

**Batch-fix integration:** Quick Wins "batch fix" button dispatches to existing `wp_content_tasks` queue via existing `WpContentJob` model. No new task type needed — reuse the existing WP pipeline dispatch pattern.

---

### 2. AI/GEO Readiness

**Classification: Extend existing `AuditCheckDefinition` system with a new check category**

The existing audit system is built for exactly this use case. `AuditCheckDefinition` has:
- `code` — string identifier (e.g. `"geo_faq_present"`, `"geo_structured_data"`)
- `applies_to` — `ContentType` enum (informational / commercial)
- `severity` — warning / error
- `auto_fixable` — boolean

**What changes:**
1. Add new `AuditCheckDefinition` seed rows with `code` values prefixed `geo_` (via Alembic data migration, not a schema migration)
2. Add detection functions to `content_audit_service.py` for each GEO check
3. Register new check codes in the `_CHECK_RUNNERS` dict (already exists in `content_audit_service.py`)
4. Add a GEO score aggregation function to `audit_service.py`: sum passed / total geo checks × 100

**New GEO check codes to seed:**
- `geo_faq_schema` — FAQPage JSON-LD present
- `geo_speakable_schema` — Speakable schema present (voice search)
- `geo_structured_answer` — Page has a direct answer paragraph (H2 + 2–3 sentence summary)
- `geo_citation_friendly` — Page cites sources (presence of external links with rel=nofollow)
- `geo_conversational_headings` — H2/H3 phrased as questions
- `geo_word_count_adequate` — Word count >= threshold for informational pages

**No new model needed.** `AuditResult` stores pass/fail per page per check code — `geo_` codes write there exactly like existing checks.

**New display:** Add a "GEO Readiness" tab or summary card to the existing `/audit/{site_id}` page — filter `audit_results` by `check_code LIKE 'geo_%'`. No new URL needed unless a standalone scoreboard is desired.

---

### 3. Client PDF — "Client Instructions"

**Classification: New WeasyPrint template, extend existing `report_service.py`**

The existing `report_service.py` already has `generate_pdf_report()` which takes `report_type: str` and dispatches to different Jinja2 templates (`reports/brief.html` or `reports/detailed.html`). The templates directory has `app/templates/reports/`.

**What changes:**
1. New Jinja2 template: `app/templates/reports/client_instructions.html` — designed for non-technical site owners; plain language, branded
2. Extend `generate_pdf_report()` with `report_type="client_instructions"` case
3. New data aggregator function in `report_service.py`: `client_report_data(db, site_id)` — collects top wins, issues, recommended actions, no technical jargon
4. New route in `routers/reports.py`: `GET /reports/{site_id}/client-instructions/pdf`

**Template design considerations:**
- Site owner audience — no SEO jargon; "Your page appears on page 2 of search results" not "position 14"
- Include: top 5 ranking pages, top 3 recommended fixes, recent wins (position improvements)
- Reuse the existing WeasyPrint executor pattern: `loop.run_in_executor(None, _render_pdf, html)`
- Separate CSS from technical reports (client-friendly fonts, larger text, site logo placeholder)

**No new model needed.** Report generation is stateless — data comes from existing tables on demand.

**Optional: Report history model** (if clients need to access past reports):
```python
class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    site_id / report_type / generated_at / file_path / generated_by_user_id
```
Defer this unless explicitly needed — generating on demand covers 90% of use cases.

---

### 4. Keyword Suggest

**Classification: New Celery task in `default` queue, Redis cache for results**

Keyword suggest involves external API calls (Google Suggest / Yandex Wordstat autocomplete), which are latency-variable and rate-limited. Pattern: Celery task with Redis result caching, not inline in the request.

**New task module:** `app/tasks/suggest_tasks.py`

```python
@celery_app.task(
    name="app.tasks.suggest_tasks.fetch_keyword_suggestions",
    bind=True,
    max_retries=3,
    queue="default",
)
def fetch_keyword_suggestions(self, site_id: str, seed_phrase: str, engines: list[str]) -> dict:
    ...
```

**New service:** `app/services/suggest_service.py`
- `get_google_suggestions(phrase)` — calls `https://suggestqueries.google.com/complete/search?q={phrase}&hl=ru&gl=ru&output=json`
- `get_yandex_wordstat_suggestions(phrase)` — calls Yandex Wordstat API (if token configured) or Yandex suggest endpoint
- `cache_suggestions(site_id, phrase, results)` — write to Redis with TTL
- `get_cached_suggestions(site_id, phrase)` — read from Redis before triggering task

**Cache strategy:**
```
Key:  "suggest:{seed_phrase_hash}"   (no site_id — suggestions are phrase-level, not site-level)
TTL:  86400 (24h) — suggest results are stable within a day
Size: ~200 bytes per phrase (20 suggestions × 10 bytes avg) — negligible Redis memory
```

**No new DB model needed for suggest results** — Redis cache is sufficient. If users want to save suggestions to their keyword list, they use the existing keyword import flow (POST to `/keywords/{site_id}/add`).

**Config additions** (`app/config.py`):
```python
YANDEX_WORDSTAT_TOKEN: str = ""  # optional; fall back to suggest API if not set
SUGGEST_CACHE_TTL: int = 86400
```

**UI flow:** User types in keyword search box → HTMX `hx-trigger="keyup changed delay:500ms"` POSTs to `/suggest?q={phrase}` → returns suggestions as HTMX fragment → user clicks to add to keyword group.

**Register in celery_app.py:**
```python
include=[..., "app.tasks.suggest_tasks"]
```
No new queue needed — `default` queue handles this. Tasks complete in < 5 seconds.

---

### 5. LLM Briefs (AI-generated content briefs)

**Classification: New Celery task (default queue), extend `ContentBrief` model, new config keys**

The existing `ContentBrief` model and `brief_service.py` are the foundation. LLM briefs extend this by adding an AI-generated section to the same model, rather than creating a parallel model.

**Model extension** (Alembic migration required):
```python
# Add to ContentBrief model
llm_brief_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI output
llm_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
llm_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "claude-3-5-haiku"
llm_prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
llm_completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

**New Celery task** in `default_tasks.py` (or new `llm_tasks.py` if scope grows):
```python
@celery_app.task(
    name="app.tasks.default_tasks.generate_llm_brief",
    bind=True,
    max_retries=2,  # LLM calls are expensive; 2 retries, not 3
    queue="default",
    soft_time_limit=120,
)
def generate_llm_brief(self, brief_id: str) -> dict:
    # Loads ContentBrief from DB
    # Constructs prompt from existing brief fields (keywords, headings, competitor data)
    # Calls Anthropic API via httpx (sync client in Celery context)
    # Writes result back to ContentBrief.llm_brief_text
```

**Token budget management:**
- Construct prompt from existing brief fields (already structured data — keywords JSON, headings JSON, competitor summary)
- Prompt template: `~500 tokens input`, target `~1500 tokens output` → total `~2000 tokens per brief` via claude-3-5-haiku
- Hard limit: `max_tokens=2000` in API call; truncate input keywords if over budget
- Log `prompt_tokens` + `completion_tokens` to `ContentBrief` for cost tracking

**API key storage:**
```python
# app/config.py
ANTHROPIC_API_KEY: str = ""  # empty = LLM briefs disabled
LLM_BRIEF_MODEL: str = "claude-3-5-haiku-20241022"
LLM_BRIEF_MAX_TOKENS: int = 2000
```

**Never store API key in DB.** It lives in `.env` → `Settings` → passed to task via config. The task checks `settings.ANTHROPIC_API_KEY` and raises a non-retryable error if empty.

**Opt-in gate:** UI shows "Generate AI brief" button only if `settings.ANTHROPIC_API_KEY != ""`. Route handler checks this before dispatching task.

**HTTP client in Celery (sync context):**
```python
import httpx

def _call_anthropic(prompt: str) -> tuple[str, int, int]:
    with httpx.Client(timeout=90) as client:
        r = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={"model": settings.LLM_BRIEF_MODEL, "max_tokens": settings.LLM_BRIEF_MAX_TOKENS, "messages": [...]},
        )
        r.raise_for_status()
        data = r.json()
        return data["content"][0]["text"], data["usage"]["input_tokens"], data["usage"]["output_tokens"]
```

**No streaming needed** — brief generation is a background task, not a real-time UI update.

---

### 6. 2FA (TOTP)

**Classification: User model extension + auth router changes + no middleware changes**

TOTP 2FA is an authentication layer change, not a middleware change. The existing JWT flow remains intact — 2FA adds a verification step between password check and token issuance.

**Model extension** (Alembic migration):
```python
# Add to User model
totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Fernet-encrypted
totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
totp_backup_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)  # hashed backup codes
```

**Encrypt TOTP secret:** Use existing `FERNET_KEY` (already in `crypto_service.py`) — do not add a new encryption key. TOTP secret is sensitive; store encrypted, decrypt only during verification.

**Auth flow change** (`routers/auth.py`):
```
POST /auth/token (existing):
  1. Verify email + password (unchanged)
  2. IF user.totp_enabled:
     a. Return {"status": "totp_required", "partial_token": <short-lived JWT>}
     b. UI shows TOTP input form
  3. POST /auth/token/totp with {partial_token, totp_code}:
     a. Validate partial_token (sub + exp, role="totp_pending")
     b. Verify TOTP code against decrypted secret (pyotp library)
     c. Return full access token
  4. ELSE: return full access token directly (unchanged for users without 2FA)
```

**New library needed:** `pyotp` — pure Python TOTP/HOTP implementation, no system deps, ~15 KB.
```bash
# Add to requirements
pyotp>=2.9.0
```

**New routes in `routers/auth.py`:**
- `POST /auth/2fa/setup` — generate secret, return QR code URI, return backup codes
- `POST /auth/2fa/enable` — verify first TOTP code, set `totp_enabled=True`
- `POST /auth/2fa/disable` — verify password + TOTP code, set `totp_enabled=False`
- `POST /auth/token/totp` — complete login with TOTP code

**No JWT middleware changes.** The existing `get_current_user` dependency in `auth/dependencies.py` does not need to change. TOTP is validated during login, not on every request.

**QR code generation:** Use `qrcode` library (pure Python) to generate a QR code as base64 PNG for the setup UI. No file storage needed.
```bash
qrcode[pil]>=7.4.2
```

**Migration impact:** Single Alembic migration adding 3 nullable columns to `users` table. No data migration needed — `totp_enabled=False` default means all existing users are unaffected.

**Backup codes:** Generate 8 × 8-character alphanumeric codes at setup. Hash with bcrypt (reuse `passlib` already in stack) before storing. Single-use — mark used in `totp_backup_codes` JSON by nulling out the used entry.

---

### 7. In-App Notifications

**Classification: New model + Redis pub/sub for delivery + polling endpoint**

**New model** (Alembic migration):
```python
class Notification(Base):
    __tablename__ = "notifications"

    id: UUID PK
    user_id: UUID FK(users.id, CASCADE)
    site_id: UUID | None FK(sites.id, SET NULL) nullable  # context link
    type: str(50)  # "position_drop", "crawl_complete", "task_created", "llm_brief_ready", ...
    title: str(255)
    body: str(1000) nullable
    link_url: str(500) nullable  # "/ui/positions/{site_id}" etc.
    is_read: bool default False
    created_at: datetime
    read_at: datetime nullable
```

**Delivery mechanism: DB polling (not Redis pub/sub)**

Redis pub/sub is elegant but adds complexity and requires a persistent connection or SSE endpoint. For this user scale (< 20 users), HTMX polling is simpler and sufficient:

```
HTMX polling: hx-get="/ui/notifications/unread-count" hx-trigger="every 30s"
```

Endpoint reads `COUNT(*) WHERE user_id=:uid AND is_read=False` — single indexed query, < 1ms. Acceptable at 30-second intervals.

Full notification list loaded on bell icon click via HTMX partial. Mark-all-read via `POST /ui/notifications/mark-read`.

**Redis pub/sub is NOT recommended here** because:
1. Requires SSE or WebSocket endpoint (not currently in the stack)
2. Connection state management adds complexity
3. 30s polling is acceptable UX for non-critical notifications

**Integration with existing Telegram alerts:**
- Notifications and Telegram alerts are parallel delivery channels, not a hierarchy
- Create a `notification_service.create_notification()` helper called alongside `telegram_service.send_alert()`
- Existing `telegram_service.py` is unchanged; notification creation is additive
- Pattern: in `position_tasks.py` where Telegram is already called, also call `create_notification()`

```python
# In position_tasks.py (existing Telegram call location)
from app.services.notification_service import create_notification_for_site_users

# After writing positions and sending Telegram:
create_notification_for_site_users(
    db=db,
    site_id=site_id,
    type="position_drop",
    title=f"Позиция упала: {keyword_phrase}",
    body=f"Позиция {prev_pos} → {new_pos}",
    link_url=f"/ui/positions/{site_id}",
)
```

**Notification types to implement initially:**
- `position_drop` — triggered from `position_tasks.py`
- `crawl_complete` — triggered from `crawl_tasks.py`
- `llm_brief_ready` — triggered from `default_tasks.generate_llm_brief`
- `task_assigned` — triggered from `task_service.py`

**Cleanup:** Add a periodic Celery Beat task to delete notifications older than 30 days:
```python
@celery_app.task(name="app.tasks.default_tasks.cleanup_old_notifications", queue="default")
def cleanup_old_notifications():
    # DELETE FROM notifications WHERE created_at < NOW() - INTERVAL '30 days'
```

---

### 8. UI Placement — Sidebar Integration

**Existing sidebar:** 6 sections in `navigation.py` `NAV_SECTIONS`:
1. Обзор (Overview)
2. Сайты (Sites)
3. Позиции и ключи (Positions & Keywords)
4. Аналитика (Analytics)
5. Контент (Content)
6. Настройки (Settings)

**Placement decisions:**

| Feature | Section | Placement Rationale |
|---------|---------|---------------------|
| Quick Wins | Аналитика | Joins positions + audit data — fits analytics section; add child `{"id": "quick-wins", "label": "Быстрые победы", "url": "/insights/{site_id}/quick-wins"}` |
| Dead Content | Аналитика | Same rationale — content health is an analytics question; add `{"id": "dead-content", "label": "Мёртвый контент", "url": "/insights/{site_id}/dead-content"}` |
| Impact Scoring | Аналитика or Контент | Show inline on Audit page (`/audit/{site_id}`) as a sort option — no new nav item needed; errors sorted by traffic impact |
| Growth Opportunities | Аналитика | Consolidates gap + lost positions + cannibalization; add `{"id": "opportunities", "label": "Точки роста", "url": "/insights/{site_id}/opportunities"}` |
| AI/GEO Readiness | Контент | Extension of audit — add as tab on `/audit/{site_id}` or child `{"id": "geo-readiness", "label": "AI/GEO готовность", "url": "/audit/{site_id}/geo"}` |
| Client PDF | Аналитика | Add to reports section or as button on site overview; no new nav item |
| Keyword Suggest | Позиции и ключи | Inline in keyword add/import flow; no separate nav item; surface as "Подсказки" in keyword input |
| LLM Briefs | Контент | Extend existing Briefs page — add "AI-бриф" button on existing brief view |
| 2FA | Настройки | Add `{"id": "security", "label": "Безопасность (2FA)", "url": "/ui/settings/security"}` to Settings section |
| Notifications | Header (global) | Bell icon in header/nav bar — not a sidebar section. Notification bell is global UI chrome |

**Suggested `NAV_SECTIONS` additions:**

In `Аналитика` section, add children:
```python
{"id": "quick-wins", "label": "Быстрые победы", "url": "/insights/{site_id}/quick-wins"},
{"id": "dead-content", "label": "Мёртвый контент", "url": "/insights/{site_id}/dead-content"},
{"id": "opportunities", "label": "Точки роста", "url": "/insights/{site_id}/opportunities"},
```

In `Настройки` section, add child:
```python
{"id": "security", "label": "Безопасность", "url": "/ui/settings/security", "admin_only": False},
```

**Note:** Impact Scoring and GEO Readiness do NOT get standalone nav items — they're presented as enhancements to existing Audit and Analytics pages. This avoids sidebar bloat. The sidebar already has 6 sections with many children.

---

## Component Map: New vs Modified

### New Files

| File | Type | Purpose |
|------|------|---------|
| `app/services/insights_service.py` | Service | Quick Wins / Dead Content / Opportunities aggregation |
| `app/services/impact_scoring_service.py` | Service | Audit error prioritization by traffic weight |
| `app/services/suggest_service.py` | Service | Keyword suggest (Google/Yandex), Redis caching |
| `app/services/notification_service.py` | Service | Create/read/mark-read notifications |
| `app/tasks/suggest_tasks.py` | Celery task | Async keyword suggest fetch |
| `app/routers/insights.py` | Router | `/insights/{site_id}/...` endpoints |
| `app/routers/notifications.py` | Router | `/ui/notifications/...` endpoints |
| `app/routers/suggest.py` | Router | `/suggest?q=...` endpoint |
| `app/routers/security.py` | Router | 2FA setup/enable/disable routes |
| `app/models/notification.py` | Model | Notification storage |
| `app/templates/insights/quick_wins.html` | Template | Quick Wins page |
| `app/templates/insights/dead_content.html` | Template | Dead Content page |
| `app/templates/insights/opportunities.html` | Template | Growth Opportunities page |
| `app/templates/reports/client_instructions.html` | Template | Client-facing PDF template |
| `app/templates/settings/security.html` | Template | 2FA setup UI |
| `app/templates/components/notifications_bell.html` | Template | Notification bell dropdown |

### Modified Files

| File | Change | Risk |
|------|--------|------|
| `app/models/user.py` | Add `totp_secret`, `totp_enabled`, `totp_backup_codes` columns | LOW — nullable, no data migration |
| `app/models/analytics.py` | Add `llm_brief_text`, `llm_generated_at`, `llm_model_used`, `llm_prompt_tokens`, `llm_completion_tokens` to `ContentBrief` | LOW — nullable |
| `app/auth/jwt.py` | Add `create_partial_token(user_id, role="totp_pending")` for TOTP step | LOW — additive |
| `app/routers/auth.py` | Add `/auth/token/totp`, `/auth/2fa/setup`, `/auth/2fa/enable`, `/auth/2fa/disable` | LOW — additive routes |
| `app/services/audit_service.py` | Register new `geo_*` check runners in `_CHECK_RUNNERS` dict | LOW — additive dict entries |
| `app/services/content_audit_service.py` | Add GEO detection functions (`detect_faq_schema`, `detect_speakable`, ...) | LOW — pure functions |
| `app/services/report_service.py` | Add `report_type="client_instructions"` case + `client_report_data()` | LOW — additive |
| `app/services/brief_service.py` | Add `trigger_llm_brief(db, brief_id)` that dispatches Celery task | LOW — additive |
| `app/tasks/default_tasks.py` | Add `generate_llm_brief` task | LOW — additive task |
| `app/tasks/position_tasks.py` | Add `create_notification_for_site_users()` call after Telegram send | LOW — additive call |
| `app/tasks/crawl_tasks.py` | Add `create_notification_for_site_users()` on crawl complete | LOW — additive call |
| `app/celery_app.py` | Add `app.tasks.suggest_tasks` to `include` list | LOW |
| `app/navigation.py` | Add new nav entries to `NAV_SECTIONS` | LOW — additive list items |
| `app/config.py` | Add `ANTHROPIC_API_KEY`, `LLM_BRIEF_MODEL`, `LLM_BRIEF_MAX_TOKENS`, `YANDEX_WORDSTAT_TOKEN`, `SUGGEST_CACHE_TTL` | LOW — new optional env vars with defaults |
| `app/templates/base.html` | Add notification bell to header | LOW |

### New Alembic Migrations

| Migration | Change |
|-----------|--------|
| `0037_add_totp_to_users.py` | Add `totp_secret`, `totp_enabled`, `totp_backup_codes` to `users` |
| `0038_add_llm_fields_to_content_briefs.py` | Add LLM output columns to `content_briefs` |
| `0039_add_notifications_table.py` | Create `notifications` table with index on `(user_id, is_read, created_at)` |
| `0040_seed_geo_audit_checks.py` | Data migration: INSERT `geo_*` rows into `audit_check_definitions` |

---

## Data Flow Diagrams

### Quick Wins Flow
```
GET /insights/{site_id}/quick-wins
  → Check Redis cache (key: "insights:{site_id}:quick_wins", TTL 1h)
  → Cache hit: return cached HTML fragment
  → Cache miss:
      insights_service.get_quick_wins(db, site_id)
        → SQL JOIN: keyword_positions + audit_results + keywords
        → Filter: position 4–20 AND audit failure in (toc, schema, links)
        → Score by position (4 = highest priority)
      → Store result in Redis
      → Render Jinja2 fragment
      → HTMX swap
```

### LLM Brief Generation Flow
```
POST /analytics/briefs/{brief_id}/llm-generate
  → Check ANTHROPIC_API_KEY configured (400 if not)
  → Check brief.llm_brief_text is None (skip if already generated)
  → Dispatch: generate_llm_brief.delay(str(brief_id))
  → Return: {"task_id": ..., "status": "queued"}
  → UI polls: GET /tasks/{task_id}/status (existing pattern)
  → Task completes: brief.llm_brief_text written to DB
  → UI polls again: returns "completed"
  → HTMX refresh: GET /analytics/briefs/{brief_id}/llm-section → shows AI text
```

### 2FA Login Flow
```
POST /auth/token {email, password}
  → Verify credentials (unchanged)
  → IF user.totp_enabled:
      → Return {"status": "totp_required", "partial_token": <JWT role=totp_pending exp=5min>}
      → UI shows TOTP code input
  POST /auth/token/totp {partial_token, totp_code}
      → Decode partial_token, verify role=totp_pending
      → Load user, decrypt totp_secret (Fernet)
      → pyotp.TOTP(secret).verify(totp_code)
      → IF valid: return full access_token (same as normal login)
      → IF invalid: 401 Unauthorized
  → ELSE: return full access_token directly (unchanged)
```

### Notification Delivery Flow
```
Celery task (position_tasks, crawl_tasks, etc.)
  → On notable event:
      notification_service.create_notification(db, user_id, type, title, body, link_url)
      → INSERT INTO notifications ...
  → On Telegram (existing path, unchanged)

HTMX polling (browser, every 30s)
  → GET /ui/notifications/unread-count
      → SELECT COUNT(*) WHERE user_id=:uid AND is_read=False
      → Return {"count": N}
  → IF N > 0: update bell badge

On bell click
  → GET /ui/notifications/list (HTMX)
      → SELECT * FROM notifications WHERE user_id=:uid ORDER BY created_at DESC LIMIT 20
      → Render notification list fragment
  → POST /ui/notifications/mark-read → mark all as read, update badge to 0
```

---

## Suggested Build Order

Dependencies drive this order. Each phase unblocks the next.

### Phase 1: Foundation — Auth & Notifications (no business logic dependencies)

Build first because:
- 2FA and notifications don't depend on any v2 analytics features
- 2FA has the highest security priority
- Notification infrastructure is needed by all later phases (LLM briefs, suggest tasks)
- Both are pure additions with no risk of breaking existing functionality

**Deliverables:**
- Migration 0037 (TOTP columns), `pyotp` added to requirements
- 2FA setup + enable + disable routes and UI
- 2FA login step (partial token → TOTP verification)
- Migration 0039 (notifications table), `notification_service.py`
- Notification bell in base.html, polling endpoint, mark-read
- Wire `create_notification()` into existing `position_tasks.py` and `crawl_tasks.py`

### Phase 2: Insights Views — Quick Wins / Dead Content / Opportunities / Impact Scoring

Build second because:
- Pure read queries over existing data — zero schema changes, zero risk
- Validates the data quality of existing tables before building more features on top
- Quick Wins is the highest business value feature (immediate actionability for SEO team)
- Redis caching infrastructure created here reuses for Keyword Suggest in Phase 3

**Deliverables:**
- `insights_service.py` + `impact_scoring_service.py`
- Router `routers/insights.py` + templates
- Redis cache pattern established
- Nav additions to Аналитика section
- Impact Scoring as sort mode on existing audit page

### Phase 3: Keyword Suggest + AI/GEO Readiness

Build third because:
- Suggest uses the Redis cache pattern from Phase 2
- GEO Readiness uses the audit check system — validate that audit infrastructure is solid (Phase 1/2 must be working)
- Both are independent of each other and of Phase 4/5

**Deliverables:**
- Migration 0040 (GEO audit check seed data)
- GEO detection functions in `content_audit_service.py`
- `suggest_service.py` + `suggest_tasks.py`
- Suggest UI in keyword input flow
- GEO score tab on audit page
- Config additions: `YANDEX_WORDSTAT_TOKEN`, `SUGGEST_CACHE_TTL`

### Phase 4: Client PDF + LLM Briefs

Build fourth because:
- Client PDF extends existing `report_service.py` — simpler, lower risk
- LLM Briefs depend on `ContentBrief` (Phase 1 must be stable) and notification infrastructure (Phase 1)
- LLM Briefs require migration 0038 which must be tested before Phase 5

**Deliverables:**
- `app/templates/reports/client_instructions.html`
- `client_report_data()` in `report_service.py`
- Migration 0038 (LLM columns on content_briefs)
- `generate_llm_brief` Celery task in `default_tasks.py`
- LLM brief trigger route + polling UI
- Config additions: `ANTHROPIC_API_KEY`, `LLM_BRIEF_MODEL`, `LLM_BRIEF_MAX_TOKENS`
- Opt-in gate: button only visible if API key configured

### Dependency Graph Summary

```
Phase 1 (Auth + Notifications)
  ├── Unblocks: Phase 2 (notification_service available)
  ├── Unblocks: Phase 4 (LLM briefs need notification on completion)
  └── No blockers

Phase 2 (Insights Views)
  ├── Unblocks: Phase 3 (Redis cache pattern established)
  └── Requires: Phase 1 done (notification wiring complete)

Phase 3 (Suggest + GEO)
  └── Requires: Phase 2 done (Redis caching pattern)

Phase 4 (PDF + LLM Briefs)
  └── Requires: Phase 1 done (notification on brief completion)
```

---

## Critical Integration Constraints

### Constraint 1: Celery Task Registration Order
Every new Celery task module must be added to `celery_app.py`'s `include` list. If the module is imported by a route before the worker has registered it, `.delay()` calls succeed but tasks never execute (silently lost). Verify by checking `flower` at port 5555.

### Constraint 2: Sync vs Async Boundary
`notification_service.create_notification()` will be called from both:
- Celery tasks (sync context) → needs a sync-compatible version using `get_sync_db()`
- FastAPI routes (async context) → needs async version using `AsyncSession`

Pattern: write both `create_notification_sync(db: Session, ...)` and `create_notification(db: AsyncSession, ...)` in `notification_service.py`. This is the established pattern in `position_service.py` which has both `write_position()` (async) and sync usage in tasks.

### Constraint 3: TOTP Partial Token Lifetime
The `partial_token` (issued after password check, before TOTP) must have a short TTL (5 minutes) and a distinct `role` claim (`"totp_pending"`) so it cannot be used as a full access token. The `get_current_user` dependency must reject tokens with `role="totp_pending"`. Add this check to `auth/dependencies.py`.

### Constraint 4: LLM Brief Idempotency
The `generate_llm_brief` task must check if `ContentBrief.llm_brief_text` is already set before calling the Anthropic API. Duplicate task dispatch (e.g., from double-click) must not result in double API charges. Check `llm_brief_text IS NOT NULL` at task start and return early if already generated.

### Constraint 5: Keyword Suggest Rate Limiting
Google Suggest and Yandex Suggest have undocumented rate limits. The suggest task should:
- Add a 500ms delay between requests in a batch
- Use the existing `proxy` infrastructure if available (check `settings.PROXY_URL`)
- Return a cached empty result (TTL 5 min) on rate limit error, not a retryable exception

### Constraint 6: `keyword_positions` Partition Queries
Any new service (insights_service, dead_content_service) querying `keyword_positions` must use the established pattern with `DISTINCT ON (keyword_id, engine) ORDER BY ... checked_at DESC` to get the latest position per keyword. Do not use `MAX(checked_at)` subquery — it does not use the partition pruning index correctly.

---

## Sources

- Codebase direct inspection (2026-04-06): `/projects/test/app/` — models, services, tasks, routers, navigation, config
- Existing research: `.planning/research/ARCHITECTURE.md` (2026-03-31)
- Existing `AuditCheckDefinition` pattern: `app/models/audit.py`, `app/services/content_audit_service.py`
- Existing report pattern: `app/services/report_service.py` (WeasyPrint + Jinja2 templates)
- Existing brief pattern: `app/services/brief_service.py`, `app/models/analytics.py`
- pyotp library: https://pyauth.github.io/pyotp/ (standard TOTP implementation, Python)
- Anthropic Messages API: https://docs.anthropic.com/en/api/messages (sync httpx compatible)
- Google Suggest API: undocumented but stable endpoint (suggestqueries.google.com)

---
*Architecture research for: SEO Management Platform v2.0 — integration design*
*Researched: 2026-04-06*
