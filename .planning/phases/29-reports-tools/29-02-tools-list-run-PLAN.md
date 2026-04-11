---
phase: 29-reports-tools
plan: 02
type: execute
wave: 2
depends_on:
  - 29-01
files_modified:
  - app/routers/mobile.py
  - app/services/mobile_tools_service.py
  - app/templates/mobile/tools/list.html
  - app/templates/mobile/tools/run.html
  - app/templates/mobile/tools/partials/tool_progress.html
autonomous: true
requirements:
  - TLS-01

must_haves:
  truths:
    - "User opens /m/tools and sees single-column card list with 6 tool cards (commercialization, meta-parser, relevant-url, brief, wordstat-batch, paa)"
    - "Wordstat-batch card shows 'Требует Wordstat' amber badge"
    - "Tap on wordstat-batch card without OAuth token redirects to /ui/integrations/wordstat/auth?return_to=/m/tools/wordstat-batch/run"
    - "User opens /m/tools/{slug}/run and sees textarea + file upload input + launch CTA"
    - "POST /m/tools/{slug}/run with textarea content creates Job, dispatches Celery task, returns HTMX polling partial"
    - "GET /m/tools/{slug}/jobs/{job_id}/status returns running → done state transition with hx-trigger stopping on done"
  artifacts:
    - path: "app/services/mobile_tools_service.py"
      provides: "parse_tool_input, get_job_for_user"
      exports: ["parse_tool_input", "get_job_for_user"]
    - path: "app/routers/mobile.py"
      provides: "GET /m/tools, GET /m/tools/{slug}/run, POST /m/tools/{slug}/run, GET /m/tools/{slug}/jobs/{job_id}/status"
      contains: "mobile_tools_list"
    - path: "app/templates/mobile/tools/list.html"
      provides: "Single-column card list with 6 tool cards"
      contains: "SEO Инструменты"
    - path: "app/templates/mobile/tools/run.html"
      provides: "Tool entry form with textarea + file upload"
      contains: "Запустить"
    - path: "app/templates/mobile/tools/partials/tool_progress.html"
      provides: "HTMX polling partial with running/done/error states"
      contains: "every 3s"
  key_links:
    - from: "app/templates/mobile/tools/list.html"
      to: "/m/tools/{slug}/run"
      via: "a href per card"
      pattern: "/m/tools/"
    - from: "app/routers/mobile.py mobile_tool_run"
      to: "_get_tool_task(slug).delay"
      via: "reuses tools.py helpers"
      pattern: "_get_tool_task"
    - from: "app/templates/mobile/tools/partials/tool_progress.html"
      to: "/m/tools/{slug}/jobs/{job_id}/status"
      via: "hx-get every 3s"
      pattern: "every 3s"
---

<objective>
Реализовать TLS-01 (часть 1): список инструментов `/m/tools`, страница запуска `/m/tools/{slug}/run` с textarea + file upload, диспатч Celery task, HTMX-поллинг прогресса. Mobile-specific endpoints, переиспользующие `TOOL_REGISTRY` и `_get_tool_task()` из `app/routers/tools.py`.

Purpose: Пользователь с телефона видит все 6 SEO-инструментов и запускает любой из них. Вся тяжёлая логика (6 Celery tasks, модели Job+Result, OAuth check) уже работает на desktop — фаза добавляет мобильный UI-слой + новые роуты + один новый input parser (file upload TXT/XLSX, D-11).

Output:
- `app/services/mobile_tools_service.py` — helpers для input parsing и job lookup
- 4 новых endpoint в `app/routers/mobile.py`
- Шаблоны `mobile/tools/list.html`, `run.html`, `partials/tool_progress.html`
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/29-reports-tools/29-CONTEXT.md
@.planning/phases/29-reports-tools/29-RESEARCH.md
@.planning/phases/29-reports-tools/29-UI-SPEC.md
@.planning/phases/29-reports-tools/29-01-reports-mobile-PLAN.md
@app/routers/mobile.py
@app/routers/tools.py
@app/templates/mobile/base_mobile.html
@app/templates/mobile/partials/position_progress.html

