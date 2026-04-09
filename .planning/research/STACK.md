# Technology Stack

**Project:** SEO Management Platform
**Researched:** 2026-04-09 (v3.0 update — additive only)
**Confidence:** HIGH (existing stack), HIGH (v3.0 additions — zero new libraries required)

---

## Existing Stack (Validated — Do Not Re-Research)

Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, PostgreSQL 16, Redis 7, Celery 5.4,
Playwright 1.47+, Jinja2 3.1, HTMX 2.0, Tailwind CSS, WeasyPrint 62, authlib 1.3,
httpx 0.27, beautifulsoup4 4.12 + lxml 5, loguru 0.7, redbeat 2.2, openpyxl 3.1,
python-telegram-bot 21, aiosmtplib 3, slowapi 0.1.9, passlib[bcrypt], python-jose,
cryptography 42, pytest 8 + pytest-asyncio + respx, anthropic ≥0.89, pyotp 2.9,
sse-starlette ≥3.3.3, mammoth 1.6.

Full details in the v1.0 and v2.0 STACK.md sections below.

---

## v3.0 New Additions

### New Libraries Required

**None.** Every capability needed for Client CRM, audit intake forms, proposal templates, and document generation is already in the installed stack. The analysis below explains why.

### Capability-to-Existing-Library Mapping

| v3.0 Capability | Library Already in Stack | How It Covers the Need |
|-----------------|--------------------------|------------------------|
| Client CRM data model (contacts, interaction history, linked sites) | SQLAlchemy 2.0 async + PostgreSQL 16 | New `Client`, `ClientContact`, `ClientInteraction` models follow the identical pattern as `Project`, `SeoTask`, `Site`. JSON columns (`JSONB`) handle flexible contact metadata. Foreign keys link clients to sites and users. UUID primary keys, Alembic migrations — no deviation from existing patterns. |
| Audit intake forms (multi-section checklists, structured input) | python-multipart 0.0.9 + Jinja2 3.1 + HTMX 2.0 | `python-multipart` already handles form bodies. HTMX `hx-post` submits individual form sections without page reload. `hx-on::after-request` + CSS classes track completion state client-side. No JS framework needed. |
| Dynamic form sections (conditional fields, section toggling) | HTMX 2.0 | `hx-swap="outerHTML"` on form section containers; server returns re-rendered partials with updated state. Already used in the pipeline approval flow — same pattern. |
| Proposal template variable substitution (client name, site metrics, pricing) | Jinja2 3.1 | `Environment.from_string()` renders a stored template string with a context dict at generation time. This is the exact mechanism used in the 7 Russian instruction templates in `client_report_service.py`. Template bodies stored in DB as `Text` columns; rendered at generation time. No additional templating engine. |
| Template editor UI (create/edit proposal templates with variable placeholders) | Jinja2 3.1 + Tailwind CSS | A `<textarea>` with syntax-hint overlay using CSS. Variable placeholders documented as `{{ variable_name }}`. Preview endpoint renders template against sample data and returns HTML fragment via HTMX. No rich text editor library needed for this scope. |
| PDF generation (proposals, audit summaries) | WeasyPrint 62 (subprocess-isolated) | `subprocess_pdf.render_pdf_in_subprocess()` already handles all PDF rendering. Proposal PDF templates follow the `client_instructions.html` / `reports/detailed.html` pattern: standalone HTML with `@page` CSS, no external assets. No changes to the PDF pipeline. |
| Async PDF generation (queue-based, status polling) | Celery 5.4 + Redis 7 | `ClientReport` model already demonstrates the `pending → generating → ready | failed` lifecycle. Same Celery task pattern, same status polling via HTMX, same `LargeBinary` PDF storage. Proposal documents are a second document type using the identical infrastructure. |
| Excel export of audit checklists | openpyxl 3.1 | Already used for keyword export. Audit checklist export follows the same `openpyxl.Workbook()` pattern. |
| Interaction history (notes, timestamps, user attribution) | SQLAlchemy 2.0 + PostgreSQL 16 | `project_comments.py` model already implements `(project_id, user_id, created_at, body)` pattern. Client interaction log is the same structure with `client_id` foreign key instead of `project_id`. |
| File attachments on client cards (briefs, signed proposals) | FastAPI + python-multipart + PostgreSQL `LargeBinary` | Pattern already established by `ClientReport.pdf_data`. For larger files, store path reference to `artifacts/` directory (already used by the report system). |

