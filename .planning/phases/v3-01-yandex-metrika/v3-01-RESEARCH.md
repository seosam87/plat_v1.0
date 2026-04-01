# Phase v3-01: Yandex Metrika — Research

**Researched:** 2026-04-01
**Phase:** v3-01-yandex-metrika

---

## 1. Yandex Metrika API

### Authentication

The Metrika Stat API uses an OAuth token passed in the `Authorization` header. Despite being called OAuth, it is a static bearer token — the user generates it once at `https://oauth.yandex.com/` and it does not expire unless revoked. This matches decision D-01 ("API-токен (статический)").

**Header format (identical to Yandex Webmaster):**
```
Authorization: OAuth <token>
```

This is the same pattern already used in `yandex_webmaster_service.py` (`_headers()` returns `{"Authorization": f"OAuth {token}"}`). No client_id/secret needed for the static token approach.

### Stat Endpoints

Base URL: `https://api-metrika.yandex.net/stat/v1/`

Two endpoints are needed for this phase:

| Endpoint | Purpose |
|----------|---------|
| `GET /stat/v1/data` | Table report — traffic by page, aggregated over a date range |
| `GET /stat/v1/data/bytime` | Time-series report — daily traffic for chart rendering |

Both accept the same core parameters.

**Core request parameters:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `ids` | int | Yes | Metrika counter ID (= `metrika_counter_id` on Site model) |
| `metrics` | string | Yes | Comma-separated metric names |
| `dimensions` | string | No | Comma-separated dimension names for grouping |
| `date1` | string | No | Start date `YYYY-MM-DD` or `NdaysAgo`. Default: `6daysAgo` |
| `date2` | string | No | End date. Default: `today` |
| `filters` | string | No | Segmentation filter expression |
| `limit` | int | No | Rows per page, max 100 000. Default: 100 |
| `offset` | int | No | 1-based row offset for pagination |
| `sort` | string | No | Sort by metric/dimension, prefix `-` for descending |
| `accuracy` | string | No | Sampling accuracy (`full`, `1`, `0.1`, etc.) |
| `group` | string | No | For `/bytime` only: `day`, `week`, `month` |

**For `/data/bytime`**, add `group=day` to get per-day rows.

### Dimensions and Metrics for This Phase

**Dimensions (grouping):**

| Dimension | Description |
|-----------|-------------|
| `ym:s:startURL` | Landing page URL — the entry page of each session |
| `ym:s:date` | Session date (used by `/bytime` automatically) |
| `ym:s:<attribution>TrafficSource` | Traffic source category (use `ym:s:trafficSource` for last-touch) |
| `ym:s:<attribution>SearchEngine` | Search engine name |

For page-level traffic breakdown, the primary dimension is `ym:s:startURL`. This groups sessions by the URL where the visitor entered the site.

**Metrics (D-05):**

| Metric | Description |
|--------|-------------|
| `ym:s:visits` | Total sessions |
| `ym:s:bounceRate` | Bounce rate (%) |
| `ym:s:pageDepth` | Average pages per session |
| `ym:s:avgVisitDurationSeconds` | Average session duration in seconds |
| `ym:s:users` | Unique users (optional, for widget) |

### Filter for Organic/Search Traffic (D-06)

Decision D-06 requires search traffic aggregated across all engines (no Yandex/Google breakdown). The filter expression:

```
ym:s:trafficSource=='organic'
```

To exclude bot traffic (strongly recommended for accurate bounce rate and engagement metrics):

```
ym:s:trafficSource=='organic' AND ym:s:isRobot=='No'
```

**Full example request — page traffic table:**
```
GET https://api-metrika.yandex.net/stat/v1/data
  ?ids=<counter_id>
  &date1=2026-03-01
  &date2=2026-03-31
  &dimensions=ym:s:startURL
  &metrics=ym:s:visits,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds
  &filters=ym:s:trafficSource=='organic' AND ym:s:isRobot=='No'
  &sort=-ym:s:visits
  &limit=500
  &offset=1
Authorization: OAuth <token>
```

**Full example request — daily time-series for chart:**
```
GET https://api-metrika.yandex.net/stat/v1/data/bytime
  ?ids=<counter_id>
  &date1=2026-01-01
  &date2=2026-03-31
  &metrics=ym:s:visits,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds
  &filters=ym:s:trafficSource=='organic' AND ym:s:isRobot=='No'
  &group=day
Authorization: OAuth <token>
```

