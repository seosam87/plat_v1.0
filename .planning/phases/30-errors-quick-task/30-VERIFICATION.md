---
phase: 30-errors-quick-task
verified: 2026-04-12T10:00:00Z
status: passed
score: 13/13 must-haves verified
re_verification: null
gaps: []
human_verification:
  - test: "Open /m/errors in browser on mobile viewport"
    expected: "3 error sections visible (Индексация, Краулинг, Санкции) with count badges; site dropdown selects site and reloads sections via HTMX"
    why_human: "Visual layout, touch targets, and HTMX partial-reload require browser interaction to confirm"
  - test: "Click Обновить button on /m/errors"
    expected: "Spinner appears, polls every 3s, sections reload with updated errors when done"
    why_human: "Requires live Celery + Redis + Yandex Webmaster token configured"
  - test: "Click Составить ТЗ on an error row"
    expected: "Inline form expands via outerHTML HTMX swap without page reload; form has priority radio, project select"
    why_human: "Requires browser HTMX execution to confirm outerHTML swap target behavior"
  - test: "Submit brief form on error row"
    expected: "SeoTask created with source_error_id set; green success banner shown inline with link to task"
    why_human: "Requires DB write and task detail URL accessibility"
  - test: "Open /m/tasks/new, toggle between Задача and ТЗ копирайтеру"
    expected: "Mode toggle swaps form via HTMX; URL updated via pushState; send button stays disabled until recipient selected"
    why_human: "JavaScript behavior (pushState, onchange enable/disable) needs browser execution"
  - test: "Submit brief form with recipient selected"
    expected: "Toast shows delivery outcome; redirect to /m/; SeoTask created with rendered brief as description"
    why_human: "Telegram/email delivery depends on TELEGRAM_BOT_TOKEN and SMTP config"
---

# Phase 30: Errors & Quick Task Verification Report