---

## Integration Points for v3.0

### CRM Data Model — Follow Existing Patterns Exactly

The `Client` table is a first-class entity, not a sub-entity of `Site`. Sites link to clients (one client, many sites — mirroring how `project_users` links users to projects).

```python
# Recommended relationship direction (HIGH confidence — matches existing FK patterns)
class Client(Base):
    __tablename__ = "clients"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contacts: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # ... created_at, updated_at with server_default=text("NOW()")

# Sites get a nullable client_id FK (most sites may not be linked to a CRM client yet)
# ALTER TABLE sites ADD COLUMN client_id UUID REFERENCES clients(id) ON DELETE SET NULL;
```

Use `JSONB` (not `JSON`) for `contacts` — PostgreSQL `JSONB` supports GIN indexing, which is needed if the team searches by phone/email across all clients.

### Proposal Templates — Jinja2 Sandboxed Environment

Proposal templates are stored in the DB and rendered on demand. Use `jinja2.sandbox.SandboxedEnvironment` instead of the main `Environment` to prevent template injection from stored user-authored templates:

```python
from jinja2.sandbox import SandboxedEnvironment

_proposal_env = SandboxedEnvironment()

def render_proposal(template_body: str, context: dict) -> str:
    tmpl = _proposal_env.from_string(template_body)
    return tmpl.render(**context)
```

This is a **critical** security detail: the main `app/template_engine.py` `_jinja_templates` instance reads files from disk and is trusted. User-authored DB templates must use the sandboxed environment to prevent `{{ config.SECRET_KEY }}` style extraction attacks.

### Audit Intake Forms — HTMX Multi-Step Pattern

Multi-section intake forms work with HTMX section-by-section submission without JS scaffolding:

```html
<!-- Each section is an independent HTMX form target -->
<div id="section-technical" hx-post="/ui/clients/{id}/audit/section/technical"
     hx-swap="outerHTML" hx-trigger="change delay:800ms">
  <!-- form fields -->
</div>
```

Server returns the re-rendered section partial with updated completion state. Progress indicator counts completed sections. This pattern avoids full-page reloads and keeps the server as the single source of truth for form state — consistent with how the pipeline approval diffs work.

### Document Generator — Reuse subprocess_pdf Unchanged

The `render_pdf_in_subprocess` function in `app/services/subprocess_pdf.py` needs zero changes. Proposal PDF generation follows this call sequence:

1. `render_proposal(template_body, context_dict)` → HTML string
2. Wrap in standalone HTML document with `@page` CSS (same as `client_instructions.html`)
3. `render_pdf_in_subprocess(html_string)` → PDF bytes
4. Store in `ProposalDocument.pdf_data` (LargeBinary) with `status="ready"`

Run via Celery task to avoid blocking the web worker. Same `generate_client_report_task` structure.

---

## What NOT to Add (v3.0 Scope)

| Avoid | Why |
|-------|-----|
| django-crispy-forms / WTForms / Flask-WTF | Django/Flask form libraries; incompatible with FastAPI. Form handling is `python-multipart` + Pydantic validation — already the project pattern. |
| TipTap / Quill / ProseMirror (rich text editor) | Heavy JS dependencies; proposal templates use `{{ variable }}` placeholders in plain text/HTML. A `<textarea>` with documented placeholder syntax is sufficient for a team of 2–5 power users. Re-evaluate if clients need WYSIWYG editing. |
| SQLAlchemy-JSONField | Third-party wrapper for JSON columns; PostgreSQL `JSONB` via native `mapped_column(JSONB, ...)` is cleaner and already used in `audit.py` model. |
| docx (python-docx) for proposal output | Out of scope per PROJECT.md. If editable DOCX output is needed later, `python-docx` is the correct addition — but not now. PDF via WeasyPrint covers all stated output needs. |
| Jinja2 main Environment for DB templates | Security risk. User-authored templates stored in DB must use `SandboxedEnvironment`. The existing `templates` singleton in `template_engine.py` is for trusted file-based templates only. |
| CKEditor / TinyMCE | Server-side CDN dependency; overkill for internal template authoring. Adds content security policy complexity. |
| Separate CRM service / microservice | Single FastAPI app is the architecture constraint. Client CRM is a new SQLAlchemy model family + router + service, not a separate deployment. |
| UUID7 / ULID for CRM primary keys | The platform uses `uuid4` throughout (22+ model files). Consistency matters more than sortability for this use case. |

