# Phase 10: Reports & Ads - Research

**Researched:** 2026-04-05
**Domain:** Dashboard aggregation, PDF/Excel generation, Celery Beat scheduling, ad traffic upload, Chart.js visualisation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Dashboard is a table of projects with key metrics per row (not cards or health map). Columns at Claude's discretion based on available DB data.
- **D-02:** Dashboard is the start page after login — URL: /ui/dashboard. Replaces current landing.
- **D-03:** Dashboard must load in <3s with 50 active projects. Use Redis cache (5-min TTL) for aggregation queries.
- **D-04:** Two report types — "brief" (1-2 pages: TOP-3/10/30 trends, task summary, recent site changes) and "detailed" (5-10 pages: full keyword table with changes, trend charts, all tasks with comments).
- **D-05:** User selects report type (brief/detailed) when generating.
- **D-06:** PDF = polished client-facing report (with logo, charts via WeasyPrint). Excel = raw data export for internal analytics (openpyxl).
- **D-07:** Morning digest is a compact Telegram text message (Markdown format: projects, key metrics, link to full report). Not PDF attachment.
- **D-08:** Reports go only to admin (single Telegram chat + email). No per-project recipient management.
- **D-09:** Schedule granularity: daily digest + optional weekly summary report. Configurable send time. Celery Beat + redbeat.
- **D-10:** Only Yandex Direct as ad source. CSV format: source, date, sessions, conversions, cost.
- **D-11:** Period comparison via two date-pickers (Period A vs Period B). Table with % and absolute delta for sessions, conversions, CR%, cost-per-conversion.
- **D-12:** Weekly/monthly trend chart per source using Chart.js.

### Claude's Discretion

- Dashboard table columns — Claude selects optimal set based on available data in DB
- Chart styling and colors — follow existing Tailwind palette
- Report template design — clean, professional look

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Dashboard shows across all projects: top positions, tasks in progress, recent site changes; loads in <3s with 50 active projects | Redis cache pattern already implemented in overview_service.py; per-project aggregate query needed |
| DASH-02 | Manager/admin can generate a project report (position trends + task progress + site changes) as PDF and Excel | report_service.py has generate_excel_report(); WeasyPrint not yet installed; Jinja2 PDF templates needed |
| DASH-03 | Reports can be scheduled for automatic delivery via Telegram and/or SMTP (Celery Beat) | digest_tasks.py pattern exists; need morning_digest_task; aiosmtplib not in pyproject.toml |
| DASH-04 | Morning Telegram digest summarising project status is optionally configurable | telegram_service.py exists; need new digest format function for cross-project summary |
| ADS-01 | User can upload ad traffic data as CSV (source, date, sessions, conversions, cost) | ad_traffic model + upload endpoint already exist in reports.py |
| ADS-02 | User can compare two periods: table with % and absolute delta for sessions, conversions, CR%, cost-per-conversion | ad_traffic_comparison() exists in report_service.py; CR% computation missing; UI template needed |
| ADS-03 | User can view a weekly/monthly traffic trend chart per source | ad_traffic model has all fields; Chart.js 4.4.0 already loaded via CDN in positions template |
</phase_requirements>

---

## Summary

Phase 10 builds on a substantial existing foundation. The `AdTraffic` model, `report_service.py`, `telegram_service.py`, `digest_service.py`, and basic Celery Beat/redbeat infrastructure are already in place from earlier phases. The core work is: (1) reworking the dashboard handler to aggregate across projects in a per-project table with Redis caching, (2) building WeasyPrint PDF templates for brief and detailed reports, (3) adding a morning digest Celery task with a new cross-project text format, (4) wiring SMTP delivery via aiosmtplib (requires addition to pyproject.toml), and (5) creating the ad traffic UI (upload form, comparison table, Chart.js trend chart).

The biggest gap is that **WeasyPrint is not installed** (not in pyproject.toml) and requires system-level Pango/Cairo dependencies. This needs a `pip install weasyprint` addition and corresponding Docker build update. The existing `ad_traffic_comparison()` function also needs CR% and cost-per-conversion deltas added. The `DigestSchedule` model (currently per-site) needs to be extended or a new global `ReportSchedule` model created for the phase-level delivery schedule.

**Primary recommendation:** Build in three tracks: (A) dashboard rewrite with Redis-cached per-project aggregation, (B) PDF/Excel report generation with WeasyPrint + Jinja2 templates, (C) ad traffic UI + Chart.js trend chart. All three are independent and can be planned as separate waves.

