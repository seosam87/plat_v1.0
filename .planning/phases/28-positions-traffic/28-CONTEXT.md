# Phase 28: Positions & Traffic - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Mobile pages for position checking (`/m/positions`) and traffic comparison (`/m/traffic`). User can launch a position check, see results with trends, compare traffic between two periods, and create tasks for dropped keywords/pages — all from mobile.

**Delivers:**
- `/m/positions` — position list with card layout, site/period filters, tab for dropped keywords
- `/m/positions` check trigger — HTMX POST to start Celery check, polling progress, "show results" button on completion
- `/m/traffic` — Metrika-based traffic comparison with preset periods, summary + per-page breakdown
- Task creation from both screens — reuse `task_form.html` partial from Phase 27

**Out of scope:**
- Position schedule management (desktop only)
- Server log analysis for traffic (Metrika only)
- Custom date picker for traffic periods (presets only)
- Position history charts/graphs (list view only)

</domain>

<decisions>
## Implementation Decisions

### Position List Display
- **D-01:** Card layout for each keyword — phrase, position, colored delta (+green/-red), engine, check date. Pattern consistent with digest blocks from Phase 27.
- **D-02:** Filters: site select + period (7d/30d/all). Sort by delta magnitude by default. Minimal mobile UI.
- **D-03:** Two tabs at top: "Все" (all keywords) and "Просевшие" (delta < 0 only). Dropped tab shows task creation button per keyword.

### Position Check Launch
- **D-04:** HTMX-polling for progress — button "Запустить проверку" → POST triggers Celery `check_positions(site_id)` → toast "Проверка запущена" → progress block polls via `hx-trigger='every 3s'` showing "Проверено X из Y ключей".
- **D-05:** On completion: polling detects status=done → shows "Проверка завершена" with button "Показать результаты" that reloads the position list via hx-get swap. NOT auto-replace.

### Traffic Comparison
- **D-06:** Data source: Yandex.Metrika API only. Sites without `metrika_token` show empty state "Метрика не подключена".
- **D-07:** Period selection: presets only — "Эта неделя vs прошлая", "Этот месяц vs прошлый", "30 дней vs 30 дней". No custom date picker.
- **D-08:** Display: summary card at top (total traffic period 1 → period 2, delta %), then per-page list sorted by delta (biggest drops first). Red for drops, green for growth. Each page row is tappable for task creation.

### Task Creation
- **D-09:** Reuse `task_form.html` partial from Phase 27. hx-get loads form with `prefilled_title` (keyword phrase or page URL). Same save/cancel flow, same toast. Unified pattern across all mobile pages.

### Claude's Discretion
- Service layer approach — new mobile-specific service or extend existing `position_service.py` / `traffic_analysis_service.py`
- Metrika API query structure — how to fetch per-page traffic for comparison
- Progress endpoint design — how to expose Celery task progress for HTMX polling

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Position System
- `app/services/position_service.py` — 11 async functions: get_latest_positions, get_position_history, get_lost_gained_keywords, compare_positions_by_date, get_position_distribution, etc.
- `app/tasks/position_tasks.py` — Celery `check_positions(site_id)` with XMLProxy/DataForSEO/SERP backends
- `app/routers/positions.py` — Desktop endpoints: trigger_position_check, get_active_task, get_task_status (SSE progress)
- `app/models/position.py` — `KeywordPosition` (partitioned by `checked_at`), `Keyword`

### Traffic System
- `app/services/traffic_analysis_service.py` — classify_visit, detect_anomalies, analyze_traffic_sources (works with logs/Metrika)
- `app/routers/traffic_analysis.py` — Desktop: dashboard, analyze_metrika, sessions
- `app/services/analytics_service.py` — Analytics queries

### Mobile Foundation
- `app/templates/base_mobile.html` — Mobile base template with bottom nav, HTMX 2.0.3, showToast()
- `app/routers/mobile.py` — Existing mobile router with /m/digest, /m/health/{site_id} routes
- `app/templates/mobile/partials/task_form.html` — Reusable inline task creation form (Phase 27)
- `app/services/mobile_digest_service.py` — Phase 27 async service pattern reference

### Models
- `app/models/keyword.py` — `Keyword` model (phrase, site_id)
- `app/models/site.py` — `Site` model (metrika_token field for Metrika availability check)
- `app/models/task.py` — `SeoTask` model (TaskType.manual for user-created tasks)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `task_form.html` partial — inline task creation, works with any `site_id` + `prefilled_title`
- `mobile_digest_service.py` — async service pattern with partition-safe queries, Russian date formatting
- `position_service.py` — full suite of position queries (latest, history, lost/gained, compare by date)
- `check_positions` Celery task — already handles XMLProxy/DataForSEO/SERP, emits progress via SSE

### Established Patterns
- Mobile routes in single `mobile.py` router, all use `Depends(get_current_user)` + `Depends(get_db)`
- Templates extend `base_mobile.html`, set `active_tab` for bottom nav
- HTMX 2.0 double-colon syntax (`hx-on::after-request`), `hx-disabled-elt="this"` for double-tap prevention
- Toast feedback via `showToast(msg, type)` global JS function
- 44px min touch targets on all interactive elements

### Integration Points
- Bottom nav tab "Позиции" → `/m/positions` (needs to activate this tab)
- Health card links to `/m/health/{site_id}` → could link to `/m/positions?site_id={id}` from position metric
- Digest deep links currently go to `/ui/sites/{id}/positions` (desktop) → can update to `/m/positions?site_id={id}` once mobile page exists

</code_context>

<specifics>
## Specific Ideas

- Progress shows "Проверено X из Y ключей" during check
- Completion shows button "Показать результаты" (not auto-refresh)
- Traffic presets: "Эта неделя vs прошлая", "Этот месяц vs прошлый", "30 дней vs 30 дней"
- Dropped keywords tab separate from "Все" with direct task creation access

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 28-positions-traffic*
*Context gathered: 2026-04-10*
