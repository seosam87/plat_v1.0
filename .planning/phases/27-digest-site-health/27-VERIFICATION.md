---
phase: 27-digest-site-health
verified: 2026-04-10T19:00:00Z
status: passed
score: 8/8 must-haves verified
---

# Phase 27: Digest & Site Health Verification Report

**Phase Goal:** Пользователь видит утреннюю сводку и карточку здоровья сайта, может перейти к проблеме одним тапом
**Verified:** 2026-04-10T19:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User opens /m/digest and sees 4 blocks: position changes, crawler errors, alerts, overdue tasks | VERIFIED | `digest.html` renders 4 sections with headings: "Изменения позиций", "Ошибки краулера", "Алерты", "Просроченные задачи". Route `GET /m/digest` confirmed in router. |
| 2 | Each block shows up to 5 items with site name | VERIFIED | `build_mobile_digest()` calls each query with `limit=5`; all query dicts include `site_name` key; template renders `item.site_name` in each block. |
| 3 | Each digest item is a tappable link leading to the relevant desktop page | VERIFIED | All `<a>` tags use `href="/ui/..."` deep links: `/ui/sites/{id}/positions`, `/ui/crawls/{id}`, `/ui/sites/{id}/monitoring`, `/ui/tasks?site_id={id}`. Touch targets: `min-h-[44px]` on all rows. |
| 4 | Empty blocks show descriptive placeholder text instead of blank space | VERIFIED | Each section has `{% if items %}...{% else %}<p>` with correct empty texts: "Нет данных за последние 7 дней", "Нет новых ошибок", "Нет активных алертов", "Нет просроченных задач". Global empty state "Дайджест пуст" also present. |
| 5 | User opens /m/health/{site_id} and sees 6 operational metrics with color indicators | VERIFIED | `health.html` iterates `metrics` list; `_format_health_metrics()` produces 6 items with labels matching UI-SPEC: "Доступность сайта", "Ошибки краулера", "Последний краулинг", "Изменения позиций (7 дн.)", "Просроченные задачи", "Статус индексации". Status dots render green/yellow/red/grey. |
| 6 | User taps 'Запустить краулинг' and gets a success toast, Celery task starts | VERIFIED | Button with `hx-post="/m/health/{{ site.id }}/crawl"` + `hx-on::after-request="if(event.detail.successful) showToast('Краулинг запущен', 'success')"`. Route calls `crawl_site_task.delay(str(site_id))`, returns 202. `hx-disabled-elt="this"` prevents double-tap. |
| 7 | User taps 'Создать задачу', inline form expands with pre-filled title, submits and gets toast | VERIFIED | Button with `hx-get="/m/health/{{ site.id }}/task-form"` loads `task_form.html` into `#task-form-slot`. Form has `hx-post="/m/health/{{ site_id }}/tasks"` with `hx-on::after-request` calling `showToast('Задача создана', 'success')`. Route creates `SeoTask` with `TaskType.manual`, returns 201. |
| 8 | Each metric shows green/yellow/red/grey dot based on operational thresholds | VERIFIED | `get_mobile_site_health()` computes color per metric using threshold logic (0=green, 1-5=yellow, >5=red for errors; >7 days=yellow for crawl age; etc.). `_format_health_metrics()` maps `color` to `status` for template. Template renders conditional CSS classes. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/mobile_digest_service.py` | Async digest + health queries | VERIFIED | 355 lines, 6 async functions, all use `AsyncSession`, no sync Session import, partition-safe `checked_at` filters present (6 occurrences), loguru logging throughout |
| `app/templates/mobile/digest.html` | Digest page template | VERIFIED | 116 lines, extends `base_mobile.html`, 4 sections in correct order, deep links to `/ui/`, empty states, chevron SVG icons, aria-labels on position rows |
| `app/routers/mobile.py` | /m/digest and health routes | VERIFIED | 282 lines, 7 route handlers (index, digest, health, crawl, task-form, create-task, plus auth). All protected endpoints use `Depends(get_current_user)` (7 usages). |
| `app/templates/mobile/health.html` | Health card page template | VERIFIED | 57 lines, extends `base_mobile.html`, `active_tab='sites'`, metric loop with status dots, crawl button with HTMX, task button with HTMX, `#task-form-slot` div |
| `app/templates/mobile/partials/task_form.html` | Inline task creation form | VERIFIED | 37 lines, no `extends` (fragment), `hx-post` to `/m/health/{{ site_id }}/tasks`, prefilled title, priority select (p1-p4), save/cancel buttons, toast on success |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `mobile.py` | `mobile_digest_service.py` | `build_mobile_digest(db)` | WIRED | Called in both `mobile_index` and `mobile_digest` handlers |
| `mobile.py` | `mobile_digest_service.py` | `get_mobile_site_health(db, site_id)` | WIRED | Called in `mobile_health` handler |
| `mobile.py` | `crawl_tasks.py` | `crawl_site_task.delay(str(site_id))` | WIRED | Called in `mobile_trigger_crawl`, passes string UUID as expected by Celery task |
| `digest.html` | Desktop pages | `href="/ui/..."` deep links | WIRED | 4 distinct deep link patterns: `/ui/sites/{id}/positions`, `/ui/crawls/{id}`, `/ui/sites/{id}/monitoring`, `/ui/tasks?site_id={id}` |
| `health.html` | `/m/health/{site_id}/crawl` | `hx-post` HTMX | WIRED | Button has `hx-post="/m/health/{{ site.id }}/crawl"` with `hx-swap="none"` |
| `health.html` | `/m/health/{site_id}/task-form` | `hx-get` HTMX | WIRED | Button has `hx-get="/m/health/{{ site.id }}/task-form"` targeting `#task-form-slot` |
| `task_form.html` | `/m/health/{site_id}/tasks` | `hx-post` form | WIRED | Form submits to `/m/health/{{ site_id }}/tasks` with title and priority fields |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `digest.html` | `position_changes`, `crawl_errors`, `alerts`, `overdue_tasks` | `build_mobile_digest()` -> 4 DB queries | Yes -- SQLAlchemy queries against KeywordPosition, Page, ChangeAlert, SeoTask with joins to Site | FLOWING |
| `health.html` | `metrics` | `get_mobile_site_health()` -> 6 DB queries | Yes -- queries CrawlJob, Page, KeywordPosition, SeoTask, Site tables with real aggregations | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Service importable | `python -c "from app.services.mobile_digest_service import build_mobile_digest, get_mobile_site_health"` | Confirmed via route imports | PASS |
| Router importable with all routes | Route listing via `router.routes` | 5 digest/health routes confirmed: GET /m/digest, GET /m/health/{site_id}, POST /m/health/{site_id}/crawl, GET /m/health/{site_id}/task-form, POST /m/health/{site_id}/tasks | PASS |
| No sync Session usage | `grep "from sqlalchemy.orm import Session"` on service file | No matches found | PASS |
| Partition-safe queries | `grep -c "checked_at"` in service | 6 occurrences covering both digest and health queries | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DIG-01 | 27-01 | Утренняя сводка: ТОП позиции, ошибки, алерты, задачи | SATISFIED | 4 blocks in digest.html, async queries in service, /m/digest route |
| DIG-02 | 27-01 | Переход к проблеме одним тапом | SATISFIED | All items are `<a>` links to `/ui/` desktop pages, min-h-[44px] touch targets |
| HLT-01 | 27-02 | Карточка здоровья: доступность, ошибки, краулинг, позиции | SATISFIED | 6 metrics with color indicators in health.html, data from get_mobile_site_health() |
| HLT-02 | 27-02 | Запуск краулинга или задача с карточки | SATISFIED | Crawl button triggers Celery task (202), task form creates SeoTask in DB (201), both confirm with toast |