## Project Constraints (from CLAUDE.md)

- Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic, asyncpg — fixed, no substitutions
- WeasyPrint for PDF, openpyxl for Excel — already decided in stack
- python-telegram-bot 21.x listed in CLAUDE.md but codebase uses raw httpx for Telegram (not python-telegram-bot) — continue the existing httpx pattern, do not introduce python-telegram-bot
- aiosmtplib for SMTP — must be added to pyproject.toml
- Celery Beat + redbeat for scheduling — already configured
- Chart.js for charts — CDN version 4.4.0 already included in positions template
- All DB changes via Alembic migrations
- Jinja2 + HTMX for all UI — no SPA
- Tailwind CSS hex palette (indigo primary, emerald success, red danger)
- Service layer coverage > 60% by iteration 4 (already past that iteration; maintain it)
- No inline style= except for dynamic width calculations

## Standard Stack

### Core (already in pyproject.toml)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| openpyxl | 3.1.5 | Excel report generation | Installed |
| redis.asyncio | 5.0.x | Redis cache for dashboard aggregation | Installed |
| celery-redbeat | 2.2.x | DB-backed Beat scheduling | Installed |
| Chart.js | 4.4.0 | Ad traffic trend charts | CDN in positions template |
| httpx | 0.27.x | Telegram API calls (sync + async) | Installed |

### Missing — Must Add
| Library | Version | Purpose | Install Command |
|---------|---------|---------|----------------|
| weasyprint | 62.x | HTML→PDF conversion | `pip install weasyprint>=62,<63` |
| aiosmtplib | 3.x | Async SMTP email delivery | `pip install aiosmtplib>=3,<4` |

**WeasyPrint system deps (Docker):** `apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info`

These are needed in the Dockerfile for the FastAPI app container (not the crawler worker). The crawler worker already uses Playwright base image which may already have them.

**Installation additions to pyproject.toml:**
```
weasyprint>=62,<63
aiosmtplib>=3,<4
```

## Architecture Patterns

### Recommended Project Structure Additions
```
app/
├── services/
│   ├── dashboard_service.py     # per-project aggregation (new)
│   ├── report_service.py        # extend: add PDF generation, CR% delta
│   ├── morning_digest_service.py # cross-project digest (new)
│   └── smtp_service.py          # aiosmtplib wrapper (new)
├── tasks/
│   ├── report_tasks.py          # morning digest + weekly report tasks (new)
│   └── digest_tasks.py          # extend: add scheduled report delivery
├── templates/
│   ├── dashboard/
│   │   └── index.html           # rewrite: project table + cache
│   ├── reports/
│   │   ├── brief.html           # PDF brief template (new)
│   │   ├── detailed.html        # PDF detailed template (new)
│   │   └── generate.html        # UI: select type + download (new)
│   └── ads/
│       ├── index.html           # ad traffic page: upload + compare + chart (new)
│       └── partials/
│           └── comparison_table.html  # HTMX partial (new)
├── models/
│   └── report_schedule.py       # global delivery schedule model (new)
└── routers/
    └── reports.py               # extend: add UI routes, PDF endpoint
```

### Pattern 1: Per-Project Dashboard Cache
**What:** Dashboard aggregates metrics for each project row via a single SQL query joining projects → tasks → keyword_positions. Cached at `dashboard:projects_table` key with 300s TTL.
**When to use:** Any cross-project aggregation that would run N queries for N projects.
**Example:**
```python
# Source: existing overview_service.py pattern
CACHE_KEY_PROJECTS = "dashboard:projects_table"
CACHE_TTL = 300

async def projects_table(db: AsyncSession) -> list[dict]:
    r = await _get_redis()
    try:
        cached = await r.get(CACHE_KEY_PROJECTS)
        if cached:
            return json.loads(cached)
        # Single SQL with LEFT JOINs + GROUP BY project
        result = await db.execute(text("""
            SELECT
                p.id, p.name, p.status, s.name AS site_name,
                COUNT(t.id) FILTER (WHERE t.status IN ('open','in_progress')) AS active_tasks,
                COUNT(t.id) FILTER (WHERE t.status = 'in_progress') AS in_progress_tasks,
                -- position distribution from latest check per project's site
                ...
            FROM projects p
            JOIN sites s ON s.id = p.site_id
            LEFT JOIN seo_tasks t ON t.project_id = p.id
            WHERE p.status != 'archived'
            GROUP BY p.id, s.name
            ORDER BY p.created_at DESC
        """))
        data = [dict(r) for r in result.mappings().all()]
        await r.set(CACHE_KEY_PROJECTS, json.dumps(data, default=str), ex=CACHE_TTL)
        return data
    finally:
        await r.aclose()
```

