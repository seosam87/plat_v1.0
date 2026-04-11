# Phase 30: Errors & Quick Task — Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Мобильные экраны `/m/errors` и `/m/tasks/new` в v4.0 Mobile & Telegram. Пользователь со смартфона видит ошибки верифицированных в Yandex Webmaster сайтов (индексация / краулинг / санкции) сгруппированными по типу, одним нажатием составляет ТЗ на исправление конкретной ошибки и сохраняет как SeoTask. Отдельно — быстро добавляет задачу в проект (текст + приоритет + проект) или составляет ТЗ копирайтеру с подстановкой ключевых слов и отправкой клиенту через Telegram/email (переиспользует паттерны Phase 29).

**Delivers:**
- `GET /m/errors` — страница с 3 секциями (Индексация / Краулинг / Санкции), top-5 samples в каждой + "Показать все" HTMX expand. Top dropdown для выбора сайта (persist в cookie `m_errors_site_id`).
- `POST /m/errors/sync` — manual refresh кнопка → Celery task `sync_yandex_errors.delay(site_id)` с HTMX polling прогресса (паттерн Phase 29).
- `POST /m/errors/{error_id}/brief` — inline HTMX swap в строке error: textarea + priority radio + project select → создаёт `SeoTask` с `source_error_id` FK, show "✓ ТЗ создано" inline.
- `GET /m/tasks/new?mode=task|brief` — одна страница с toggle [Задача] [ТЗ копирайтеру], HTMX swap формы.
- `POST /m/tasks/new` (mode=task) — 3 поля (text, priority, project) → создаёт SeoTask с auto-filled title/description/url + showToast + redirect на `/m/`.
- `POST /m/tasks/new` (mode=brief) — расширенная форма (keywords, tone, length, project, recipient) → рендерит Jinja2 шаблон `briefs/copywriter_brief.txt.j2` → создаёт SeoTask + отправляет через Telegram/email (переиспользует helpers из Phase 29).
- Новая таблица `yandex_errors` (Alembic миграция) — row per sample с status workflow (open/ignored/resolved).
- Расширение `TaskType` enum: `+yandex_indexing`, `+yandex_crawl`, `+yandex_sanction` + новый nullable FK `SeoTask.source_error_id → yandex_errors.id`.

**Out of scope (block if suggested):**
- Yandex Metrika errors → defer (нет готовых error endpoints в API)
- Auto-schedule через Celery Beat для sync_yandex_errors → defer (MVP = manual refresh only)
- Новое поле `Site.yandex_host_id` + desktop UI для привязки → defer (mapping по `Site.domain` достаточно для MVP)
- Отдельная модель `Brief` / таблица `briefs` → defer (используем SeoTask + расширенный TaskType enum)
- Отдельная модель `QuickTask` → defer (auto-fill SeoTask полей достаточно)
- Переиспользование Celery brief-tool из Phase 29 для TSK-02 → отдельный flow (там краул+анализ, здесь — ручные данные+шаблон)
- Desktop UI для `/ui/errors` или `/ui/tasks/new` → Phase 30 **только мобильные экраны**
- Assignee field в quick task → defer (only text+priority+project в MVP)
- Bulk ignore/resolve errors → defer (single-row actions only)
- Multi-site "all errors" aggregated view → defer (per-site dropdown only)
- Error filtering/search внутри секции → defer (топ-5 + "Показать все" без фильтров)
- Rendering brief PDF через WeasyPrint → defer (text-based ТЗ достаточно для копирайтера, PDF — Phase 29 scope)
- Site→Project auto-resolution при отсутствии Project.site_id → блокируется 422 без magic

</domain>

<decisions>
## Implementation Decisions

### Gray Area 1 — Errors: источники данных

