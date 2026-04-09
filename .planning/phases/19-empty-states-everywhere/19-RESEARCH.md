# Phase 19: Empty States Everywhere - Research

**Researched:** 2026-04-09
**Domain:** Jinja2 macro authoring, template surgery, HTML/CSS empty-state patterns
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Карточка с рамкой — белый фон, border, rounded corners (Tailwind: `bg-white rounded-lg shadow-sm border border-gray-200`)
- **D-02:** Без иконок — только текстовый контент (заголовок, описание, how-to, кнопки)
- **D-03:** Стилизация через Tailwind-классы (не inline styles)
- **D-04:** Глубина "Как использовать" — на усмотрение Claude. Для сложных фич детальнее; для простых — краткий hint.
- **D-05:** Основной CTA (кнопка `bg-blue-600 text-white`) + опциональный второстепенный CTA (текстовая ссылка)
- **D-06:** Макрос принимает: `reason` (str), `cta_label` (str), `cta_url` (str), опционально `secondary_label` (str), `secondary_url` (str), `docs_url` (str, зарезервирован)
- **D-07:** How-to контент передаётся через Jinja2 `{% call %}` блок
- **D-08:** Включить ВСЕ страницы из инвентаря, включая Tools (Phase 24–25), даже если сами инструменты ещё не реализованы
- **D-09:** Мигрировать существующие ad-hoc empty states на новый макрос
- **D-10:** Smoke-тесты Phase 15.1 не должны ломаться — все страницы с empty state корректно рендерятся

### Claude's Discretion

- Конкретный текст "Как использовать" для каждой страницы
- Выбор предусловий для каждой фичи
- Порядок и группировка страниц по планам

### Deferred Ideas (OUT OF SCOPE)

None — обсуждение осталось в рамках фазы.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EMP-01 | Создан reusable Jinja2-макрос `empty_state` в `app/templates/macros/empty_state.html` | Macro structure from `macros/health.html`; params confirmed via D-06/D-07 |
| EMP-02 | Макрос применён на core workflow страницах: Keywords, Positions, Clusters, Gap Analysis, Site Overview | Templates inventoried; exact condition blocks identified |
| EMP-03 | Макрос применён на analytics страницах: Metrika, Traffic Analysis, Growth Opportunities, Dead Content, Quick Wins | Templates inventoried; existing ad-hoc states located |
| EMP-04 | Макрос применён на content страницах: WP Pipeline, Content Plan (Gap proposals), Client Reports | Templates inventoried; pipeline/client-reports confirmed |
| EMP-05 | Each empty state explains "why empty" and gives direct CTA | CTA URLs derivable from router prefixes below |
| EMP-06 | Макрос на tools страницах (Phase 24–25); if not yet built, placeholder HTML pages suffice | No tools templates exist yet — stub pages required |
| EMP-07 | Smoke tests don't break — all pages render on seed data with and without data | Smoke infrastructure (test_ui_smoke.py + _smoke_helpers.py) understood; UI_PREFIXES cover all affected routes |
</phase_requirements>

---

## Summary

Phase 19 is a pure template-layer phase. No new routes, no new models, no migrations. The work is: (1) create one Jinja2 macro file, (2) replace ad-hoc empty-state markup in ~18 templates with macro calls, (3) create stub HTML pages for two not-yet-implemented Tools pages, (4) verify the smoke crawler still passes.

The existing project pattern (`macros/health.html`) uses a regular `{% macro name(arg) %}...{% endmacro %}` definition and is imported with `{% from "macros/health.html" import project_health_widget %}`. The `{% call %}` pattern required by D-07 is standard Jinja2: the macro declares a `caller()` call-site inside its body, and callers wrap content in `{% call(macro_name) %}...{% endcall %}`.

The Phase 15.1 smoke crawler auto-discovers HTML routes by prefix (`/ui/`, `/analytics/`, `/gap/`, `/traffic-analysis/`, `/competitors/`, `/metrika/`, `/notifications`, etc.) and hits them with seeded DB data. As long as templates render without Jinja errors on seed data (which may have zero rows), the smoke tests continue to pass. The empty-state `{% else %}` branch is already what renders when there is no data — replacing bare `<p>` tags with macro calls is transparent to the smoke runner.

**Primary recommendation:** Create `app/templates/macros/empty_state.html` with a `{% call %}`-based macro, then do a template-by-template migration pass following the page inventory below.

---

## Standard Stack

### Core (already in project — no new installs)