No orphaned requirements -- REQUIREMENTS.md maps DIG-01, DIG-02, HLT-01, HLT-02 to Phase 27, all covered.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No anti-patterns detected |

No TODO/FIXME/PLACEHOLDER comments. No empty return stubs. No hardcoded empty data flowing to rendering. No console.log-only handlers.

### Human Verification Required

### 1. Digest Page Visual Layout

**Test:** Open `/m/digest` on a mobile device or responsive simulator with test data in the database
**Expected:** 4 blocks render in order with colored dots, chevron icons, and proper spacing. Items are tappable and lead to correct desktop pages.
**Why human:** Visual layout, touch interaction quality, and navigation flow require manual testing

### 2. Health Card Action Feedback

**Test:** Open `/m/health/{site_id}`, tap "Запустить краулинг", then tap "Создать задачу" and submit
**Expected:** Crawl button disables during request, shows green toast "Краулинг запущен". Task form expands inline, submits successfully, shows toast "Задача создана", form disappears.
**Why human:** Toast animations, button disable state, form expand/collapse UX require visual confirmation

### 3. Empty State Rendering

**Test:** Open `/m/digest` with a fresh database (no sites/data)
**Expected:** Global empty state "Дайджест пуст" with instruction text, no broken layout
**Why human:** Empty state visual quality needs manual check

### Gaps Summary

No gaps found. All 8 observable truths verified across both plans. All 4 requirement IDs (DIG-01, DIG-02, HLT-01, HLT-02) satisfied with implementation evidence. Service layer uses proper async patterns with partition-safe queries. Templates are wired to routes with real data flowing from database queries through service functions to Jinja2 rendering. HTMX actions (crawl trigger, task creation) are connected to backend endpoints with proper toast feedback.

---

_Verified: 2026-04-10T19:00:00Z_
_Verifier: Claude (gsd-verifier)_
