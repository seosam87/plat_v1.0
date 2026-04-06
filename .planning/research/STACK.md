# Technology Stack

**Project:** SEO Management Platform
**Researched:** 2026-04-06 (v2.0 update — additive only)
**Confidence:** HIGH (existing stack), MEDIUM–HIGH (new additions)

---

## Existing Stack (Validated — Do Not Re-Research)

Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, PostgreSQL 16, Redis 7, Celery 5.4,
Playwright 1.47+, Jinja2 3.1, HTMX 2.0, Tailwind CSS, WeasyPrint 62, authlib 1.3,
httpx 0.27, beautifulsoup4 4.12 + lxml 5, loguru 0.7, redbeat 2.2, openpyxl 3.1,
python-telegram-bot 21, aiosmtplib 3, slowapi 0.1.9, passlib[bcrypt], python-jose,
cryptography 42, pytest 8 + pytest-asyncio + respx.

Full details in the v1.0 STACK.md section below.

---

## v2.0 New Additions

### New Libraries Required

| Library | Version | Feature | Why |
|---------|---------|---------|-----|
| anthropic | ≥0.89.0 | LLM Briefs (opt-in AI content) | Official Anthropic Python SDK; `AsyncAnthropic` client for non-blocking calls inside Celery tasks and FastAPI endpoints; full streaming support via `async with client.messages.stream()`; Python 3.9+; latest stable as of April 2026 |
| pyotp | 2.9.0 | 2FA TOTP | De-facto standard Python TOTP library; RFC 6238 compliant; works with Google Authenticator, Authy, any TOTP app; pure Python, no system deps; `pyotp.TOTP(secret).verify(token)` is one line |
| qrcode[pil] | ≥8.2 | 2FA QR code display | Generates provisioning URI QR codes for authenticator app setup; `qrcode[pil]` extra required for PNG/SVG output; Pillow is already a transitive dep via WeasyPrint so no new system dep added |
| sse-starlette | ≥3.3.3 | In-app real-time notifications | Production-ready SSE for Starlette/FastAPI following W3C spec; `EventSourceResponse` wraps any async generator; auto-disconnect detection; latest stable v3.3.3 released March 2026 |

### Not Needed (Already Covered)

| Capability | Existing Dep That Covers It | Notes |
|------------|----------------------------|-------|
| Keyword suggest HTTP calls (Google/Yandex) | `httpx 0.27` | Google and Yandex autocomplete endpoints are unauthenticated JSON APIs — call directly with `httpx.AsyncClient`; no wrapper library needed |
| Wordstat API HTTP calls | `httpx 0.27` | Yandex Wordstat API (`api.wordstat.yandex.net`) is a standard REST/JSON API — call with `httpx.AsyncClient` and Bearer token; no wrapper library adds value |
| GEO/AI readiness content analysis | `beautifulsoup4 + lxml` | Checking for FAQ schema, structured data presence, heading structure, author markup — all HTML parsing already covered by existing bs4+lxml stack |
| NLP / language detection | Not needed | GEO readiness checklist is rule-based (schema present? FAQ markup? author tag?), not semantic NLP; adding spaCy or langdetect would be massive overhead for what is essentially a DOM traversal task |
| Streaming SSE to browser (LLM briefs) | `sse-starlette` (new, above) | The same SSE infrastructure covers both notification push and streaming LLM output to the browser |

---

## Integration Patterns

### LLM Briefs — anthropic SDK in Celery + FastAPI

**Problem:** `AsyncAnthropic` uses asyncio; Celery workers run in a synchronous execution context by default.

**Solution — two patterns:**

1. **Celery task generates the brief (non-streaming, background):**
   Use the sync `Anthropic` client inside the Celery task (Celery handles its own event loop per task).
   Result stored in DB; UI polls or receives SSE notification when done.

2. **FastAPI endpoint streams brief to browser (opt-in streaming):**
   Use `AsyncAnthropic` directly in a FastAPI `async def` endpoint wrapped in `EventSourceResponse`.
   The endpoint itself streams Claude's response token-by-token via SSE.

Do not use `AsyncAnthropic` inside a standard Celery task without `asyncio.run()` — Celery's worker thread does not have a running event loop.

