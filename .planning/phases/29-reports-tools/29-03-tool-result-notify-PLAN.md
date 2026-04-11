---
phase: 29-reports-tools
plan: 03
type: execute
wave: 3
depends_on:
  - 29-02
files_modified:
  - app/routers/mobile.py
  - app/services/mobile_tools_service.py
  - app/templates/mobile/tools/result.html
  - app/templates/mobile/tools/partials/result_modal.html
  - app/tasks/commerce_check_tasks.py
  - app/tasks/meta_parse_tasks.py
  - app/tasks/relevant_url_tasks.py
  - app/tasks/paa_tasks.py
  - app/tasks/wordstat_batch_tasks.py
  - app/tasks/brief_tasks.py
autonomous: true
requirements:
  - TLS-02

must_haves:
  truths:
    - "User opens /m/tools/{slug}/jobs/{job_id} and sees summary card + top-20 result rows + 'Скачать XLSX' + 'Показать все'"
    - "After tool task completes, user receives in-app notification with link_url=/m/tools/{slug}/jobs/{job_id}"
    - "Notification fires for all 6 tools (commerce, meta-parser, relevant-url, brief, wordstat-batch, paa)"
    - "'Показать все' opens HTMX modal with full paginated results"
    - "'Скачать XLSX' hits existing /ui/tools/{slug}/{job_id}/export?format=xlsx"
  artifacts:
    - path: "app/templates/mobile/tools/result.html"
      provides: "Mobile result view with summary + top-20 table + CTAs"
      contains: "Скачать XLSX"
    - path: "app/templates/mobile/tools/partials/result_modal.html"
      provides: "Full paginated results modal body"
      contains: "modal"
    - path: "app/routers/mobile.py"
      provides: "GET /m/tools/{slug}/jobs/{job_id}, GET /m/tools/{slug}/jobs/{job_id}/all"
      contains: "mobile_tool_result"
    - path: "app/tasks/commerce_check_tasks.py"
      provides: "notify() call on completion"
      contains: "tool.completed"
  key_links:
    - from: "app/templates/mobile/tools/result.html"
      to: "/ui/tools/{slug}/{job_id}/export?format=xlsx"
      via: "Скачать XLSX link"
      pattern: "export\\?format=xlsx"
    - from: "app/tasks/commerce_check_tasks.py"
      to: "app.services.notifications.notify"
      via: "asyncio.run wrapper"
      pattern: "tool.completed"
    - from: "notification.link_url"
      to: "/m/tools/{slug}/jobs/{job_id}"
      via: "string format"
      pattern: "/m/tools/.*jobs"
---

<objective>
Реализовать TLS-02 и завершить TLS-01: мобильное view результатов `/m/tools/{slug}/jobs/{job_id}` (summary + top-20 + XLSX + «Показать все» модал) + in-app notify() во всех 6 tool Celery tasks с `link_url` на mobile result page.

Purpose: После запуска инструмента пользователь получает in-app уведомление (двойной safety: HTMX polling + notify()) и открывает mobile-friendly summary результата. Существующий `/ui/tools/{slug}/{job_id}/export` endpoint переиспользуется для XLSX download.

Output:
- 2 новых endpoint в `app/routers/mobile.py`
- Расширение `mobile_tools_service.py` helper для top-20 rows
- Шаблоны `mobile/tools/result.html` + partial `result_modal.html`
- Добавление `notify()` в 6 tool tasks
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/29-reports-tools/29-CONTEXT.md
@.planning/phases/29-reports-tools/29-RESEARCH.md
@.planning/phases/29-reports-tools/29-UI-SPEC.md
@.planning/phases/29-reports-tools/29-02-tools-list-run-PLAN.md
@app/routers/mobile.py
@app/routers/tools.py
@app/services/notifications.py
@app/tasks/suggest_tasks.py
@app/tasks/commerce_check_tasks.py
@app/tasks/meta_parse_tasks.py
@app/tasks/relevant_url_tasks.py
@app/tasks/paa_tasks.py
@app/tasks/wordstat_batch_tasks.py
@app/tasks/brief_tasks.py

<interfaces>
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