---

## Installation (v3.0 Additions)

```bash
# No new packages required.
# All v3.0 features are implemented using the existing installed stack.
# Run migrations only:
alembic revision --autogenerate -m "add_clients_audit_intake_proposals"
alembic upgrade head
```

---

## Version Compatibility (v3.0 — No Changes)

No new packages means no new compatibility surface. The existing compatibility matrix (v1.0 and v2.0 sections below) applies unchanged.

The one implementation note: `jinja2.sandbox.SandboxedEnvironment` is part of `Jinja2 3.1.x` — no separate install. Confirm with:

```python
from jinja2.sandbox import SandboxedEnvironment  # ships with jinja2>=2.0
```

---

## Alternatives Considered (v3.0 Scope)

| Category | Decision | Alternative | Why Not |
|----------|----------|-------------|---------|
| Proposal template rendering | Jinja2 `SandboxedEnvironment` | Mustache / Handlebars (chevron) | Jinja2 is already the stack template engine; Mustache is less expressive (no filters, no conditionals); adding a second template engine creates confusion about which to use where |
| Proposal template rendering | Jinja2 `SandboxedEnvironment` | String `.format()` / f-strings | Not safe for stored templates; no loops or conditionals; Jinja2 sandbox is the correct tool |
| Audit form state storage | DB rows (per-section answers) | Redis session keys | DB rows are queryable, exportable to Excel, survive Redis flushes; Redis sessions are ephemeral — wrong for audit data that persists through the client relationship |
| Client contacts storage | `JSONB` column | Separate `client_contacts` table | JSONB is appropriate when contact schema is flexible (phone, email, messenger handles vary); a separate table adds JOIN complexity with no query benefit at this scale (< 500 clients) |
| PDF proposal output | WeasyPrint (existing) | Playwright `page.pdf()` | Playwright requires a browser launch per document; WeasyPrint subprocess isolation already solves the memory leak problem; no reason to change |

---

## v2.0 New Additions (Preserved Reference)

### New Libraries Required

| Library | Version | Feature | Why |
|---------|---------|---------|-----|
| anthropic | ≥0.89.0 | LLM Briefs (opt-in AI content) | Official Anthropic Python SDK; `AsyncAnthropic` client for non-blocking calls inside Celery tasks and FastAPI endpoints; full streaming support via `async with client.messages.stream()` |
| pyotp | 2.9.0 | 2FA TOTP | De-facto standard Python TOTP library; RFC 6238 compliant; works with Google Authenticator, Authy, any TOTP app; pure Python, no system deps |
| qrcode[pil] | ≥8.2 | 2FA QR code display | Generates provisioning URI QR codes for authenticator app setup; `qrcode[pil]` extra required for PNG output; Pillow is already a transitive dep via WeasyPrint |
| sse-starlette | ≥3.3.3 | In-app real-time notifications | Production-ready SSE for Starlette/FastAPI; `EventSourceResponse` wraps any async generator; auto-disconnect detection |

### Integration Patterns (v2.0)

**LLM Briefs — anthropic SDK in Celery + FastAPI:**
Use sync `Anthropic` client inside Celery tasks (no event loop required). Use `AsyncAnthropic` in FastAPI streaming endpoints via `EventSourceResponse`.

**In-App Notifications — sse-starlette + Redis Pub/Sub:**
Redis pub/sub (already in stack) as notification bus. SSE endpoint subscribes to per-user channel; Celery tasks publish on completion. HTMX 2.0 `hx-ext="sse"` extension handles browser-side subscription.

---