<interfaces>
<!-- Extracted from app/routers/tools.py — executor reuses these directly -->

From app/routers/tools.py:
```python
TOOL_REGISTRY: dict[str, dict] = {
    "commercialization": {
        "name": "Проверка коммерциализации",
        "description": "Анализ коммерциализации поисковой выдачи по ключевым фразам",
        "input_type": "phrases",  # or "urls"
        "form_field": "phrases",   # or "urls"
        "input_col": "input_phrases",
        "count_col": "phrase_count",
        "limit": 200,
        "cta": "Проверить коммерциализацию",
        "slug": "commercialization",
        "has_domain_field": False,
    },
    "meta-parser":    {..., "limit": 500, "has_domain_field": False},
    "relevant-url":   {..., "limit": 100, "has_domain_field": True},
    "brief":          {..., "limit": 30,  "has_region_field": True, "export_only_xlsx": True},
    "wordstat-batch": {..., "limit": 1000, "needs_oauth": "wordstat", "export_only_xlsx": True},
    "paa":            {..., "limit": 50},
}

def _get_tool_models(slug: str) -> tuple[type, type]:
    """Returns (JobModel, ResultModel) for slug. Lazy-imports to avoid cycles."""

def _get_tool_task(slug: str):
    """Returns Celery task function (e.g. run_commerce_check)."""

def _check_oauth_token_sync(needs_oauth: str) -> str | None:
    """Returns token if present, None otherwise. Runs in executor."""
```

From app/routers/tools.py dispatch pattern (lines ~380-440):
```python
job_kwargs: dict = {
    "id": uuid.uuid4(),
    "status": "pending",
    "user_id": user.id,
    "created_at": datetime.now(timezone.utc),
    registry["input_col"]: lines,
    registry["count_col"]: len(lines),
}
if registry.get("has_domain_field"):
    job_kwargs["target_domain"] = domain.strip()
if registry.get("has_region_field"):
    job_kwargs["input_region"] = int(region or 213)

job = JobModel(**job_kwargs)
db.add(job)
await db.commit()
await db.refresh(job)

# Brief tool uses a chain; others use .delay()
if slug == "brief":
    celery_chain(
        run_brief_step1_serp.si(job_id_str),
        run_brief_step2_crawl.si(job_id_str),
        run_brief_step3_aggregate.si(job_id_str),
        run_brief_step4_finalize.si(job_id_str),
    ).delay()
else:
    _get_tool_task(slug).delay(job_id_str)
```

From app/templates/mobile/partials/position_progress.html (pattern to clone):
```html
{% if status in ["started", "running"] %}
<div id="tool-progress-slot"
     hx-get="/m/tools/{{ slug }}/jobs/{{ job_id }}/status"
     hx-trigger="every 3s"
     hx-target="this"
     hx-swap="outerHTML">
  <!-- spinner + progress bar -->
</div>
{% elif status == "done" %}
<div id="tool-progress-slot">
  <!-- NO hx-trigger — polling stops -->
  <a href="/m/tools/{{ slug }}/jobs/{{ job_id }}">Показать результаты</a>
</div>
{% else %}  {# error #}
<div id="tool-progress-slot">Ошибка. Попробуйте ещё раз.</div>
{% endif %}
```

From app/services/batch_wordstat_service.py:
```python
def check_wordstat_oauth_token(db) -> str | None:
    """Sync helper — returns token if present, None otherwise."""
```