Pattern for calling notify() from SYNC Celery task (from suggest_tasks.py):
```python
async def _send_notify(user_id, title, body, link_url, kind="tool.completed"):
    from app.database import AsyncSessionLocal
    from app.services.notifications import notify
    async with AsyncSessionLocal() as db:
        await notify(
            db=db, user_id=user_id, kind=kind,
            title=title, body=body, link_url=link_url,
            site_id=None, severity="info",
        )
        await db.commit()

# At end of sync Celery task:
import asyncio
if job and job.user_id:
    asyncio.run(_send_notify(job.user_id, title, body, link_url))
```

From app/routers/tools.py existing export endpoint (reused, NOT modified):
```python
@router.get("/{slug}/{job_id}/export", name="tool_export")
async def tool_export(
    slug: str,
    job_id: uuid.UUID,
    format: str = Query(default="csv"),
    ...
) -> StreamingResponse:
    # Returns XLSX or CSV for all 6 tools. Brief supports only xlsx.
```
URL: `/ui/tools/{slug}/{job_id}/export?format=xlsx`

From app/routers/tools.py _result_to_row (existing helper, used for table rows):
```python
def _result_to_row(slug: str, result) -> list:
    """Returns list of column values for a result row. Per-tool shape."""
```

Task signatures (return lines identified by grep):
- commerce_check_tasks.py: `def run_commerce_check(self, job_id: str) -> dict` — returns at line ~111 after writing results+status to DB. Job has `user_id`.
- meta_parse_tasks.py: `def run_meta_parse(self, job_id: str) -> dict` — returns at line 81.
- relevant_url_tasks.py: `def run_relevant_url(self, job_id: str) -> dict` — returns at line 109.
- paa_tasks.py: `def run_paa(self, job_id: str) -> dict` — returns at line 150.
- wordstat_batch_tasks.py: `def run_wordstat_batch(self, job_id: str) -> dict` — returns at line 145.
- brief_tasks.py: 4-step chain; notify goes in `run_brief_step4_finalize` which returns at line 252.

