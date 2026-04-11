# Phase 29: Reports & Tools — Research

**Researched:** 2026-04-11
**Domain:** Mobile UI (FastAPI + Jinja2 + HTMX 2.0) — PDF report delivery + tool runner
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Wizard шаг 1 = Проект (1:1 с desktop). `generate_pdf_report(project_id, report_type)` используется без изменений. Проект select подтягивается из `project_service.get_accessible_projects`.
- **D-02:** 2 типа отчётов в мобильном wizard'е — `brief` и `detailed`. `client_instructions.html` остаётся только на desktop в MVP.
- **D-03:** Single-page form — одна страница `/m/reports/new` с проект-селектом + radio-cards типа + кнопкой «Создать». НЕТ multi-step wizard, НЕТ HTMX swap между шагами.
- **D-04:** После POST «Создать» пользователь остаётся на том же экране. Result-блок появляется inline под формой через HTMX swap либо server-side render при наличии `?report_id=` в URL.
- **D-05:** Recipient source — flat `<select>` из Client CRM с фильтром `email IS NOT NULL OR telegram_username IS NOT NULL`. НЕТ ручного ввода.
- **D-06:** Telegram delivery = link-based. Endpoint `GET /reports/download/{token}` (token в Redis, TTL 7 дней). `telegram_service.send_message_sync` используется как есть. `send_document_sync` НЕ создаётся.
- **D-07:** Feedback = `showToast()` pattern из Phase 28. success/error toast.
- **D-08:** `/m/tools` = single-column card list. Весь card tappable.
- **D-09:** Каждая карточка: name (крупно), description (мелко), limit (справа), badge «Требует Wordstat» только для wordstat-batch.
- **D-10:** OAuth handling — карточка tappable даже без токена. Backend → 302 redirect на `/ui/integrations/wordstat/auth?return_to=/m/tools/wordstat-batch/run` при отсутствии токена.
- **D-11:** Input — textarea + optional file upload (TXT/XLSX). Оба одновременно. Desktop limits сохраняются. Если оба заполнены — ошибка.
- **D-12:** Progress = HTMX polling `every 3s` + дублирующий in-app notify(). Toast «Запущено», progress-блок, кнопка «Показать результаты» при завершении.
- **D-13:** Result view = summary top card + первые 20 строк + «Скачать XLSX» CTA + «Показать все» (HTMX модал).
- **D-14:** Notification `link_url` = `/m/tools/{slug}/jobs/{job_id}`.

### Claude's Discretion

- Service layer — новый `mobile_reports_service.py` и `mobile_tools_service.py`, либо расширить существующие. Planner решает.
- Token generation — `secrets.token_urlsafe(32)` + Redis `SETEX`. Fallback в БД table если Redis недоступен. Planner решает.
- Форма single-page — full form POST или HTMX boost. Planner решает.
- Pagination / «Показать все» — HTMX модал с load-more или обычная pagination. Planner решает.
- HTMX polling endpoint для tools — переиспользовать существующий из Phase 24 или создать mobile-specific. Planner решает.

### Deferred Ideas (OUT OF SCOPE)