### Pattern 2: WeasyPrint PDF from Jinja2 Template
**What:** Render a Jinja2 template to HTML string, pass to WeasyPrint, return bytes.
**When to use:** All PDF generation in this phase.
**Example:**
```python
# Source: WeasyPrint 62.x official docs
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

def generate_pdf(template_name: str, context: dict) -> bytes:
    env = Environment(loader=FileSystemLoader("app/templates/reports"))
    html_str = env.get_template(template_name).render(**context)
    pdf_bytes = HTML(string=html_str, base_url="app/static/").write_pdf()
    return pdf_bytes
```

**Important:** WeasyPrint renders synchronously. Wrap in `asyncio.get_event_loop().run_in_executor(None, generate_pdf, ...)` when calling from async FastAPI handler, or offload to Celery task.

### Pattern 3: Morning Digest Celery Task
**What:** Celery Beat task fired at configurable time, aggregates cross-project metrics, sends Telegram text message.
**When to use:** Daily morning digest (D-07, D-08, D-09).
**Example:**
```python
@celery_app.task(
    name="app.tasks.report_tasks.send_morning_digest",
    bind=True,
    max_retries=2,
    queue="default",
    soft_time_limit=60,
)
def send_morning_digest(self) -> dict:
    from app.database import get_sync_db
    from app.services.morning_digest_service import build_morning_digest
    from app.services.telegram_service import send_message_sync
    with get_sync_db() as db:
        msg = build_morning_digest(db)
        sent = send_message_sync(msg)
    return {"sent": sent}
```

### Pattern 4: ReportSchedule — Global Schedule Model
**What:** New model for the global delivery schedule (morning digest time, weekly report day/time).
**When to use:** DASH-03, DASH-04.

The existing `DigestSchedule` model is per-site and tied to the weekly crawl change digest. A new `ReportSchedule` table (single row, global) stores the morning digest time and weekly summary parameters.

```python
class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    id: int  # PK, always 1 (singleton row)
    morning_digest_enabled: bool
    morning_hour: int
    morning_minute: int
    weekly_report_enabled: bool
    weekly_day_of_week: int  # 1=Mon..7=Sun
    weekly_hour: int
    weekly_minute: int
    smtp_to: str | None  # admin email, nullable
    updated_at: datetime
```

### Pattern 5: Ad Traffic CR% Delta Computation
**What:** The existing `ad_traffic_comparison()` lacks CR% and cost-per-conversion. Extend it.
**When to use:** ADS-02 requirement.
```python
# Extend the comparison dict per source:
cr_a = (va["conversions"] / va["sessions"] * 100) if va["sessions"] else 0
cr_b = (vb["conversions"] / vb["sessions"] * 100) if vb["sessions"] else 0
cpc_a = (va["cost"] / va["conversions"]) if va["conversions"] else None
cpc_b = (vb["cost"] / vb["conversions"]) if vb["conversions"] else None
```

### Pattern 6: Chart.js Trend Chart for Ad Traffic
**What:** Fetch aggregate data per source per week/month from `/reports/sites/{site_id}/ad-traffic/trend`, render with Chart.js.
**When to use:** ADS-03 requirement.

Chart.js 4.4.0 is already loaded in positions/index.html via CDN. The ads template should include the same CDN script tag since it will not extend a template that auto-loads it (base.html does not include Chart.js globally).

```html
<!-- In ads/index.html -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<canvas id="trend-chart" height="300"></canvas>
<script>
const ctx = document.getElementById('trend-chart').getContext('2d');
new Chart(ctx, {
  type: 'line',
  data: {
    labels: {{ period_labels | tojson }},
    datasets: {{ chart_datasets | tojson }}  // one dataset per source
  },
  options: { responsive: true, ... }
});
</script>
```

### Anti-Patterns to Avoid

