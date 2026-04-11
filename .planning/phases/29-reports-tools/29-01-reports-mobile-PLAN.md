---
phase: 29-reports-tools
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - app/config.py
  - app/routers/mobile.py
  - app/services/mobile_reports_service.py
  - app/templates/mobile/reports/new.html
  - app/templates/mobile/reports/partials/result_block.html
autonomous: true
requirements:
  - REP-01
  - REP-02

must_haves:
  truths:
    - "User opens /m/reports/new and sees project select + 2 radio-cards (Краткий / Подробный) + recipient select + disabled 'Создать отчёт' button"
    - "After selecting project + report type the 'Создать отчёт' button becomes enabled"
    - "POST /m/reports/new generates PDF via report_service.generate_pdf_report and reveals inline result block with [Скачать PDF][Отправить в Telegram][Отправить email] CTAs"
    - "GET /reports/download/{token} returns the PDF bytes with application/pdf content-type"
    - "POST /m/reports/{report_token}/send/telegram sends message_sync with absolute download URL and shows showToast('Отчёт отправлен', 'success')"
    - "POST /m/reports/{report_token}/send/email sends PDF as email attachment to client.email"
  artifacts:
    - path: "app/config.py"
      provides: "APP_BASE_URL setting"
      contains: "APP_BASE_URL"
    - path: "app/services/mobile_reports_service.py"
      provides: "list_clients_for_reports, store_report_token, load_report_pdf"
      exports: ["list_clients_for_reports", "store_report_token", "load_report_pdf"]
    - path: "app/routers/mobile.py"
      provides: "/m/reports/new GET+POST, /reports/download/{token}, /m/reports/{token}/send/telegram, /m/reports/{token}/send/email"
      contains: "mobile_report_new"
    - path: "app/templates/mobile/reports/new.html"
      provides: "Single-page report creation form extending base_mobile.html"
      contains: "Отчёт клиенту"
    - path: "app/templates/mobile/reports/partials/result_block.html"
      provides: "Inline result block with 3 CTAs revealed after POST"
      contains: "Отчёт готов"
  key_links:
    - from: "app/templates/mobile/reports/new.html"
      to: "POST /m/reports/new"
      via: "form action hx-post or plain POST"
      pattern: "(hx-post|action)=\"/m/reports/new\""
    - from: "app/routers/mobile.py mobile_report_create"
      to: "report_service.generate_pdf_report"
      via: "await generate_pdf_report(db, project_id, report_type)"
      pattern: "generate_pdf_report\\(db"
    - from: "app/routers/mobile.py report_download"
      to: "Redis token store"
      via: "aioredis.from_url(settings.REDIS_URL) .get(f'reports:dl:{token}')"
      pattern: "reports:dl:"
    - from: "app/routers/mobile.py send_telegram"
      to: "telegram_service.send_message_sync"
      via: "text + absolute download URL"
      pattern: "send_message_sync"
    - from: "app/routers/mobile.py send_email"
      to: "smtp_service.send_email_with_attachment_sync"
      via: "PDF bytes + filename"
      pattern: "send_email_with_attachment_sync"
---

<objective>
Реализовать REP-01 и REP-02: пользователь с телефона открывает `/m/reports/new`, формирует PDF (brief/detailed) и одной кнопкой отправляет его клиенту в Telegram (link-based) или email (attachment).

Purpose: Закрыть мобильный сценарий «отчёт клиенту» из v4.0 Mobile & Telegram. Весь тяжёлый функционал (WeasyPrint, SMTP, Telegram) уже работает — нужен только мобильный UI-слой + Redis token endpoint для скачивания PDF.

Output:
- `APP_BASE_URL` в settings (используется для абсолютных ссылок в Telegram)
- `app/services/mobile_reports_service.py` — helper функции
- Новые endpoints в `app/routers/mobile.py` (5 штук)
- Шаблоны `app/templates/mobile/reports/new.html` + partial `result_block.html`
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/29-reports-tools/29-CONTEXT.md
@.planning/phases/29-reports-tools/29-RESEARCH.md
@.planning/phases/29-reports-tools/29-UI-SPEC.md