- Scheduled reports / регулярная отправка → Phase 36+
- Кастомные шаблоны отчётов → отдельная фаза
- Batch-отправка одного отчёта нескольким клиентам → defer
- PDF preview на мобильном → defer (download сразу)
- Расширение TOOL_REGISTRY (добавление новых tools) → отдельная фаза
- SeoAgent / AI-помощник внутри tool → Phase 33
- Третий тип отчёта (client_instructions.html) — остаётся только для desktop в MVP
- Mobile OAuth flow для wordstat-batch — desktop OAuth handshake используется как есть
- История отправок (ReportDelivery model) — defer, сейчас fire-and-forget
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REP-01 | Пользователь может сформировать PDF-отчёт для клиента с телефона (выбор проекта → тип → создать) | `report_service.generate_pdf_report()` уже работает; нужны mobile router endpoints + шаблон `/m/reports/new` |
| REP-02 | Пользователь может отправить готовый отчёт клиенту в Telegram или email одной кнопкой | `telegram_service.send_message_sync()` + `smtp_service.send_email_with_attachment_sync()` + Redis token endpoint |
| TLS-01 | Пользователь может запустить любой из 6 SEO-инструментов с телефона | `TOOL_REGISTRY` + существующие Celery tasks; нужны mobile /m/tools/* endpoints + шаблоны |
| TLS-02 | Пользователь получает уведомление о завершении и видит результаты | `notify()` в Celery tasks + HTMX polling partial + mobile result view template |
</phase_requirements>

---

## Summary

Фаза 29 — исключительно UI-слой поверх уже существующей инфраструктуры. Вся тяжёлая логика уже написана: WeasyPrint PDF генерация работает через `report_service.generate_pdf_report(db, project_id, report_type)`, 6 Celery tasks для инструментов существуют, `notify()` helper готов, SMTP и Telegram delivery services работают. Задача фазы — написать mobile endpoints в `app/routers/mobile.py` (или отдельный `mobile_reports_tools.py`), шаблоны (`app/templates/mobile/reports/` и `app/templates/mobile/tools/`) и один новый Redis-backed token endpoint для скачивания PDF.

Ключевой паттерн уже задан Phase 28: `mobile_templates.TemplateResponse(...)` + HTMX polling через `position_progress.html` + `showToast()` из `base_mobile.html`. Фаза 29 копирует этот паттерн для двух новых сценариев.

Главный архитектурный вопрос: notify() в существующих Celery tasks (commerce_check, meta_parse, etc.) сейчас НЕ вызывает notify() — нужно добавить вызов с `link_url = /m/tools/{slug}/jobs/{job_id}`. Паттерн уже есть в `suggest_tasks.py` и `position_tasks.py`.

**Primary recommendation:** Добавить endpoints в `app/routers/mobile.py` (или новый router), создать шаблоны по образцу Phase 28, добавить notify() в 6 tool tasks, создать Redis download-token endpoint.

---

## Standard Stack

### Core (все уже в проекте)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.x | ASGI router | Locked stack |
| Jinja2 | 3.1.x | Mobile templates | `mobile_templates = Jinja2Templates(directory="app/templates")` — уже в mobile.py |
| HTMX | 2.0.3 | Polling partials | CDN в base_mobile.html, уже работает |
| WeasyPrint | 62.x | PDF generation | Уже используется в `report_service.generate_pdf_report()` |
| openpyxl | 3.1.x | XLSX download | Уже используется в `tools.py` export |
| redis-py (asyncio) | 5.0.x | Download token storage | Pattern: `redis.asyncio.from_url(settings.REDIS_URL)` — уже в >5 роутерах |
| SQLAlchemy 2.0 | 2.0.x | Async ORM | Locked stack |
| Celery | 5.4.x | Background tasks | Locked stack |

### Redis Pattern (подтверждено кодобазой)

```python
# Установленный паттерн из keyword_suggest.py, overview_service.py
import redis.asyncio as aioredis

async def _get_redis():
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# Token storage (D-06):
r = await _get_redis()
await r.setex(f"reports:dl:{token}", 604800, str(report_id))

# Sync version для Celery tasks (из mobile.py positions pattern):
import redis as redis_lib
r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
r.setex(key, ttl, value)
```

**Версии не нужно устанавливать — всё уже есть в проекте.**

---

## Architecture Patterns

### Recommended Project Structure (новые файлы)

```
app/
├── routers/
│   └── mobile.py                  # Дописать новые endpoints (или mobile_reports_tools.py)
├── services/
│   ├── mobile_reports_service.py  # generate_mobile_report(), list_clients_with_contacts()
│   └── mobile_tools_service.py    # get_tool_job(), get_tool_results_top20()
└── templates/
    └── mobile/
        ├── reports/
        │   └── new.html            # /m/reports/new — form + result block
        └── tools/
            ├── list.html           # /m/tools — card list
            ├── run.html            # /m/tools/{slug}/run — input form
            ├── result.html         # /m/tools/{slug}/jobs/{job_id}
            └── partials/
                ├── tool_progress.html  # HTMX polling (clone position_progress.html)
                └── tool_result_modal.html  # "Показать все" modal content
```

### Pattern 1: Mobile Report Generation (синхронный PDF)

PDF генерируется синхронно в HTTP-запросе (WeasyPrint через `asyncio.run_in_executor`). Это допустимо — WeasyPrint уже делает это в `generate_pdf_report()`, время генерации 1-5 секунд, что вписывается в `< 3s UI pages` constraint только если запрос быстрый. При медленной генерации — spinner на кнопке.

Альтернатива: Celery task для PDF + HTMX polling. Но CONTEXT.md D-03 говорит про single-page form без дополнительных шагов, а D-04 предполагает inline result reveal — синхронный подход проще для MVP.

**Решение для planner:** синхронный PDF (уже работает в desktop). Если WeasyPrint займёт > 3s — добавить spinner на кнопку через JS `hx-indicator`.

```python
# Source: app/routers/reports.py (existing) + app/services/report_service.py
@router.post("/m/reports/new", response_class=HTMLResponse)
async def mobile_report_create(
    request: Request,
    project_id: uuid.UUID = Form(...),
    report_type: str = Form("brief"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    pdf_bytes = await report_service.generate_pdf_report(db, project_id, report_type)
    # Store PDF in Redis with token, return result block partial
    token = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL)
    await r.setex(f"reports:dl:{token}", 604800, ...)  # store pdf_bytes or report metadata
    return mobile_templates.TemplateResponse(
        "mobile/reports/new.html",
        {"request": request, "token": token, "report_type": report_type, ...},
    )
```

**Важный вопрос о хранении PDF:** Redis `SETEX` хранит строку — PDF bytes нельзя хранить напрямую в Redis с `decode_responses=True`. Варианты:
1. Хранить в Redis без `decode_responses` как bytes (best для временного хранения)
2. Хранить в PostgreSQL в отдельной table `mobile_report_cache` с TTL-cleanup
3. Хранить в файловой системе `/tmp/reports/{token}.pdf` — не персистентно в Docker

**Рекомендация planner:** хранить PDF bytes в Redis без decode_responses (отдельный Redis client), ключ `reports:dl:{token}` → PDF bytes, TTL 7 дней. При скачивании — `await r.get(key)` → StreamingResponse. Если Redis недоступен — fallback: записать PDF в `/tmp/` и хранить путь в Redis.

### Pattern 2: Tool Run + HTMX Polling (clone от Phase 28)

```python
# Source: app/routers/mobile.py — mobile_trigger_position_check (verbatim pattern)
@router.post("/m/tools/{slug}/run", response_class=HTMLResponse)
async def mobile_tool_run(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    # 1. Parse input (textarea or file upload)
    # 2. Validate: not empty, not both, not over limit
    # 3. Create Job record (same as tools.py tool_submit)
    # 4. Dispatch Celery task
    # 5. Return progress partial (tool_progress.html) with hx-trigger="every 3s"
    ...

@router.get("/m/tools/{slug}/jobs/{job_id}/status", response_class=HTMLResponse)
async def mobile_tool_job_status(...):
    # Returns tool_progress.html partial (running/done/error states)
    # When done: link_url = /m/tools/{slug}/jobs/{job_id}
    ...
```

**Ключевой вопрос:** существующий `GET /ui/tools/{slug}/{job_id}/status` возвращает desktop template `tools/{slug}/partials/job_status.html`. Для mobile нужен отдельный endpoint с mobile partial — `tool_progress.html` в `/m/` prefix. Это согласовано с D-14 (mobile result endpoint `/m/tools/{slug}/jobs/{job_id}`).

### Pattern 3: notify() в tool tasks

Существующие tool tasks (commerce_check, meta_parse, etc.) НЕ вызывают notify(). Нужно добавить по образцу `suggest_tasks.py`:

```python
# Source: app/tasks/suggest_tasks.py (существующий паттерн)
# В конце каждого tool task (commerce_check_tasks.py, meta_parse_tasks.py, etc.):
from app.services.notifications import notify

# Добавить user_id в Job model (уже есть: job.user_id)
async with AsyncSessionLocal() as db:
    await notify(
        db=db,
        user_id=job.user_id,
        kind="tool.completed",
        title=f"{tool_name} завершён",
        body=f"Обработано {count} результатов",
        link_url=f"/m/tools/{slug}/jobs/{str(job_uuid)}",
        severity="info",
    )
    await db.commit()
```

**Критично:** все 6 tool tasks уже имеют `job.user_id` (подтверждено: `job_kwargs["user_id"] = user.id` в tools.py). Нет необходимости менять модели.

### Pattern 4: Telegram link-based delivery (D-06)

```python
# New endpoint: GET /reports/download/{token}
@router.get("/reports/download/{token}")
async def report_download(token: str) -> StreamingResponse:
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    pdf_bytes = await r.get(f"reports:dl:{token}")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Token expired or invalid")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="report.pdf"'},
    )

# Telegram delivery (D-06):
platform_url = settings.APP_BASE_URL  # e.g. "https://seo.example.com"
download_url = f"{platform_url}/reports/download/{token}"
telegram_service.send_message_sync(
    f"Отчёт клиенту готов: {project_name}\n{download_url}"
)
```

**Важно:** `APP_BASE_URL` (или аналог) должен быть в `settings` (проверить `app/config.py`). Если нет — planner должен добавить.

### Pattern 5: Client select with contacts (D-05)

Модель `Client` имеет `email` и поле `telegram_username` в `ClientContact` (НЕ в `Client` напрямую). Это важное открытие: `Client.telegram_username` отсутствует в Client модели — оно в `ClientContact.telegram_username`.

```python
# Нужна query с JOIN на ClientContact:
from sqlalchemy import or_, select
from app.models.client import Client, ClientContact

stmt = (
    select(Client, ClientContact)
    .join(ClientContact, ClientContact.client_id == Client.id, isouter=True)
    .where(
        Client.is_deleted == False,
        or_(Client.email.isnot(None), ClientContact.telegram_username.isnot(None))
    )
    .distinct(Client.id)
    .order_by(Client.company_name)
)
```

Либо упрощённо — только клиенты с `Client.email IS NOT NULL` (проще), так как Telegram username лежит в связанной таблице и доставка Telegram в D-06 идёт через link в ЧАТ-ID бота (не по telegram_username).

**Уточнение:** текущий `telegram_service.send_message_sync()` шлёт в `settings.TELEGRAM_CHAT_ID` — это системный чат, не чат клиента. Для отправки клиенту нужен telegram_username или chat_id клиента. CONTEXT.md D-06 говорит "link-based" — ссылка на download endpoint отправляется через send_message_sync, что шлёт администратору платформы (не клиенту). Это fire-and-forget для MVP.

### Anti-Patterns to Avoid

- **Хранить PDF bytes в Redis с decode_responses=True** — `decode_responses=True` ломает работу с binary data. Используйте отдельный Redis client без decode_responses или base64-encode.
- **Переиспользовать desktop tool status endpoint** (`/ui/tools/{slug}/{job_id}/status`) для mobile polling — он рендерит desktop template. Создайте отдельный `/m/tools/{slug}/jobs/{job_id}/status`.
- **Генерировать PDF в Celery task для mobile MVP** — избыточно; WeasyPrint уже запускается в executor в report_service.py, достаточно для одного пользователя.
- **Блокировать tool dispatch на отсутствие OAuth** — D-10 говорит: карточка всегда tappable, redirect происходит при попытке запуска если нет токена.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF generation | WeasyPrint wrapper | `report_service.generate_pdf_report()` | Уже работает с WeasyPrint subprocess isolation |
| Celery task dispatch | Custom task runner | `_get_tool_task(slug).delay(job_id_str)` из tools.py | 6 tasks уже написаны и работают |
| Job status polling | Custom WebSocket | HTMX `every 3s` polling | Уже доказан в Phase 28, position_progress.html |
| In-app notification | Custom push service | `notify()` из `app/services/notifications.py` | Phase 17 инфраструктура |
| Email attachment | Custom MIME builder | `smtp_service.send_email_with_attachment_sync()` | Уже работает с PDF bytes |
| XLSX export | Custom serializer | Существующий `tool_export` endpoint | Все 6 форматов уже реализованы |
| Tool input parsing | Custom uploader | `openpyxl` для XLSX + `.splitlines()` для TXT | Стандарт в проекте |
| Auth on download endpoint | Custom token system | `secrets.token_urlsafe(32)` + Redis SETEX | Достаточно для MVP, не требует БД |

---

## Runtime State Inventory

> Фаза — добавление новых endpoint'ов и шаблонов. Не rename/refactor. Нет существующего runtime state для миграции.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Нет — phase создаёт новые Redis keys `reports:dl:{token}` с TTL 7 дней | Нет миграции данных |
| Live service config | Нет — существующий Redis, SMTP, Telegram используются без изменений | Нет |
| OS-registered state | Нет | Нет |
| Secrets/env vars | `APP_BASE_URL` — может отсутствовать в config.py (нужен для формирования download URL в Telegram) | Проверить и добавить в Settings если нет |
| Build artifacts | Нет | Нет |

---

## Common Pitfalls

### Pitfall 1: Redis binary vs string для PDF bytes

**What goes wrong:** Если создать Redis client с `decode_responses=True` и попробовать `setex(key, ttl, pdf_bytes)` — будет `UnicodeDecodeError` или `TypeError`.

**Why it happens:** `decode_responses=True` автоматически декодирует все Redis ответы как UTF-8 строки, PDF bytes не являются валидным UTF-8.

**How to avoid:** Создавать отдельный Redis client для PDF storage без `decode_responses`:
```python
r = aioredis.from_url(settings.REDIS_URL)  # НЕТ decode_responses=True
await r.set(f"reports:dl:{token}", pdf_bytes, ex=604800)
```

**Warning signs:** `UnicodeDecodeError` или `TypeError: a bytes-like object is required` при работе с Redis.

### Pitfall 2: File upload (multipart) в FastAPI form

**What goes wrong:** `request.form()` не парсит `<input type="file">` — нужно явно объявить `UploadFile` параметр.

**Why it happens:** FastAPI разделяет form fields и file uploads в декларации endpoint'а.

**How to avoid:**
```python
@router.post("/m/tools/{slug}/run")
async def mobile_tool_run(
    slug: str,
    request: Request,
    phrases: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    ...
):
    if phrases and file:
        raise HTTPException(422, "Используйте одно из двух: текст или файл")
```

**Warning signs:** `422 Unprocessable Entity` при отправке файла.

### Pitfall 3: HTMX polling не останавливается на done/error

**What goes wrong:** Если шаблон `tool_progress.html` в состоянии `done` или `error` всё ещё содержит `hx-trigger="every 3s"` — polling продолжается бесконечно.

**Why it happens:** HTMX polling останавливается только когда элемент с `hx-trigger` удалён из DOM или заменён элементом без этого атрибута.

**How to avoid:** В состоянии `done` и `error` рендерить `<div id="tool-progress-slot">` без `hx-trigger` атрибута. Паттерн уже правильно реализован в `position_progress.html`.

**Warning signs:** Запросы к `/m/tools/{slug}/jobs/{job_id}/status` продолжают идти после завершения задачи.

### Pitfall 4: Tool tasks не имеют notify() — TLS-02 не выполнится

**What goes wrong:** Пользователь запускает инструмент, закрывает экран, уведомление не приходит.

**Why it happens:** Существующие 6 tool tasks (commerce_check_tasks, meta_parse_tasks, etc.) НЕ вызывают `notify()` — это подтверждено аудитом кода. Только `suggest_tasks.py` и `position_tasks.py` используют notify().

**How to avoid:** В каждый из 6 tool tasks добавить notify() вызов при статусах `complete`, `partial` и опционально `failed`:
```python
# В конце run_commerce_check(), run_meta_parse(), etc.:
from app.database import AsyncSessionLocal
import asyncio

async def _send_notify(user_id, job_uuid, slug, count):
    async with AsyncSessionLocal() as db:
        from app.services.notifications import notify
        await notify(
            db=db, user_id=user_id, kind="tool.completed",
            title=f"Инструмент завершён",
            body=f"Обработано {count} результатов",
            link_url=f"/m/tools/{slug}/jobs/{str(job_uuid)}",
            severity="info",
        )
        await db.commit()

asyncio.run(_send_notify(job.user_id, job_uuid, slug, len(results)))
```

**Warning signs:** TLS-02 acceptance test провалится — уведомление не появляется после завершения task.

### Pitfall 5: Client.telegram_username не существует

**What goes wrong:** `Client` model не имеет поля `telegram_username` — оно находится в `ClientContact` (связанная модель).

**Why it happens:** CONTEXT.md ссылается на `app/models/client.py` с `telegram_username` — но это в `ClientContact`, не в `Client`. Client имеет `email` поле.

**How to avoid:** При фильтрации клиентов для recipient select использовать LEFT JOIN с `ClientContact`:
```python
stmt = select(Client).outerjoin(ClientContact).where(
    Client.is_deleted == False,
    or_(Client.email.isnot(None), ClientContact.telegram_username.isnot(None))
).distinct()
```

Или упростить: показывать только клиентов с `Client.email IS NOT NULL` для email delivery, и всех клиентов для Telegram (delivery идёт в системный chat).

**Warning signs:** `AttributeError: 'Client' object has no attribute 'telegram_username'`.

### Pitfall 6: APP_BASE_URL отсутствует в settings

**What goes wrong:** Telegram download link формируется как relative URL вместо абсолютного.

**Why it happens:** Telegram бот не может открыть relative URL.

**How to avoid:** Проверить `app/config.py` на наличие `APP_BASE_URL` или аналога. Если нет — добавить:
```python
class Settings(BaseSettings):
    APP_BASE_URL: str = "http://localhost:8000"
```

---

## Code Examples

### Существующий Redis pattern (из keyword_suggest.py)

```python
# Source: app/routers/keyword_suggest.py
import redis.asyncio as aioredis

client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
await client.setex(f"suggest:lock:{site_id}", 300, "1")
```

### HTMX polling template pattern (из position_progress.html)

```html
<!-- Source: app/templates/mobile/partials/position_progress.html -->
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
  <!-- done state — NO hx-trigger! -->
  <a href="/m/tools/{{ slug }}/jobs/{{ job_id }}">Показать результаты</a>
</div>
{% endif %}
```

### PDF generation (из report_service.py)

```python
# Source: app/services/report_service.py (уже работает)
pdf_bytes = await report_service.generate_pdf_report(db, project_id, report_type)
# report_type: "brief" | "detailed"
# Returns: bytes
```

### notify() в Celery task (из suggest_tasks.py)

```python
# Source: app/tasks/suggest_tasks.py (реальный пример)
async with AsyncSessionLocal() as db:
    await notify(
        db=db, user_id=_user_id, kind="tool.completed",
        title="Инструмент завершён",
        body=f"Обработано {count} результатов",
        link_url=f"/m/tools/{slug}/jobs/{job_id_str}",
        site_id=None, severity="info",
    )
    await db.commit()
asyncio.run(...)  # wrap for sync Celery task
```

### File upload parsing pattern (из tools.py tool_submit)

```python
# Source: app/routers/tools.py
form_data = await request.form()
raw_text = form_data.get(registry["form_field"], "") or ""
lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
```

Для file upload (новое):
```python
# TXT: content = await file.read(); lines = content.decode().splitlines()
# XLSX: wb = openpyxl.load_workbook(io.BytesIO(content)); lines = [row[0].value for row in ws.iter_rows()]
```

---

## Environment Availability

> Step 2.6: Нет новых внешних зависимостей — все библиотеки уже установлены в проекте.

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| WeasyPrint 62.x | PDF generation | Подтверждено (используется в report_service.py) | — |
| redis-py asyncio | Token storage | Подтверждено (используется в 5+ файлах) | — |
| aiosmtplib | Email delivery | Подтверждено (smtp_service.py) | — |
| openpyxl | XLSX file parsing + export | Подтверждено (tools.py) | — |
| Celery 5.4 | Tool tasks | Подтверждено (6 tasks работают) | — |

**Missing dependencies with no fallback:** None.

---

## Inventory: Что уже существует, что нужно создать

### Уже существует (переиспользуется без изменений)

| File | What's Used |
|------|-------------|
| `app/services/report_service.py` | `generate_pdf_report(db, project_id, "brief"\|"detailed")` |
| `app/services/smtp_service.py` | `send_email_with_attachment_sync(to, subject, html, pdf_bytes, filename)` |
| `app/services/telegram_service.py` | `send_message_sync(text)` |
| `app/services/notifications.py` | `notify(db, user_id, kind, title, body, link_url)` |
| `app/routers/tools.py` | `TOOL_REGISTRY` dict, `_get_tool_models()`, `_get_tool_task()`, `_result_to_row()` |
| `app/templates/mobile/base_mobile.html` | `showToast()`, HTMX 2.0.3, bottom nav |
| `app/templates/mobile/partials/position_progress.html` | Polling partial pattern |
| `app/templates/mobile/partials/task_form.html` | HTMX form partial pattern |
| `app/services/project_service.py` | `get_accessible_projects(db, user)` |
| `app/services/client_service.py` | `list_clients(db)` (нужен with_contacts filter) |

### Нужно создать

| File | What To Build |
|------|--------------|
| `app/routers/mobile.py` (дописать) или `mobile_reports_tools.py` | 8-10 новых endpoints |
| `app/services/mobile_reports_service.py` | `list_clients_for_reports()`, token helpers |
| `app/services/mobile_tools_service.py` | `get_job_top20_results()`, file upload parsing |
| `app/templates/mobile/reports/new.html` | Single-page form + result block |
| `app/templates/mobile/tools/list.html` | 6 tool cards |
| `app/templates/mobile/tools/run.html` | Input form + progress slot |
| `app/templates/mobile/tools/result.html` | Summary + top-20 + XLSX + modal |
| `app/templates/mobile/tools/partials/tool_progress.html` | Polling partial |
| `app/templates/mobile/tools/partials/tool_result_modal.html` | "Показать все" modal |
| Изменения в 6 Celery tasks | Добавить `notify()` вызов при завершении |
| `GET /reports/download/{token}` | PDF download endpoint с Redis token |

### Нет необходимости в Alembic миграции

Никаких новых таблиц не создаётся. Следующий номер миграции был бы `0055`, но он не нужен.

---

## Critical Technical Decisions для planner

### Решение 1: Хранение PDF для скачивания

Нужно решить: где хранить PDF bytes между генерацией и скачиванием.

**Option A (рекомендуется):** Redis bytes store
- Создать Redis client без `decode_responses=True`
- `await r.set(f"reports:dl:{token}", pdf_bytes, ex=604800)`
- При GET `/reports/download/{token}` — `pdf_bytes = await r.get(key)`
- Pros: TTL автоматически, быстро, без схемы БД
- Cons: PDF bytes занимают RAM Redis; для 100 PDF по 500KB = 50MB (приемлемо)

**Option B (fallback):** Временный файл на диске
- `Path(f"/tmp/reports/{token}.pdf").write_bytes(pdf_bytes)`
- При скачивании читать файл
- Cons: нет автоматического TTL, не персистентно между restarts Docker контейнера

### Решение 2: Где разместить новые endpoints

**Option A (рекомендуется):** Дописать в `app/routers/mobile.py`
- Все mobile endpoints в одном файле — консистентно с Phase 26-28
- Файл уже 621 строка — станет ~900-1000 строк, управляемо

**Option B:** Новый файл `app/routers/mobile_reports_tools.py`
- Чище при большом объёме
- Требует регистрации нового router в `main.py`

### Решение 3: notify() в tool tasks — где именно добавить

Добавить в конец `run_commerce_check`, `run_meta_parse`, `run_relevant_url`, `run_wordstat_batch`, `run_paa`, и в `run_brief_step4_finalize`. Паттерн: `asyncio.run()` wrapping async notify call.

---

## Open Questions

1. **APP_BASE_URL в settings**
   - What we know: telegram_service.send_message_sync() отправляет текст; download URL должен быть абсолютным
   - What's unclear: Есть ли `APP_BASE_URL` или аналог в `app/config.py`
   - Recommendation: Проверить при планировании; если нет — добавить `APP_BASE_URL: str = ""` в Settings

2. **Telegram delivery — кому именно**
   - What we know: `send_message_sync` шлёт в `settings.TELEGRAM_CHAT_ID` (системный чат)
   - What's unclear: Ожидает ли пользователь что ссылка на PDF уйдёт именно клиенту или себе в Telegram
   - Recommendation: Для MVP — отправлять себе в системный чат (как все текущие алерты). CONTEXT.md не уточняет. Не блокирует.

3. **Wordstat OAuth redirect URL**
   - What we know: Существующий desktop flow принимает token через `/ui/settings`, не через `/ui/integrations/wordstat/auth`
   - What's unclear: CONTEXT.md упоминает `/ui/integrations/wordstat/auth?return_to=...` — этот endpoint нужно проверить при планировании
   - Recommendation: Planner должен проверить существование этого пути; если нет — редиректить на `/ui/settings` с note

---

## Sources

### Primary (HIGH confidence — кодобаза проверена лично)

- `/opt/seo-platform/app/services/report_service.py` — `generate_pdf_report()` signature и реализация
- `/opt/seo-platform/app/services/telegram_service.py` — `send_message_sync()` signature
- `/opt/seo-platform/app/services/smtp_service.py` — `send_email_with_attachment_sync()` signature
- `/opt/seo-platform/app/services/notifications.py` — `notify()` signature
- `/opt/seo-platform/app/routers/tools.py` — `TOOL_REGISTRY` структура, 6 handlers
- `/opt/seo-platform/app/routers/mobile.py` — mobile_templates pattern, HTMX polling pattern
- `/opt/seo-platform/app/templates/mobile/partials/position_progress.html` — canonical polling template
- `/opt/seo-platform/app/models/client.py` — Client + ClientContact field structure
- `/opt/seo-platform/app/tasks/commerce_check_tasks.py` — tool task pattern без notify()
- `/opt/seo-platform/app/tasks/suggest_tasks.py` — notify() pattern в Celery task

### Secondary (MEDIUM confidence)

- CONTEXT.md (decisions D-01 … D-14) — пользовательские решения
- UI-SPEC.md (29-UI-SPEC.md) — одобрённый UI дизайн контракт

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — все библиотеки и сервисы подтверждены в кодобазе
- Architecture: HIGH — паттерны скопированы из Phase 28 (mobile.py)
- Pitfalls: HIGH — обнаружены через аудит кода (binary Redis, отсутствие notify() в tool tasks, Client.telegram_username)
- Open questions: 3 малых вопроса, не блокируют планирование

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (стабильная кодобаза, месяц актуальности)
