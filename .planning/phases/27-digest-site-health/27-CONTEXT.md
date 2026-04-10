# Phase 27: Digest & Site Health - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Mobile digest page (`/m/digest`) showing a morning summary across all projects, and site health card (`/m/health/{site_id}`) with operational metrics and actionable buttons. User can navigate to problems with one tap and take action (start crawl, create task) without leaving mobile UI.

**Delivers:**
- `/m/digest` — morning summary with 4 blocks (positions, crawler errors, alerts, overdue tasks)
- `/m/health/{site_id}` — site health card with 6 operational metrics
- Deep link navigation from digest items to relevant pages
- Actions: start crawl + create task from health card, confirmed with toast

**Out of scope:**
- Push notifications / Telegram digest replacement — existing Telegram digest stays as-is
- Dedicated mobile pages for positions, errors, tasks — Phases 28–31
- Weekly digest UI — this is morning/operational digest only

</domain>

<decisions>
## Implementation Decisions

### Digest Content
- **D-01:** Block order: Позиции → Ошибки краулера → Алерты → Просроченные задачи. SEO-critical first, operational second.
- **D-02:** TOP-5 items per block. Compact, fits one screen without excessive scrolling.

### Digest Data Source
- **D-03:** Claude's Discretion — choose between new `mobile_digest_service.py`, extending `morning_digest_service.py`, or another approach. Existing services to consider: `morning_digest_service.py` (Telegram HTML), `digest_service.py` (weekly/redbeat), `site_service.py`, `change_monitoring_service.py`.

### Digest Navigation
- **D-04:** Claude's Discretion — decide deep link strategy for taps from digest items. Consider that `/m/positions`, `/m/errors` etc. don't exist yet (Phases 28–31). Options include: desktop pages, `/m/` placeholders, or smart fallback (mobile if exists, else desktop).

### Site Health Card
- **D-05:** 6 metric blocks: (1) Доступность сайта (последний HTTP-статус), (2) Свежие ошибки краулера (количество), (3) Статус последнего краулинга (дата + результат), (4) Резкие изменения позиций (дельта за 7 дней), (5) Просроченные задачи (количество), (6) Статус индексации (данные GSC/Yandex если есть).
- **D-06:** Visual: простой вертикальный список с иконками статуса (цветные индикаторы по состоянию: зелёный/жёлтый/красный).

### Health Card Actions
- **D-07:** Claude's Discretion — choose how to trigger crawl start and task creation (HTMX inline, fetch API, or hybrid). Both actions confirmed with toast notification.
- **D-08:** Task creation flow: мини-форма — нажатие раскрывает 2-3 поля inline (текст задачи предзаполнен из ошибки, приоритет, возможно проект). Кнопка "Сохранить" отправляет и показывает тост.

### Claude's Discretion
- D-03: Digest data source architecture
- D-04: Deep link strategy from digest
- D-07: API approach for health card actions (HTMX vs fetch)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Digest & Health Services
- `app/services/morning_digest_service.py` — current Telegram morning digest builder (positions + tasks per project)
- `app/services/digest_service.py` — weekly digest with redbeat scheduling, `build_digest()` returns structured dict
- `app/services/site_service.py:90` — `compute_site_health()` returns 7-step setup completeness snapshot
- `app/services/change_monitoring_service.py` — alert rules, change detection, Telegram dispatch

### Models & Data
- `app/models/task.py` — `SeoTask` with `due_date`, `TaskStatus` (for overdue task queries)
- `app/models/crawl.py` — crawl jobs, errors (for crawler error counts)
- `app/models/position.py` — keyword positions (for position delta calculation)

### Mobile Foundation (Phase 26)
- `app/templates/base_mobile.html` — mobile base template with bottom nav, toast support
- `app/routers/mobile.py` — existing `/m/` router with `Depends(get_current_user)`
- `app/main.py` — UIAuthMiddleware protecting `/m/` paths

### Project Context
- `.planning/REQUIREMENTS.md` — DIG-01, DIG-02, HLT-01, HLT-02 acceptance criteria
- `.planning/ROADMAP.md` section Phase 27 — success criteria and dependencies
- `.planning/phases/26-mobile-foundation/26-CONTEXT.md` — Phase 26 decisions (mobile patterns)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `morning_digest_service.py::build_morning_digest()` — queries projects, positions, tasks; returns Telegram HTML. Data gathering logic reusable, format not.
- `digest_service.py::build_digest()` — returns structured dict with position changes, tasks, period. Good data model reference.
- `compute_site_health()` — 7 indexed queries, returns `SiteHealth` dataclass. Setup-focused, needs extension for operational metrics.
- `change_monitoring_service.py` — `ChangeAlert` model, alert rules, dispatch. Source for alerts block in digest.
- `base_mobile.html` — has toast container (from Phase 26), HTMX loaded, active-tab logic for bottom nav.

### Established Patterns
- Mobile routes use plain `Jinja2Templates` (not nav-aware wrapper) — per Phase 26 decision
- HTMX 2.0.3 for partial updates, Tailwind via CDN
- Celery tasks for long operations (crawl, position checks) — already have retry=3
- Toast notifications via HTMX swap-oob pattern (existing in desktop)

### Integration Points
- New mobile templates in `app/templates/mobile/` (digest.html, health.html)
- New endpoints in `app/routers/mobile.py` (or separate router — Claude's choice)
- Digest service needs async version for FastAPI handlers (existing `build_morning_digest` is sync/Celery)
- Health card needs new query service combining crawl status + position delta + task overdue + indexation

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 27-digest-site-health*
*Context gathered: 2026-04-10*