## v1.0 Stack (Preserved Reference)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | Runtime | 3.12 is the stable LTS-track release with best async performance |
| FastAPI | 0.115.x | ASGI web framework | 0.115 stable branch; lifespan-only startup (no deprecated `on_event`) |
| Pydantic | 2.7+ | Data validation | Rust-core; 3–5x faster than v1; FastAPI 0.111+ requires v2 |
| PostgreSQL | 16.x | Primary database | PG16 parallel query gains; battle-tested Docker images |
| asyncpg | 0.29.x | Async PostgreSQL driver | Required by SQLAlchemy async engine; fastest pure-async PG driver |
| SQLAlchemy | 2.0.x (≥2.0.30) | ORM + query builder | Only version with proper async support; `AsyncSession` + `async_sessionmaker` |
| Alembic | 1.13.x | Database migrations | Explicit SQLAlchemy 2.0 async engine support in `env.py` |
| Redis | 7.2.x | Message broker + cache | LTS branch; Redis 8 in preview — not for production |
| Celery | 5.4.x | Distributed task queue | 5.4 fixes Python 3.12 compatibility; `task_acks_late=True` for reliability |
| Playwright | 1.47+ | Browser automation | Async-native; stealth context options; `playwright[chromium]` only |
| Jinja2 | 3.1.x | Server-side HTML templating | Pairs natively with FastAPI; stable; `SandboxedEnvironment` for DB templates |
| HTMX | 2.0.x | Partial page updates | 2.0 from the start; `hx-ws`/`hx-sse` moved to extensions |

### Supporting Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| python-jose[cryptography] | 3.3.x | JWT encode/decode |
| passlib[bcrypt] | 1.7.x | Password hashing (cost factor 12) |
| cryptography | 42.x | Fernet encryption for WP credentials and TOTP secrets |
| python-multipart | 0.0.9+ | Form/file upload parsing |
| slowapi | 0.1.9 | Rate limiting (Redis storage backend) |
| greenlet | 3.x | SQLAlchemy async bridge |
| httpx | 0.27.x | Async HTTP client (WP REST, GSC, DataForSEO) |
| redis-py | 5.0.x | Redis client (cache, pub/sub, rate counters) |
| flower | 2.0.x | Celery task monitoring UI (secure with Basic Auth) |
| redbeat | 2.2.x | DB-backed Celery Beat schedule (survives Redis flush) |
| openpyxl | 3.1.x | Excel read/write (.xlsx) |
| weasyprint | 62.x | HTML→PDF (subprocess-isolated for memory leak mitigation) |
| mammoth | 1.6.x | DOCX→HTML conversion (brief uploads) |
| authlib | 1.3.x | OAuth 2.0 (GSC integration; `AsyncOAuth2Client` on httpx) |
| python-telegram-bot | 21.x | Telegram push alerts (async-native v21) |
| aiosmtplib | 3.x | Async SMTP email dispatch |
| beautifulsoup4 | 4.12.x | HTML parsing (TOC, schema detection, GEO checks) |
| lxml | 5.x | Fast XML/HTML parser (bs4 backend) |
| loguru | 0.7.x | Structured JSON logging (10 MB rotation, 30-day retention) |
| pydantic-settings | 2.x | Type-validated settings from `.env` |
| pytest | 8.x | Test runner |
| pytest-asyncio | 0.23.x | Async test support (`asyncio_mode = "auto"`) |
| pytest-cov | 5.x | Coverage reporting (`--cov-fail-under=60`) |
| respx | 0.21.x | Mock httpx calls in tests |

---

## Sources

- Codebase inspection (2026-04-09): `app/services/subprocess_pdf.py`, `app/services/client_report_service.py`, `app/models/client_report.py`, `app/models/project.py`, `app/models/site.py`, `app/template_engine.py`, `requirements.txt` — HIGH confidence
- Jinja2 3.1 sandbox documentation: `jinja2.sandbox.SandboxedEnvironment` ships with Jinja2 ≥2.0 — HIGH confidence (stdlib knowledge)
- PostgreSQL 16 JSONB vs JSON: JSONB supports GIN indexes, JSON does not — HIGH confidence
- WeasyPrint memory leak mitigation via subprocess: Decision D-12, documented in Phase 14 CONTEXT.md — HIGH confidence (in-codebase decision record)
- mammoth 1.6.x already in requirements.txt for DOCX intake — HIGH confidence (requirements.txt inspection)

---

*Stack research updated for v3.0 milestone: Client CRM, Audit Intake, Proposal Templates, Document Generator*
*Original research: 2026-03-31 | v2.0 update: 2026-04-06 | v3.0 update: 2026-04-09*