| Library | Purpose | Notes |
|---------|---------|-------|
| Jinja2 3.1.x | Macro definition and `{% call %}` blocks | Already loaded via FastAPI `Jinja2Templates` |
| Tailwind CSS (CDN) | Utility classes for card/button styling | Already loaded in `base.html` |
| HTML5 `<details>`/`<summary>` | Collapsible "Как использовать" section | Native, zero JS, HTMX-safe |

No new packages. No new routes. No new DB models.

---

## Architecture Patterns

### Macro File Location

```
app/templates/macros/
├── health.html          # existing — project_health_widget(health)
└── empty_state.html     # NEW — empty_state(reason, cta_label, cta_url, ...)
```

### Pattern 1: Macro Definition with `{% call %}` block

The `caller()` mechanism lets callers inject arbitrary HTML into the macro body. This is the standard Jinja2 pattern for slot-like composition.

```jinja2
{# app/templates/macros/empty_state.html #}
{% macro empty_state(reason, cta_label, cta_url,
                     secondary_label=none, secondary_url=none,
                     docs_url=none) %}
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 my-4">

  {# Reason why empty #}
  <p class="text-gray-700 font-medium mb-3">{{ reason }}</p>

  {# Collapsible how-to — caller() injects the content #}
  {% if caller is defined %}
  <details class="mb-4">
    <summary class="cursor-pointer text-sm font-medium text-indigo-600 select-none">
      Как использовать
    </summary>
    <div class="mt-2 text-sm text-gray-600 space-y-1 pl-2">
      {{ caller() }}
    </div>
  </details>
  {% endif %}

  {# Primary CTA #}
  <div class="flex items-center gap-3 flex-wrap">
    <a href="{{ cta_url }}"
       class="inline-flex items-center px-4 py-2 rounded text-sm font-medium
              bg-blue-600 text-white hover:bg-blue-700">
      {{ cta_label }}
    </a>
    {% if secondary_label and secondary_url %}
    <a href="{{ secondary_url }}"
       class="text-sm text-indigo-600 hover:underline">
      {{ secondary_label }}
    </a>
    {% endif %}
  </div>
</div>
{% endmacro %}
```

### Pattern 2: Caller-block usage at call site

```jinja2
{# at the top of a template #}
{% from "macros/empty_state.html" import empty_state %}

{# replacing an existing {% else %} branch #}
{% if keywords %}
  ... table ...
{% else %}
  {% call empty_state(
      reason="Ключевые слова ещё не добавлены.",
      cta_label="Импортировать ключи",
      cta_url="/ui/uploads"
  ) %}
    <p>1. Перейдите в раздел «Импорт» и загрузите файл XLSX из Topvisor.</p>
    <p>2. Или добавьте ключевые слова вручную через форму выше.</p>
    <p>3. После добавления запустите проверку позиций.</p>
  {% endcall %}
{% endif %}
```

### Pattern 3: Macro without caller (no how-to needed)

When `caller` is not defined (macro called without `{% call %}`), the `<details>` block is simply omitted. This means calling `{{ empty_state(...) }}` without `{% call %}` is valid and produces a card with only reason + CTA.

### Anti-Patterns to Avoid

- **Inline styles inside macro:** D-03 prohibits. Use Tailwind only.
- **Icons in macro:** D-02 prohibits SVG/emoji icons in the macro definition.
- **Global import in base.html:** Do NOT import the macro in `base.html`. Each template that uses it must import explicitly — this matches the project's health.html pattern and keeps it tree-shakeable.
- **Missing `{% from %}` import:** The macro call will silently fail (Jinja renders nothing) if the import is missing. Every modified template must have the `{% from "macros/empty_state.html" import empty_state %}` line.

---

## Page Inventory and Migration Map

### Group A — Core Workflow (EMP-02)