- **N+1 queries in dashboard:** Do not call `site_overview()` per project row as the current handler does for N sites. Replace with a single aggregated SQL query.
- **Blocking WeasyPrint in async handler:** WeasyPrint is synchronous. Never call it directly in an `async def` FastAPI route without `run_in_executor`.
- **Telegram message > 4096 chars:** Morning digest must truncate. The `format_weekly_digest()` pattern in `telegram_service.py` already handles this — replicate it.
- **Missing base_url in WeasyPrint:** Without `base_url`, CSS `url()` references and `@font-face` fail silently. Always pass `base_url` pointing to static files.
- **PDF chart rendering:** WeasyPrint cannot execute JavaScript. Charts in PDF must be rendered as static SVG or PNG images, not Chart.js canvas elements.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF generation | Custom HTML-to-PDF | WeasyPrint 62.x | CSS paged media, font rendering, pagination are extremely complex |
| Redis cache key expiry | Manual TTL tracking | `redis.asyncio.set(..., ex=TTL)` | Already proven pattern in overview_service.py |
| Celery Beat cron | File-based crontab | redbeat `RedBeatSchedulerEntry` | Survives container restart, already wired in celery_app.py |
| SMTP TLS handshake | Custom asyncio socket | aiosmtplib | TLS, AUTH, EHLO negotiation are error-prone to implement |
| Excel multi-sheet | Custom CSV | openpyxl Workbook | Already used in generate_excel_report() |
| Period delta % | Custom formula | Extend existing `_delta()` in report_service.py | Already handles zero-division |

**Key insight:** Most infrastructure is already built. The phase is primarily UI + thin service extensions, not new infrastructure.

## Common Pitfalls

### Pitfall 1: WeasyPrint Charts in PDF
**What goes wrong:** Developer puts a `<canvas>` with Chart.js in the PDF template; the PDF renders a blank canvas.
**Why it happens:** WeasyPrint renders HTML without JavaScript execution.
**How to avoid:** For PDF charts, use SVG (rendered server-side via a charting library) or pass pre-rendered base64 PNG images as `<img src="data:image/png;base64,...">` generated with `matplotlib` or similar. For this phase, the brief report is 1-2 pages — consider using a simple SVG bar chart drawn from the position data, or omit charts from the brief and include only in the detailed report with static bar representation using CSS.
**Warning signs:** PDF opens but chart area is blank.

### Pitfall 2: Dashboard Loads Slowly with N Site Queries
**What goes wrong:** The existing `ui_dashboard` handler calls `site_overview()` per site in a loop — O(N) queries for N sites.
**Why it happens:** The current code iterates `sites[:20]` and calls `await site_overview(db, s.id)` for each, which runs a SQL query per site.
**How to avoid:** Replace with a single SQL query joining all tables and cache the result. Use the Redis cache pattern from `overview_service.py`.
**Warning signs:** Dashboard route takes >1s per additional site in the loop.

### Pitfall 3: aiosmtplib in Celery Sync Task
**What goes wrong:** Celery tasks are synchronous by default. `aiosmtplib` is async-only.
**Why it happens:** Developer imports `aiosmtplib` and tries to `await` inside a sync Celery task function.
**How to avoid:** Either (a) use `asyncio.run(send_email(...))` inside the sync Celery task, or (b) create an `smtp_service.send_email_sync()` wrapper that calls `asyncio.run()`. Pattern (b) is cleaner and consistent with `telegram_service.send_message_sync()`.
**Warning signs:** `RuntimeError: no running event loop` in Celery worker logs.

### Pitfall 4: CR% Division by Zero
**What goes wrong:** CR% = conversions / sessions * 100 raises ZeroDivisionError when sessions = 0.
**Why it happens:** Some ad sources may have days with zero sessions in a period.
**How to avoid:** Always guard: `cr = (conversions / sessions * 100) if sessions > 0 else 0.0`.
**Warning signs:** 500 error when comparing periods with sparse data.

### Pitfall 5: ReportSchedule Singleton Row
**What goes wrong:** Multiple rows created in `report_schedules` table; Beat registers duplicate tasks.
**Why it happens:** UPSERT logic not enforced at DB level.
**How to avoid:** Add `UNIQUE` constraint on a fixed `config_key = 'global'` column, or use `id = 1` as a fixed PK with `INSERT ... ON CONFLICT DO UPDATE`.
**Warning signs:** Two morning digest Telegram messages per day.

### Pitfall 6: PDF base_url for Static Assets
**What goes wrong:** Logo/CSS fails to load in PDF; logo missing, layout broken.
**Why it happens:** WeasyPrint resolves relative URLs against base_url; if not set, it uses the current working directory which differs in Docker.
**How to avoid:** Always call `HTML(string=html_str, base_url="/projects/test/app/static/")` or use absolute HTTPS URLs for all assets in the PDF template.

## Code Examples

