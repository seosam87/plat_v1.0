# Phase 23: Document Generator - Research

**Researched:** 2026-04-09
**Domain:** PDF document generation, async Celery tasks, PostgreSQL bytea storage, HTMX polling, SMTP attachment delivery
**Confidence:** HIGH

## Summary

Phase 23 builds the document generation feature on top of Phase 22's ProposalTemplate model. The implementation is almost entirely a composition of existing, verified codebase components: the `subprocess_pdf.py` subprocess-isolated WeasyPrint renderer, the `template_variable_resolver` from Phase 22, and the Celery + HTMX polling pattern established in the client-reports feature (Phase 14). No new libraries or techniques are required.

The primary new artifact is the `GeneratedDocument` SQLAlchemy model with a 3-version cap per (client, template) group. The UI entrypoint is a new "Документы" tab in the existing client detail page (`/ui/crm/clients/{id}`), following the established tab structure. Sending via Telegram and SMTP is a Celery task that calls `telegram_service.send_message_sync()` and a to-be-extended `smtp_service.send_email_sync_with_attachment()`.

The one non-trivial gap is that the existing `smtp_service.send_email_sync()` signature does not accept attachment bytes. A thin extension — a new function `send_email_with_attachment_sync()` — is needed to send the PDF file to the client's email address. Everything else is direct reuse.

**Primary recommendation:** Copy the `client_reports` router + task + model pattern precisely; adapt for the template-based document context and the 3-version cap.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** PDF stored in PostgreSQL (bytea / LargeBinary), max 3 versions per document. When regenerating, the oldest version is deleted if the limit is exceeded.
- **D-02:** Generation via Celery task using existing `subprocess_pdf.py` (subprocess-isolated WeasyPrint, Phase 14 D-12).
- **D-03:** Generation status shown via HTMX polling (every 2-3 seconds) — established pattern from positions and crawler.
- **D-04:** "Regenerate" button on a document — creates a new version from the same template + current data.
- **D-05:** Entry point is the client documents page `/ui/crm/clients/{id}/documents`. "Create document" button with template + site selection form.
- **D-06:** Document list — table: name, type (badge), site, date, status, actions (download/send/regenerate). Filters: type + date.
- **D-07:** Documents are linked to a client — "Документы" tab in the client card (alongside Сайты, Контакты, История).
- **D-08:** "Send" button on a document row → dropdown with channel selection: Telegram / Email. Address taken from CRM (client email/phone).
- **D-09:** Before sending — confirm dialog: "Отправить КП на info@client.com через Email?" — OK/Cancel.
- **D-10:** Sending via existing `telegram_service.send_message_sync()` and `smtp_service.send_email_sync()` in Celery task.
- **D-11:** Generation and sending require `require_manager_or_above` (as in CRM). Client role does not see the generator.

### Claude's Discretion
- GeneratedDocument model: concrete fields, indexes, FK
- PDF file naming on download
- Celery task status format (pending/processing/ready/failed)
- Document list pagination (if needed)
- Document display order (by date desc by default)