```python
# Pattern 1: Celery task (sync client)
from anthropic import Anthropic

@celery_app.task(bind=True, max_retries=3)
def generate_brief_task(self, site_id: int, keyword_cluster_id: int):
    client = Anthropic()  # sync client
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    # save to DB

# Pattern 2: FastAPI streaming endpoint (async client)
from anthropic import AsyncAnthropic
from sse_starlette.sse import EventSourceResponse

@router.get("/briefs/{brief_id}/stream")
async def stream_brief(brief_id: int):
    async def generate():
        client = AsyncAnthropic()
        async with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield {"data": text}
    return EventSourceResponse(generate())
```

### 2FA TOTP — pyotp + qrcode Flow

Store `totp_secret` (base32, Fernet-encrypted) per user in the DB.
Generate once at 2FA setup; never regenerate unless user disables and re-enables.

```python
import pyotp, qrcode, io, base64

# Setup: generate secret and QR
secret = pyotp.random_base32()
uri = pyotp.totp.TOTP(secret).provisioning_uri(
    name=user.email, issuer_name="SEO Platform"
)
img = qrcode.make(uri)
buf = io.BytesIO()
img.save(buf, format="PNG")
qr_b64 = base64.b64encode(buf.getvalue()).decode()
# Return qr_b64 to template as data: URI

# Verification: check submitted token
totp = pyotp.TOTP(decrypted_secret)
if not totp.verify(submitted_token, valid_window=1):
    raise HTTPException(status_code=401, detail="Invalid OTP")
```

The `valid_window=1` allows 1 step of clock drift (±30 seconds) which covers most mobile clock skew.

Encrypt `totp_secret` with the same Fernet key used for WP credentials — already in the stack.

### In-App Notifications — sse-starlette + Redis Pub/Sub

Use Redis pub/sub (already in stack via `redis-py 5.0`) as the notification bus.
SSE endpoint subscribes to a per-user channel; Celery tasks publish events on task completion.

```python
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as aioredis

@router.get("/notifications/stream")
async def notification_stream(current_user: User = Depends(get_current_user)):
    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"user:{current_user.id}:notifications")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield {"data": message["data"].decode()}
        finally:
            await pubsub.unsubscribe()
            await r.aclose()
    return EventSourceResponse(event_generator())
```

HTMX 2.0 supports SSE via the `hx-ext="sse"` extension (moved from core in 2.0).
Load `htmx-ext-sse` from CDN alongside HTMX core.

### Keyword Suggest — httpx Direct Calls (No New Library)

Google Autocomplete endpoint (no auth, no API key required):
```
GET https://www.google.com/complete/search?client=firefox&q={query}&hl=ru
```
Returns JSON array; parse with stdlib `json`. Rate-limit to ~1 req/sec with `asyncio.sleep` in Celery batch tasks.

Yandex Suggest endpoint (no auth, no API key required):
```
GET https://wordstat-api.yandex.net/v1/suggest?q={query}
```
Or Yandex search suggest:
```
GET https://suggest.yandex.ru/suggest-ya.cgi?srv=topnews&v=4&part={query}&lang=ru
```
Both return JSON; parse with stdlib `json`.

Yandex Wordstat API (`api.wordstat.yandex.net`) — requires OAuth token from Yandex Direct account. Use the existing `httpx.AsyncClient` with `Authorization: Bearer {token}` header. No wrapper library needed.

### GEO/AI Readiness Checks — bs4+lxml (Already in Stack)

Rule-based DOM checks on already-crawled HTML snapshots (stored in DB by Playwright crawler):

| Check | Implementation |
|-------|---------------|
| FAQ schema present | `soup.find("script", {"type": "application/ld+json"})` — parse JSON, check `@type == "FAQPage"` |
| Author markup | `soup.find(itemprop="author")` or `rel="author"` link |
| Heading structure (H1→H2→H3) | Count heading tags, check nesting order |
| Article schema | Look for `@type: Article` or `BlogPosting` in JSON-LD |
| Internal links count | Count `<a href>` pointing to same domain |
| Page word count | `len(soup.get_text().split())` |
| Breadcrumb schema | `@type: BreadcrumbList` in JSON-LD |
| HowTo / Step schema | `@type: HowTo` in JSON-LD |

No NLP, no ML model, no new library. This is pattern matching on existing crawl data.

---

## Installation (v2.0 Additions Only)