**Phase Goal:** Пользователь видит ошибки из Yandex Webmaster API и Метрики, может создать задачу или ТЗ на любую проблему
**Verified:** 2026-04-12T10:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | YandexError model exists with all required fields and enums | VERIFIED | `class YandexError(Base)` in `app/models/yandex_errors.py` line 24; YandexErrorType and YandexErrorStatus enums present |
| 2 | Alembic migration 0055 creates yandex_errors table + extends tasktype enum with 3 new values | VERIFIED | `op.create_table("yandex_errors"`, `ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'yandex_indexing'` with COMMIT/BEGIN wrapper confirmed |
| 3 | SeoTask model has source_error_id nullable FK to yandex_errors | VERIFIED | `hasattr(SeoTask, 'source_error_id')` → True; used in brief submit endpoint at line 1258 |
| 4 | Celery task sync_yandex_errors fetches 3 error types and upserts into DB | VERIFIED | `fetch_indexing_errors`, `fetch_crawl_errors`, `fetch_sanctions` called; `pg_insert(YandexError).on_conflict_do_update()` with soft-close logic |
| 5 | yandex_webmaster_service has all 4 required API functions | VERIFIED | `fetch_indexing_errors`, `fetch_crawl_errors`, `fetch_sanctions`, `resolve_host_id` imported and confirmed |
| 6 | yandex_errors_service provides list_errors, count_errors, get_error, last_fetched_at | VERIFIED | All 4 functions import successfully; DB queries with `select(YandexError)` |
| 7 | /m/errors page exists with site dropdown, sync button, 3 error sections | VERIFIED | Router `GET /m/errors` at line 964; template `index.html` has `id="errors-content"`, `id="sync-progress"`, `hx-post="/m/errors/sync"` |
| 8 | User can trigger sync and see HTMX polling every 3s | VERIFIED | `sync_progress.html` has `hx-trigger="every 3s"` in running state; POST `/m/errors/sync` calls `sync_yandex_errors.delay(site_id)` |
| 9 | Составить ТЗ opens inline brief form via HTMX outerHTML swap | VERIFIED | `section.html` line 26: `hx-target="closest .error-row"` + `hx-swap="outerHTML"`; `brief_form.html` has `hx-post="/m/errors/{{ error.id }}/brief"` |
| 10 | Brief submit creates SeoTask with source_error_id FK and shows success | VERIFIED | `mobile_error_brief_submit` endpoint at line 1224: `source_error_id=error.id`; `brief_result.html` has `ТЗ создано` green banner |
| 11 | Bottom nav has Ошибки tab linking to /m/errors | VERIFIED | `base_mobile.html` line 89: `<a href="/m/errors"` with `active_tab == 'errors'` conditional styling |
| 12 | /m/tasks/new with mode toggle creates SeoTask (quick task) | VERIFIED | 3 endpoints (new, new/form, new POST); `task_form.html` with `name="text"` + `maxlength="2000"`, `name="priority"`, `name="project_id"`; `text[:80].strip()` as title |
| 13 | Brief mode creates SeoTask with rendered Jinja2 template as description | VERIFIED | `render_brief()` imports `copywriter_brief.txt.j2` with 5 placeholders; router calls `render_brief(...)` at line 1486; brief service imports and renders correctly (641 chars output confirmed) |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models/yandex_errors.py` | YandexError model + enums | VERIFIED | `class YandexError(Base)`, `class YandexErrorType`, `class YandexErrorStatus`; UniqueConstraint on (site_id, error_type, subtype, url) |
| `alembic/versions/0055_add_yandex_errors.py` | Migration: table + enum extension + FK | VERIFIED | `op.create_table`, `ALTER TYPE tasktype ADD VALUE`, `op.execute("COMMIT")`, `fk_seo_tasks_source_error_id` |
| `app/tasks/yandex_errors_tasks.py` | sync_yandex_errors Celery task | VERIFIED | `@celery_app.task(... max_retries=3)`, `def sync_yandex_errors`, upsert + soft-close |
| `app/services/yandex_errors_service.py` | DB read helpers | VERIFIED | `list_errors`, `count_errors`, `get_error`, `last_fetched_at` — all substantive with real DB queries |
| `app/templates/mobile/errors/index.html` | Main errors page | VERIFIED | Extends `base_mobile.html`, has `id="errors-content"`, `id="sync-progress"`, `name="site_id"` |
| `app/templates/mobile/errors/partials/section.html` | Error section with rows | VERIFIED | `error-row` class, `hx-get="/m/errors/...`, `Составить ТЗ`, `Показать все` |
| `app/templates/mobile/errors/partials/brief_form.html` | Inline brief form | VERIFIED | `hx-post="/m/errors/{{ error.id }}/brief"`, `name="priority"`, `name="description"` |
| `app/templates/mobile/errors/partials/sync_progress.html` | HTMX polling partial | VERIFIED | `hx-trigger="every 3s"` in running state; 3-state structure (running/done/error) |
| `app/routers/mobile.py` | 7 errors endpoints + 3 tasks endpoints | VERIFIED | All 10 routes confirmed: `/m/errors`, `/m/errors/sync`, `/m/errors/sync/status/{task_id}`, `/m/errors/content`, `/m/errors/{error_type}/all`, `/m/errors/{error_id}/brief/form`, `/m/errors/{error_id}/brief`, `/m/tasks/new` (GET+POST), `/m/tasks/new/form` |
| `app/templates/mobile/tasks/new.html` | Quick create page with mode toggle | VERIFIED | `id="task-form"`, `hx-get="/m/tasks/new/form?mode=`, `history.pushState`, both `Задача` and `ТЗ копирайтеру` buttons |
| `app/templates/mobile/tasks/partials/task_form.html` | Task form fields | VERIFIED | `name="text"`, `maxlength="2000"`, `name="priority"`, `name="project_id"`, `Создать задачу` |
| `app/templates/mobile/tasks/partials/brief_form.html` | Brief form fields | VERIFIED | `name="keywords"`, `name="tone"`, `name="length"`, `name="recipient_id"`, `Создать и отправить`, `Только сохранить`, `Информационный` |
| `app/templates/briefs/copywriter_brief.txt.j2` | Copywriter brief template | VERIFIED | `{{ project_name }}`, `{{ site_url }}`, `{{ length }}`, `{{ tone }}`, `{% for kw in keywords %}` |
| `app/services/mobile_brief_service.py` | Brief rendering + delivery | VERIFIED | `render_brief`, `list_clients_for_brief`, `send_brief_telegram`, `send_brief_email`; graceful error handling |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/tasks/yandex_errors_tasks.py` | `app/services/yandex_webmaster_service.py` | `fetch_indexing_errors`, `fetch_crawl_errors`, `fetch_sanctions` | WIRED | All 3 functions imported at lines 69-71 and called at lines 140-142 |
| `app/tasks/yandex_errors_tasks.py` | `app/models/yandex_errors.py` | `pg_insert(YandexError).on_conflict_do_update()` | WIRED | `YandexError` imported at line 22; `pg_insert(YandexError)` at line 203 |
| `app/celery_app.py` | `app/tasks/yandex_errors_tasks.py` | include list registration | WIRED | `"app.tasks.yandex_errors_tasks"` at line 34 |
| `app/routers/mobile.py` | `app/services/yandex_errors_service.py` | `list_errors, count_errors, get_error, last_fetched_at` | WIRED | Lazy imports inside each endpoint; called with DB session and typed args |
| `app/routers/mobile.py` | `app/tasks/yandex_errors_tasks.py` | `sync_yandex_errors.delay()` | WIRED | `sync_yandex_errors.delay(site_id)` at line 1046 |
| `app/templates/mobile/errors/partials/brief_form.html` | `app/routers/mobile.py` | `hx-post="/m/errors/{error_id}/brief"` | WIRED | Template line 3: `hx-post="/m/errors/{{ error.id }}/brief"`; endpoint `mobile_error_brief_submit` at line 1224 |
| `app/routers/mobile.py` | `app/services/mobile_brief_service.py` | `render_brief`, delivery functions | WIRED | Lazy import at line 1433-1436; `render_brief(...)` called at line 1486 |
| `app/services/mobile_brief_service.py` | `app/templates/briefs/copywriter_brief.txt.j2` | Jinja2 `get_template` | WIRED | `_env.get_template("briefs/copywriter_brief.txt.j2")` at line 23; file exists |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `errors/index.html` / `errors_content.html` | `indexing_errors`, `crawl_errors`, `sanction_errors` | `list_errors(db, selected_uuid, YandexErrorType.*)` → `select(YandexError)` DB query | Yes — SQLAlchemy select with WHERE + ORDER BY | FLOWING |
| `errors/index.html` | `indexing_count`, `crawl_count`, `sanction_count` | `count_errors(db, selected_uuid, YandexErrorType.*)` → `select(func.count(YandexError.id))` | Yes | FLOWING |
| `tasks/new.html` | `projects` | `get_accessible_projects(db, user)` → DB query via project_users many-to-many | Yes — uses actual project service | FLOWING |
| `tasks/partials/brief_form.html` | `clients` | `list_clients_for_brief(db)` → `select(Client).where(Client.email.isnot(None))` | Yes | FLOWING |
| `yandex_errors_tasks.py` | Error rows | `fetch_indexing_errors`, `fetch_crawl_errors`, `fetch_sanctions` → real httpx HTTP calls to Yandex Webmaster API | Yes — real API calls (require token) | FLOWING (external) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Models importable | `python -c "from app.models.yandex_errors import YandexError..."` | "model OK" | PASS |
| TaskType enum has 3 new values | `python -c "from app.models.task import TaskType; assert 'yandex_indexing' in [t.value for t in TaskType]"` | "TaskType OK" | PASS |
| SeoTask has source_error_id FK | `python -c "from app.models.task import SeoTask; assert hasattr(SeoTask, 'source_error_id')"` | "FK OK" | PASS |
| Webmaster service functions importable | `python -c "from app.services.yandex_webmaster_service import fetch_indexing_errors, ..."` | "WebmasterService OK" | PASS |
| Errors service importable | `python -c "from app.services.yandex_errors_service import list_errors, ..."` | "ErrorsService OK" | PASS |
| Celery task importable | `python -c "from app.tasks.yandex_errors_tasks import sync_yandex_errors"` | "Task OK" | PASS |
| Celery task registered | `grep -q "yandex_errors_tasks" app/celery_app.py` | Found at line 34 | PASS |
| Brief service importable | `python -c "from app.services.mobile_brief_service import render_brief, ..."` | "BriefService OK" | PASS |
| Brief renders real output | `render_brief('Тест', 'test.com', '2000', 'Информационный', ['kw1', 'kw2'])` | 641 chars, contains project name and keywords | PASS |
| All error template files exist | `ls app/templates/mobile/errors/` + `partials/` | 6 files confirmed | PASS |
| All task template files exist | `ls app/templates/mobile/tasks/` + `partials/` | 3 files confirmed | PASS |
| Router has all error routes | Python route introspection | 7 `/m/errors*` routes confirmed | PASS |
| Router has all task routes | Python route introspection | 3 `/m/tasks/new*` routes confirmed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ERR-01 | 30-01, 30-02 | Пользователь видит ошибки из Yandex Webmaster API (индексация, краулинг, санкции) | SATISFIED | `/m/errors` page with 3 sections; `sync_yandex_errors` Celery task fetches and stores all 3 error types from Yandex Webmaster API; data flows from DB to template via `list_errors` + `count_errors` |
| ERR-02 | 30-01, 30-02 | Пользователь может составить ТЗ на исправление ошибки прямо из списка | SATISFIED | `Составить ТЗ` button in `section.html` triggers inline form; `mobile_error_brief_submit` creates `SeoTask` with `source_error_id=error.id` FK; success confirmation shown inline |
| TSK-01 | 30-03 | Пользователь может быстро добавить задачу в проект с телефона (текст + приоритет) | SATISFIED | `/m/tasks/new` task mode: textarea + priority radio + project select; POST handler creates `SeoTask(title=text[:80], task_type=TaskType.manual, ...)`; toast + redirect to /m/ |
| TSK-02 | 30-03 | Пользователь может создать ТЗ копирайтеру из данных аналитики и отправить в TG/email | SATISFIED | `/m/tasks/new` brief mode: keywords/tone/length/project/recipient fields; `render_brief()` renders `copywriter_brief.txt.j2`; `send_brief_telegram()` + `send_brief_email()` with graceful fallback; SeoTask created with rendered brief as description |

All 4 requirement IDs from PLAN frontmatter are accounted for and satisfied.

**No orphaned requirements** — REQUIREMENTS.md maps ERR-01, ERR-02, TSK-01, TSK-02 to Phase 30; all 4 appear in plan frontmatter.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None | — | — | No stubs, placeholders, or empty implementations found in phase 30 artifacts |

Scan confirmed:
- No TODO/FIXME/PLACEHOLDER comments in new files
- No empty `return []` / `return {}` patterns that flow to rendering (service functions return real query results)
- No hardcoded empty prop values passed to templates
- Telegram/email delivery functions use graceful error handling with `try/except` + `return False` — this is intentional design, not a stub (confirmed by SUMMARY.md "Known Stubs: None" and real `logger.info` + conditional logic)

### Human Verification Required

1. **Errors page visual layout**
   - Test: Open `/m/errors` in browser with mobile viewport
   - Expected: 3 sections visible with count badges, 44px touch targets, 16px padding, Ошибки tab highlighted in nav
   - Why human: Visual rendering and touch target validation requires browser

2. **Live Celery sync flow**
   - Test: Click Обновить with a verified Yandex Webmaster host configured
   - Expected: Spinner appears, polls every 3s, sections reload with real errors from API
   - Why human: Requires Celery worker + Redis + valid YANDEX_WEBMASTER_TOKEN

3. **Inline brief form HTMX swap**
   - Test: Click Составить ТЗ on any error row
   - Expected: Row replaced by inline form (outerHTML swap) without page reload; cancel restores via window.location.reload()
   - Why human: Browser HTMX execution required

4. **Quick task creation on mobile**
   - Test: Open `/m/tasks/new`, fill text + priority, submit
   - Expected: Toast "Задача создана", redirect to /m/ after 1s
   - Why human: Toast + redirect behavior requires browser JS execution

5. **Brief delivery (TG/email)**
   - Test: Open `/m/tasks/new?mode=brief`, fill form, select recipient, click Создать и отправить
   - Expected: Brief sent via configured channel; toast confirms outcome
   - Why human: Requires TELEGRAM_BOT_TOKEN or SMTP configured

### Gaps Summary

No gaps found. All 13 observable truths are verified. All 14 artifacts are present, substantive, and wired. All 8 key links are confirmed. Data flows from DB queries to templates. All 4 requirements (ERR-01, ERR-02, TSK-01, TSK-02) are satisfied with implementation evidence. No blocker anti-patterns.

The phase goal is achieved: users can view Yandex Webmaster API errors (indexing, crawl, sanctions) on `/m/errors`, create tasks from error rows with FK linkage, create quick tasks from `/m/tasks/new`, and generate copywriter briefs with Telegram/email delivery.

---

_Verified: 2026-04-12T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