Note: `/bytime` does not support the `dimensions` parameter in the same way — it returns date-bucketed rows without page-level grouping. For per-page time-series you would need to call `/data/bytime` once per page URL filtered, which is expensive. The pragmatic approach: store daily site-aggregate snapshots and page-aggregate snapshots separately (see Data Model section).

### Rate Limits & Pagination

| Limit | Value |
|-------|-------|
| Requests per second (per IP) | 30 |
| Requests per day (per user) | 5 000 |
| Concurrent requests (per user) | 3 |
| Requests per 5 minutes (per user) | 200 |
| Rows per request (`limit`) | max 100 000 |
| HTTP 420 | returned when any quota is exceeded |

**Pagination:** Use `offset` (1-based). Pattern: fetch with `limit=500`, check `total_rows` in response, loop incrementing `offset` by `limit` until all rows fetched. Same approach as `gsc_service.py` `start_row` pattern.

For a typical site with 100–500 organic landing pages, a single request with `limit=500` is sufficient. No pagination loop needed for most cases.

### Response Format

```json
{
  "query": { "ids": [12345], "date1": "2026-03-01", "date2": "2026-03-31", ... },
  "data": [
    {
      "dimensions": [{"id": "https://example.com/page-1/", "name": "https://example.com/page-1/"}],
      "metrics": [1240, 32.5, 3.2, 185.0]
    }
  ],
  "total_rows": 87,
  "total_rows_rounded": false,
  "sampled": false,
  "sample_share": 1.0,
  "totals": [[45200, 28.1, 2.9, 172.0]],
  "min": [...],
  "max": [...],
  "data_lag": 86400
}
```

Key fields:
- `data[i].dimensions[0].name` — page URL string
- `data[i].metrics` — array of metric values in the same order as the `metrics` parameter
- `total_rows` — use for pagination loop
- `sampled` — if `true`, results are sampled; set `accuracy=full` to force exact counts (slower)
- `data_lag` — delay in seconds; Metrika typically has 1-day lag, so `date2=yesterday` is safer than `today`

---

## 2. Data Model Design

### Traffic Snapshot Table

Two tables are needed to support D-04 (page-level + site aggregate), D-07 (period comparison), D-09 (traffic page with table), and D-11 (site overview widget).

**Table 1: `metrika_traffic_daily`** — daily site-aggregate, for the chart time-series and widget

```sql
CREATE TABLE metrika_traffic_daily (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id     UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    traffic_date DATE NOT NULL,
    visits      INTEGER NOT NULL DEFAULT 0,
    users       INTEGER NOT NULL DEFAULT 0,
    bounce_rate NUMERIC(5,2),           -- percent, e.g. 34.50
    page_depth  NUMERIC(5,2),           -- e.g. 3.20
    avg_duration_seconds INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (site_id, traffic_date)
);
CREATE INDEX ix_metrika_traffic_daily_site_date
    ON metrika_traffic_daily (site_id, traffic_date DESC);
```

**Table 2: `metrika_traffic_pages`** — per-page aggregate over a date range snapshot

```sql
CREATE TABLE metrika_traffic_pages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id      UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end   DATE NOT NULL,
    page_url     TEXT NOT NULL,
    visits       INTEGER NOT NULL DEFAULT 0,
    bounce_rate  NUMERIC(5,2),
    page_depth   NUMERIC(5,2),
    avg_duration_seconds INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (site_id, period_start, period_end, page_url)
);
CREATE INDEX ix_metrika_traffic_pages_site_period
    ON metrika_traffic_pages (site_id, period_start, period_end);
```

**Table 3: `metrika_events`** — manual event markers for chart overlay (D-10)

```sql
CREATE TABLE metrika_events (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id    UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    event_date DATE NOT NULL,
    label      VARCHAR(255) NOT NULL,
    color      VARCHAR(20) DEFAULT '#6b7280',  -- CSS color for annotation
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_metrika_events_site_date
    ON metrika_events (site_id, event_date);
```

**Site model additions** (new nullable columns on `sites` table):

```python
metrika_counter_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
metrika_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet-encrypted
```

### Storage Strategy

**Persist:**
- Daily site-aggregate snapshots (`metrika_traffic_daily`) — lightweight, enables chart and widget
- Per-page snapshots per requested period (`metrika_traffic_pages`) — enables table view and delta computation
- Manual event markers (`metrika_events`) — user-managed, no API interaction