<!-- Canonical references (existing code — переиспользуется) -->
@app/routers/mobile.py
@app/routers/reports.py
@app/services/report_service.py
@app/services/smtp_service.py
@app/services/telegram_service.py
@app/services/client_service.py
@app/services/project_service.py
@app/templates/mobile/base_mobile.html
@app/templates/mobile/partials/position_progress.html
@app/config.py

<interfaces>
<!-- Contracts the executor needs. DO NOT re-explore codebase. -->

From app/services/report_service.py:
```python
async def generate_pdf_report(
    db: AsyncSession,
    project_id: uuid.UUID,
    report_type: str = "brief",  # "brief" | "detailed"
) -> bytes:
    """Returns PDF bytes via WeasyPrint (subprocess isolation). 1-5s typical."""
```

From app/services/telegram_service.py:
```python
def send_message_sync(text: str) -> bool:
    """Sends text to settings.TELEGRAM_CHAT_ID (system chat). Returns True on success."""
```

From app/services/smtp_service.py:
```python
def send_email_with_attachment_sync(
    to: str,
    subject: str,
    body_html: str,
    attachment_bytes: bytes,
    attachment_filename: str,
) -> bool:
    """Returns True on success."""
```

From app/services/project_service.py:
```python
async def get_accessible_projects(db: AsyncSession, user: User) -> list[Project]:
    """Returns projects the user can access. Project has .id (UUID) and .name (str)."""
```

From app/services/client_service.py:
```python
async def list_clients(
    db: AsyncSession,
    include_deleted: bool = False,
    ...
) -> list[Client]:
    """Client has: id, company_name, email (nullable), is_deleted."""
```

From app/models/client.py:
```python
class Client(Base):
    id: UUID
    company_name: str
    email: str | None  # <-- filter source
    is_deleted: bool
    # NOTE: telegram_username is in ClientContact (separate table), NOT on Client
```

From app/services/notifications.py:
```python
async def notify(
    db: AsyncSession,
    user_id: UUID,
    kind: str,
    title: str,
    body: str,
    link_url: str,
    site_id: UUID | None = None,
    severity: Literal["info", "warning", "error"] = "info",
) -> Notification:
    """Caller commits transaction."""
```

From app/routers/mobile.py (existing pattern to clone):
```python
router = APIRouter(prefix="/m", tags=["mobile"])
mobile_templates = Jinja2Templates(directory="app/templates")

@router.post("/positions/check", status_code=202, response_class=HTMLResponse)
async def mobile_trigger_position_check(
    request: Request,
    site_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    ...
    return mobile_templates.TemplateResponse(
        "mobile/partials/position_progress.html",
        {"request": request, "status": "started", ...},
    )
```

From app/config.py (current Settings class):
```python
class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    SMTP_HOST: str = ""
    # ... NO APP_BASE_URL yet — need to add
```

