# Phase 13: Impact Scoring & Growth Opportunities - Research

**Researched:** 2026-04-06
**Domain:** SEO analytics — pre-computed impact scoring, Kanban sort integration, Growth Opportunities dashboard with drill-down
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** impact_score = severity_weight × месячный трафик страницы из Метрики (MetrikaTrafficPage.visits за 30 дней).
- **D-02:** Фиксированные веса по severity: warning=1, error=3, critical=5. Без UI для настройки весов.
- **D-03:** Веса применяются на уровне severity (не per check_code). Все warning-ошибки имеют одинаковый вес.
- **D-04:** Добавить сортировку по impact_score в существующий Kanban (/ui/projects/{id}/kanban) — на усмотрение Claude (toggle/dropdown/кнопка).
- **D-05:** Табы по категориям: Gaps | Потери | Каннибализация | Тренд. Каждый таб — отдельная секция с данными.
- **D-06:** Visibility trend — только числа: текущий показатель + % изменения за неделю/месяц. Без графиков и спарклайнов.
- **D-07:** Содержимое каждого таба — на усмотрение Claude (какие колонки, какие метрики показывать).
- **D-08:** Клик по записи в табе открывает выдвижную боковую панель (slide-over) с деталями, не уходя с дашборда.
- **D-09:** Из панели можно перейти на полную страницу (gap analysis, positions, clusters) по кнопке «Подробнее».
- **Folded Todo:** Fix position check ignores keyword engine preference — исправить в рамках Phase 13.

### Claude's Discretion

- Kanban: способ переключения сортировки (toggle, dropdown, кнопка)
- Содержимое каждого таба (колонки, метрики, сортировка)
- Slide-over панель: какие детали показывать для каждого типа записи
- Celery task: частота пересчёта impact scores, batch size
- Определение «потерянных позиций» (порог дельты)
- Определение «активных каннибализаций» (логика кластеризации)

### Deferred Ideas (OUT OF SCOPE)

- Настраиваемые веса severity через UI
- Индивидуальные веса per check_code
- Графики и спарклайны для visibility trend
- "Proxy management, XMLProxy integration and health checker"
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IMP-01 | Все ошибки (404, noindex, нет schema) имеют impact_score = severity_weight × месячный трафик страницы | New `error_impact_scores` table + `compute_impact_scores` Celery task + JOIN between AuditResult/AuditCheckDefinition/MetrikaTrafficPage |
| IMP-02 | Задачи в Kanban можно сортировать по impact_score; самые критичные ошибки видны первыми | `error_impact_scores` feeds kanban sort; SeoTask has no impact_score column directly — JOIN via url; HTMX partial re-sort |
| GRO-01 | Дашборд Growth Opportunities агрегирует: gap-ключи, потерянные позиции, каннибализации, visibility тренд | All data already exists: GapKeyword, KeywordLatestPosition (delta), cluster_service.detect_cannibalization(), MetrikaTrafficDaily |
| GRO-02 | Пользователь может drill-down из карточки Opportunities в соответствующий раздел | Slide-over panel (HTMX out-of-band or inline swap) + «Подробнее» link to /gap/{site_id}, /ui/positions/{site_id}, /ui/cannibalization/{site_id} |
</phase_requirements>

---

## Summary

Phase 13 adds two features on top of Phase 12 infrastructure: (1) pre-computed impact scores for audit errors stored in a new `error_impact_scores` table and surfaced in the Kanban board, and (2) a Growth Opportunities dashboard at `/analytics/{site_id}/opportunities` with four tabs backed by existing data models.

The phase is primarily a data-aggregation and UI task. All source data already exists: `AuditResult` + `AuditCheckDefinition` (severity), `MetrikaTrafficPage` (30-day visits), `KeywordLatestPosition` (delta for lost positions), `GapKeyword` (gap analysis), `detect_cannibalization()` in cluster_service, and `MetrikaTrafficDaily` (visibility trend). No new external API calls are required.

The Kanban sort integration is a targeted modification to `main.py:ui_kanban()` and `kanban.html` — currently tasks are ordered by `created_at`; the sort needs to JOIN against `error_impact_scores` by task URL. The slide-over panel follows HTMX patterns already established in Quick Wins and Dead Content.