### Deferred Ideas (OUT OF SCOPE)
- **DOC-06:** Variable overrides at generation time (v3.x)
- **DOC-07:** Auto-generate proposal after intake completion (v3.x)
- **DOC-08:** Document audit trail via audit_log (v3.x)
- Global document list `/ui/documents` (separate page + sidebar) — add as Phase 23.1 if needed
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOC-01 | User can generate PDF from a proposal template + client + site data (async Celery task) | `subprocess_pdf.render_pdf_in_subprocess()` + `render_template_preview()` + `generate_client_pdf` task pattern — all verified in codebase |
| DOC-02 | User can view list of generated documents per client with filters by type and date | CRM tab pattern from `detail.html` + table with query filters in router |
| DOC-03 | User can download generated PDF documents | `client_reports.py` download endpoint pattern — return `Response(content=pdf_bytes, media_type="application/pdf")` |
| DOC-04 | System supports document types (proposal, audit_report, brief) | `TemplateType` enum already exists in `proposal_template.py` — re-use directly on GeneratedDocument |
| DOC-05 | User can send generated document via Telegram or SMTP | `telegram_service.send_message_sync()` + smtp extension for attachment — Celery task pattern from `client_report_tasks.py` |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy 2.0 async | 2.0.30+ | GeneratedDocument ORM model + async queries | Project-wide ORM; `AsyncSession` pattern throughout |
| Alembic | 1.13.x | Migration 0046 for generated_documents table | Established migration chain; next number is 0046 |
| FastAPI | 0.115.x | New documents router at `/ui/crm/clients/{id}/documents` | Project framework |
| Celery 5.4.x | 5.4.x | `generate_document_pdf` async task | All long-running ops use Celery |
| WeasyPrint (subprocess) | via subprocess_pdf.py | PDF rendering | D-02 locks this; subprocess isolation is mandatory |
| Jinja2 SandboxedEnvironment | 3.1.x | Template rendering via `render_template_preview()` | Phase 22 established this; reuse directly |
| HTMX 2.0.x | 2.0.x | Status polling + form submission + dropdown | Project-wide UI library |
| aiosmtplib | 3.x | SMTP delivery with PDF attachment | Async SMTP used in existing smtp_service |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| loguru | 0.7.x | Structured logging in service + task | All log calls use loguru |
| python-multipart | 0.0.9+ | Form parsing for generate form | Required for FastAPI form bodies |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PostgreSQL bytea storage | Filesystem path reference | Bytea locked by D-01; filesystem needs volume mounts and cleanup jobs |
| Celery task for send | Direct send in FastAPI handler | Celery is mandatory for all external API calls per CLAUDE.md constraint |

**No new package installations required.** All dependencies already in the project.

---

## Architecture Patterns

### Recommended File Structure

New files to create:

```
app/
├── models/
│   └── generated_document.py      # GeneratedDocument model (new)
├── services/
│   └── document_service.py        # CRUD + 3-version cap logic (new)
├── tasks/
│   └── document_tasks.py          # generate + send Celery tasks (new)
├── routers/
│   └── documents.py               # /ui/crm/clients/{id}/documents router (new)
├── templates/
│   └── crm/
│       ├── _documents_tab.html    # tab panel partial (new)
│       └── documents/
│           ├── _doc_row.html      # table row partial (new)
│           └── _gen_status.html   # HTMX polling status partial (new)
alembic/
└── versions/
    └── 0046_add_generated_documents.py  # migration (new)
```

Files to modify:

```
app/main.py                         # register documents_router
app/templates/crm/detail.html       # add "Документы" tab button + panel
app/services/smtp_service.py        # add send_email_with_attachment_sync()
tests/
└── test_document_service.py        # unit tests (new)
```

### Pattern 1: GeneratedDocument Model

Closely mirrors `ClientReport` but with additional FKs and version semantics:

```python
# app/models/generated_document.py
class GeneratedDocument(Base):
    __tablename__ = "generated_documents"
    __table_args__ = (
        Index("ix_gd_client_created", "client_id", "created_at"),
        Index("ix_gd_template_id", "template_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proposal_templates.id", ondelete="SET NULL"), nullable=True)
    document_type: Mapped[TemplateType] = mapped_column(SAEnum(TemplateType, name="templatetype"), nullable=False)
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, default="document.pdf")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
```

**Key FK decisions:**
- `client_id` ON DELETE CASCADE — document dies if client deleted
- `site_id` ON DELETE SET NULL — document survives if site deleted (historical record)
- `template_id` ON DELETE SET NULL — document survives if template deleted (PDF is self-contained)
- `document_type` reuses existing `templatetype` PostgreSQL enum (already in DB from migration 0045)

### Pattern 2: 3-Version Cap in document_service.py

```python
# app/services/document_service.py
MAX_VERSIONS = 3

async def enforce_version_cap(db: AsyncSession, client_id: uuid.UUID, template_id: uuid.UUID) -> None:
    """Delete oldest documents beyond MAX_VERSIONS for this client+template pair."""
    result = await db.execute(
        select(GeneratedDocument)
        .where(
            GeneratedDocument.client_id == client_id,
            GeneratedDocument.template_id == template_id,
        )
        .order_by(GeneratedDocument.created_at.asc())
    )
    docs = list(result.scalars().all())
    if len(docs) >= MAX_VERSIONS:
        to_delete = docs[: len(docs) - MAX_VERSIONS + 1]
        for doc in to_delete:
            await db.delete(doc)
```