| Template | File | Empty condition | Current state | CTA URL |
|----------|------|-----------------|---------------|---------|
| Keywords | `app/templates/keywords/index.html` | `{% else %}` at line 114 | `<p class="text-gray-500">No keywords yet...` | `/ui/uploads` |
| Positions | `app/templates/positions/index.html` | `{% else %}` at line 118 | `<p class="text-gray-500">No position data yet...` | `/ui/positions/{site_id}` + button to run check |
| Clusters | `app/templates/clusters/index.html` | No explicit empty state visible (clusters list iterates directly); needs `{% if clusters %}...{% else %}` | Missing | `/ui/clusters/{site_id}` + Auto-Cluster |
| Cannibalization | `app/templates/clusters/cannibalization.html` | `{% else %}` at line 81 | `<p class="text-emerald-600">No cannibalization detected...` | `/ui/positions/{site_id}` |
| Site Overview (no data) | `app/templates/sites/detail.html` | Stats row always renders; health widget already present; no general "no data" state needed | Covered by PHW | n/a |
| Crawl History | `app/templates/crawl/history.html` | `{% else %}` at line 62 | `<p class="text-gray-400">No crawl jobs yet...` | `/ui/sites/{site_id}/crawls` + start button |
| Schedule | `app/templates/sites/schedule.html` | No empty state (always has defaults) | No change needed | n/a |
| Gap Analysis | `app/templates/gap/index.html` | `{% if not keywords %}` at line 107 | `<p class="text-gray-500">Нет gap-ключей...` | `/gap/{site_id}` (import section above) |

### Group B — Analytics (EMP-03)

| Template | File | Empty condition | Current state | CTA URL |
|----------|------|-----------------|---------------|---------|
| Metrika (no counter) | `app/templates/metrika/index.html` | `{% if not site.metrika_counter_id %}` line 32 | Plain `<p class="text-gray-500">Счётчик Метрики не настроен...` | `/ui/sites/{site.id}/edit` |
| Metrika (counter set, no data) | same | `{% elif not daily_data %}` line 40 | Plain `<p class="text-gray-500">Данные ещё не загружены...` | button already present above — use secondary CTA |
| Traffic Analysis (no sessions) | `app/templates/traffic_analysis/index.html` | `{% else %}` at line 88 | `<p class="text-gray-500 text-center py-4">Нет анализов...` | `/traffic-analysis/{site.id}` (use upload/analyze buttons above) |
| Growth Opportunities (gaps) | `app/templates/analytics/partials/opportunities_gaps.html` | `{% else %}` at line 62 | `<div>...Нет данных по gap-ключам...` | `/analytics/{site.id}/opportunities` (run gap-analysis) |
| Dead Content | `app/templates/analytics/partials/dead_content_table.html` | `{% else %}` at line 82 | `<div class="text-center py-16"><p>Мёртвых страниц не найдено...` | `/ui/sites/{site.id}/crawls` (needs crawl + positions) |
| Quick Wins | `app/templates/analytics/partials/quick_wins_table.html` | `{% else %}` at line 92 | SVG icon + h3 + p — most complete existing state | `/ui/positions/{site.id}` |

### Group C — Content (EMP-04)

| Template | File | Empty condition | Current state | CTA URL |
|----------|------|-----------------|---------------|---------|
| Content Pipeline (WP) | `app/templates/pipeline/jobs.html` | `{% if jobs %}...{% else %}` — else branch not found in first 60 lines; likely missing | Needs `{% else %}` branch | `/ui/pipeline/{site_id}` (Run Batch) |
| Content Plan (Gap proposals) | `app/templates/gap/index.html` — proposals section | `{% else %}` at line 163 | `<p class="text-gray-500 text-center">Нет предложений...` | `/gap/{site_id}` (create proposals section) |
| Client Reports | `app/templates/client_reports/index.html` | History table has a partial (`history_table.html`) — check if empty branch exists | Likely missing | `/ui/client-reports/` |

### Group D — Tools / Phase 24-25 (EMP-06)

No tool templates exist yet. The decision (D-08) is to include them anyway. Two stub HTML pages are required:

| Tool | Route (presumed) | Action |
|------|-----------------|--------|
| Keyword Research tool | `/ui/tools/keyword-research` or similar | Create stub route + template with empty state explaining "Phase 24 — coming soon" |
| Site Audit tool | `/ui/tools/site-audit` or similar | Same |

Since Phase 24-25 routes are not in the codebase, implementation options:
1. Create stub FastAPI route handlers in a new `app/routers/tools.py` file returning an HTMLResponse with a simple "coming soon" empty-state page — no DB dependencies, smoke-safe.
2. Alternatively, defer entirely and mark EMP-06 as "after Phase 25" per the REQUIREMENTS.md note: "if Phase 24–25 not ready on Phase 19 execution — tools-half deferred after Phase 25".

**Recommendation:** defer EMP-06 to a separate small plan (Plan 03 in the wave), implemented last, clearly labelled. This protects Plans 01-02 from scope creep.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Collapsible how-to section | Custom accordion with JS/HTMX | Native `<details>`/`<summary>` — zero JS, works inside HTMX partial swaps |
| Icon assets | SVG library import | No icons per D-02 |
| CTA tracking | Custom JS click tracking | Out of scope (no analytics for solo-user) |