**Primary recommendation:** Implement the `error_impact_scores` table + Celery task first (wave 1), then Growth Opportunities dashboard (wave 2), then Kanban integration (wave 3). This ordering ensures impact scores exist before the Kanban sort queries them, and the dashboard can be built independently of the Kanban change.

---

## Standard Stack

### Core (all already in project — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy 2.0 async | 2.0.30+ | ORM for new table, queries | Established project ORM |
| Alembic | 1.13.x | Migration for error_impact_scores | Project migration tool |
| Celery 5.4 | 5.4.x | Background pre-computation of scores | Project task queue |
| FastAPI | 0.115.x | New router for Opportunities | Project web framework |
| Jinja2 + HTMX 2.0 | 3.1.x / 2.0.x | Dashboard template + tab switching | Established UI pattern |
| asyncpg | 0.29.x | Async DB driver | Project driver |

**No new packages needed for Phase 13.** All required libraries are already installed.

---

## Architecture Patterns

### New Table: `error_impact_scores`

The impact score is pre-computed and stored, not calculated on-the-fly per request. This mirrors the `keyword_latest_positions` pattern from Phase 12. The table is a materialized snapshot refreshed by Celery.

```python
# app/models/impact_score.py  (new file)
class ErrorImpactScore(Base):
    __tablename__ = "error_impact_scores"
    __table_args__ = (
        UniqueConstraint("site_id", "page_url", "check_code",
                         name="uq_eis_site_page_check"),
    )
    id: Mapped[uuid.UUID] = ...
    site_id: Mapped[uuid.UUID] = ...   # FK sites.id CASCADE
    page_url: Mapped[str] = ...        # normalized URL
    check_code: Mapped[str] = ...      # e.g. "missing_schema"
    severity: Mapped[str] = ...        # "warning" | "error" | "critical"
    severity_weight: Mapped[int] = ... # 1 | 3 | 5
    monthly_traffic: Mapped[int] = ... # visits from MetrikaTrafficPage (30d sum)
    impact_score: Mapped[int] = ...    # severity_weight * monthly_traffic
    computed_at: Mapped[datetime] = ...
```

**Migration:** `0038_add_error_impact_scores.py` (next in sequence)

**Index needed:** `(site_id, impact_score DESC)` for fast Kanban sort queries.

### Celery Task: `compute_impact_scores`

```python
# app/tasks/impact_tasks.py  (new file)
@celery_app.task(
    name="app.tasks.impact_tasks.compute_impact_scores",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def compute_impact_scores(self, site_id: str) -> dict:
    ...
```

**Logic:**
1. Fetch all non-passing AuditResults for the site (status != 'pass') joined with AuditCheckDefinition for severity.
2. Fetch MetrikaTrafficPage rows for last 30 days grouped by normalized page_url → SUM(visits).
3. Python-side URL normalization using `normalize_url()` to match URLs across tables.
4. Compute `impact_score = SEVERITY_WEIGHTS[severity] * monthly_traffic`. If no traffic data: impact_score = severity_weight × 0 = 0 (but record still inserted so UI can sort).
5. Bulk upsert via `INSERT ... ON CONFLICT DO UPDATE` (same pattern as `refresh_latest_positions()`).

**Severity weights (fixed per D-02):**
```python
SEVERITY_WEIGHTS = {"warning": 1, "error": 3, "critical": 5}
```

**Scheduling:** Task runs after every audit completion (triggered from audit_tasks.py) and can be manually triggered from the site page. No periodic Beat schedule needed — audit-driven is sufficient.

### New Service: `impact_score_service.py`

```python
# app/services/impact_score_service.py

async def get_impact_scores_for_site(
    db: AsyncSession, site_id: uuid.UUID, limit: int = 200
) -> list[dict]:
    """Return top N error_impact_scores ordered by impact_score DESC."""
    ...

async def upsert_impact_scores(
    db: AsyncSession, rows: list[dict]
) -> int:
    """Bulk upsert into error_impact_scores. Returns row count."""
    ...
```

### Kanban Sort Integration

The Kanban board is currently served from `main.py:ui_kanban()`. The sort toggle adds a `sort` query parameter (`sort=impact` vs default `sort=created`).