**Decision (Claude's discretion):** Version cap is enforced at document creation time, before the new record is inserted. Cap is per (client_id, template_id) pair.

### Pattern 3: Celery Task — generate_document_pdf

Mirrors `generate_client_pdf` exactly:

```python
# app/tasks/document_tasks.py
@celery_app.task(
    name="app.tasks.document_tasks.generate_document_pdf",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def generate_document_pdf(self, document_id: str, template_id: str, client_id: str, site_id: str | None) -> dict:
    async def _run():
        async with AsyncSessionLocal() as db:
            try:
                # 1. Fetch template body
                # 2. resolve_template_variables(db, client_id, site_id)
                # 3. render_template_preview(template_body, variables)
                # 4. render_pdf_in_subprocess(html_string)
                # 5. Update GeneratedDocument.pdf_data, status="ready"
                ...
            except Exception as exc:
                # Mark status="failed", store error_message
                raise
    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=15)
```

**Status lifecycle:** `pending` → `processing` → `ready` | `failed`

### Pattern 4: HTMX Polling Status

Reuse the exact pattern from `client_reports/partials/generation_status.html`:

```html
<!-- crm/documents/_gen_status.html — non-terminal state -->
<span id="doc-status-{{ doc_id }}"
      hx-get="/ui/crm/clients/{{ client_id }}/documents/{{ doc_id }}/status"
      hx-trigger="every 3s"
      hx-swap="outerHTML">
  Генерация...
</span>

<!-- Terminal states (ready/failed) — no hx-trigger, polling stops -->
```

When status becomes `ready`, the status endpoint returns the terminal HTML (no `hx-trigger`), halting polling. Also fires `HX-Trigger: refreshDocList` to update the document table.

### Pattern 5: Documents Router — entry under /ui/crm

```python
# app/routers/documents.py
router = APIRouter(prefix="/ui/crm/clients/{client_id}/documents", tags=["documents"])

# GET  /                          — documents tab content (HTMX partial or full page)
# POST /generate                  — create GeneratedDocument record + dispatch Celery task
# GET  /{doc_id}/status           — HTMX polling endpoint
# GET  /{doc_id}/download         — streaming PDF response
# POST /{doc_id}/send             — dispatch send task (channel=telegram|email)
# DELETE /{doc_id}                — soft? hard delete (Claude's discretion: hard, consistent with template model)
```

### Pattern 6: Client Detail Tab Addition

Add to `app/templates/crm/detail.html`:

```html
{# In tab bar #}
<button class="crm-tab" data-tab="documents" onclick="switchTab('documents')"
        style="padding:0.75rem 1.25rem;font-size:0.875rem;font-weight:500;border:none;background:none;cursor:pointer;border-bottom:2px solid transparent;color:#6b7280;">
  Документы
</button>

{# Tab panel #}
<div id="tab-documents" class="crm-tab-panel" style="display:none;">
  {% include "crm/_documents_tab.html" %}
</div>
```

The documents tab panel is loaded from `_documents_tab.html` which contains the generation form and document table.

### Pattern 7: SMTP Attachment Extension

The existing `smtp_service.send_email_sync()` does not support file attachments. A new function is needed:

```python
# Extension to app/services/smtp_service.py
async def _send_email_with_attachment_async(
    to: str, subject: str, body_html: str,
    attachment_bytes: bytes, attachment_filename: str
) -> bool:
    import aiosmtplib
    from email.mime.application import MIMEApplication

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    part = MIMEApplication(attachment_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
    msg.attach(part)

    await aiosmtplib.send(msg, hostname=settings.SMTP_HOST, port=settings.SMTP_PORT,
                          username=settings.SMTP_USER or None, password=settings.SMTP_PASSWORD or None,
                          use_tls=True, timeout=30)
    return True


def send_email_with_attachment_sync(
    to: str, subject: str, body_html: str,
    attachment_bytes: bytes, attachment_filename: str
) -> bool:
    """Send email with PDF attachment. Used by document send Celery task."""
    if not settings.SMTP_HOST:
        logger.debug("SMTP not configured, skipping email delivery")
        return False
    try:
        asyncio.run(_send_email_with_attachment_async(to, subject, body_html, attachment_bytes, attachment_filename))
        logger.info("Email with attachment sent", to=to, filename=attachment_filename)
        return True
    except Exception as exc:
        logger.warning("SMTP attachment delivery failed", to=to, error=str(exc))
        return False
```

**Note:** D-10 says "use existing `smtp_service.send_email_sync()`" — however, sending a PDF document requires an attachment. The decision context refers to using the existing service as the delivery mechanism (not building a new SMTP stack). The extension adds attachment support to the same service file. This is the correct interpretation.

### Pattern 8: Dropdown Send with Confirm Dialog

```html
<!-- In _doc_row.html — send button -->
<div style="position:relative;display:inline-block;">
  <button onclick="toggleSendMenu('{{ doc.id }}')" style="...">Отправить ▼</button>
  <div id="send-menu-{{ doc.id }}" style="display:none;position:absolute;...">
    {% if client.email %}
    <button onclick="confirmSend('{{ doc.id }}', 'email', '{{ client.email }}')" style="...">
      Email: {{ client.email }}
    </button>
    {% endif %}
    <button onclick="confirmSend('{{ doc.id }}', 'telegram', '')" style="...">
      Telegram
    </button>
  </div>
</div>

<script>
function confirmSend(docId, channel, address) {
  var msg = channel === 'email'
    ? 'Отправить документ на ' + address + ' через Email?'
    : 'Отправить документ в Telegram?';
  if (!confirm(msg)) return;
  htmx.ajax('POST', '/ui/crm/clients/.../documents/' + docId + '/send',
    {values: {channel: channel}, target: '#send-result-' + docId});
}
</script>
```

This implements D-08 (dropdown) and D-09 (confirm dialog) using plain JS + HTMX, consistent with the `if (!confirm(...)) return;` pattern in other delete operations.

### Anti-Patterns to Avoid
- **Direct WeasyPrint in Celery worker body:** Always go through `render_pdf_in_subprocess()`. Direct use causes OOM accumulation (D-02, D-12 decision from Phase 14).
- **Storing ORM objects in template variables:** `resolve_template_variables()` must return plain dicts — no ORM model instances (established pitfall from Phase 22 SUMMARY).
- **Polling without terminal state:** Status HTML for `ready`/`failed` must NOT include `hx-trigger`. Polling must stop at terminal states.
- **Hard-deleting documents with active Celery task:** Check status != "pending" before delete.
- **Using `ON DELETE CASCADE` on template_id:** Deleting a template would cascade-delete all historical documents. Use `ON DELETE SET NULL` — the PDF is self-contained.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF rendering | Custom WeasyPrint integration | `subprocess_pdf.render_pdf_in_subprocess()` | OOM leak mitigation already solved |
| Template variable resolution | Custom resolver | `template_variable_resolver.resolve_template_variables()` | 15 vars already implemented and tested |
| Jinja2 rendering | Raw Jinja2 Environment | `render_template_preview()` | SandboxedEnvironment + error handling already in place |
| Telegram notification | Direct httpx calls | `telegram_service.send_message_sync()` | Graceful skip if not configured, error handling |
| Async status polling | WebSockets or SSE | HTMX `hx-trigger="every 3s"` | Established project pattern, no new infra |
| PDF storage | Filesystem + path references | `LargeBinary` column | D-01 is locked; bytea simplifies backup and Docker volume management |

---

## Common Pitfalls

### Pitfall 1: `templatetype` Enum Already Exists in PostgreSQL
**What goes wrong:** Creating a new `SAEnum(TemplateType, name="templatetype")` column in the migration fails with "type already exists" if Alembic tries to re-create the enum type.
**Why it happens:** The `templatetype` PostgreSQL enum was created by migration 0045. Alembic's `--autogenerate` may try to create it again.
**How to avoid:** In migration 0046, reference the existing type with `create_type=False`:
```python
sa.Column('document_type', sa.Enum('proposal','audit_report','brief', name='templatetype', create_type=False), nullable=False)
```
Or use `postgresql_existing_type=True` kwarg. Always inspect the generated migration before applying.
**Warning signs:** `ProgrammingError: type "templatetype" already exists` on `alembic upgrade head`.

### Pitfall 2: Version Cap Race Condition
**What goes wrong:** If two generation requests fire simultaneously for the same client+template, both pass the `len(docs) < MAX_VERSIONS` check before either commits, resulting in 4+ versions.
**Why it happens:** Async gap between read and write without locking.
**How to avoid:** At this scale (internal team, not high concurrency), this is acceptable. Document the limitation; a SELECT FOR UPDATE lock is overkill for a 3-version soft cap. The cap is a housekeeping concern, not a hard data integrity constraint.

### Pitfall 3: SMTP send_email_sync() Doesn't Accept Attachments
**What goes wrong:** Calling existing `send_email_sync(to, subject, body)` for document delivery silently sends an email without the PDF.
**Why it happens:** The existing function signature has no `attachment_bytes` parameter.
**How to avoid:** Add `send_email_with_attachment_sync()` to `smtp_service.py`. Do NOT modify the existing function signature — other callers use it.

### Pitfall 4: Telegram Has No Native PDF Attachment Support via sendMessage
**What goes wrong:** `send_message_sync()` sends text-only messages. Sending a document via Telegram requires `sendDocument` API endpoint, not `sendMessage`.
**Why it happens:** The existing `telegram_service.py` only wraps `sendMessage`.
**How to avoid:** For Phase 23, the Telegram send can either:
  - (Recommended) Send a text message: "Документ КП готов: {document name} для клиента {company_name}. Скачайте в платформе: /ui/crm/clients/{id}/documents" — this satisfies DOC-05 without needing `sendDocument`.
  - (Optional extension) Add `send_document_sync(file_bytes, filename)` using `sendDocument` API.
  Given D-10 says "use existing `telegram_service.send_message_sync()`", the text-only approach is the correct implementation.

### Pitfall 5: Client Email May Be Null
**What goes wrong:** Attempting to send email when `client.email` is None causes a 500 error or sends to a null address.
**Why it happens:** The Client model allows nullable email.
**How to avoid:** In the router's send endpoint, check `client.email is not None` before dispatching the email task. Return a 400 with "Email клиента не указан" if absent. The UI should also conditionally show/hide the Email option in the dropdown.

### Pitfall 6: Template Body May Reference Variables Not Yet Loaded
**What goes wrong:** `render_template_preview()` returns empty-string for a variable if `resolve_template_variables()` returns None for the site.
**Why it happens:** If `site_id` is null (template without site context), all site/position variables resolve to empty string or zero.
**How to avoid:** Generation form must require site selection. Set `required` on the site select. `site_id` should be non-nullable on generation (though stored as nullable in the model to allow template deletion).

---

## Code Examples

### Example 1: Creating a GeneratedDocument Record and Dispatching Task

```python
# Verified pattern — mirrors client_reports.py:generate_report()
from app.services.document_service import create_document_record, enforce_version_cap
from app.tasks.document_tasks import generate_document_pdf

# 1. Enforce 3-version cap (delete oldest if needed)
await enforce_version_cap(db, client_id=client_id, template_id=template_id)

# 2. Create pending record
doc = await create_document_record(db, client_id=client_id, site_id=site_id,
                                   template_id=template_id, document_type=template.template_type)
# 3. Dispatch task
task = generate_document_pdf.delay(str(doc.id), str(template_id), str(client_id), str(site_id) if site_id else None)

# 4. Store celery_task_id
doc.celery_task_id = task.id
await db.commit()
```

### Example 2: Download Endpoint

```python
# Source: mirrors app/routers/client_reports.py:download_report()
@router.get("/{doc_id}/download")
async def download_document(doc_id: uuid.UUID, client_id: uuid.UUID,
                             db: AsyncSession = Depends(get_db),
                             _user: User = Depends(require_manager_or_above)) -> Response:
    doc = await document_service.get_document(db, doc_id)
    if not doc or doc.client_id != client_id:
        raise HTTPException(status_code=404)
    if doc.status != "ready" or doc.pdf_data is None:
        raise HTTPException(status_code=400, detail="PDF не готов")
    filename = doc.file_name or f"document-{doc.id}.pdf"
    return Response(
        content=doc.pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

### Example 3: Alembic Migration 0046 — Enum Reuse

```python
# Critical: create_type=False because 'templatetype' exists from migration 0045
def upgrade() -> None:
    op.create_table(
        "generated_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_type",
                  sa.Enum("proposal", "audit_report", "brief",
                          name="templatetype", create_type=False),
                  nullable=False),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False, server_default="document.pdf"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["proposal_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gd_client_created", "generated_documents", ["client_id", "created_at"])
    op.create_index("ix_gd_template_id", "generated_documents", ["template_id"])
```

### Example 4: Document Celery Task Core Logic

```python
# app/tasks/document_tasks.py
async def _run(document_id, template_id, client_id, site_id):
    async with AsyncSessionLocal() as db:
        doc = await db.get(GeneratedDocument, uuid.UUID(document_id))
        doc.status = "processing"
        await db.commit()

        try:
            template = await template_service.get_template(db, uuid.UUID(template_id))
            variables = await resolve_template_variables(
                db, uuid.UUID(client_id), uuid.UUID(site_id) if site_id else None
            )
            html_string = render_template_preview(template.body, variables)
            pdf_bytes = render_pdf_in_subprocess(html_string)

            doc.pdf_data = pdf_bytes
            doc.status = "ready"
            doc.file_name = _build_filename(template, variables)
            await db.commit()
            return {"status": "ready", "size": len(pdf_bytes)}
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)[:500]
            await db.commit()
            raise