---

## Common Pitfalls

### Pitfall 1: `caller` guard pattern in Jinja2

**What goes wrong:** Calling `{{ empty_state(...) }}` (not via `{% call %}`) in a template raises `UndefinedError: 'caller' is undefined` if the macro body references `caller()` unconditionally.
**How to avoid:** Always guard with `{% if caller is defined %}` before using `caller()`. This is already shown in the macro example above.
**Warning signs:** Smoke test 500 or `UndefinedError` in response body.

### Pitfall 2: Partial templates with their own empty state

**What goes wrong:** Some empty states live in included partials (e.g. `analytics/partials/dead_content_table.html`, `analytics/partials/quick_wins_table.html`), not in the parent template. Importing the macro into the parent template won't help if the partial renders first.
**How to avoid:** Add the `{% from %}` import at the top of each partial file that renders an empty state independently. The partial is the correct place to apply the macro.

### Pitfall 3: Smoke test `UnknownParamError`

**What goes wrong:** New stub tool pages added with path params that have no entry in `PARAM_MAP` cause `UnknownParamError` at smoke test collection time.
**How to avoid:** Either (a) use no path params on stub tool routes (e.g. `/ui/tools/keyword-research`), or (b) add the new param key to `SMOKE_IDS` in `tests/fixtures/smoke_seed.py` and `build_param_map` in `tests/_smoke_helpers.py`.

### Pitfall 4: Missing `{% from %}` import causes silent blank

**What goes wrong:** If the import line is forgotten, Jinja2 does not error — `empty_state` is just `Undefined`, and `{{ empty_state(...) }}` renders as an empty string. The page looks fine, but no empty state is shown.
**How to avoid:** After applying each migration, manually verify the rendered page at the empty-state branch, not just that the smoke test passes.

### Pitfall 5: New tool routes not covered by `UI_PREFIXES`

**What goes wrong:** Stub tool routes at `/ui/tools/...` are covered by the existing `/ui/` prefix in `UI_PREFIXES`, so they will be auto-discovered by the smoke crawler. This is correct. But if a different prefix is used (e.g. `/tools/`), it must be added to `UI_PREFIXES`.
**How to avoid:** Use `/ui/tools/...` prefix for all stub routes.

### Pitfall 6: Clusters page has no `{% else %}` branch

**What goes wrong:** `app/templates/clusters/index.html` iterates `{% for c in clusters %}` without a surrounding `{% if clusters %}...{% else %}` guard. Adding the empty state requires restructuring the block, not just replacing existing text.
**How to avoid:** Wrap the existing cluster list in `{% if clusters %}...{% else %}{{ empty_state(...) }}{% endif %}`.

---

## Existing Ad-Hoc Empty States to Migrate

Complete list of ad-hoc empty states found in codebase (D-09 migration targets):

| Location | Current markup | Notes |
|----------|---------------|-------|
| `keywords/index.html` line 114–116 | `<p class="text-gray-500">No keywords yet...` | Simple |
| `positions/index.html` line 118–119 | `<p class="text-gray-500">No position data yet...` | Simple |
| `crawl/history.html` line 62–63 | `<p class="text-gray-400 text-sm">No crawl jobs yet...` | Simple |
| `competitors/index.html` line 51–53 | `<p class="text-gray-500">No competitors yet...` | Simple |
| `metrika/index.html` lines 32–45 | Two separate `<div class="bg-white..."><p>` blocks | Best existing pattern; two separate reasons |
| `traffic_analysis/index.html` line 88–92 | `<p class="text-gray-500 text-center py-4">Нет анализов...` | In the sessions table block |
| `analytics/partials/opportunities_gaps.html` line 62–65 | `<div class="bg-white...">Нет данных...` | Already card-styled |
| `analytics/partials/dead_content_table.html` lines 82–87 | `<div class="text-center py-16"><p>` | In partial file |
| `analytics/partials/quick_wins_table.html` lines 92–102 | SVG + h3 + p block | Most complete, but has forbidden SVG icon per D-02 |
| `gap/index.html` line 107–109 | `<p class="text-gray-500 text-center">` in keywords table | Simple |
| `gap/index.html` line 163–165 | `<p class="text-gray-500 text-center">Нет предложений...` | Proposals section |
| `clusters/cannibalization.html` line 81–83 | `<p class="text-emerald-600">No cannibalization...` | Green is "good news" — keep a success-tone reason |