```bash
# LLM integration
uv pip install "anthropic>=0.89.0"

# 2FA
uv pip install "pyotp>=2.9.0" "qrcode[pil]>=8.2"

# In-app notifications (SSE)
uv pip install "sse-starlette>=3.3.3"

# HTMX SSE extension (no pip install — load from CDN in base template)
# <script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>
```

---

## Alternatives Considered (v2.0 Scope)

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| LLM SDK | anthropic (official) | openai SDK / LiteLLM | Project chose Claude as co-pilot; official SDK has best feature parity and typing; LiteLLM adds abstraction overhead for a single-provider use case |
| Real-time notifications | SSE via sse-starlette | WebSockets (fastapi-websockets) | SSE is unidirectional server→client — sufficient for notifications; WebSockets add stateful connection management and do not work through HTTP/2 multiplexing without extra config; HTMX 2.0 SSE extension is simpler than a WebSocket integration |
| Real-time notifications | SSE via sse-starlette | Polling (HTMX hx-trigger="every 5s") | Polling wastes connections; SSE is clean push model; Redis pub/sub backend means no DB polling either |
| 2FA | pyotp | python-otp | python-otp is a thin wrapper; pyotp is the community standard with 12M+ monthly downloads; better maintained |
| QR code | qrcode[pil] | segno | segno is a modern alternative with better SVG output; qrcode is simpler and Pillow is already a transitive dep — no additional system library needed |
| Keyword suggest | Direct httpx calls | google-search-results (SerpApi) | SerpApi is paid; Google's unofficial autocomplete endpoint is free and stable for low-volume SEO tooling; this is not production search infrastructure |
| Wordstat integration | Direct httpx calls | YandexWordstatAPI PyPI package | The PyPI package is a thin wrapper with minimal maintenance; using httpx directly gives full control and fits existing request patterns |
| GEO readiness analysis | bs4+lxml (existing) | spaCy + NLP pipeline | GEO readiness is DOM/schema inspection, not semantic NLP; spaCy would add ~150 MB to the Docker image and language model downloads for zero functional benefit |

---

## What NOT to Add (v2.0 Scope)

| Avoid | Why |
|-------|-----|
| spaCy / NLTK / transformers | GEO readiness checklist is rule-based DOM inspection, not NLP; these libraries add hundreds of MB to the Docker image for no benefit |
| openai SDK | Anthropic SDK covers all LLM needs; mixing SDKs creates confusion and doubles API key management surface |
| LiteLLM | Unnecessary abstraction layer for a single LLM provider; adds routing complexity and another dep to update |
| websockets / starlette WebSocket | SSE is sufficient for one-way notifications; WebSockets add complexity without benefit in this use case |
| serpapi / dataforseo-suggest | Paid APIs for keyword suggest; free direct endpoints to Google/Yandex autocomplete are sufficient for internal tooling at this scale |
| YandexWordstatAPI (PyPI) | Unmaintained wrapper; direct httpx calls are cleaner and already the project pattern |
| qrcode without [pil] extra | The base package generates only ASCII QR codes; `[pil]` is required for PNG output that can be embedded in HTML as a data: URI |
| pyotp with HOTP instead of TOTP | HOTP is counter-based and requires counter sync; TOTP (time-based) is what every authenticator app uses by default |

---

## Version Compatibility (New Additions)

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| anthropic ≥0.89.0 | Python 3.9+, httpx 0.27.x | SDK uses httpx internally for transport; already in stack — no conflict |
| pyotp 2.9.0 | Python 3.9+ | Pure Python; no C extensions; no system deps |
| qrcode[pil] ≥8.2 | Pillow (auto-installed) | Pillow is already a transitive dep of WeasyPrint; no version conflict expected |
| sse-starlette ≥3.3.3 | FastAPI 0.115 / Starlette 0.40 | sse-starlette 3.x targets Starlette 0.36+; no breaking changes with FastAPI 0.115 |

---