```

### Example 5: Document Filename Convention (Claude's Discretion)

```python
def _build_filename(template, variables: dict) -> str:
    """Build download filename: {type}_{client_name}_{YYYY-MM-DD}.pdf"""
    import re
    from datetime import date
    client_name = variables.get("client", {}).get("name", "client")
    safe_name = re.sub(r"[^\w\-]", "_", client_name)[:40]
    return f"{template.template_type.value}_{safe_name}_{date.today().isoformat()}.pdf"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct weasyprint.HTML().write_pdf() in Celery | subprocess_pdf.render_pdf_in_subprocess() | Phase 14 (D-12) | OOM mitigation; mandatory pattern |
| Pydantic v1 validators | Pydantic v2 field_validator | Project-wide | All models use v2 |
| FastAPI on_event("startup") | asynccontextmanager lifespan | FastAPI 0.93+ | Deprecated pattern not used |

---

## Open Questions

1. **Telegram document vs message**
   - What we know: D-10 says "use existing `telegram_service.send_message_sync()`" which is text-only
   - What's unclear: Does "send via Telegram" mean attach the PDF or just notify with a link?
   - Recommendation: Implement as text notification with link ("Документ готов, скачайте: ..."). Matches DOC-05 acceptance criteria without requiring new Telegram API surface. If attachment is required, add `send_document_sync()` to telegram_service as a follow-up.