- **D-01:** Только Yandex Webmaster API. 3 типа ошибок — indexing (samples), crawl (samples), sanctions. Yandex Metrika исключена из MVP (нет готовых error endpoints). Текст "Метрики" в goal ROADMAP трактуется как "будет в backlog-фазе".
- **D-02:** Site↔host mapping через `Site.domain` ↔ `ascii_host_url` из Webmaster `/user/{user_id}/hosts/`. Результат кэшируется в Redis под ключом `yandex:host_map:{user_id}` с TTL 1 день. Нет новых полей в Site модели. Если сайт не найден в верифицированных hosts → в UI показываем "Хост не привязан, проверьте верификацию в Webmaster".

### Gray Area 2 — Errors sync strategy

- **D-03:** Гибрид: cached + manual refresh. Новая таблица `yandex_errors` в DB, `/m/errors` читает из DB. Pull-to-refresh button запускает Celery task `sync_yandex_errors.delay(site_id)`, прогресс через HTMX polling (паттерн Phase 29 D-12 — `hx-trigger="every 3s"` + notify() на завершение). Celery Beat авто-schedule — deferred.
- **D-04:** Схема `yandex_errors`:
  - `id: UUID PK`
  - `site_id: UUID FK → sites.id (CASCADE)`
  - `error_type: Enum('indexing', 'crawl', 'sanction')` — 3 значения
  - `subtype: String(100)` — e.g. `"robots_txt"`, `"duplicate"`, `"404"`, `"redirect_loop"`, `"adult_content"`, `"manual_penalty"`
  - `url: String(2000), nullable` — null для sanctions, required для indexing/crawl
  - `title: String(500)` — человекочитаемое название (например "Страница возвращает 404")
  - `detail: Text, nullable` — доп. описание из Webmaster API payload
  - `detected_at: DateTime` — когда ошибка впервые обнаружена (из Webmaster response, если есть)
  - `fetched_at: DateTime` — когда мы её pulled в нашу DB
  - `status: Enum('open', 'ignored', 'resolved'), default 'open'`
  - Индексы: `(site_id, error_type)`, `(site_id, status)`
- **D-05:** Sync task `sync_yandex_errors(site_id)` в `app/tasks/yandex_errors_tasks.py`:
  1. Resolve host_id через кэш / API
  2. Fetch все 3 типа ошибок (3 API calls) с лимитами (Webmaster предоставляет samples, не все записи — достаточно для MVP)
  3. Upsert в `yandex_errors` через `(site_id, error_type, subtype, url)` unique key (если уже есть — update fetched_at + detail; если нет — INSERT с status=open)
  4. Soft-close записи которых больше нет в API: мы помечаем их `status='resolved'` автоматически (error считается "ушёл" если в последнем sync его не было)
  5. Celery retry=3 для API failures (CLAUDE.md constraint)

### Gray Area 3 — /m/errors layout

- **D-06:** `/m/errors` = одна страница, 3 секции с заголовками (Индексация / Краулинг / Санкции). В каждом заголовке секции — count-badge (`N`). Под заголовком — top-5 samples (sorted by detected_at DESC, status='open' first). CTA "Показать все (N)" под секцией → HTMX swap (`hx-target=closest section`) раскрывает полный список с pagination (20 per page, "Загрузить ещё" internal link).
- **D-07:** Top dropdown для выбора сайта — показывает только сайты пользователя с `Site.domain` (любые, не только верифицированные в Webmaster). Change → HTMX swap секций (`hx-target=#errors-content`) + persist selection в session cookie `m_errors_site_id`. Если хост не привязан в Webmaster — секции показывают "Хост не привязан к Yandex Webmaster. Верифицируйте сайт в Webmaster и нажмите Обновить."

### Gray Area 4 — ERR-02: ТЗ на ошибку