## v1.0 Stack (Preserved Reference)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | Runtime | 3.12 is the stable LTS-track release with best async performance; 3.13 exists but ecosystem adoption lags — stay on 3.12 for 2025 builds |
| FastAPI | 0.115.x | ASGI web framework | 0.115 (released late 2024) is the stable branch for 2025; 0.111 is fine but 0.115 adds Pydantic v2 perf wins and lifespan-only startup (no deprecated `on_event`) |
| Pydantic | 2.7+ | Data validation (FastAPI dependency) | Pydantic v2 is Rust-core; 3–5x faster than v1; FastAPI 0.111+ requires v2 — do not mix with v1 |
| PostgreSQL | 16.x | Primary database | PG16 adds logical replication improvements and parallel query gains; PG17 exists (Oct 2024) but Docker images are less battle-tested — 16 is the safe 2025 production choice |
| asyncpg | 0.29.x | Async PostgreSQL driver | Required by SQLAlchemy async engine; fastest pure-async PG driver; no sync fallback needed |
| SQLAlchemy | 2.0.x (≥2.0.30) | ORM + query builder | 2.0 is the only version with proper async support; use `AsyncSession` + `async_sessionmaker` pattern; never use 1.4 legacy style |
| Alembic | 1.13.x | Database migrations | Tight SQLAlchemy coupling means staying on latest 1.13.x; use `--autogenerate` but always review generated migrations before applying |
| Redis | 7.2.x | Message broker + cache | Redis 7.2 is the LTS branch for 2025; Redis 8 is in preview — don't use it in production yet |
| Celery | 5.4.x | Distributed task queue | 5.4 fixes several Python 3.12 compatibility issues present in 5.3; use `celery[redis]` extra; configure `task_acks_late=True` for reliability |
| Celery Beat | 5.4.x (bundled) | Periodic task scheduler | Use `django-celery-beat`-style DB backend via `celery-beat-scheduler` or the built-in `redbeat` for DB-driven schedule changes without worker restart |
| Playwright | 1.45+ (≥1.47) | Browser automation / SERP parsing | 1.47+ adds better stealth context options; use `playwright[chromium]` only to keep Docker image small; async API throughout |
| Jinja2 | 3.1.x | Server-side HTML templating | Pairs natively with FastAPI via `Jinja2Templates`; 3.1.x is stable; no breaking changes expected |
| HTMX | 2.0.x | Partial page updates without SPA | HTMX 2.0 (released mid-2024) removed some legacy attributes (`hx-ws`, `hx-sse` moved to extensions) — use 2.0 from the start to avoid later migration |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Auth & Security** | | | |
| python-jose[cryptography] | 3.3.x | JWT encode/decode | Use for `access_token` + `refresh_token`; set `algorithm="HS256"` minimum, `RS256` if you need public key verification |
| passlib[bcrypt] | 1.7.x | Password hashing | `CryptContext(schemes=["bcrypt"])` — bcrypt cost factor 12 recommended for 2025 hardware |
| cryptography | 42.x | Fernet symmetric encryption | WP Application Password encryption at rest; `Fernet` is in this package; pin to 42.x (43 has minor API changes) |
| python-multipart | 0.0.9+ | Form/file upload parsing | Required for FastAPI form bodies and CSV/XLSX uploads; FastAPI does not auto-install it |
| slowapi | 0.1.9 | Rate limiting for FastAPI | Wraps `limits` library; integrates with FastAPI middleware; attach to `app.state.limiter`; use Redis storage backend in production |
| **Database Utilities** | | | |
| greenlet | 3.x | SQLAlchemy async bridge | Required by SQLAlchemy async; installed automatically but pin it to avoid breakage on Python 3.12 |
| **HTTP Client** | | | |
| httpx | 0.27.x | Async HTTP client | Use for WP REST API, GSC OAuth, DataForSEO calls; `httpx.AsyncClient` with connection pooling; replaces `requests` entirely |
| **Task Queue Extras** | | | |
| redis-py | 5.0.x | Redis client (Celery uses it internally) | Also use directly for manual cache writes, rate-limit counters, and pub/sub |
| flower | 2.0.x | Celery task monitoring UI | Web UI at port 5555; shows worker status, task history, failure rates; secure behind HTTP Basic Auth in production |
| redbeat | 2.2.x | DB-backed Celery Beat schedule | Stores periodic task schedule in Redis; enables UI-driven schedule changes without restarting Beat worker; replaces file-based `celerybeat-schedule` |
| **Data Import/Export** | | | |
| openpyxl | 3.1.x | Excel read/write (.xlsx) | Keyword import from Topvisor XLSX format + report export; pure Python, no LibreOffice dependency |
| **PDF Generation** | | | |
| weasyprint | 62.x | HTML→PDF conversion | Renders Jinja2 templates to PDF; no headless Chrome dependency; best choice for server-side PDF in Python 2025; produces clean print-quality output |
| **OAuth** | | | |
| authlib | 1.3.x | OAuth 2.0 client flows | GSC OAuth 2.0 integration; `AsyncOAuth2Client` wraps `httpx`; handles token refresh automatically; better than `requests-oauthlib` for async |
| **Notifications** | | | |
| python-telegram-bot | 21.x | Telegram Bot API | Async-native in v21; use `Bot.send_message()` directly inside Celery tasks; no need for polling — push-only for alerts |
| aiosmtplib | 3.x | Async SMTP email | Non-blocking email dispatch from Celery tasks; replaces smtplib for async contexts |
| **Parsing & Content** | | | |
| beautifulsoup4 | 4.12.x | HTML parsing | TOC generation, schema detection, internal link analysis; use `lxml` parser for speed |
| lxml | 5.x | Fast XML/HTML parser | BS4 backend; also useful for direct XPath queries on crawled pages |
| **Monitoring & Logging** | | | |
| loguru | 0.7.x | Structured logging | JSON sink config: `logger.add("logs/app.log", serialize=True, rotation="10 MB", retention="30 days")`; replaces stdlib logging entirely |
| **Config & Environment** | | | |
| pydantic-settings | 2.x | Settings from .env files | `BaseSettings` moved here in Pydantic v2; reads `.env` + environment variables; type-validated config |
| python-dotenv | 1.0.x | .env file loader | Used by pydantic-settings under the hood; also useful in `docker-compose.yml` env loading |
| **Testing** | | | |
| pytest | 8.x | Test runner | 2025 standard; use with `pytest-asyncio` for async test functions |
| pytest-asyncio | 0.23.x | Async test support | Set `asyncio_mode = "auto"` in `pyproject.toml` to avoid decorating every async test |
| httpx | 0.27.x | Test HTTP client | `AsyncClient(app=app, base_url="http://test")` replaces `TestClient` for async FastAPI |
| factory-boy | 3.3.x | Test fixtures/factories | SQLAlchemy factories for seeding test DB; cleaner than raw fixture dicts |
| pytest-cov | 5.x | Coverage reporting | `--cov=app --cov-fail-under=60` per PROJECT.md constraint |
| respx | 0.21.x | Mock httpx calls in tests | Mock WP REST API, GSC, DataForSEO calls without real network; pairs naturally with httpx |