Job model fields (all 6 tool jobs have these — verified):
```python
class <Tool>Job:
    id: UUID
    user_id: UUID  # <-- already exists on all 6 models
    status: str  # "pending" | "running" | "complete" | "partial" | "failed"
    created_at: datetime
    # tool-specific: input_phrases (list), phrase_count (int), etc.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: mobile_tools_service.py — input parsing (textarea+file) and job lookup helper</name>
  <read_first>
    - app/routers/tools.py
    - app/models/commerce_check_job.py
  </read_first>
  <files>
    - app/services/mobile_tools_service.py
  </files>
  <action>
  Create `app/services/mobile_tools_service.py` with this exact content:

  ```python
  """Mobile tools helpers: input parsing (textarea + file upload) and job lookup.

  Per D-11: textarea and file upload are both available; if both provided —
  error 'Используйте одно из двух: текст или файл'.
  """
  from __future__ import annotations

  import io
  import uuid
  from dataclasses import dataclass
  from typing import Any

  from fastapi import HTTPException, UploadFile
  from loguru import logger
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession


  @dataclass
  class ToolInputResult:
      lines: list[str]
      count: int


  async def parse_tool_input(
      raw_text: str,
      upload: UploadFile | None,
      limit: int,
  ) -> ToolInputResult:
      """Parse textarea OR file upload into a list of trimmed non-empty lines.

      D-11 rules:
      - If both `raw_text` and `upload` are non-empty → raise 422 'Используйте одно из двух'
      - If neither → raise 422 'Список не может быть пустым'
      - If count > limit → raise 422 'Превышен лимит: {limit} строк'
      - File .xlsx → openpyxl reads column A
      - File .txt (or any non-xlsx) → splitlines() on decoded bytes
      """
      has_text = bool(raw_text and raw_text.strip())
      has_file = upload is not None and (upload.filename or "").strip() != ""

      if has_text and has_file:
          raise HTTPException(
              status_code=422,
              detail="Используйте одно из двух: текст или файл",
          )
      if not has_text and not has_file:
          raise HTTPException(status_code=422, detail="Список не может быть пустым")

      if has_text:
          lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
      else:
          content = await upload.read()
          filename = (upload.filename or "").lower()
          if filename.endswith(".xlsx"):
              lines = _parse_xlsx(content)
          else:
              try:
                  decoded = content.decode("utf-8", errors="replace")
              except Exception as exc:
                  raise HTTPException(status_code=422, detail="Не удалось прочитать файл") from exc
              lines = [ln.strip() for ln in decoded.splitlines() if ln.strip()]

      if not lines:
          raise HTTPException(status_code=422, detail="Список не может быть пустым")
      if len(lines) > limit:
          raise HTTPException(status_code=422, detail=f"Превышен лимит: {limit} строк")

      return ToolInputResult(lines=lines, count=len(lines))


  def _parse_xlsx(content: bytes) -> list[str]:
      """Read column A from first worksheet. Skip header if it's non-data-ish."""
      import openpyxl
      try:
          wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
      except Exception as exc:
          raise HTTPException(status_code=422, detail="Не удалось прочитать XLSX") from exc
      ws = wb.active
      result: list[str] = []
      for row in ws.iter_rows(values_only=True):
          if not row:
              continue
          cell = row[0]
          if cell is None:
              continue
          s = str(cell).strip()
          if s:
              result.append(s)
      wb.close()
      return result


  async def get_job_for_user(
      db: AsyncSession,
      job_model: type,
      job_id: uuid.UUID,
      user_id: uuid.UUID,
  ) -> Any | None:
      """Return job instance if it exists and belongs to user, else None."""
      stmt = select(job_model).where(job_model.id == job_id, job_model.user_id == user_id)
      result = await db.execute(stmt)
      return result.scalars().first()
  ```

  Rationale:
  - `parse_tool_input` is the ONLY new logic for D-11 — reused by POST /m/tools/{slug}/run in Task 2
  - `get_job_for_user` centralizes the ownership check used by status + result endpoints
  - openpyxl is already in project deps (tools.py uses it for export)
  - No changes to existing tool models or tasks
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('app/services/mobile_tools_service.py').read())"</automated>
    <automated>python -c "from app.services.mobile_tools_service import parse_tool_input, get_job_for_user, ToolInputResult, _parse_xlsx"</automated>
  </verify>
  <acceptance_criteria>
    - test -f app/services/mobile_tools_service.py
    - grep -q "async def parse_tool_input" app/services/mobile_tools_service.py
    - grep -q "async def get_job_for_user" app/services/mobile_tools_service.py
    - grep -q "Используйте одно из двух" app/services/mobile_tools_service.py
    - grep -q "Превышен лимит" app/services/mobile_tools_service.py
    - grep -q "openpyxl.load_workbook" app/services/mobile_tools_service.py
    - python -c "import ast; ast.parse(open('app/services/mobile_tools_service.py').read())"
    - python -c "from app.services.mobile_tools_service import parse_tool_input, get_job_for_user"
  </acceptance_criteria>
  <done>Service module parses, exports the two helpers, enforces D-11 both-populated rule with exact error copy from UI-SPEC.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Mobile tools endpoints (list, run, status polling) in mobile.py</name>
  <read_first>
    - app/routers/mobile.py
    - app/routers/tools.py
    - app/services/mobile_tools_service.py
  </read_first>
  <files>
    - app/routers/mobile.py
  </files>
  <action>
  Append these 4 endpoints at the END of `app/routers/mobile.py` (after the /m/reports endpoints added in Plan 01).

  **Imports to merge** (check what's already imported; add missing ones):
  ```python
  import asyncio
  from datetime import datetime, timezone
  from celery import chain as celery_chain
  from fastapi import File, Query, UploadFile
  from fastapi.responses import RedirectResponse
  from app.routers.tools import (
      TOOL_REGISTRY,
      _get_tool_models,
      _get_tool_task,
      _check_oauth_token_sync,
  )
  from app.services.mobile_tools_service import parse_tool_input, get_job_for_user
  ```

  **Append these handlers verbatim:**

  ```python
  # ---------------------------------------------------------------------------
  # /m/tools — Phase 29 Mobile Tools (TLS-01)
  # ---------------------------------------------------------------------------

  @router.get("/tools", response_class=HTMLResponse, name="mobile_tools_list")
  async def mobile_tools_list(
      request: Request,
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> HTMLResponse:
      """Single-column card list of 6 tools (D-08, D-09)."""
      tools = [
          {"slug": slug, **info}
          for slug, info in TOOL_REGISTRY.items()
      ]
      return mobile_templates.TemplateResponse(
          "mobile/tools/list.html",
          {"request": request, "active_tab": "more", "tools": tools},
      )


  @router.get("/tools/{slug}/run", response_class=HTMLResponse, name="mobile_tool_run_form")
  async def mobile_tool_run_form(
      slug: str,
      request: Request,
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ):
      """Tool entry screen. For wordstat-batch: redirect to desktop OAuth if no token (D-10)."""
      if slug not in TOOL_REGISTRY:
          raise HTTPException(status_code=404, detail="Unknown tool")
      registry = TOOL_REGISTRY[slug]

      # D-10: OAuth check — redirect to desktop handshake if missing
      needs_oauth = registry.get("needs_oauth")
      if needs_oauth:
          token = await asyncio.get_event_loop().run_in_executor(
              None, lambda: _check_oauth_token_sync(needs_oauth)
          )
          if not token:
              return RedirectResponse(
                  f"/ui/integrations/{needs_oauth}/auth?return_to=/m/tools/{slug}/run",
                  status_code=303,
              )

      return mobile_templates.TemplateResponse(
          "mobile/tools/run.html",
          {
              "request": request,
              "active_tab": "more",
              "slug": slug,
              "tool": {"slug": slug, **registry},
          },
      )


  @router.post("/tools/{slug}/run", response_class=HTMLResponse)
  async def mobile_tool_run_submit(
      slug: str,
      request: Request,
      phrases: str = Form(default=""),
      domain: str = Form(default=""),
      region: str = Form(default="213"),
      upload: UploadFile | None = File(default=None),
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> HTMLResponse:
      """Parse input, create Job, dispatch Celery task, return polling partial."""
      if slug not in TOOL_REGISTRY:
          raise HTTPException(status_code=404, detail="Unknown tool")
      registry = TOOL_REGISTRY[slug]

      parsed = await parse_tool_input(phrases, upload, registry["limit"])

      JobModel, _ = _get_tool_models(slug)
      job_kwargs: dict = {
          "id": uuid.uuid4(),
          "status": "pending",
          "user_id": user.id,
          "created_at": datetime.now(timezone.utc),
          registry["input_col"]: parsed.lines,
          registry["count_col"]: parsed.count,
      }
      if registry.get("has_domain_field"):
          job_kwargs["target_domain"] = (domain or "").strip()
      if registry.get("has_region_field"):
          try:
              job_kwargs["input_region"] = int(region or "213")
          except (ValueError, TypeError):
              job_kwargs["input_region"] = 213

      job = JobModel(**job_kwargs)
      db.add(job)
      await db.commit()
      await db.refresh(job)
      job_id_str = str(job.id)

      if slug == "brief":
          from app.tasks.brief_tasks import (
              run_brief_step1_serp,
              run_brief_step2_crawl,
              run_brief_step3_aggregate,
              run_brief_step4_finalize,
          )
          celery_chain(
              run_brief_step1_serp.si(job_id_str),
              run_brief_step2_crawl.si(job_id_str),
              run_brief_step3_aggregate.si(job_id_str),
              run_brief_step4_finalize.si(job_id_str),
          ).delay()
      else:
          _get_tool_task(slug).delay(job_id_str)

      logger.info("mobile tool dispatched slug={} job_id={} user={}", slug, job_id_str, user.id)
      return mobile_templates.TemplateResponse(
          "mobile/tools/partials/tool_progress.html",
          {
              "request": request,
              "slug": slug,
              "job_id": job_id_str,
              "status": "started",
              "checked": 0,
              "total": parsed.count,
          },
      )


  @router.get("/tools/{slug}/jobs/{job_id}/status", response_class=HTMLResponse)
  async def mobile_tool_job_status(
      slug: str,
      job_id: uuid.UUID,
      request: Request,
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> HTMLResponse:
      """HTMX polling endpoint — returns tool_progress.html partial."""
      if slug not in TOOL_REGISTRY:
          raise HTTPException(status_code=404, detail="Unknown tool")
      JobModel, _ = _get_tool_models(slug)

      job = await get_job_for_user(db, JobModel, job_id, user.id)
      if job is None:
          raise HTTPException(status_code=404, detail="Job not found")

      # Normalize status: pending/running → started, complete/partial → done, else error
      status_raw = (job.status or "").lower()
      if status_raw in ("pending", "running", "started"):
          status = "started"
      elif status_raw in ("complete", "done", "partial"):
          status = "done"
      else:
          status = "error"

      total = getattr(job, TOOL_REGISTRY[slug]["count_col"], 0) or 0
      checked = getattr(job, "processed_count", None)
      if checked is None:
          checked = total if status == "done" else 0

      return mobile_templates.TemplateResponse(
          "mobile/tools/partials/tool_progress.html",
          {
              "request": request,
              "slug": slug,
              "job_id": str(job_id),
              "status": status,
              "checked": checked,
              "total": total,
          },
      )
  ```

  **Constraints:**
  - Reuse `_get_tool_task`, `_get_tool_models`, `_check_oauth_token_sync`, `TOOL_REGISTRY` from `app/routers/tools.py` — do NOT duplicate them
  - Brief tool still uses chain pattern (4 steps) — copied verbatim
  - Status normalization handles both `processed_count` (if tool model has it) and falls back to total on done
  - OAuth redirect happens BEFORE rendering form, per D-10
  - No changes to tools.py or any tool task file (Plan 03 handles notify)
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('app/routers/mobile.py').read())"</automated>
    <automated>python -c "from app.routers.mobile import router; paths = [r.path for r in router.routes]; need = ['/m/tools', '/m/tools/{slug}/run', '/m/tools/{slug}/jobs/{job_id}/status']; missing = [n for n in need if n not in paths]; assert not missing, f'missing {missing}, got {[p for p in paths if \"/tools\" in p]}'"</automated>
  </verify>
  <acceptance_criteria>
    - grep -q "mobile_tools_list" app/routers/mobile.py
    - grep -q "mobile_tool_run_form" app/routers/mobile.py
    - grep -q "mobile_tool_run_submit" app/routers/mobile.py
    - grep -q "mobile_tool_job_status" app/routers/mobile.py
    - grep -q "from app.routers.tools import" app/routers/mobile.py
    - grep -q "TOOL_REGISTRY" app/routers/mobile.py
    - grep -q "_get_tool_task" app/routers/mobile.py
    - grep -q "_get_tool_models" app/routers/mobile.py
    - grep -q "_check_oauth_token_sync" app/routers/mobile.py
    - grep -q "parse_tool_input" app/routers/mobile.py
    - grep -q "get_job_for_user" app/routers/mobile.py
    - grep -q "return_to=/m/tools/" app/routers/mobile.py
    - grep -q "celery_chain" app/routers/mobile.py
    - python -c "import ast; ast.parse(open('app/routers/mobile.py').read())"
    - python -c "from app.routers.mobile import router"
  </acceptance_criteria>
  <done>4 new tool endpoints on /m/ router, module parses clean, OAuth redirect + brief chain reuse verified.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Mobile tool templates (list.html, run.html, tool_progress.html partial)</name>
  <read_first>
    - app/templates/mobile/base_mobile.html
    - app/templates/mobile/partials/position_progress.html
    - app/templates/mobile/positions.html
    - .planning/phases/29-reports-tools/29-UI-SPEC.md
  </read_first>
  <files>
    - app/templates/mobile/tools/list.html
    - app/templates/mobile/tools/run.html
    - app/templates/mobile/tools/partials/tool_progress.html
  </files>
  <action>
  **Create app/templates/mobile/tools/list.html** (D-08, D-09 + UI-SPEC Section 2):

  ```html
  {% extends "mobile/base_mobile.html" %}
  {% block title %}SEO Инструменты{% endblock %}
  {% block content %}
  <div class="p-4">
    <h1 class="text-xl font-semibold mb-4">SEO Инструменты</h1>

    <div class="bg-white rounded-lg divide-y divide-gray-100">
      {% for t in tools %}
      <a href="/m/tools/{{ t.slug }}/run"
         class="flex items-center gap-3 p-4 min-h-[44px] no-underline text-inherit">
        <div class="flex-1 min-w-0">
          <div class="text-sm font-semibold truncate">{{ t.name }}</div>
          <div class="text-xs text-gray-500 truncate">{{ t.description }}</div>
        </div>
        <div class="flex flex-col items-end gap-1 flex-shrink-0">
          {% if t.needs_oauth == 'wordstat' %}
            <span class="bg-amber-100 text-amber-800 text-xs rounded px-2 py-0.5 font-semibold">Требует Wordstat</span>
          {% endif %}
          <span class="text-xs text-gray-400">до {{ t.limit }} фраз</span>
        </div>
        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
      </a>
      {% endfor %}
    </div>
  </div>
  {% endblock %}
  ```

  **Create app/templates/mobile/tools/run.html** (D-11 + UI-SPEC Section 3):

  ```html
  {% extends "mobile/base_mobile.html" %}
  {% block title %}{{ tool.name }}{% endblock %}
  {% block content %}
  <div class="p-4">
    <a href="/m/tools" class="text-sm text-indigo-600 underline mb-2 inline-block">← Инструменты</a>
    <h1 class="text-xl font-semibold mb-1">{{ tool.name }}</h1>
    <div class="text-sm text-gray-500 mb-4">{{ tool.description }}</div>
    <div class="text-xs text-gray-400 mb-3">Лимит: до {{ tool.limit }} фраз</div>

    <form hx-post="/m/tools/{{ slug }}/run"
          hx-target="#tool-progress-slot"
          hx-swap="outerHTML"
          hx-encoding="multipart/form-data"
          enctype="multipart/form-data">

      <label class="block text-xs text-gray-500 mb-1">Введите фразы</label>
      <textarea name="phrases"
                class="w-full min-h-[120px] rounded-lg border border-gray-300 bg-white p-3 text-sm mb-3"
                placeholder="Введите фразы (по одной на строку)"></textarea>

      <label class="block text-xs text-gray-500 mb-1">или файл (TXT / XLSX)</label>
      <input type="file" name="upload" accept=".txt,.xlsx"
             class="w-full text-sm mb-3">

      {% if tool.has_domain_field %}
      <label class="block text-xs text-gray-500 mb-1">Домен</label>
      <input type="text" name="domain"
             class="w-full min-h-[44px] rounded-lg border border-gray-300 bg-white px-3 text-sm mb-3"
             placeholder="example.ru">
      {% endif %}

      {% if tool.has_region_field %}
      <label class="block text-xs text-gray-500 mb-1">Регион</label>
      <select name="region"
              class="w-full min-h-[44px] rounded-lg border border-gray-300 bg-white px-3 text-sm mb-3">
        <option value="213">Москва (213)</option>
        <option value="2">Санкт-Петербург (2)</option>
        <option value="225">Россия (225)</option>
      </select>
      {% endif %}

      <button type="submit"
              class="w-full min-h-[44px] rounded-lg text-white font-semibold text-sm"
              style="background:#4f46e5;">
        Запустить
      </button>
    </form>

    <div id="tool-progress-slot" class="mt-4"></div>
  </div>

  <script>
  // D-11 client-side safety: validate exclusive input before submit
  document.querySelector('form[hx-post]').addEventListener('htmx:configRequest', function(evt){
    const txt = evt.detail.elt.querySelector('textarea[name=phrases]').value.trim();
    const file = evt.detail.elt.querySelector('input[name=upload]').files[0];
    if (txt && file){
      evt.preventDefault();
      showToast('Используйте одно из двух: текст или файл', 'error');
    }
  });
  document.body.addEventListener('htmx:afterRequest', function(evt){
    if (evt.detail.successful && evt.detail.pathInfo.requestPath.endsWith('/run')){
      showToast('Запущено', 'success');
    } else if (!evt.detail.successful && evt.detail.pathInfo.requestPath.endsWith('/run')){
      try {
        const j = JSON.parse(evt.detail.xhr.responseText || '{}');
        showToast(j.detail || 'Ошибка запуска', 'error');
      } catch(e){ showToast('Ошибка запуска', 'error'); }
    }
  });
  </script>
  {% endblock %}
  ```

  **Create app/templates/mobile/tools/partials/tool_progress.html** (clone of position_progress.html for tools, D-12 + UI-SPEC):

  ```html
  {# Tool progress polling partial. Pattern source: position_progress.html #}
  {% if status in ["started", "running"] %}
  <div id="tool-progress-slot"
       hx-get="/m/tools/{{ slug }}/jobs/{{ job_id }}/status"
       hx-trigger="every 3s"
       hx-target="this"
       hx-swap="outerHTML"
       aria-live="polite">
    <div class="bg-white rounded-lg p-4 flex items-center gap-3 mt-4">
      <svg class="animate-spin h-5 w-5 text-indigo-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <div class="flex-1">
        <div class="text-sm font-semibold">
          {% if total and total > 0 %}Проверено {{ checked }} из {{ total }}{% else %}Выполняется...{% endif %}
        </div>
        {% if total and total > 0 %}
        <div class="w-full h-2 bg-gray-200 rounded-full mt-2">
          <div class="h-2 rounded-full" style="background:#4f46e5;width:{{ (checked / total * 100) | int }}%"></div>
        </div>
        {% endif %}
      </div>
    </div>
  </div>
  {% elif status == "done" %}
  <div id="tool-progress-slot" aria-live="polite">
    <div class="bg-white rounded-lg p-4 flex items-center gap-3 mt-4">
      <svg class="h-5 w-5 text-green-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span class="text-sm font-semibold flex-1">Завершено — {{ total }} результатов</span>
      <a class="min-h-[44px] rounded-lg text-white font-semibold text-sm px-4 py-3 no-underline"
         style="background:#4f46e5;"
         href="/m/tools/{{ slug }}/jobs/{{ job_id }}">Показать результаты</a>
    </div>
  </div>
  {% else %}
  <div id="tool-progress-slot" aria-live="polite">
    <div class="bg-white rounded-lg p-4 flex items-center gap-3 mt-4">
      <svg class="h-5 w-5 text-red-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
      <span class="text-sm font-semibold flex-1 text-red-700">Ошибка. Попробуйте ещё раз.</span>
    </div>
  </div>
  {% endif %}
  ```

  **Critical constraints:**
  - `done` and `error` branches have NO `hx-trigger` (Research Pitfall 3 — polling must stop)
  - Accent `#4f46e5` only on primary CTA + progress fill
  - Copy from UI-SPEC copywriting table verbatim
  - File input `accept=".txt,.xlsx"` matches D-11
  - Domain field rendered ONLY for tools where `has_domain_field == True` (relevant-url)
  - Region field rendered ONLY for tools where `has_region_field == True` (brief)
  </action>
  <verify>
    <automated>python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); env.get_template('mobile/tools/list.html'); env.get_template('mobile/tools/run.html'); env.get_template('mobile/tools/partials/tool_progress.html'); print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - test -f app/templates/mobile/tools/list.html
    - test -f app/templates/mobile/tools/run.html
    - test -f app/templates/mobile/tools/partials/tool_progress.html
    - grep -q "SEO Инструменты" app/templates/mobile/tools/list.html
    - grep -q 'href="/m/tools/{{ t.slug }}/run"' app/templates/mobile/tools/list.html
    - grep -q "Требует Wordstat" app/templates/mobile/tools/list.html
    - grep -q "needs_oauth == 'wordstat'" app/templates/mobile/tools/list.html
    - grep -q "← Инструменты" app/templates/mobile/tools/run.html
    - grep -q 'hx-post="/m/tools/{{ slug }}/run"' app/templates/mobile/tools/run.html
    - grep -q 'enctype="multipart/form-data"' app/templates/mobile/tools/run.html
    - grep -q 'accept=".txt,.xlsx"' app/templates/mobile/tools/run.html
    - grep -q "Запустить" app/templates/mobile/tools/run.html
    - grep -q "Введите фразы" app/templates/mobile/tools/run.html
    - grep -q 'name="phrases"' app/templates/mobile/tools/run.html
    - grep -q 'name="upload"' app/templates/mobile/tools/run.html
    - grep -q "has_domain_field" app/templates/mobile/tools/run.html
    - grep -q "has_region_field" app/templates/mobile/tools/run.html
    - grep -q 'hx-trigger="every 3s"' app/templates/mobile/tools/partials/tool_progress.html
    - grep -q '/m/tools/{{ slug }}/jobs/{{ job_id }}/status' app/templates/mobile/tools/partials/tool_progress.html
    - grep -q "Показать результаты" app/templates/mobile/tools/partials/tool_progress.html
    - grep -q "Ошибка. Попробуйте ещё раз." app/templates/mobile/tools/partials/tool_progress.html
    - python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); env.get_template('mobile/tools/list.html'); env.get_template('mobile/tools/run.html'); env.get_template('mobile/tools/partials/tool_progress.html')"
  </acceptance_criteria>
  <done>Three templates parse, follow UI-SPEC copy/colors exactly, polling stops on done/error.</done>
</task>

</tasks>

<verification>
- [ ] GET /m/tools renders 6 tool cards; wordstat-batch has amber "Требует Wordstat" badge
- [ ] GET /m/tools/wordstat-batch/run without OAuth token 303-redirects to /ui/integrations/wordstat/auth?return_to=/m/tools/wordstat-batch/run
- [ ] GET /m/tools/commercialization/run renders textarea + file input + "Запустить" CTA
- [ ] POST /m/tools/commercialization/run with phrases creates CommerceCheckJob, dispatches task, returns polling partial
- [ ] GET /m/tools/commercialization/jobs/{job_id}/status returns running partial during work, done partial with "Показать результаты" link after completion
- [ ] Polling partial has hx-trigger ONLY in started/running state (stops on done/error)
- [ ] D-11: posting both textarea and file → 422 with "Используйте одно из двух"
- [ ] No tool task files modified (Plan 03 handles notify)
</verification>

<success_criteria>
- All 3 tasks pass acceptance_criteria
- `from app.routers.mobile import router` imports cleanly
- 4 new endpoints registered
- 3 new templates parse via Jinja2
- TLS-01 covered (tool list + run + progress). TLS-02 covered by Plan 03.
</success_criteria>

<output>
Write `.planning/phases/29-reports-tools/29-02-SUMMARY.md` per template.
</output>