**Query on-demand (D-08):**
- No auto-collection via Celery Beat
- Triggered by user button click → Celery task → calls API → upserts into DB
- For period comparison: user selects two date ranges → system fetches both via API and computes delta in-memory, then optionally caches the snapshot rows

**Do not store:**
- Raw API responses (too verbose)
- Per-page daily time-series (too many rows; not in scope for this phase)

---

## 3. Period Comparison

### Approach (D-07)

User selects Period A (`date_a_start` to `date_a_end`) and Period B (`date_b_start` to `date_b_end`). The system:

1. Fetches aggregated page-level data for period A (one API call to `/stat/v1/data`)
2. Fetches aggregated page-level data for period B (one API call to `/stat/v1/data`)
3. Joins the two result sets on `page_url`
4. Computes delta: `visits_b - visits_a` (positive = growth, negative = decline)
5. Identifies "new traffic" pages: pages in B not in A (`visits_a = 0`)
6. Identifies "lost" pages: pages in A not in B (`visits_b = 0`)

**Python delta computation pattern (mirrors `position_service.compare_positions_by_date`):**

```python
def compute_period_delta(
    rows_a: list[dict],
    rows_b: list[dict],
) -> list[dict]:
    map_a = {r["page_url"]: r for r in rows_a}
    map_b = {r["page_url"]: r for r in rows_b}
    all_urls = set(map_a) | set(map_b)
    result = []
    for url in all_urls:
        a = map_a.get(url, {})
        b = map_b.get(url, {})
        visits_a = a.get("visits", 0)
        visits_b = b.get("visits", 0)
        result.append({
            "page_url": url,
            "visits_a": visits_a,
            "visits_b": visits_b,
            "visits_delta": visits_b - visits_a,
            "bounce_rate_a": a.get("bounce_rate"),
            "bounce_rate_b": b.get("bounce_rate"),
            "is_new": visits_a == 0 and visits_b > 0,
            "is_lost": visits_a > 0 and visits_b == 0,
        })
    return sorted(result, key=lambda r: -(r["visits_b"] or 0))
```

### Existing Patterns

- `position_service.compare_positions_by_date` — SQL-level FULL OUTER JOIN between two date snapshots; Metrika comparison is simpler (pure Python join, no SQL needed since both datasets are fetched fresh from API)
- `ad_traffic.py` model — stores `traffic_date`, `sessions`, `cost` per row; similar flat structure to `metrika_traffic_daily`
- Positions delta display in templates — `p.delta > 0` → green arrow, `p.delta < 0` → red arrow; reuse same pattern for visits delta

---

## 4. Chart.js Event Overlay

### Annotation Plugin

Chart.js 4.x (already loaded from CDN: `chart.js@4.4.0`) supports annotations via the separate `chartjs-plugin-annotation` plugin. Load from CDN:

```html
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
```

The plugin must be loaded after `chart.js`. It auto-registers itself globally.

### Implementation Pattern

Vertical line event markers are configured via `plugins.annotation.annotations` in the Chart.js options. Each event becomes a named annotation object.

**Full working example for traffic chart with event overlays:**

```javascript
// events = [{date: "2026-02-15", label: "Schema.org добавлена", color: "#7c3aed"}, ...]
function buildAnnotations(events) {
  const annotations = {};
  events.forEach((ev, i) => {
    annotations['event_' + i] = {
      type: 'line',
      xMin: ev.date,   // must match a label in the chart's labels array
      xMax: ev.date,
      borderColor: ev.color || '#6b7280',
      borderWidth: 2,
      borderDash: [4, 4],
      label: {
        display: true,
        content: ev.label,
        backgroundColor: 'rgba(0,0,0,0.75)',
        color: '#ffffff',
        position: 'start',   // top of line
        font: { size: 11 },
        padding: 4,
        borderRadius: 4,
      }
    };
  });
  return annotations;
}

const ctx = document.getElementById('traffic-chart').getContext('2d');
const chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: labels,   // array of 'YYYY-MM-DD' strings
    datasets: [{
      label: 'Визиты (органика)',
      data: visits,
      borderColor: '#4f46e5',
      backgroundColor: 'rgba(79,70,229,.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 2,
    }]
  },
  options: {
    responsive: true,
    scales: {
      x: { title: { display: true, text: 'Дата' } },
      y: { beginAtZero: true, title: { display: true, text: 'Визиты' } }
    },
    plugins: {
      legend: { display: false },
      annotation: {
        annotations: buildAnnotations(events)
      }
    }
  }
});
```