- **D-08:** ТЗ сохраняется как `SeoTask` с новым task_type.
  - Расширяем `TaskType` enum: `+yandex_indexing`, `+yandex_crawl`, `+yandex_sanction` (Alembic migration alters Postgres enum type).
  - Новый nullable FK в модели: `SeoTask.source_error_id: UUID FK → yandex_errors.id, nullable, ondelete=SET NULL`.
  - При создании ТЗ из error:
    - `site_id = error.site_id`
    - `url = error.url or ""` (empty string если sanctions)
    - `title = error.title` (auto-filled)
    - `description = user text` (из textarea)
    - `task_type = yandex_indexing/yandex_crawl/yandex_sanction` (по error.error_type)
    - `priority = user selected`
    - `project_id = user selected` (nullable)
    - `source_error_id = error.id`
- **D-09:** UI flow создания ТЗ = **inline expand в строке ошибки**.
  - В каждой строке error есть кнопка "Составить ТЗ" (right-aligned).
  - Click → HTMX `hx-get="/m/errors/{error_id}/brief/form"`, `hx-target="closest .error-row"`, swap outerHTML.
  - Swap разворачивает форму: textarea (description), radio priority (P1/P2/P3/P4, default P3), project `<select>` (все проекты пользователя, nullable), кнопки [Сохранить] [Отмена].
  - POST `/m/errors/{error_id}/brief` создаёт SeoTask → HTMX возвращает строку-confirmation "✓ ТЗ создано — <a>открыть</a>" с ссылкой на desktop `/ui/tasks/{task_id}`.
  - Остаёмся на `/m/errors`, scroll position сохраняется.

### Gray Area 5 — TSK-01: быстрая задача (model mismatch)

- **D-10:** Auto-fill SeoTask поля, nullable не добавляем.
  - Форма `/m/tasks/new?mode=task`: `textarea` (required, maxlen 2000) + priority radio (P1-P4, default P3) + project select (все проекты пользователя, required) + [Создать].
  - Backend mapping:
    - `title = text[:80].strip()` (первые 80 символов, trim whitespace)
    - `description = text` (полный)
    - `url = ""` (empty string, NOT null — SeoTask.url остаётся NOT NULL)
    - `site_id = Project.site_id` (из выбранного проекта)
    - `task_type = manual`
    - `status = open`
    - `priority = user selected`
    - `project_id = user selected`
    - `source_error_id = null`
  - Если `Project.site_id is null` → 422 с сообщением "У проекта нет привязанного сайта. Привяжите сайт в настройках проекта."
  - Success → `showToast("Задача создана")` + redirect на `/m/` (dashboard).

### Gray Area 6 — TSK-02: ТЗ копирайтеру из аналитики

- **D-11:** Новый flow, НЕ переиспользуем Celery brief-tool из Phase 29.
  - Форма `/m/tasks/new?mode=brief`: textarea `keywords` (1 на строку, required) + `tone` select (`информационный` / `коммерческий` / `экспертный`) + `length` select (1000 / 2000 / 3000 / 5000 слов) + `project` select (required) + `recipient` select (Client CRM с фильтром `email IS NOT NULL OR telegram_username IS NOT NULL`, nullable — если null, то brief сохраняется как SeoTask без отправки) + [Создать и отправить] / [Только сохранить].
  - Backend:
    - Рендерит Jinja2 шаблон `app/templates/briefs/copywriter_brief.txt.j2` с плейсхолдерами `{keywords}`, `{tone}`, `{length}`, `{project_name}`, `{site_url}`.
    - Создаёт SeoTask с `task_type=manual`, `title="ТЗ копирайтеру: {N} ключевых слов"`, `description=rendered text`, `url=""`, `site_id=Project.site_id`.
    - Если recipient выбран — отправляет через Phase 29 паттерн:
      - Telegram: `store_report_pdf()` аналог для text → token → `send_message_sync(text+link)` ИЛИ inline text message без PDF
      - Email: `send_email_sync(subject, body=rendered_text)` (attachment не нужен — это plain text)
  - Для Phase 30 оптимизация: для text briefs (не PDF) Telegram отправляет просто **текст сообщения** без Redis token (короткий brief помещается в одно сообщение <4096 chars). Email — plain text body, no attachment. Если rendered text >4000 chars — прикрепляем как `.txt` attachment.
  - Success → `showToast("ТЗ создано и отправлено клиенту")` (или "ТЗ сохранено" если recipient=null) + redirect на `/m/`.
  - **Jinja2 template structure** (создаётся в этой фазе):
    ```
    # ТЗ копирайтеру

    **Проект:** {{ project_name }}
    **Сайт:** {{ site_url }}
    **Объём:** {{ length }} слов
    **Tone of voice:** {{ tone }}

    ## Ключевые слова
    {% for kw in keywords %}
    - {{ kw }}
    {% endfor %}

    ## Требования
    [template-specific text here, expanded by planner based on this decision]
    ```