### Dashboard Per-Project Aggregate SQL (single query)
```sql
-- Source: extended from existing overview_service.py pattern
SELECT
    p.id,
    p.name,
    p.status,
    s.name AS site_name,
    p.site_id,
    COUNT(t.id) FILTER (WHERE t.status IN ('open', 'assigned')) AS open_tasks,
    COUNT(t.id) FILTER (WHERE t.status = 'in_progress') AS in_progress_tasks,
    COUNT(t.id) FILTER (WHERE t.status = 'review') AS review_tasks,
    -- latest position snapshot for the project's site
    (SELECT COUNT(*) FROM keyword_positions kp2
        WHERE kp2.site_id = p.site_id
          AND kp2.position <= 10
          AND kp2.checked_at = (
            SELECT MAX(checked_at) FROM keyword_positions WHERE site_id = p.site_id
          )
    ) AS top10_count,
    p.created_at
FROM projects p
JOIN sites s ON s.id = p.site_id
LEFT JOIN seo_tasks t ON t.project_id = p.id
WHERE p.status != 'archived'
GROUP BY p.id, s.name, p.site_id
ORDER BY p.created_at DESC
```

Note: Position subquery per row may be expensive at 50 projects. Optimize by computing per-site TOP-10 once in a CTE.

### WeasyPrint PDF Generation (async-safe)
```python
# Source: WeasyPrint 62.x docs + asyncio executor pattern
import asyncio
from functools import partial
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

def _render_pdf_sync(template_path: str, context: dict, base_url: str) -> bytes:
    env = Environment(loader=FileSystemLoader("app/templates"))
    html = env.get_template(template_path).render(**context)
    return HTML(string=html, base_url=base_url).write_pdf()

async def generate_pdf(template_path: str, context: dict) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        partial(_render_pdf_sync, template_path, context, "app/static/")
    )
```

### Morning Digest Telegram Message Format
```python
# Source: pattern from telegram_service.format_weekly_digest()
def format_morning_digest(projects: list[dict], date_str: str) -> str:
    lines = [
        f"☀️ <b>SEO Morning Digest — {date_str}</b>",
        "",
    ]
    for p in projects[:10]:  # cap at 10 projects for message length
        status_icon = "🟢" if p["in_progress_tasks"] > 0 else "⚪"
        lines.append(
            f"{status_icon} <b>{p['name']}</b> — "
            f"TOP-10: {p['top10_count']}, "
            f"Tasks: {p['open_tasks']} open / {p['in_progress_tasks']} in progress"
        )
    lines.append("")
    lines.append(f"🔗 <a href='{settings.APP_URL}/ui/dashboard'>Open Dashboard</a>")
    msg = "\n".join(lines)
    return msg[:4000]  # Telegram 4096-char limit
```

Note: `settings.APP_URL` does not currently exist in `app/config.py` — add it as an optional field with a default.

### SMTP Sync Wrapper for Celery
```python
# Source: aiosmtplib docs + existing send_message_sync() pattern
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

async def _send_email_async(to: str, subject: str, body_html: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html"))
    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        use_tls=True,
        timeout=30,
    )
    return True

def send_email_sync(to: str, subject: str, body_html: str) -> bool:
    try:
        asyncio.run(_send_email_async(to, subject, body_html))
        return True
    except Exception as exc:
        logger.warning("SMTP send failed", error=str(exc))
        return False
```