Redis pattern (existing, from keyword_suggest.py):
```python
import redis.asyncio as aioredis
client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
await client.setex(f"suggest:lock:{site_id}", 300, "1")

# For binary PDF storage use decode_responses=False:
client = aioredis.from_url(settings.REDIS_URL)  # no decode_responses
await client.set(f"reports:dl:{token}", pdf_bytes, ex=604800)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: APP_BASE_URL setting + mobile_reports_service with Redis token helpers</name>
  <read_first>
    - app/config.py
    - app/services/client_service.py
    - app/services/project_service.py
  </read_first>
  <files>
    - app/config.py
    - app/services/mobile_reports_service.py
  </files>
  <action>
  **Step 1 — Add APP_BASE_URL to app/config.py Settings class.**

  Locate the `Settings(BaseSettings)` class and add this field after the existing `TELEGRAM_*` block (around line 55, before `SMTP` block):
  ```python
  # Mobile reports download links (absolute URL for Telegram delivery)
  APP_BASE_URL: str = "http://localhost:8000"
  ```
  Do NOT change any other field. Do NOT reformat the file.

  **Step 2 — Create app/services/mobile_reports_service.py** with this exact content (per D-05, D-06, canonical refs):
  ```python
  """Mobile reports helpers: client list, Redis download token storage."""
  from __future__ import annotations

  import secrets
  import uuid
  from dataclasses import dataclass

  import redis.asyncio as aioredis
  from loguru import logger
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from app.config import settings
  from app.models.client import Client

  TOKEN_TTL_SECONDS = 604800  # 7 days
  TOKEN_KEY_PREFIX = "reports:dl:"


  @dataclass
  class ClientForReports:
      id: uuid.UUID
      company_name: str
      email: str | None
      has_email: bool


  async def list_clients_for_reports(db: AsyncSession) -> list[ClientForReports]:
      """Return non-deleted clients with email (for recipient select on /m/reports/new).

      Per D-05: flat select from Client CRM filtered by email IS NOT NULL.
      Telegram delivery goes to system chat (not per-client), so email is the
      only hard-filter criterion here.
      """
      stmt = (
          select(Client)
          .where(Client.is_deleted == False)  # noqa: E712
          .where(Client.email.isnot(None))
          .order_by(Client.company_name)
      )
      result = await db.execute(stmt)
      clients = result.scalars().all()
      return [
          ClientForReports(
              id=c.id,
              company_name=c.company_name,
              email=c.email,
              has_email=bool(c.email),
          )
          for c in clients
      ]


  def _binary_redis_client() -> aioredis.Redis:
      """Redis client WITHOUT decode_responses — required for PDF bytes storage."""
      return aioredis.from_url(settings.REDIS_URL)


  async def store_report_pdf(pdf_bytes: bytes) -> str:
      """Store PDF bytes under a fresh token key. Returns the token.

      Key: reports:dl:{token}  TTL: 7 days.
      """
      token = secrets.token_urlsafe(32)
      r = _binary_redis_client()
      try:
          await r.set(f"{TOKEN_KEY_PREFIX}{token}", pdf_bytes, ex=TOKEN_TTL_SECONDS)
          logger.info("stored report pdf token={} bytes={}", token, len(pdf_bytes))
      finally:
          await r.aclose()
      return token


  async def load_report_pdf(token: str) -> bytes | None:
      """Load PDF bytes by token. Returns None if missing/expired."""
      r = _binary_redis_client()
      try:
          data = await r.get(f"{TOKEN_KEY_PREFIX}{token}")
      finally:
          await r.aclose()
      return data


  def build_download_url(token: str) -> str:
      """Build absolute /reports/download/{token} URL using settings.APP_BASE_URL."""
      base = (settings.APP_BASE_URL or "http://localhost:8000").rstrip("/")
      return f"{base}/reports/download/{token}"
  ```

  Rationale (from D-01..D-07, Research Pitfall 1):
  - Separate Redis client without `decode_responses=True` because PDF bytes are not UTF-8
  - `secrets.token_urlsafe(32)` gives ~43-char URL-safe token
  - TTL 604800 = 7 days per D-06
  - `list_clients_for_reports` filters by `Client.email IS NOT NULL` only (Telegram goes to system chat, see Research Pitfall 5)
  </action>
  <verify>
    <automated>python -c "from app.config import settings; assert hasattr(settings, 'APP_BASE_URL'), 'APP_BASE_URL missing'; print('APP_BASE_URL=', settings.APP_BASE_URL)"</automated>
    <automated>python -c "from app.services.mobile_reports_service import list_clients_for_reports, store_report_pdf, load_report_pdf, build_download_url, TOKEN_KEY_PREFIX; assert TOKEN_KEY_PREFIX == 'reports:dl:'"</automated>
  </verify>
  <acceptance_criteria>
    - grep -q "APP_BASE_URL" app/config.py
    - grep -q "APP_BASE_URL: str" app/config.py
    - test -f app/services/mobile_reports_service.py
    - grep -q "def list_clients_for_reports" app/services/mobile_reports_service.py
    - grep -q "def store_report_pdf" app/services/mobile_reports_service.py
    - grep -q "def load_report_pdf" app/services/mobile_reports_service.py
    - grep -q "def build_download_url" app/services/mobile_reports_service.py
    - grep -q "reports:dl:" app/services/mobile_reports_service.py
    - grep -q "604800" app/services/mobile_reports_service.py
    - grep -q "decode_responses" app/services/mobile_reports_service.py
    - python -c "import ast; ast.parse(open('app/services/mobile_reports_service.py').read())"
  </acceptance_criteria>
  <done>Config has APP_BASE_URL, new service file compiles and exposes the 4 helpers used by Task 2.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Mobile report endpoints (GET /m/reports/new, POST /m/reports/new, GET /reports/download/{token}, send endpoints)</name>
  <read_first>
    - app/routers/mobile.py
    - app/routers/reports.py
    - app/services/mobile_reports_service.py
    - app/services/report_service.py
    - app/services/project_service.py
  </read_first>
  <files>
    - app/routers/mobile.py
  </files>
  <action>
  Append new endpoints at the END of `app/routers/mobile.py` (after the last existing `@router.*` handler, before any final module-level code if present). Use the existing `router = APIRouter(prefix="/m", tags=["mobile"])` and `mobile_templates` — do NOT create a new router.

  **Imports to add** (merge into existing imports at top of file — do NOT duplicate):
  ```python
  from fastapi import File, UploadFile  # UploadFile unused here; add in Plan 02
  from fastapi.responses import StreamingResponse
  from app.services import report_service
  from app.services.mobile_reports_service import (
      build_download_url,
      list_clients_for_reports,
      load_report_pdf,
      store_report_pdf,
  )
  from app.services.project_service import get_accessible_projects
  from app.services import telegram_service, smtp_service
  ```
  (Omit `File, UploadFile` if not used yet — they're needed in Plan 02.)

  **Append these 5 handlers verbatim** (adapt only to match existing codestyle — 4-space indent, loguru, `mobile_templates.TemplateResponse`):

  ```python
  # ---------------------------------------------------------------------------
  # /m/reports — Phase 29 Reports & Tools (REP-01, REP-02)
  # ---------------------------------------------------------------------------

  @router.get("/reports/new", response_class=HTMLResponse, name="mobile_report_new")
  async def mobile_report_new(
      request: Request,
      report_token: str | None = None,
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> HTMLResponse:
      """Single-page form for creating a PDF report (D-03).

      If ?report_token=... is present, result block is pre-rendered (server-side
      reveal alternative to HTMX swap — simpler for MVP per D-04).
      """
      projects = await get_accessible_projects(db, user)
      clients = await list_clients_for_reports(db)
      ctx = {
          "request": request,
          "active_tab": "more",
          "projects": projects,
          "clients": clients,
          "report_token": report_token,
          "report_type": request.query_params.get("report_type", ""),
          "project_name": request.query_params.get("project_name", ""),
      }
      return mobile_templates.TemplateResponse("mobile/reports/new.html", ctx)


  @router.post("/reports/new", response_class=HTMLResponse)
  async def mobile_report_create(
      request: Request,
      project_id: uuid.UUID = Form(...),
      report_type: str = Form("brief"),
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> HTMLResponse:
      """Generate PDF synchronously, store bytes in Redis, return inline result partial."""
      if report_type not in ("brief", "detailed"):
          raise HTTPException(status_code=422, detail="report_type must be brief|detailed")

      try:
          pdf_bytes = await report_service.generate_pdf_report(db, project_id, report_type)
      except Exception as exc:
          logger.error("mobile report generation failed: {}", exc)
          raise HTTPException(status_code=500, detail="Не удалось сгенерировать отчёт") from exc

      token = await store_report_pdf(pdf_bytes)

      # Load project name for display
      from app.models.project import Project
      proj = await db.get(Project, project_id)
      project_name = proj.name if proj else ""

      clients = await list_clients_for_reports(db)
      return mobile_templates.TemplateResponse(
          "mobile/reports/partials/result_block.html",
          {
              "request": request,
              "report_token": token,
              "report_type": report_type,
              "project_name": project_name,
              "clients": clients,
          },
      )


  @router.get("/reports/download/{token}", name="mobile_report_download")
  async def mobile_report_download(token: str) -> StreamingResponse:
      """Token-protected PDF download (D-06). No auth — token IS the auth."""
      pdf_bytes = await load_report_pdf(token)
      if not pdf_bytes:
          raise HTTPException(status_code=404, detail="Token expired or invalid")
      return StreamingResponse(
          iter([pdf_bytes]),
          media_type="application/pdf",
          headers={"Content-Disposition": 'attachment; filename="report.pdf"'},
      )


  @router.post("/reports/{token}/send/telegram", response_class=JSONResponse)
  async def mobile_report_send_telegram(
      token: str,
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> JSONResponse:
      """Send link-based Telegram delivery (D-06): send_message_sync with absolute URL."""
      pdf_bytes = await load_report_pdf(token)
      if not pdf_bytes:
          return JSONResponse({"ok": False, "error": "Ссылка истекла"}, status_code=410)

      url = build_download_url(token)
      ok = telegram_service.send_message_sync(f"Отчёт клиенту готов:\n{url}")
      if not ok:
          return JSONResponse(
              {"ok": False, "error": "Ошибка отправки в Telegram"},
              status_code=502,
          )
      return JSONResponse({"ok": True})


  @router.post("/reports/{token}/send/email", response_class=JSONResponse)
  async def mobile_report_send_email(
      token: str,
      client_id: uuid.UUID = Form(...),
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> JSONResponse:
      """Send PDF as email attachment to selected Client.email."""
      from app.models.client import Client as ClientModel
      client = await db.get(ClientModel, client_id)
      if client is None or client.is_deleted or not client.email:
          return JSONResponse(
              {"ok": False, "error": "Ошибка: email клиента не указан"},
              status_code=422,
          )

      pdf_bytes = await load_report_pdf(token)
      if not pdf_bytes:
          return JSONResponse({"ok": False, "error": "Ссылка истекла"}, status_code=410)

      ok = smtp_service.send_email_with_attachment_sync(
          to=client.email,
          subject="SEO-отчёт",
          body_html="<p>Во вложении — актуальный SEO-отчёт по вашему проекту.</p>",
          attachment_bytes=pdf_bytes,
          attachment_filename="report.pdf",
      )
      if not ok:
          return JSONResponse(
              {"ok": False, "error": "Ошибка отправки email"},
              status_code=502,
          )
      return JSONResponse({"ok": True})
  ```

  **Critical constraints:**
  - Do NOT introduce new router — use the existing `router = APIRouter(prefix="/m", ...)`
  - Download endpoint path will be `/m/reports/download/{token}` due to router prefix; RESEARCH.md mentions `/reports/download/{token}` but since we're in the /m/ router, the effective URL is `/m/reports/download/{token}` — update `build_download_url` in mobile_reports_service.py accordingly:
    ```python
    return f"{base}/m/reports/download/{token}"
    ```
    Edit `app/services/mobile_reports_service.py` `build_download_url` to use `/m/reports/download/` prefix.
  - Keep existing endpoints untouched.
  </action>
  <verify>
    <automated>python -c "from app.routers.mobile import router; paths = [r.path for r in router.routes]; assert any('/reports/new' in p for p in paths), paths; assert any('/reports/download/' in p for p in paths), paths; print('OK paths:', [p for p in paths if 'reports' in p])"</automated>
    <automated>python -c "import ast; ast.parse(open('app/routers/mobile.py').read())"</automated>
  </verify>
  <acceptance_criteria>
    - grep -q "mobile_report_new" app/routers/mobile.py
    - grep -q "mobile_report_create" app/routers/mobile.py
    - grep -q "mobile_report_download" app/routers/mobile.py
    - grep -q "mobile_report_send_telegram" app/routers/mobile.py
    - grep -q "mobile_report_send_email" app/routers/mobile.py
    - grep -q "generate_pdf_report" app/routers/mobile.py
    - grep -q "store_report_pdf" app/routers/mobile.py
    - grep -q "load_report_pdf" app/routers/mobile.py
    - grep -q "send_message_sync" app/routers/mobile.py
    - grep -q "send_email_with_attachment_sync" app/routers/mobile.py
    - grep -q "/m/reports/download/" app/services/mobile_reports_service.py
    - python -c "import ast; ast.parse(open('app/routers/mobile.py').read())"
    - python -c "from app.routers.mobile import router"
  </acceptance_criteria>
  <done>All 5 endpoints registered on the /m/ router, module parses and imports cleanly, build_download_url returns `/m/reports/download/...`.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Mobile report templates (new.html single-page form + result_block.html partial)</name>
  <read_first>
    - app/templates/mobile/base_mobile.html
    - app/templates/mobile/positions.html
    - app/templates/mobile/traffic.html
    - .planning/phases/29-reports-tools/29-UI-SPEC.md
  </read_first>
  <files>
    - app/templates/mobile/reports/new.html
    - app/templates/mobile/reports/partials/result_block.html
  </files>
  <action>
  **Create app/templates/mobile/reports/new.html** (single-page form, D-03 + UI-SPEC Section «1. /m/reports/new»):

  ```html
  {% extends "mobile/base_mobile.html" %}
  {% block title %}Отчёт клиенту{% endblock %}
  {% block content %}
  <div class="p-4">
    <h1 class="text-xl font-semibold mb-4">Отчёт клиенту</h1>

    {% if not projects %}
      <div class="bg-white rounded-lg p-4 text-sm text-gray-500">
        Нет проектов. Создайте проект на полной версии платформы.
      </div>
    {% else %}
    <form id="report-form"
          hx-post="/m/reports/new"
          hx-target="#result-slot"
          hx-swap="innerHTML"
          hx-indicator="#submit-spinner">

      <label class="block text-xs text-gray-500 mb-1">Проект</label>
      <select name="project_id" id="project-select"
              class="w-full min-h-[44px] rounded-lg border border-gray-300 bg-white px-3 mb-4 text-sm"
              required>
        <option value="">— Выберите проект —</option>
        {% for p in projects %}
          <option value="{{ p.id }}">{{ p.name }}</option>
        {% endfor %}
      </select>

      <label class="block text-xs text-gray-500 mb-2">Тип отчёта</label>
      <div class="grid grid-cols-1 gap-2 mb-4" id="report-type-cards">
        <label class="bg-white rounded-lg border-2 border-gray-200 p-4 cursor-pointer report-type-card block">
          <input type="radio" name="report_type" value="brief" class="sr-only" required>
          <div class="text-sm font-semibold">Краткий (1-2 стр.)</div>
          <div class="text-xs text-gray-500">Топ-изменения + задачи</div>
        </label>
        <label class="bg-white rounded-lg border-2 border-gray-200 p-4 cursor-pointer report-type-card block">
          <input type="radio" name="report_type" value="detailed" class="sr-only">
          <div class="text-sm font-semibold">Подробный (5-10 стр.)</div>
          <div class="text-xs text-gray-500">Полная таблица keywords + задачи + изменения</div>
        </label>
      </div>

      <button type="submit" id="submit-btn" disabled
              class="w-full min-h-[44px] rounded-lg text-white font-semibold text-sm opacity-50 cursor-not-allowed"
              style="background:#4f46e5;">
        <span class="htmx-indicator inline-block" id="submit-spinner">⏳</span>
        Создать отчёт
      </button>
    </form>

    <div id="result-slot" class="mt-4">
      {% if report_token %}
        {% include "mobile/reports/partials/result_block.html" %}
      {% endif %}
    </div>
    {% endif %}
  </div>

  <script>
  (function(){
    const form = document.getElementById('report-form');
    if (!form) return;
    const btn = document.getElementById('submit-btn');
    const select = document.getElementById('project-select');
    const cards = document.querySelectorAll('.report-type-card');

    function refresh(){
      const project = select.value;
      const type = form.querySelector('input[name="report_type"]:checked');
      const ok = project && type;
      btn.disabled = !ok;
      btn.classList.toggle('opacity-50', !ok);
      btn.classList.toggle('cursor-not-allowed', !ok);
    }
    select.addEventListener('change', refresh);
    cards.forEach(card => {
      card.addEventListener('click', () => {
        cards.forEach(c => c.classList.replace('border-indigo-600', 'border-gray-200'));
        card.classList.replace('border-gray-200', 'border-indigo-600');
        const input = card.querySelector('input[type=radio]');
        input.checked = true;
        refresh();
      });
    });
    refresh();
  })();
  </script>
  {% endblock %}
  ```

  **Create app/templates/mobile/reports/partials/result_block.html** (inline result, D-04 + UI-SPEC Section «Result block»):

  ```html
  {# Result block revealed after POST /m/reports/new. D-04 + UI-SPEC #}
  {% set has_email_clients = clients and clients|selectattr('has_email')|list %}
  <div class="bg-white rounded-lg p-4 mt-4">
    <div class="text-sm font-semibold text-green-700 mb-2">Отчёт готов</div>
    <div class="text-xs text-gray-500 mb-3">
      {{ project_name }} — {% if report_type == 'brief' %}Краткий (1-2 стр.){% else %}Подробный (5-10 стр.){% endif %}
    </div>

    <a href="/m/reports/download/{{ report_token }}"
       class="block w-full min-h-[44px] rounded-lg text-sm font-semibold text-center border border-gray-300 text-gray-700 bg-white py-3 mb-2">
       Скачать PDF
    </a>

    <button type="button"
            class="w-full min-h-[44px] rounded-lg text-white font-semibold text-sm py-3 mb-2"
            style="background:#4f46e5;"
            onclick="sendReportTelegram('{{ report_token }}')">
      Отправить в Telegram
    </button>

    <div class="mb-2">
      <label class="block text-xs text-gray-500 mb-1">Клиент (email)</label>
      <select id="report-client-select"
              class="w-full min-h-[44px] rounded-lg border border-gray-300 bg-white px-3 text-sm">
        <option value="">— Выберите клиента —</option>
        {% for c in clients %}
          {% if c.has_email %}
          <option value="{{ c.id }}">📧 {{ c.company_name }}</option>
          {% endif %}
        {% endfor %}
      </select>
    </div>

    <button type="button"
            class="w-full min-h-[44px] rounded-lg text-sm font-semibold border border-gray-300 text-gray-700 bg-white py-3 {% if not has_email_clients %}opacity-40{% endif %}"
            onclick="sendReportEmail('{{ report_token }}')">
      Отправить email
    </button>
  </div>

  <script>
  async function sendReportTelegram(token){
    try {
      const r = await fetch('/m/reports/' + token + '/send/telegram', {method:'POST'});
      const data = await r.json();
      if (r.ok && data.ok) {
        showToast('Отчёт отправлен', 'success');
      } else {
        showToast(data.error || 'Ошибка: клиент не привязан к Telegram', 'error');
      }
    } catch(e){ showToast('Ошибка сети', 'error'); }
  }
  async function sendReportEmail(token){
    const sel = document.getElementById('report-client-select');
    const clientId = sel ? sel.value : '';
    if (!clientId){ showToast('Выберите клиента', 'error'); return; }
    try {
      const fd = new FormData();
      fd.append('client_id', clientId);
      const r = await fetch('/m/reports/' + token + '/send/email', {method:'POST', body: fd});
      const data = await r.json();
      if (r.ok && data.ok) {
        showToast('Отчёт отправлен', 'success');
      } else {
        showToast(data.error || 'Ошибка: email клиента не указан', 'error');
      }
    } catch(e){ showToast('Ошибка сети', 'error'); }
  }
  </script>
  ```

  **Constraints (from UI-SPEC):**
  - Accent `#4f46e5` only on primary CTA + selected radio-card border
  - `min-h-[44px]` on all interactive elements
  - Font sizes: `text-xl` heading, `text-sm` body, `text-xs` secondary (no other sizes)
  - Toast pattern via global `showToast(msg, level)` from base_mobile.html
  - Empty state copy: "Нет проектов. Создайте проект на полной версии платформы."

  **Per D-02:** Only two radio-card options: brief + detailed. NO `client_instructions` option.
  **Per D-03:** Single page, NO multi-step wizard, NO HTMX swap between steps.
  **Per D-05:** Recipient list only shows clients with `has_email=True`.
  </action>
  <verify>
    <automated>test -f app/templates/mobile/reports/new.html && test -f app/templates/mobile/reports/partials/result_block.html</automated>
    <automated>python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); env.get_template('mobile/reports/new.html'); env.get_template('mobile/reports/partials/result_block.html'); print('templates parse OK')"</automated>
  </verify>
  <acceptance_criteria>
    - test -f app/templates/mobile/reports/new.html
    - test -f app/templates/mobile/reports/partials/result_block.html
    - grep -q "Отчёт клиенту" app/templates/mobile/reports/new.html
    - grep -q "extends \"mobile/base_mobile.html\"" app/templates/mobile/reports/new.html
    - grep -q "hx-post=\"/m/reports/new\"" app/templates/mobile/reports/new.html
    - grep -q "Краткий (1-2 стр.)" app/templates/mobile/reports/new.html
    - grep -q "Подробный (5-10 стр.)" app/templates/mobile/reports/new.html
    - grep -q "Создать отчёт" app/templates/mobile/reports/new.html
    - grep -q 'value="brief"' app/templates/mobile/reports/new.html
    - grep -q 'value="detailed"' app/templates/mobile/reports/new.html
    - grep -q 'min-h-\[44px\]' app/templates/mobile/reports/new.html
    - grep -q "#4f46e5" app/templates/mobile/reports/new.html
    - grep -q "Отчёт готов" app/templates/mobile/reports/partials/result_block.html
    - grep -q "Скачать PDF" app/templates/mobile/reports/partials/result_block.html
    - grep -q "Отправить в Telegram" app/templates/mobile/reports/partials/result_block.html
    - grep -q "Отправить email" app/templates/mobile/reports/partials/result_block.html
    - grep -q "/m/reports/download/" app/templates/mobile/reports/partials/result_block.html
    - grep -q "send/telegram" app/templates/mobile/reports/partials/result_block.html
    - grep -q "send/email" app/templates/mobile/reports/partials/result_block.html
    - grep -q "showToast" app/templates/mobile/reports/partials/result_block.html
    - python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); env.get_template('mobile/reports/new.html'); env.get_template('mobile/reports/partials/result_block.html')"
  </acceptance_criteria>
  <done>Both templates parse via Jinja2, render from base_mobile.html, contain form + HTMX POST + result block with 3 CTAs per UI-SPEC.</done>
</task>

</tasks>

<verification>
- [ ] GET /m/reports/new renders single-page form with project select, 2 radio-cards, disabled submit
- [ ] POST /m/reports/new with valid project_id + report_type generates PDF and returns result_block partial
- [ ] GET /m/reports/download/{token} returns application/pdf with PDF bytes
- [ ] POST /m/reports/{token}/send/telegram calls telegram_service.send_message_sync
- [ ] POST /m/reports/{token}/send/email sends attachment via smtp_service
- [ ] All templates extend base_mobile.html
- [ ] Accent #4f46e5 used only on primary CTA + selected card border
- [ ] Deferred ideas NOT implemented: no scheduled reports, no PDF preview, no ReportDelivery table, no client_instructions type
</verification>

<success_criteria>
- All 3 tasks pass their acceptance_criteria
- `from app.routers.mobile import router` imports cleanly
- Jinja2 can parse both new templates
- REP-01 covered: 3-step (project select → radio-card → submit) flow working
- REP-02 covered: Telegram + email CTAs in result block both reach delivery services
</success_criteria>

<output>
After completion: write `.planning/phases/29-reports-tools/29-01-SUMMARY.md` per template.
</output>