- **D-12:** Mode toggle UI.
  - `/m/tasks/new` — одна страница, 2 toggle вверху: [Задача] [ТЗ копирайтеру].
  - Активный toggle persist в query-param (`?mode=task` / `?mode=brief`, default=task) для shareable URL.
  - Toggle change → HTMX swap формы (`hx-get="/m/tasks/new/form?mode=brief"`, `hx-target="#task-form"`).
  - Visual: два полноширинных button toggle, active state = accent color (из UI-SPEC Phase 29).

### Claude's Discretion

- **Jinja2 template для copywriter brief** — точная структура placeholder-ов может быть расширена planner-ом. Главное: 5 подстановок (project_name, site_url, length, tone, keywords list).
- **HTMX inline form HTML markup** — структура row-swap может быть реализована через dedicated partial template.
- **Empty state copy** — "Нет ошибок" / "Нет задач" / "Нет клиентов с контактами" — следовать UI-SPEC Phase 29 copywriting rules.
- **Error icons** — иконки для 3 типов ошибок (иконка Heroicons для каждого) — planner выбирает из inline SVG Heroicons registry (D-14 Phase 29).
- **Priority radio UI** — 4 радиокнопки с цветом и лейблом (P1 red / P2 orange / P3 gray / P4 blue), пример из существующих `app/templates/tasks/*.html`.

### Folded Todos

_Не применимо — ни один backlog-todo не подошёл по scope (оба matched на общее keyword "tasks", но это position-check bug и proxy health-checker — out of phase scope)._

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing code patterns (reuse)
- `app/services/yandex_webmaster_service.py` — существующий API client, нужно добавить 3 новых функции для fetch errors (indexing_errors, crawl_errors, sanctions). Паттерн уже установлен (httpx + _headers + API_BASE).
- `app/routers/yandex.py` — admin endpoints для тестирования Yandex integration, НЕ мобильный роутер.
- `app/routers/mobile.py` — все `/m/*` endpoints. Phase 30 endpoints добавляются сюда (append).
- `app/models/task.py` — SeoTask модель + TaskType enum. Phase 30 **расширяет** enum через Alembic migration.
- `app/tasks/suggest_tasks.py` — REFERENCE pattern для Celery task с notify() call (из Phase 29 RESEARCH Pitfall 4).
- `app/services/mobile_reports_service.py` (Phase 29) — Redis token helpers для PDF delivery. Phase 30 может частично переиспользовать для brief text delivery (или создать аналогичный `mobile_brief_service`).
- `app/services/mobile_tools_service.py` (Phase 29) — паттерн `get_job_for_user` / `parse_tool_input` для polling-aware endpoints.
- `app/templates/mobile/base_mobile.html` (Phase 26) — layout обёртка для всех `/m/*` страниц.
- `app/templates/mobile/tools/partials/tool_progress.html` (Phase 29) — REFERENCE pattern для HTMX polling (остановка в done/error ветках — Phase 29 Pitfall 3).