### Ad Traffic Trend API Endpoint
```python
@router.get("/sites/{site_id}/ad-traffic/trend")
async def ad_traffic_trend(
    site_id: uuid.UUID,
    granularity: str = "weekly",  # "weekly" | "monthly"
    db: AsyncSession = Depends(get_db),
) -> dict:
    # GROUP BY source + date_trunc(granularity, traffic_date)
    # Returns {labels: [...], datasets: [{label: source, data: [...]}]}
    ...
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| PDF via browser print | WeasyPrint 62.x (CSS paged media) | Server-side, no browser launch overhead |
| Chart.js 3.x | Chart.js 4.4.0 (already in codebase) | Breaking changes: dataset `label` required, `tension` replaces `lineTension` |
| Celery file-based Beat | redbeat (Redis-backed) | Survives container restart, already configured |
| Blocking SMTP | aiosmtplib 3.x | Non-blocking from Celery via asyncio.run() |

**Note on Chart.js 4.4.0:** Already loaded via CDN in `app/templates/positions/index.html`. The base template does NOT include it globally — each template that needs Chart.js must include the `<script>` tag.

## Open Questions

1. **Charts in PDF reports**
   - What we know: WeasyPrint cannot render JavaScript canvas charts
   - What's unclear: Best lightweight approach for server-side chart rendering in PDF — SVG via simple template math, matplotlib PNG, or omit charts from brief/detailed PDF entirely
   - Recommendation: For the brief (1-2 pages), use a CSS-only position distribution bar (pure HTML/CSS, no JS needed). For the detailed PDF, embed a pre-computed SVG bar chart from the position distribution data. Avoids `matplotlib` dependency.

2. **APP_URL for Telegram links**
   - What we know: `settings` does not have `APP_URL`
   - What's unclear: Should the morning digest include a link back to the dashboard?
   - Recommendation: Add `APP_URL: str = "http://localhost:8000"` to `app/config.py` Settings. Used in Telegram digest links.

3. **SMTP credentials in config**
   - What we know: No SMTP settings in `app/config.py` currently
   - What's unclear: Whether user has SMTP configured
   - Recommendation: Add optional SMTP settings to config (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM) with empty defaults. SMTP delivery silently skips if not configured, matching the Telegram pattern.

4. **Report schedule UI location**
   - What we know: No existing report schedule UI; digest schedules exist per-site in monitoring
   - What's unclear: Where to expose the morning digest schedule config in the UI
   - Recommendation: Add a "Reports" subsection to the Settings sidebar, URL `/ui/admin/report-schedule`. Single form: toggle daily digest on/off, set send time, toggle weekly summary, set email recipient.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10 | Runtime | Yes | 3.10.12 | N/A (3.12 per CLAUDE.md, but 3.10 is what is installed) |
| openpyxl | Excel reports | Yes | 3.1.5 | — |
| redis.asyncio | Dashboard cache | Yes | 5.0.x | — |
| celery-redbeat | Beat scheduling | Yes | 2.2.x | — |
| Chart.js | Ad traffic charts | Yes (CDN) | 4.4.0 | — |
| WeasyPrint | PDF generation | No | — | Must install + add to pyproject.toml |
| aiosmtplib | SMTP delivery | No | — | Must install + add to pyproject.toml |
| Pango/Cairo (system) | WeasyPrint | Unknown | — | Must install via apt in Dockerfile |

**Missing dependencies with no fallback:**
- `weasyprint` — required for DASH-02 PDF export; no alternative in the stack
- `aiosmtplib` — required for DASH-03 SMTP delivery; without it only Telegram delivery works

**Missing dependencies with fallback:**
- System libs (Pango/Cairo) for WeasyPrint — if Dockerfile cannot install them, fall back to a simpler approach: generate the PDF by calling a Celery task that uses a subprocess to a headless browser, but this contradicts the stack — better to ensure WeasyPrint system deps are in Dockerfile.

**Note on Python version:** CLAUDE.md specifies Python 3.12 but the running environment shows 3.10.12. This discrepancy does not affect implementation — the Docker container uses the configured version. Code should remain 3.10+ compatible (no 3.12-only syntax).

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `app/services/overview_service.py`, `app/services/report_service.py`, `app/services/digest_service.py`, `app/services/telegram_service.py` — existing patterns verified
- Codebase inspection: `app/celery_app.py` — Celery + redbeat configuration verified
- Codebase inspection: `app/models/ad_traffic.py`, `app/models/change_monitoring.py` — data model state verified
- Codebase inspection: `app/routers/reports.py` — existing endpoints verified
- Codebase inspection: `app/templates/positions/index.html` — Chart.js 4.4.0 CDN load pattern verified
- Codebase inspection: `app/templates/dashboard/index.html` — current dashboard template verified
- Codebase inspection: `pyproject.toml` — dependency gap (no weasyprint, no aiosmtplib) verified
- CLAUDE.md: WeasyPrint 62.x + openpyxl + aiosmtplib + Chart.js stack confirmed

### Secondary (MEDIUM confidence)
- WeasyPrint 62.x docs: `HTML(string=..., base_url=...).write_pdf()` API pattern — from training knowledge (Aug 2025), consistent with CLAUDE.md recommendation
- aiosmtplib 3.x docs: `aiosmtplib.send()` function API — from training knowledge
- Chart.js 4.4.0: `new Chart(ctx, {type, data, options})` API — verified in existing codebase usage

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from pyproject.toml and installed packages
- Architecture: HIGH — existing patterns directly observed in codebase
- Pitfalls: HIGH — WeasyPrint/async/cache issues are well-known and observed from codebase structure
- Environment gaps: HIGH — verified by running pip show and checking pyproject.toml

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable stack, 30-day horizon)