**Approach:** A sort toggle button in the Kanban header makes an HTMX GET request to the same `/ui/projects/{project_id}/kanban?sort=impact` URL. Since the full page reloads via HTMX, this is the simplest approach without introducing partial swaps for the whole board.

```html
<!-- Kanban header addition -->
<button
  hx-get="/ui/projects/{{ project_id }}/kanban?sort=impact"
  hx-target="body"
  hx-push-url="true"
  class="px-3 py-1.5 text-sm font-medium rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
  Sort by Impact
</button>
```

When `sort=impact`, `ui_kanban()` JOINs tasks to `error_impact_scores` on `task.url = eis.page_url AND task.site_id = eis.site_id` and orders by `MAX(eis.impact_score) DESC NULLS LAST` per task. Tasks without impact scores sort to the bottom.

**Impact score badge on each task card:**
```html
{% if task.impact_score %}
<span class="text-[0.65rem] font-mono text-orange-600 ml-1">⚡{{ task.impact_score }}</span>
{% endif %}
```

### Growth Opportunities Dashboard

**Route:** `/analytics/{site_id}/opportunities`
**Template:** `app/templates/analytics/opportunities.html`
**Router file:** `app/routers/opportunities.py` (new) — registered under `/analytics` prefix

**Tab structure (HTMX-driven):**

```
/analytics/{site_id}/opportunities              # full page, default tab = gaps
/analytics/{site_id}/opportunities/tabs/gaps    # HTMX partial
/analytics/{site_id}/opportunities/tabs/losses  # HTMX partial
/analytics/{site_id}/opportunities/tabs/cannibal # HTMX partial
/analytics/{site_id}/opportunities/tabs/trend   # HTMX partial
```

Pattern follows `quick_wins_table` partial pattern exactly.

**Tab 1 — Gaps (gap keywords):**
- Source: `GapKeyword` table — already populated by gap analysis feature
- Columns: phrase, competitor_domain, competitor_position, our_position, potential_score
- Sorted by: potential_score DESC
- Count + total estimated traffic in stats strip