### Phase 29 contracts (locked decisions applicable here)
- `.planning/phases/29-reports-tools/29-CONTEXT.md`:
  - D-05: Client CRM select с `email IS NOT NULL OR telegram_username IS NOT NULL` фильтром — применимо к TSK-02 recipient.
  - D-06: Link-based Telegram delivery через Redis token + `/m/reports/download/{token}` — частично применимо к TSK-02 (для длинных brief).
  - D-07: `showToast()` feedback pattern.
  - D-12: HTMX polling `every 3s` + notify() double-safety.
  - D-13: summary card + top-20 + "Показать все" modal — применимо к "Показать все" паттерну в /m/errors.
- `.planning/phases/29-reports-tools/29-UI-SPEC.md`:
  - Spacing scale (4/8/16/24/32/48/64, touch target 44px, bottom nav 64px).
  - Color 60/30/10 (#f5f5f5 / #ffffff / #4f46e5).
  - Typography (3 размера 12/14/20px, 2 веса 400/600).
  - Heroicons inline SVG registry.

### Phase 26 mobile foundation
- `app/templates/mobile/base_mobile.html` — обёртка, bottom nav.
- Mobile authentication pattern via `get_current_user` dependency.

### ROADMAP and REQUIREMENTS
- `.planning/ROADMAP.md` §Phase 30 — goal, success criteria, REQ IDs.
- `.planning/REQUIREMENTS.md` §ERR-01, ERR-02, TSK-01, TSK-02 — подтверждение requirement scope.

### Yandex Webmaster API docs (researcher ответственность)
- `https://yandex.ru/dev/webmaster/doc/dg/concepts/about.html` — общая документация API v4.
- Specific error endpoints (researcher найдёт точные пути):
  - Indexing errors / excluded samples
  - Crawl errors / broken samples
  - Sanctions / host sanctions endpoint

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`yandex_webmaster_service.py`** — уже есть httpx AsyncClient + `_headers()` + `is_configured()` + `list_hosts()`. Phase 30 добавляет `fetch_indexing_errors()`, `fetch_crawl_errors()`, `fetch_sanctions()` в тот же файл.
- **`app/models/task.py` SeoTask** — reused для ТЗ на ошибку (с новым task_type + source_error_id) и для быстрых задач (с auto-filled полями).
- **`app/services/mobile_reports_service.py`** (Phase 29) — helpers для Redis + Client CRM select частично reused в `mobile_brief_service` для TSK-02.
- **`app/routers/mobile.py`** (Phase 29) — Phase 30 добавляет endpoints append к существующему роутеру.
- **`app/tasks/suggest_tasks.py`** — reference для Celery task pattern (retry=3, notify() on completion, on_failure handler).
- **Client CRM модель** — уже используется в Phase 29 mobile reports, reuse для TSK-02 recipient select.

### Established Patterns
- **HTMX polling** (Phase 29): `hx-trigger="every 3s"` с остановкой в done/error ветках (Pitfall 3 Phase 29).
- **Redis binary mode** для bytes storage (Phase 29 Pitfall 1) — не применимо к Phase 30 (только text).
- **SQLAlchemy 2.0 async** с `AsyncSession = Depends(get_db)`, `await db.execute(stmt)` — стандартный паттерн.
- **Alembic migration** для DB schema changes — MUST для новой таблицы `yandex_errors` и расширения TaskType enum.
- **Loguru logging** — `logger.info/warning/error` в сервисах.
- **Celery retry=3** для external API calls (CLAUDE.md constraint).
- **`showToast()`** JS helper (Phase 28/29).

### Integration Points
- **`app/routers/mobile.py`** — все новые endpoints append сюда:
  - `GET /m/errors`
  - `POST /m/errors/sync`
  - `GET /m/errors/sync/status/{task_id}`
  - `GET /m/errors/{error_id}/brief/form`
  - `POST /m/errors/{error_id}/brief`
  - `GET /m/tasks/new` (+ ?mode=task|brief)
  - `GET /m/tasks/new/form?mode=brief` (HTMX swap partial)
  - `POST /m/tasks/new` (handles both modes)
- **`app/celery_app.py`** — новый module import: `app.tasks.yandex_errors_tasks` (contains `sync_yandex_errors` task).
- **`app/templates/mobile/`** — новые поддиректории:
  - `errors/index.html`, `errors/section.html`, `errors/partials/brief_form.html`, `errors/partials/brief_result.html`
  - `tasks/new.html`, `tasks/partials/task_form.html`, `tasks/partials/brief_form.html`
- **`app/templates/briefs/copywriter_brief.txt.j2`** — новый template для TSK-02 rendering.
- **Navigation / bottom nav** — добавляем ссылку на `/m/errors` и `/m/tasks/new` в `base_mobile.html`. Planner решит структуру bottom nav для v4.0 (может нужно переделать с учётом reports/tools/errors/tasks).

</code_context>

<specifics>
## Specific Ideas

- **"Хост не привязан"** состояние на `/m/errors` — когда Site.domain не найден в Webmaster hosts. Пользователь видит понятный call-to-action, не generic error.
- **Title auto-fill `text[:80]`** для TSK-01 — UX оптимизация чтобы не заставлять писать отдельный title.
- **Mode toggle persisted в query-param** — `/m/tasks/new?mode=brief` shareable для Telegram sharing.
- **Soft-close resolved errors** — при re-sync ошибка которая больше не возвращается API, автоматически помечается `status='resolved'`. Это даёт historical track.
- **Text brief без Redis token** — если rendered text <4000 chars, отправляется как inline Telegram message. Attachment только для длинных brief (>4000 chars, как `.txt`).
- **TaskType enum расширение через Alembic** — Postgres enum ALTER требует specific syntax (`ALTER TYPE ... ADD VALUE 'new_value'`), planner должен это учесть.

</specifics>

<deferred>
## Deferred Ideas

- **Yandex Metrika errors** — текст "Метрики" в goal ROADMAP декларирует намерение, но API не даёт готовых error endpoints. Defer до backlog-фазы "Metrika error detection via custom goals/segments".
- **Celery Beat auto-schedule** для `sync_yandex_errors` — Phase 30 только manual refresh. Auto-schedule defer до отдельной фазы "Background sync jobs".
- **Новое поле `Site.yandex_host_id`** + UI привязки в desktop settings — domain matching достаточно для MVP.
- **Отдельная модель `Brief`** / таблица `briefs` — SeoTask + TaskType enum достаточно.
- **Отдельная модель `QuickTask`** — auto-fill SeoTask полей достаточно.
- **Celery brief-tool reuse** для TSK-02 — это другой flow (crawl+analysis vs manual+template). Defer идею слияния.
- **Desktop `/ui/errors`** — Phase 30 = mobile only. Desktop error view — отдельная фаза.
- **Assignee field** в quick task — UI говорит только text+priority+project. Defer.
- **Bulk error actions** (ignore/resolve multiple) — single-row only в MVP.
- **Multi-site aggregated errors view** — per-site dropdown only.
- **Error filtering/search** внутри секции — top-5 + "Показать все" без фильтров.
- **PDF rendering для copywriter brief** — text достаточно.
- **Project→Site auto-resolution magic** — 422 блок если Project.site_id is null.
- **Error notifications** (Telegram alert при новых ошибках после sync) — defer.
- **"Ignore" и "Resolve" buttons** в UI для ручного управления error статусом — defer (только auto-close при sync).
- **History / audit log изменений error status** — defer.

### Reviewed Todos (not folded)

- **Fix position check ignores keyword engine preference** (`2026-04-02-fix-position-check-ignores-keyword-engine-preference.md`) — matched на keyword "tasks", но это bug position-check (Phase 28 domain), не Phase 30 scope. Остаётся в backlog.
- **Proxy management, XMLProxy integration and health checker** (`2026-04-02-proxy-management-xmlproxy-integration-and-health-checker.md`) — matched на keyword "tasks", но относится к crawler/proxy infrastructure, не Phase 30 scope. Остаётся в backlog.

</deferred>

---

*Phase: 30-errors-quick-task*
*Context gathered: 2026-04-11*