**CRUD for event markers** — simple HTMX form: POST `/metrika/{site_id}/events` with `event_date` + `label` + `color`, returns updated annotations JSON, JS re-renders chart. DELETE via button. No page reload needed.

### Date Format Note

The chart's `labels` array will be `['2026-01-01', '2026-01-02', ...]`. For `xMin`/`xMax` to resolve correctly, the event date string must exactly match a label value. Since the chart always covers the full fetched date range, any event date within range will find its label.

---

## 5. Codebase Integration Patterns

### Service Layer

**Pattern:** `app/services/{module}_service.py` — module-level async functions, `db: AsyncSession` as first arg for DB operations, `httpx.AsyncClient` for API calls.

**New file:** `app/services/metrika_service.py`

Key functions to implement:
```python
async def fetch_daily_traffic(counter_id: str, token: str, date1: str, date2: str) -> list[dict]
async def fetch_page_traffic(counter_id: str, token: str, date1: str, date2: str, limit: int = 500) -> list[dict]
async def save_daily_snapshots(db: AsyncSession, site_id: UUID, rows: list[dict]) -> int
async def save_page_snapshots(db: AsyncSession, site_id: UUID, period_start: date, period_end: date, rows: list[dict]) -> int
async def get_daily_traffic(db: AsyncSession, site_id: UUID, days: int = 90) -> list[dict]
async def get_page_traffic(db: AsyncSession, site_id: UUID, period_start: date, period_end: date) -> list[dict]
async def compute_period_delta(rows_a: list[dict], rows_b: list[dict]) -> list[dict]
async def get_events(db: AsyncSession, site_id: UUID) -> list[dict]
async def create_event(db: AsyncSession, site_id: UUID, event_date: date, label: str, color: str) -> MetrikaEvent
async def delete_event(db: AsyncSession, event_id: UUID) -> None
```

**Celery task:** `app/tasks/metrika_tasks.py` — `fetch_metrika_data` task triggered by button click (D-08), wraps `fetch_daily_traffic` + `fetch_page_traffic` + save calls.

**API call pattern** (from `yandex_webmaster_service.py`):
```python
API_BASE = "https://api-metrika.yandex.net/stat/v1"
TIMEOUT = 30.0

def _headers(token: str) -> dict:
    return {"Authorization": f"OAuth {token}"}

async def fetch_page_traffic(counter_id: str, token: str, date1: str, date2: str, limit: int = 500) -> list[dict]:
    params = {
        "ids": counter_id,
        "date1": date1,
        "date2": date2,
        "dimensions": "ym:s:startURL",
        "metrics": "ym:s:visits,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds",
        "filters": "ym:s:trafficSource=='organic' AND ym:s:isRobot=='No'",
        "sort": "-ym:s:visits",
        "limit": limit,
        "offset": 1,
    }
    all_rows = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        while True:
            resp = await client.get(f"{API_BASE}/data", params=params, headers=_headers(token))
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("data", [])
            if not rows:
                break
            metric_keys = ["visits", "bounce_rate", "page_depth", "avg_duration_seconds"]
            for row in rows:
                url = row["dimensions"][0]["name"]
                metrics = row["metrics"]
                all_rows.append(dict(zip(["page_url"] + metric_keys, [url] + metrics)))
            total = data.get("total_rows", 0)
            if len(all_rows) >= total:
                break
            params["offset"] += limit
    return all_rows
```

### Router Pattern

**Pattern:** `app/routers/{module}.py` — `APIRouter(prefix="/{module}", tags=["{module}"])`. Mix of JSON API endpoints and `HTMLResponse` endpoints for HTMX partial rendering.

**New file:** `app/routers/metrika.py`

Endpoints:
```
GET  /metrika/{site_id}               → HTML page (traffic page, D-09)
POST /metrika/{site_id}/fetch         → JSON, triggers Celery fetch task
GET  /metrika/{site_id}/daily         → JSON, returns daily snapshot for chart
GET  /metrika/{site_id}/pages         → JSON, returns page table for period
GET  /metrika/{site_id}/compare       → JSON, period comparison delta
POST /metrika/{site_id}/events        → JSON, create event marker
DELETE /metrika/{site_id}/events/{id} → JSON, delete event marker
GET  /metrika/{site_id}/widget        → HTML partial, site overview widget (D-11)
```

Settings endpoints (add to sites router or metrika router):
```
PUT  /metrika/{site_id}/settings      → save counter_id + token
```

**Registration in `app/main.py`:**
```python
from app.routers import metrika
app.include_router(metrika.router)
```