All 6 tools' Job model has `id`, `user_id`, `status` fields.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Mobile result endpoints + top-20 helper + templates</name>
  <read_first>
    - app/routers/mobile.py
    - app/routers/tools.py
    - app/services/mobile_tools_service.py
    - app/templates/mobile/base_mobile.html
    - .planning/phases/29-reports-tools/29-UI-SPEC.md
  </read_first>
  <files>
    - app/services/mobile_tools_service.py
    - app/routers/mobile.py
    - app/templates/mobile/tools/result.html
    - app/templates/mobile/tools/partials/result_modal.html
  </files>
  <action>
  **Step 1 — Extend `app/services/mobile_tools_service.py`** — append these helpers (do NOT remove existing `parse_tool_input` or `get_job_for_user`):

  ```python
  from sqlalchemy import func


  async def get_top_results(
      db: AsyncSession,
      result_model: type,
      job_id: uuid.UUID,
      limit: int = 20,
  ) -> list:
      """Return first `limit` rows for a job (ordered by primary key)."""
      stmt = (
          select(result_model)
          .where(result_model.job_id == job_id)
          .order_by(result_model.id)
          .limit(limit)
      )
      result = await db.execute(stmt)
      return list(result.scalars().all())


  async def count_results(
      db: AsyncSession,
      result_model: type,
      job_id: uuid.UUID,
  ) -> int:
      """Total result row count for a job."""
      stmt = select(func.count(result_model.id)).where(result_model.job_id == job_id)
      result = await db.execute(stmt)
      return int(result.scalar() or 0)


  async def get_paginated_results(
      db: AsyncSession,
      result_model: type,
      job_id: uuid.UUID,
      page: int = 1,
      page_size: int = 50,
  ) -> list:
      """Return one page of results. 1-indexed `page`."""
      offset = max(0, (page - 1) * page_size)
      stmt = (
          select(result_model)
          .where(result_model.job_id == job_id)
          .order_by(result_model.id)
          .offset(offset)
          .limit(page_size)
      )
      result = await db.execute(stmt)
      return list(result.scalars().all())
  ```

  **Step 2 — Append 2 endpoints at END of `app/routers/mobile.py`:**

  Add import (merge with existing):
  ```python
  from app.routers.tools import _result_to_row, _EXPORT_HEADERS
  from app.services.mobile_tools_service import (
      count_results,
      get_paginated_results,
      get_top_results,
  )
  ```

  ```python
  @router.get("/tools/{slug}/jobs/{job_id}", response_class=HTMLResponse, name="mobile_tool_result")
  async def mobile_tool_result(
      slug: str,
      job_id: uuid.UUID,
      request: Request,
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> HTMLResponse:
      """Mobile result view — summary + top-20 + XLSX link + 'Показать все' button (D-13)."""
      if slug not in TOOL_REGISTRY:
          raise HTTPException(status_code=404, detail="Unknown tool")
      registry = TOOL_REGISTRY[slug]
      JobModel, ResultModel = _get_tool_models(slug)

      job = await get_job_for_user(db, JobModel, job_id, user.id)
      if job is None:
          raise HTTPException(status_code=404, detail="Job not found")

      total = await count_results(db, ResultModel, job_id)
      top_rows = await get_top_results(db, ResultModel, job_id, limit=20)
      top_values = [_result_to_row(slug, r) for r in top_rows]

      status_label = {
          "complete": "Завершено",
          "done": "Завершено",
          "partial": "Завершено",
          "failed": "Ошибка",
      }.get((job.status or "").lower(), "Завершено")

      return mobile_templates.TemplateResponse(
          "mobile/tools/result.html",
          {
              "request": request,
              "active_tab": "more",
              "slug": slug,
              "job_id": str(job_id),
              "tool": {"slug": slug, **registry},
              "job": job,
              "status_label": status_label,
              "total": total,
              "top_values": top_values,
              "headers": _EXPORT_HEADERS.get(slug, []),
          },
      )


  @router.get("/tools/{slug}/jobs/{job_id}/all", response_class=HTMLResponse)
  async def mobile_tool_result_all(
      slug: str,
      job_id: uuid.UUID,
      request: Request,
      page: int = 1,
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user),
  ) -> HTMLResponse:
      """'Показать все' modal content — paginated full results (HTMX target)."""
      if slug not in TOOL_REGISTRY:
          raise HTTPException(status_code=404, detail="Unknown tool")
      JobModel, ResultModel = _get_tool_models(slug)

      job = await get_job_for_user(db, JobModel, job_id, user.id)
      if job is None:
          raise HTTPException(status_code=404, detail="Job not found")

      page_size = 50
      rows = await get_paginated_results(db, ResultModel, job_id, page, page_size)
      total = await count_results(db, ResultModel, job_id)
      values = [_result_to_row(slug, r) for r in rows]

      return mobile_templates.TemplateResponse(
          "mobile/tools/partials/result_modal.html",
          {
              "request": request,
              "slug": slug,
              "job_id": str(job_id),
              "headers": _EXPORT_HEADERS.get(slug, []),
              "values": values,
              "page": page,
              "page_size": page_size,
              "total": total,
              "has_next": (page * page_size) < total,
          },
      )
  ```

  **Step 3 — Create `app/templates/mobile/tools/result.html`** (D-13 + UI-SPEC Section 4):

  ```html
  {% extends "mobile/base_mobile.html" %}
  {% block title %}{{ tool.name }}{% endblock %}
  {% block content %}
  <div class="p-4">
    <a href="/m/tools/{{ slug }}/run" class="text-sm text-indigo-600 underline mb-2 inline-block">← {{ tool.name }}</a>

    <div class="bg-white rounded-lg p-4 mb-4">
      <div class="flex items-center gap-2 mb-2">
        <div class="text-sm font-semibold flex-1 truncate">{{ tool.name }}</div>
        {% if status_label == "Ошибка" %}
          <span class="bg-red-100 text-red-700 text-xs rounded px-2 py-0.5 font-semibold">Ошибка</span>
        {% else %}
          <span class="bg-green-100 text-green-700 text-xs rounded px-2 py-0.5 font-semibold">Завершено</span>
        {% endif %}
      </div>
      <div class="text-xs text-gray-500 mb-3">Всего результатов: {{ total }}</div>
      <a href="/ui/tools/{{ slug }}/{{ job_id }}/export?format=xlsx"
         class="block w-full min-h-[44px] rounded-lg text-sm font-semibold text-center border border-gray-300 text-gray-700 bg-white py-3 no-underline">
         Скачать XLSX
      </a>
    </div>

    {% if total == 0 %}
      <div class="bg-white rounded-lg p-4 text-sm text-gray-500">
        Результатов нет. Запустите инструмент с данными.
      </div>
    {% else %}
    <div class="bg-white rounded-lg divide-y divide-gray-100">
      {% for row in top_values %}
      <div class="p-3 min-h-[44px]">
        {% for val in row %}
          <div class="{% if loop.first %}text-sm font-semibold truncate{% else %}text-xs text-gray-500 truncate{% endif %}">
            {% if headers and loop.index0 < headers|length %}<span class="text-gray-400">{{ headers[loop.index0] }}:</span> {% endif %}{{ val }}
          </div>
        {% endfor %}
      </div>
      {% endfor %}
    </div>

    {% if total > 20 %}
    <button type="button"
            class="w-full min-h-[44px] rounded-lg text-sm font-semibold border border-gray-300 text-gray-700 bg-white mt-3 py-3"
            hx-get="/m/tools/{{ slug }}/jobs/{{ job_id }}/all?page=1"
            hx-target="#modal-slot"
            hx-swap="innerHTML">
      Показать все
    </button>
    {% endif %}
    {% endif %}

    <div id="modal-slot"></div>
  </div>
  {% endblock %}
  ```

  **Step 4 — Create `app/templates/mobile/tools/partials/result_modal.html`** (full paginated list):

  ```html
  {# 'Показать все' modal: full paginated result table #}
  <div id="result-modal"
       class="fixed inset-0 bg-black/40 z-50 flex items-end"
       onclick="if(event.target===this){this.remove();}">
    <div class="bg-white rounded-t-lg w-full max-h-[85vh] overflow-y-auto p-4"
         onclick="event.stopPropagation();">
      <div class="flex items-center gap-2 mb-3">
        <div class="text-sm font-semibold flex-1">Все результаты ({{ total }})</div>
        <button type="button" class="text-sm text-gray-500 px-3 py-1" onclick="document.getElementById('result-modal').remove();">Закрыть</button>
      </div>

      <div class="divide-y divide-gray-100">
        {% for row in values %}
        <div class="p-3 min-h-[44px]">
          {% for val in row %}
            <div class="{% if loop.first %}text-sm font-semibold truncate{% else %}text-xs text-gray-500 truncate{% endif %}">
              {% if headers and loop.index0 < headers|length %}<span class="text-gray-400">{{ headers[loop.index0] }}:</span> {% endif %}{{ val }}
            </div>
          {% endfor %}
        </div>
        {% endfor %}
      </div>

      {% if has_next %}
      <button type="button"
              class="w-full min-h-[44px] rounded-lg text-sm font-semibold border border-gray-300 text-gray-700 bg-white mt-3 py-3"
              hx-get="/m/tools/{{ slug }}/jobs/{{ job_id }}/all?page={{ page + 1 }}"
              hx-target="#result-modal"
              hx-swap="outerHTML">
        Показать ещё
      </button>
      {% endif %}
    </div>
  </div>
  ```

  **Constraints:**
  - Skip modal append complexity — modal is a single self-contained element replaced on pagination
  - `Скачать XLSX` links to existing desktop export endpoint (reuse, no new code)
  - Empty state copy from UI-SPEC: "Результатов нет. Запустите инструмент с данными."
  - Back link pattern: `← {{ tool.name }}`
  - Status badge: green "Завершено" for complete/partial/done, red "Ошибка" for failed
  - No accent #4f46e5 usage here (result view uses secondary outline buttons only)
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('app/routers/mobile.py').read()); ast.parse(open('app/services/mobile_tools_service.py').read())"</automated>
    <automated>python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); env.get_template('mobile/tools/result.html'); env.get_template('mobile/tools/partials/result_modal.html')"</automated>
    <automated>python -c "from app.routers.mobile import router; paths = [r.path for r in router.routes]; assert '/m/tools/{slug}/jobs/{job_id}' in paths; assert '/m/tools/{slug}/jobs/{job_id}/all' in paths"</automated>
  </verify>
  <acceptance_criteria>
    - grep -q "def get_top_results" app/services/mobile_tools_service.py
    - grep -q "def count_results" app/services/mobile_tools_service.py
    - grep -q "def get_paginated_results" app/services/mobile_tools_service.py
    - grep -q "mobile_tool_result" app/routers/mobile.py
    - grep -q "mobile_tool_result_all" app/routers/mobile.py
    - grep -q "_result_to_row" app/routers/mobile.py
    - grep -q "_EXPORT_HEADERS" app/routers/mobile.py
    - test -f app/templates/mobile/tools/result.html
    - test -f app/templates/mobile/tools/partials/result_modal.html
    - grep -q "Скачать XLSX" app/templates/mobile/tools/result.html
    - grep -q "/ui/tools/{{ slug }}/{{ job_id }}/export?format=xlsx" app/templates/mobile/tools/result.html
    - grep -q "Показать все" app/templates/mobile/tools/result.html
    - grep -q "Результатов нет. Запустите инструмент с данными." app/templates/mobile/tools/result.html
    - grep -q "Все результаты" app/templates/mobile/tools/partials/result_modal.html
    - grep -q "Показать ещё" app/templates/mobile/tools/partials/result_modal.html
    - python -c "import ast; ast.parse(open('app/routers/mobile.py').read())"
    - python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); env.get_template('mobile/tools/result.html'); env.get_template('mobile/tools/partials/result_modal.html')"
    - python -c "from app.routers.mobile import router"
  </acceptance_criteria>
  <done>2 new result endpoints, service helpers, and templates landed; result.html links to existing XLSX export and shows top-20 + 'Показать все' modal.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Add notify() to 6 tool Celery tasks (commerce, meta, relevant, paa, wordstat, brief)</name>
  <read_first>
    - app/tasks/commerce_check_tasks.py
    - app/tasks/meta_parse_tasks.py
    - app/tasks/relevant_url_tasks.py
    - app/tasks/paa_tasks.py
    - app/tasks/wordstat_batch_tasks.py
    - app/tasks/brief_tasks.py
    - app/services/notifications.py
    - app/tasks/suggest_tasks.py
  </read_first>
  <files>
    - app/tasks/commerce_check_tasks.py
    - app/tasks/meta_parse_tasks.py
    - app/tasks/relevant_url_tasks.py
    - app/tasks/paa_tasks.py
    - app/tasks/wordstat_batch_tasks.py
    - app/tasks/brief_tasks.py
  </files>
  <action>
  For each of the 6 tool task files, add a notify() call JUST BEFORE the final `return` statement of the main task function. The pattern is identical across files except `slug`, `tool_name`, and `return` line.

  **Common pattern — add this helper at module top (after existing imports) in EACH of the 6 files:**

  ```python
  async def _send_mobile_notify(
      user_id, title: str, body: str, slug: str, job_id_str: str
  ) -> None:
      """Fire in-app notification with link to /m/tools/{slug}/jobs/{job_id}."""
      from app.database import AsyncSessionLocal
      from app.services.notifications import notify
      try:
          async with AsyncSessionLocal() as db:
              await notify(
                  db=db,
                  user_id=user_id,
                  kind="tool.completed",
                  title=title,
                  body=body,
                  link_url=f"/m/tools/{slug}/jobs/{job_id_str}",
                  site_id=None,
                  severity="info",
              )
              await db.commit()
      except Exception:
          from loguru import logger
          logger.exception("mobile notify failed slug={} job={}", slug, job_id_str)
  ```

  **File 1: app/tasks/commerce_check_tasks.py**
  - Locate `def run_commerce_check(self, job_id: str) -> dict` (line ~19)
  - Find final `return {"status": status, "count": len(results)}` (around line 111)
  - Immediately BEFORE that return, add:
  ```python
  # TLS-02: in-app notification for mobile
  try:
      with get_sync_db() as _db:
          _job = _db.get(CommerceCheckJob, job_uuid)
          _user_id = _job.user_id if _job else None
      if _user_id:
          import asyncio
          asyncio.run(_send_mobile_notify(
              user_id=_user_id,
              title="Проверка коммерциализации завершена",
              body=f"Обработано {len(results)} фраз",
              slug="commercialization",
              job_id_str=job_id,
          ))
  except Exception:
      from loguru import logger
      logger.exception("notify wrap failed")
  ```

  **File 2: app/tasks/meta_parse_tasks.py**
  - Locate `def run_meta_parse(self, job_id: str) -> dict`
  - Final return at line ~81: `return {"status": "complete", "count": len(results)}`
  - Before the final return, add the same block, substituting:
    - `_job = _db.get(MetaParseJob, job_uuid)` (verify import of MetaParseJob exists — add if missing)
    - `title="Парсер мета-тегов завершён"`
    - `body=f"Обработано {len(results)} URL"`
    - `slug="meta-parser"`

  **File 3: app/tasks/relevant_url_tasks.py**
  - Locate `def run_relevant_url(self, job_id: str) -> dict`
  - Final return at line ~109
  - Before return add block with:
    - `_job = _db.get(RelevantUrlJob, job_uuid)`
    - `title="Поиск релевантного URL завершён"`
    - `body=f"Обработано {len(results)} фраз"`
    - `slug="relevant-url"`

  **File 4: app/tasks/paa_tasks.py**
  - Locate `def run_paa(self, job_id: str) -> dict`
  - Final return at line ~150: `return {"status": "complete", "count": len(all_results)}`
  - Before return add block with:
    - `_job = _db.get(PAAJob, job_uuid)`
    - `title="PAA-парсер завершён"`
    - `body=f"Получено {len(all_results)} вопросов"`
    - `slug="paa"`

  **File 5: app/tasks/wordstat_batch_tasks.py**
  - Locate `def run_wordstat_batch(self, job_id: str) -> dict`
  - Final return at line ~145: `return {"status": final_status, "count": processed_count}`
  - Before return add block with:
    - `_job = _db.get(WordstatBatchJob, job_uuid)`
    - `title="Wordstat пакет завершён"`
    - `body=f"Обработано {processed_count} фраз"`
    - `slug="wordstat-batch"`

  **File 6: app/tasks/brief_tasks.py**
  - Locate `def run_brief_step4_finalize(self, job_id: str) -> str` (line ~231)
  - Final return at line ~252: `return job_id`
  - Before return add:
  ```python
  try:
      with get_sync_db() as _db:
          _job = _db.get(BriefJob, uuid.UUID(job_id))
          _user_id = _job.user_id if _job else None
      if _user_id:
          import asyncio
          asyncio.run(_send_mobile_notify(
              user_id=_user_id,
              title="Копирайтерское ТЗ готово",
              body="Brief финализирован",
              slug="brief",
              job_id_str=job_id,
          ))
  except Exception:
      from loguru import logger
      logger.exception("notify wrap failed")
  ```
  Note: brief uses `job_id` as the string (task receives `job_id: str`) and `BriefJob` for lookup. Verify `BriefJob` and `uuid` are imported (add if missing).

  **Rules:**
  - Do NOT modify any existing return value, existing logic, or existing imports you aren't adding
  - Do NOT remove or rename any existing helper
  - `_send_mobile_notify` helper is IDENTICAL in all 6 files (duplicate on purpose — avoids cross-task coupling)
  - notify() is wrapped in try/except so failure does NOT break the task return
  - Use `get_sync_db()` (already imported in each task file) to fetch user_id synchronously before calling asyncio.run
  - For brief_tasks.py, user_id lookup uses `uuid.UUID(job_id)` and `BriefJob` model — ensure both are imported at top of file
  </action>
  <verify>
    <automated>python -c "import ast; [ast.parse(open(f).read()) for f in ['app/tasks/commerce_check_tasks.py','app/tasks/meta_parse_tasks.py','app/tasks/relevant_url_tasks.py','app/tasks/paa_tasks.py','app/tasks/wordstat_batch_tasks.py','app/tasks/brief_tasks.py']]"</automated>
    <automated>python -c "from app.tasks.commerce_check_tasks import run_commerce_check; from app.tasks.meta_parse_tasks import run_meta_parse; from app.tasks.relevant_url_tasks import run_relevant_url; from app.tasks.paa_tasks import run_paa; from app.tasks.wordstat_batch_tasks import run_wordstat_batch; from app.tasks.brief_tasks import run_brief_step4_finalize; print('all task imports OK')"</automated>
  </verify>
  <acceptance_criteria>
    - grep -q "_send_mobile_notify" app/tasks/commerce_check_tasks.py
    - grep -q "_send_mobile_notify" app/tasks/meta_parse_tasks.py
    - grep -q "_send_mobile_notify" app/tasks/relevant_url_tasks.py
    - grep -q "_send_mobile_notify" app/tasks/paa_tasks.py
    - grep -q "_send_mobile_notify" app/tasks/wordstat_batch_tasks.py
    - grep -q "_send_mobile_notify" app/tasks/brief_tasks.py
    - grep -q "tool.completed" app/tasks/commerce_check_tasks.py
    - grep -q "tool.completed" app/tasks/meta_parse_tasks.py
    - grep -q "tool.completed" app/tasks/relevant_url_tasks.py
    - grep -q "tool.completed" app/tasks/paa_tasks.py
    - grep -q "tool.completed" app/tasks/wordstat_batch_tasks.py
    - grep -q "tool.completed" app/tasks/brief_tasks.py
    - grep -q "/m/tools/commercialization/jobs/" app/tasks/commerce_check_tasks.py
    - grep -q "/m/tools/meta-parser/jobs/" app/tasks/meta_parse_tasks.py
    - grep -q "/m/tools/relevant-url/jobs/" app/tasks/relevant_url_tasks.py
    - grep -q "/m/tools/paa/jobs/" app/tasks/paa_tasks.py
    - grep -q "/m/tools/wordstat-batch/jobs/" app/tasks/wordstat_batch_tasks.py
    - grep -q "/m/tools/brief/jobs/" app/tasks/brief_tasks.py
    - python -c "import ast; [ast.parse(open(f).read()) for f in [__import__(q).q for q in []]] if False else [ast.parse(open(f).read()) for f in [\"app/tasks/commerce_check_tasks.py\",\"app/tasks/meta_parse_tasks.py\",\"app/tasks/relevant_url_tasks.py\",\"app/tasks/paa_tasks.py\",\"app/tasks/wordstat_batch_tasks.py\",\"app/tasks/brief_tasks.py\"]]"
    - python -c "from app.tasks.commerce_check_tasks import run_commerce_check; from app.tasks.meta_parse_tasks import run_meta_parse; from app.tasks.relevant_url_tasks import run_relevant_url; from app.tasks.paa_tasks import run_paa; from app.tasks.wordstat_batch_tasks import run_wordstat_batch; from app.tasks.brief_tasks import run_brief_step4_finalize"
  </acceptance_criteria>
  <done>All 6 task files import cleanly, contain the _send_mobile_notify helper and the tool.completed notify call with the correct mobile link_url.</done>
</task>

</tasks>

<verification>
- [ ] GET /m/tools/{slug}/jobs/{job_id} renders summary card + top-20 result rows
- [ ] Скачать XLSX button links to /ui/tools/{slug}/{job_id}/export?format=xlsx
- [ ] Показать все button opens modal via HTMX with paginated full results
- [ ] Показать ещё button loads next page within modal
- [ ] After Celery task finishes, in-app Notification row exists with kind=tool.completed and link_url=/m/tools/{slug}/jobs/{job_id}
- [ ] All 6 tool tasks gained the notify helper without changing their return values
- [ ] Deferred ideas NOT implemented: no ReportDelivery, no scheduled runs, no new tools in TOOL_REGISTRY
</verification>

<success_criteria>
- All 2 tasks pass acceptance_criteria
- `from app.routers.mobile import router` still imports cleanly
- 2 new result endpoints registered
- 2 new templates parse via Jinja2
- TLS-02 covered (notify + mobile result view). TLS-01 fully covered across Plan 02 + Plan 03.
</success_criteria>

<output>
Write `.planning/phases/29-reports-tools/29-03-SUMMARY.md` per template.
</output>