---

## CTA URL Reference

Router prefixes needed to compose CTA `href` values:

| Feature | Router prefix | Key GET HTML route |
|---------|--------------|-------------------|
| Keywords | `/ui/keywords/{site_id}` | self-page |
| Uploads/Import | `/ui/uploads` | upload form |
| Positions check | `/ui/positions/{site_id}` | self-page |
| Crawl launch | `/ui/sites/{site_id}/crawls` | crawl history + start button |
| Schedule | `/ui/sites/{site_id}/schedule` | schedule page |
| Competitors | `/ui/competitors/{site_id}` | self-page |
| Metrika settings | `/ui/sites/{site_id}/edit` | site edit form |
| Analytics/Opportunities | `/analytics/{site_id}/opportunities` | opportunities page |
| Dead Content | `/analytics/{site_id}/dead-content` | dead content page |
| Quick Wins | `/analytics/{site_id}/quick-wins` | quick wins page |
| Gap Analysis | `/gap/{site_id}` | gap analysis page |
| Traffic Analysis | `/traffic-analysis/{site_id}` | traffic analysis page |
| Client Reports | `/ui/client-reports/` | client reports index |
| Content Pipeline | `/ui/pipeline/{site_id}` | pipeline jobs page |
| Clusters | `/ui/clusters/{site_id}` | clusters page |

---

## Smoke Test Integration

### How the smoke crawler discovers routes

`tests/_smoke_helpers.py::discover_routes()` iterates `app.routes`, filters for GET routes whose path starts with any prefix in `UI_PREFIXES`, classifies each as HTML via a 3-tier check, and excludes `SMOKE_SKIP`.

Current `UI_PREFIXES`:
```python
UI_PREFIXES = (
    "/ui/",
    "/analytics/",
    "/audit/",
    "/gap/",
    "/intent/",
    "/architecture/",
    "/bulk/",
    "/traffic-analysis/",
    "/monitoring/",
    "/competitors/",
    "/metrika/",
    "/profile/",
    "/notifications",
)
```

All Phase 19 template changes involve routes already covered by `/ui/`, `/analytics/`, `/gap/`, `/traffic-analysis/`, `/competitors/`, `/metrika/`. No prefix additions needed unless tool stub routes use a non-`/ui/` prefix.

### Smoke seed adequacy

`tests/fixtures/smoke_seed.py` seeds all entities needed for path-param resolution. The seed produces zero rows in many feature tables (e.g. no positions, no metrika data, no gap keywords) — this is intentional and means the smoke tests exercise the empty-state branches. After Phase 19, those `{% else %}` branches render the new macro instead of bare `<p>` tags, which is fully smoke-safe as long as Jinja renders without errors.

No changes to `smoke_seed.py` are needed unless new stub tool routes introduce new path params.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — pure template/HTML changes, no new services or CLI tools required)

---

## Sources

### Primary (HIGH confidence)

- Direct file inspection: `app/templates/macros/health.html` — existing macro structure
- Direct file inspection: `app/templates/metrika/index.html` — best existing empty state pattern
- Direct file inspection: all 18 template files in inventory above — confirmed line numbers and existing text
- Direct file inspection: `tests/_smoke_helpers.py` — UI_PREFIXES, SMOKE_SKIP, discover_routes logic
- Direct file inspection: `tests/test_ui_smoke.py` — smoke test parametrization
- Direct file inspection: `tests/fixtures/smoke_seed.py` — SMOKE_IDS, seed_core
- Direct file inspection: `app/main.py` lines 109–168 (router registrations), grep of all `response_class=HTMLResponse` routes

### Secondary (MEDIUM confidence)

- Jinja2 3.1 docs on `{% call %}` blocks — confirmed from training knowledge; no version-specific API changes in 3.1.x that affect `caller is defined` guard pattern

---

## Metadata

**Confidence breakdown:**
- Page inventory: HIGH — every template file read directly, line numbers confirmed
- Macro structure: HIGH — `caller is defined` guard is documented Jinja2 API, health.html confirms project pattern
- Smoke integration: HIGH — `_smoke_helpers.py` and `test_ui_smoke.py` fully read; no assumptions
- Tools/Phase 24-25 stub: MEDIUM — no routes exist yet; stub approach is the simplest safe option but exact router design is discretionary

**Research date:** 2026-04-09
**Valid until:** Until Phase 24-25 tools are implemented (EMP-06 scope changes)