2. **Version cap scope: per (client, template) or per (client,)?**
   - What we know: D-01 says "max 3 versions per document"; "При перегенерации" suggests it's per regeneration of the same document
   - What's unclear: Is "document" = (client + template) pair, or just per client?
   - Recommendation: Per (client_id, template_id) pair. A client can have 3 proposal versions, 3 audit_report versions, etc. independently.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 23 adds no new external dependencies. All required services (PostgreSQL, Redis, Celery, WeasyPrint, aiosmtplib) are already present in the Docker Compose stack and used by prior phases.

---

## Validation Architecture

`workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`. Section skipped.

---

## Sources

### Primary (HIGH confidence)
- `app/services/subprocess_pdf.py` — WeasyPrint subprocess isolation API
- `app/services/client_report_service.py` — PDF generation + storage pattern
- `app/routers/client_reports.py` — generation flow, status polling, download, send endpoints
- `app/tasks/client_report_tasks.py` — Celery PDF + email + telegram task patterns
- `app/services/smtp_service.py` — SMTP send_email_sync() (attachment gap confirmed)
- `app/services/telegram_service.py` — send_message_sync() (text-only confirmed)
- `app/models/client_report.py` — LargeBinary pdf_data pattern
- `app/models/proposal_template.py` — TemplateType enum, confirmed reusable
- `app/templates/crm/detail.html` — tab structure for "Документы" insertion point
- `app/templates/analytics/partials/fix_status.html` — HTMX polling pattern
- `alembic/versions/0045_add_proposal_templates.py` — templatetype enum exists; next migration = 0046
- `.planning/phases/22-proposal-templates/22-01-SUMMARY.md` — template_service, variable_resolver APIs

### Secondary (MEDIUM confidence)
- aiosmtplib MIMEApplication attachment pattern — standard Python email.mime pattern, no library changes needed
- Telegram sendMessage vs sendDocument distinction — well-known Telegram Bot API behavior

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use, verified in codebase
- Architecture: HIGH — every pattern has a working codebase precedent
- Pitfalls: HIGH — enum reuse pitfall and SMTP gap are verified by direct code inspection

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable stack; no fast-moving dependencies)