**Tab 2 — Потери (lost positions):**
- Source: `KeywordLatestPosition` table — `delta` column (negative = dropped)
- "Lost" definition (Claude's discretion per CONTEXT.md): delta <= -5 (significant drop, not noise)
- Columns: keyword phrase, current_position, previous_position, delta, url
- Sorted by: delta ASC (worst drops first)
- JOIN to keywords table for phrase

**Tab 3 — Каннибализация:**
- Source: `cluster_service.detect_cannibalization()` — returns list of {keyword_id, phrase, pages: [{url, position}]}
- "Active" definition: 2+ pages ranking in top-50 for the same keyword (not top-100 — reduces noise)
- Columns: keyword phrase, competing URLs, positions
- Sorted by: number of competing pages DESC

**Tab 4 — Тренд (visibility trend):**
- Source: `MetrikaTrafficDaily` table — SUM(visits) per week/month
- Current week vs previous week: % change
- Current month vs previous month: % change
- Display as stats strip only — no chart (D-06)

### Slide-Over Panel

A slide-over panel is a CSS fixed-position right drawer, toggled via HTMX. The pattern is not currently used in the codebase, but is straightforward with Tailwind:

```html
<!-- Slide-over overlay + drawer (shared partial) -->
<div id="slide-over" class="hidden fixed inset-0 z-50">
  <div class="absolute inset-0 bg-black bg-opacity-30" onclick="closeSlideOver()"></div>
  <div class="absolute right-0 top-0 h-full w-96 bg-white shadow-xl overflow-y-auto p-6"
       id="slide-over-content">
    <!-- Filled by HTMX -->
  </div>
</div>
```

**HTMX trigger for slide-over:**
```html
<tr class="cursor-pointer hover:bg-gray-50"
    hx-get="/analytics/{{ site.id }}/opportunities/detail/gap/{{ item.id }}"
    hx-target="#slide-over-content"
    hx-on::after-request="document.getElementById('slide-over').classList.remove('hidden')">
```

**Detail endpoints (one per tab type):**
```
GET /analytics/{site_id}/opportunities/detail/gap/{gap_keyword_id}
GET /analytics/{site_id}/opportunities/detail/loss/{keyword_id}
GET /analytics/{site_id}/opportunities/detail/cannibal/{keyword_id}
GET /analytics/{site_id}/opportunities/detail/trend
```

Each returns an HTML partial for the slide-over content. The «Подробнее» link at the bottom of each panel navigates to the full section.

### Navigation Entry

Add to `analytics` section in `app/navigation.py`:
```python
{"id": "opportunities", "label": "Growth Opportunities", "url": "/analytics/{site_id}/opportunities"},
```

### Folded Todo: Position Check Engine Bug

The CONTEXT.md includes a folded todo: "Fix position check ignores keyword engine preference." Review of `position_tasks.py` shows that `check_positions()` already correctly splits keywords by engine (line 54: `yandex_kws = [kw for kw in keywords if not kw.engine or kw.engine.value == "yandex"]`). The earlier quick task `260402-v3j` (commit 23e77f6) addressed a position engine bug. The planner should verify the current state and either confirm it's fixed or scope a targeted investigation rather than assuming a full rewrite is needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Bulk upsert into error_impact_scores | Custom UPDATE loop | `INSERT ... ON CONFLICT DO UPDATE` — same pattern as `refresh_latest_positions()` in position_service.py |
| URL matching across tables | Custom string comparison | `normalize_url()` from `app/utils/url_normalize.py` — already used in quick_wins_service.py and dead_content_service.py |
| Tab switching without full reload | Custom JS fetch | HTMX `hx-get` + `hx-target` — same pattern as quick_wins filter dropdowns |
| Slide-over animation | Custom CSS animation | Tailwind `transition-transform translate-x-full` — simple enough inline |
| Batch score computation | ORM row-by-row | Raw SQL with `text()` for the JOIN across audit_results + audit_check_definitions + metrika_traffic_pages |

---

## Common Pitfalls

### Pitfall 1: URL Mismatch Between audit_results and metrika_traffic_pages

**What goes wrong:** `AuditResult.page_url` and `MetrikaTrafficPage.page_url` are stored as raw strings from different sources (crawler vs Metrika API). A trailing slash difference or http/https discrepancy causes a zero-join, making impact_score = 0 for all pages even when traffic exists.

**Why it happens:** MetrikaTrafficPage URLs come from Yandex Metrika (may have trailing slash), AuditResult URLs come from the crawler (may not). Without normalization, the JOIN yields empty results silently.

**How to avoid:** Always run both URLs through `normalize_url()` before comparing. In the Celery task, build a Python dict `traffic_by_norm_url` from Metrika rows, then look up each AuditResult URL after normalizing it.

**Warning signs:** All impact_scores are 0 after first run; check counts in error_impact_scores vs audit_results.

### Pitfall 2: Kanban Query N+1 for Impact Scores

**What goes wrong:** The `ui_kanban()` handler currently loads tasks with a simple SELECT. If impact_score is fetched per-task individually, 50 tasks = 50 extra queries.

**How to avoid:** Do a single JOIN or subquery: `SELECT seo_tasks.*, MAX(eis.impact_score) FROM seo_tasks LEFT JOIN error_impact_scores eis ON eis.page_url = seo_tasks.url GROUP BY seo_tasks.id`. Use `text()` for this since it spans two tables without an ORM relationship.

### Pitfall 3: detect_cannibalization() Uses keyword_positions (Partitioned), Not keyword_latest_positions

**What goes wrong:** The existing `detect_cannibalization()` in cluster_service.py queries the `keyword_positions` partitioned table with `DISTINCT ON` — exactly the slow pattern that Phase 12 replaced. For 100K keywords, this can take 8-15 seconds.

**How to avoid:** For the Growth Opportunities tab, rewrite the cannibalization detection to use `keyword_latest_positions` flat table instead of `keyword_positions`. The `KeywordLatestPosition` model already has `position` and `url` fields. The query becomes a simple GROUP BY on the flat table.

### Pitfall 4: Slide-Over Panel Leaves Stale Content on Re-Open

**What goes wrong:** If the user clicks row A, then row B, the slide-over fills with B's content. But if they navigate away and come back, the panel may show old content if not cleared.

**How to avoid:** Clear `#slide-over-content` innerHTML when closing the panel. Add `hx-on::after-request` to reset scroll position. This is a simple JS `closeSlideOver()` function.

### Pitfall 5: Celery Task Triggered Too Frequently

**What goes wrong:** If compute_impact_scores is triggered after every individual AuditResult write (inside a batch), it runs hundreds of times per audit cycle.

**How to avoid:** Trigger the task only at the end of the full audit batch job completion, not per-result. The existing audit_tasks.py already has a completion signal — hook into that.

---

## Code Examples

### Bulk Upsert Pattern (from position_service.py)

```python
# Source: app/services/position_service.py refresh_latest_positions()
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(ErrorImpactScore).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=["site_id", "page_url", "check_code"],
    set_={
        "severity": stmt.excluded.severity,
        "severity_weight": stmt.excluded.severity_weight,
        "monthly_traffic": stmt.excluded.monthly_traffic,
        "impact_score": stmt.excluded.impact_score,
        "computed_at": stmt.excluded.computed_at,
    },
)
await db.execute(stmt)
await db.commit()
```

### HTMX Tab Switching Pattern (from quick_wins.html)

```html
<!-- Source: app/templates/analytics/quick_wins.html -->
<select
  hx-get="/analytics/{{ site.id }}/quick-wins/table"
  hx-target="#quick-wins-table"
  hx-trigger="change"
  hx-include="[name='issue_type'],[name='content_type']"
>
```

For tabs, use `hx-get` on tab buttons with `hx-target="#tab-content"`.

### normalize_url Usage (from quick_wins_service.py)

```python
# Source: app/services/quick_wins_service.py
from app.utils.url_normalize import normalize_url

traffic_by_norm: dict[str, int] = {}
for row in metrika_rows:
    norm = normalize_url(row.page_url)
    if norm:
        traffic_by_norm[norm] = traffic_by_norm.get(norm, 0) + row.visits

# Then for each audit result:
norm_url = normalize_url(audit_result.page_url)
traffic = traffic_by_norm.get(norm_url, 0)
```

### Celery Task Structure (from existing tasks)

```python
# Source: app/tasks/analytics_tasks.py
@celery_app.task(
    name="app.tasks.impact_tasks.compute_impact_scores",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def compute_impact_scores(self, site_id: str) -> dict:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_compute_scores(site_id))
    except Exception as exc:
        logger.error("Impact score computation failed", site_id=site_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()
```

### Lost Positions Query (using keyword_latest_positions)

```python
# Recommended implementation — uses flat table, not partitioned keyword_positions
result = await db.execute(text("""
    SELECT
        klp.keyword_id,
        k.phrase,
        klp.url,
        klp.position,
        klp.previous_position,
        klp.delta
    FROM keyword_latest_positions klp
    JOIN keywords k ON k.id = klp.keyword_id
    WHERE klp.site_id = :site_id
      AND klp.delta <= :threshold
      AND klp.position IS NOT NULL
    ORDER BY klp.delta ASC
    LIMIT 200
"""), {"site_id": site_id, "threshold": -5})
```

### Cannibalization Query (using keyword_latest_positions, not keyword_positions)

```python
# Replaces detect_cannibalization() slow partitioned scan for the Opportunities tab
result = await db.execute(text("""
    WITH multi_page AS (
        SELECT keyword_id, COUNT(DISTINCT url) AS page_count
        FROM keyword_latest_positions
        WHERE site_id = :site_id
          AND position IS NOT NULL
          AND position <= 50
          AND url IS NOT NULL
        GROUP BY keyword_id
        HAVING COUNT(DISTINCT url) >= 2
    )
    SELECT klp.keyword_id, k.phrase, klp.url, klp.position
    FROM keyword_latest_positions klp
    JOIN keywords k ON k.id = klp.keyword_id
    JOIN multi_page mp ON mp.keyword_id = klp.keyword_id
    WHERE klp.site_id = :site_id
      AND klp.position <= 50
    ORDER BY klp.keyword_id, klp.position
"""), {"site_id": site_id})
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Impact score computed on-the-fly per request | Pre-computed in Celery, stored in error_impact_scores | UI pages stay under 3s |
| detect_cannibalization() scans partitioned keyword_positions | Use keyword_latest_positions flat table for Growth Opportunities | Eliminates 8-15s scans |
| Kanban sorted by created_at only | Toggle to sort by impact_score | User sees highest-value tasks first |

---

## Data Model Inventory

Before implementing, the planner must verify these existing tables and their relevant fields:

| Table | Fields Needed | Verified In |
|-------|--------------|-------------|
| `audit_results` | site_id, page_url, check_code, status | app/models/audit.py |
| `audit_check_definitions` | code, severity | app/models/audit.py |
| `metrika_traffic_pages` | site_id, page_url, visits, period_start, period_end | app/models/metrika.py |
| `keyword_latest_positions` | site_id, keyword_id, position, previous_position, delta, url | app/models/keyword_latest_position.py |
| `gap_keywords` | site_id, phrase, competitor_domain, competitor_position, our_position, potential_score | app/models/gap.py |
| `seo_tasks` | site_id, url, status, task_type | app/models/task.py |
| `metrika_traffic_daily` | site_id, traffic_date, visits | app/models/metrika.py |

**New table to create:** `error_impact_scores` — migration 0038.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 13 is code/config changes only. All external dependencies (PostgreSQL 16, Redis 7, Celery) are already verified running from previous phases. No new external dependencies introduced.

---

## Open Questions

1. **Position engine bug scope (Folded Todo)**
   - What we know: Quick task `260402-v3j` (commit 23e77f6) was completed on 2026-04-02 titled "Fix position check engine bug"
   - What's unclear: Whether this fully resolved the engine preference issue or if a residual bug remains affecting impact score data quality
   - Recommendation: Planner should add a Wave 0 task to read commit 23e77f6 and verify the fix is complete before building impact scores on top of position data. If the fix is complete, no additional work needed. If not, scope a targeted fix as Wave 0.

2. **Metrika traffic period selection for impact score**
   - What we know: `MetrikaTrafficPage` has `period_start` and `period_end` — multiple rows per page per site (one per fetch window)
   - What's unclear: Whether the most recent 30-day period covers today-30d to today, or whether multiple overlapping records exist
   - Recommendation: In `compute_impact_scores`, filter `MetrikaTrafficPage` to the most recent record per page_url using `ORDER BY period_end DESC` with DISTINCT ON, then sum visits. Alternatively use the row with `period_end = MAX(period_end)` for each page per site.

3. **Gap keyword count vs potential traffic for stats strip**
   - What we know: `GapKeyword.frequency` is nullable — Topvisor imports may not always populate it
   - What's unclear: How many gap keywords in practice have null frequency
   - Recommendation: Show COUNT(*) as primary metric; show SUM(frequency) only if frequency is non-null for > 50% of rows. Otherwise label it "частотность недоступна".

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `app/models/audit.py`, `app/models/metrika.py`, `app/models/keyword_latest_position.py`, `app/models/gap.py`, `app/models/task.py`, `app/models/cluster.py`
- Direct code inspection: `app/services/quick_wins_service.py`, `app/services/dead_content_service.py`, `app/services/cluster_service.py`, `app/services/position_service.py`
- Direct code inspection: `app/routers/projects.py`, `app/routers/quick_wins.py`, `app/routers/dead_content.py`, `app/main.py:ui_kanban()`
- Direct code inspection: `app/templates/analytics/quick_wins.html`, `app/templates/analytics/dead_content.html`, `app/templates/projects/kanban.html`
- Direct code inspection: `app/navigation.py`, `app/tasks/analytics_tasks.py`, `app/tasks/position_tasks.py`
- Project config: `.planning/config.json` (nyquist_validation: false — Validation Architecture section omitted)

### Secondary (MEDIUM confidence)
- Phase 13 CONTEXT.md — decisions D-01 through D-09, confirmed against codebase
- REQUIREMENTS.md — IMP-01, IMP-02, GRO-01, GRO-02 requirement text

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use, verified via source
- Architecture: HIGH — patterns directly observed in Phase 12 implementation
- Pitfalls: HIGH — URL mismatch and N+1 are confirmed risks from reading actual query patterns
- Cannibalization slow scan: HIGH — confirmed by reading cluster_service.py line 145-167

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (stable stack, no external dependencies)