### Template/UI Pattern

**Pattern:** `app/templates/{module}/` directory with Jinja2 templates extending `base.html`. HTMX for partial updates without full page reload. Tailwind CSS hex values from existing color palette.

**New files:**
- `app/templates/metrika/index.html` — main traffic page (table + chart + event manager)
- `app/templates/metrika/_widget.html` — site overview widget partial

**Navigation addition** in `base.html`:
```html
<a href="/ui/metrika">Traffic</a>
```

**HTMX button trigger pattern** (from positions template):
```html
<button class="btn btn-primary"
  hx-post="/metrika/{{ site_id }}/fetch"
  hx-swap="none"
  onclick="this.textContent='Загрузка...'; this.disabled=true">
  Загрузить данные Метрики
</button>
```

**Chart.js** is already used at `positions/index.html` loaded via CDN `chart.js@4.4.0`. The traffic chart requires the additional `chartjs-plugin-annotation` CDN load.

**Site Overview widget** (D-11) — add to `sites/detail.html` via HTMX:
```html
<div hx-get="/metrika/{{ site.id }}/widget" hx-trigger="load" hx-swap="innerHTML"></div>
```

### Crypto Pattern

Decision D-03 deferred to implementation. Recommendation: **use Fernet encryption**, same as `encrypted_app_password` on Site. Reasons:
1. `crypto_service.py` already has `encrypt()`/`decrypt()` functions — zero new code
2. The Metrika token grants read access to traffic data for all sites on that counter; if the DB leaks, plaintext tokens are immediately exploitable
3. The threat model (internal tool, single VPS) does not require plaintext for performance reasons

**Token storage pattern:**
```python
# When saving settings
site.metrika_token = encrypt(raw_token)

# When using token for API calls
raw_token = decrypt(site.metrika_token)
```

---

## 6. Risks & Considerations

### API Data Lag

Metrika's `data_lag` field indicates data may be 1+ days behind. The `/stat/v1/data` response includes this value in seconds. Always use `date2=yesterday` (not `today`) for accurate results, or inform the user via UI that today's data may be incomplete.

### Sampling

For counters with high traffic, Metrika may return sampled results (`sampled: true`). Setting `accuracy=full` forces exact counts but makes queries slower and may hit rate limits faster. For this tool (managing 20–100 sites), sampling should not be an issue for most clients. Expose `sampled` flag in the fetch task result so the user is informed.

### Rate Limit Impact

The 200 requests/5-min limit is the binding constraint for bulk operations. Fetching 2 date ranges for one site = 2 requests. With 3 concurrent request limit, fetching all 100 sites in parallel is not possible. Strategy: fetch one site at a time (user-initiated per-site button), not bulk across all sites simultaneously. This avoids the rate limit problem entirely.

### Single API Key for Multiple Sites (D-02)

Each site has its own counter ID and token. Token is stored encrypted per-site on the Site model. If the user manages multiple sites under one Metrika account, they use the same token value but different counter IDs — both fields are stored independently per Site row.

### `ym:s:startURL` vs. Canonical URL

`startURL` is the actual URL the user landed on, including query strings and fragments. This may create many variants of the same page (e.g., `?utm_source=…`). Recommendation: normalize URLs by stripping query parameters before storing in `metrika_traffic_pages.page_url`. Discuss with user whether UTM-stripped or raw URLs are preferred.

### No `/bytime` + `dimensions` Combination

The `/bytime` endpoint does not support `dimensions` grouping by `startURL` — it returns site-aggregate time-series only. This means per-page daily time-series (e.g., "show traffic for /blog/ over 90 days") is not directly available. Options if needed later: (a) call `/data` with date range = 1 day for each day in a loop (expensive), or (b) use the Logs API (requires separate quota and setup). For Phase v3-01 scope, per-page time-series is not required — only site-aggregate chart + per-page aggregate table.

### Chart.js Annotation Plugin Version

The existing code loads `chart.js@4.4.0`. The annotation plugin must be version-compatible: use `chartjs-plugin-annotation@3.0.1` (compatible with Chart.js 4.x). Version 2.x is for Chart.js 3.x and will silently fail.

### Celery Task Failure Handling

Per project constraints (retry=3, site failure must not stop others): Metrika fetch Celery task should catch `httpx.HTTPStatusError` and log via loguru. HTTP 420 (rate limit) should trigger exponential backoff retry, not immediate failure. Use `self.retry(countdown=60)` on rate limit hit.

---

## RESEARCH COMPLETE