---

## Sources

- Anthropic Python SDK GitHub (anthropics/anthropic-sdk-python) — v0.89.0, April 3, 2026: [https://github.com/anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python)
- Anthropic Python SDK docs: [https://platform.claude.com/docs/en/api/sdks/python](https://platform.claude.com/docs/en/api/sdks/python)
- pyotp PyPI v2.9.0: [https://pypi.org/project/pyotp/](https://pypi.org/project/pyotp/)
- pyotp documentation: [https://pyauth.github.io/pyotp/](https://pyauth.github.io/pyotp/)
- qrcode PyPI v8.2 (May 2025): [https://pypi.org/project/qrcode/](https://pypi.org/project/qrcode/)
- sse-starlette v3.3.3 (March 2026): [https://pypi.org/project/sse-starlette/](https://pypi.org/project/sse-starlette/)
- FastAPI SSE tutorial: [https://fastapi.tiangolo.com/tutorial/server-sent-events/](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- Yandex Wordstat API documentation: [https://yandex.com/support2/wordstat/en/content/api-structure](https://yandex.com/support2/wordstat/en/content/api-structure)
- Google Autocomplete suggest endpoint: [https://www.fromdev.com/2025/04/how-to-scrape-google-autocomplete-suggestions-for-long-tail-keyword-research-in-python.html](https://www.fromdev.com/2025/04/how-to-scrape-google-autocomplete-suggestions-for-long-tail-keyword-research-in-python.html)
- GEO/AI readiness and structured data best practices 2025: [https://totheweb.com/blog/beyond-seo-your-geo-checklist-mastering-content-creation-for-ai-search-engines/](https://totheweb.com/blog/beyond-seo-your-geo-checklist-mastering-content-creation-for-ai-search-engines/)
- FastAPI + TOTP 2FA implementation: [https://codevoweb.com/two-factor-authentication-2fa-in-fastapi-and-python/](https://codevoweb.com/two-factor-authentication-2fa-in-fastapi-and-python/)

---

*Stack research updated for v2.0 milestone: SEO Insights & AI features*
*Original research: 2026-03-31 | Updated: 2026-04-06*
