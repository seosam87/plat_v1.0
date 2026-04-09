# Phase 21: Site Audit Intake - Research

**Researched:** 2026-04-09
**Domain:** HTMX form with section-level persistence, SQLAlchemy model with JSON fields, verification checklist from platform data
**Confidence:** HIGH

## Summary

Phase 21 adds a structured intake form for sites with 5 tabbed sections, section-by-section HTMX save, a verification checklist pulling real-time status from existing platform models, and an "intake complete" badge. The phase is architecturally straightforward — it follows the exact same patterns established in Phase 20 (CRM detail page with tab switching, HTMX partial saves, toast notifications) and introduces one new model (`SiteIntake`) with a 1:1 relationship to `Site`.

The primary technical challenge is the verification checklist (Tab 5), which queries across 4 different models/tables (Site, OAuthToken, SitemapEntry, CrawlJob) to derive 5 boolean statuses. The form sections themselves are simple — Tab 1 and Tab 3 are read-only displays, Tab 2 stores user-entered goals/competitors in JSON, and Tab 4 stores robots.txt notes.

**Primary recommendation:** Follow Phase 20 CRM patterns exactly — module-level async service functions, router with `Depends(get_db)` and `Depends(require_manager_or_above)`, Jinja2 templates with inline styles, JS tab switching, HTMX `hx-post` with `hx-swap="none"` and `HX-Trigger: showToast` response headers.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Tabbed layout (consistent with CRM detail page from Phase 20) -- 5 tabs on a single page
- **D-02:** 5 sections/tabs: Доступы, Цели и конкуренты, Аналитика (GSC/Метрика), Технический SEO, Чеклист верификации
- **D-03:** Explicit "Сохранить раздел" button at the bottom of each tab -- HTMX POST saves only that section, toast confirmation
- **D-04:** Tab 1 minimal approach -- show existing Site model data as read-only + link to site settings. No additional credential fields.
- **D-05:** Tab 2 fields: главная цель (textarea), целевые регионы (text), список конкурентов (dynamic list URLs up to 10), заметки (textarea)
- **D-06:** Tab 3 show GSC/Metrika/Yandex region as read-only indicators + links to configure
- **D-07:** Tab 4 show SEO plugin + sitemap status read-only, robots.txt notes editable
- **D-08:** Tab 5 static snapshot on load, "Перепроверить" button refreshes via HTMX
- **D-09:** 3 states per checklist item: Подключено (green), Не настроено (red), Не проверено (gray)
- **D-10:** Checklist items: WP подключен, GSC подключен, Метрика подключена, Sitemap найден, Краул выполнен
- **D-11:** Checkmark on saved/completed tabs. No progress bar.
- **D-12:** "Завершить intake" button always active. If not all sections saved, shows warning confirm dialog.
- **D-13:** Badge "Анкета заполнена" in site list and site detail page
- **D-14:** Completion sets status on intake record (not Site model), allows re-opening
- **D-15:** New `SiteIntake` model with JSON fields per section + section completion flags + overall status (draft/complete)
- **D-16:** One intake per site (1:1 via site_id FK). Creating intake implicit on first visit.

### Claude's Discretion
- Exact JSON schema for intake section data
- Pagination/filtering in intake list (if needed)
- Error handling for verification checklist items

### Deferred Ideas (OUT OF SCOPE)
- INTAKE-06: Auto-generate baseline crawl on intake completion
- INTAKE-07: Intake answers pre-populate proposal template variables (Phase 22 dependency)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INTAKE-01 | User can fill a structured intake form per site (access, goals, competitors, GSC/Metrika status, SEO setup) | SiteIntake model with JSON fields, 5-tab form layout, service layer for CRUD |
| INTAKE-02 | User can see a verification checklist (WP verified, GSC connected, Metrika linked, sitemap found, crawl done) | Checklist service querying Site, OAuthToken, SitemapEntry, CrawlJob models |
| INTAKE-03 | Checklist items auto-populate from existing platform data | Service functions querying across 4 existing tables; 3-state mapping logic |
| INTAKE-04 | User can save intake form as draft and resume later (section-by-section HTMX save) | HTMX hx-post per section endpoint, JSON field update per section, section_flags tracking |
| INTAKE-05 | Site shows "intake complete" status after form is finished | Status field on SiteIntake, badge rendering in site list and detail templates |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech Stack:** Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic, asyncpg, Jinja2 + HTMX -- fixed, no substitutions
- **Database:** PostgreSQL 16 only; all schema changes via Alembic migrations
- **Security:** `require_manager_or_above` for CRM writes (STATE.md decision)
- **Testing:** pytest + httpx AsyncClient; service layer coverage > 60%
- **Logging:** loguru, JSON format
- **UI pages < 3s:** No heavy queries; checklist is a snapshot, not live polling

## Standard Stack

No new libraries needed for this phase. Everything is already in the project.

### Core (existing, already installed)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| FastAPI | 0.115.x | Web framework + routing | In use |
| SQLAlchemy | 2.0.x | ORM with async session | In use |
| Alembic | 1.13.x | Database migrations | In use |
| Jinja2 | 3.1.x | Server-side templating | In use |
| HTMX | 2.0.x | Partial page updates | In use (CDN) |
| loguru | 0.7.x | Logging | In use |

No `npm install` or `pip install` needed.

## Architecture Patterns

### Recommended Project Structure

New files for this phase:
```
app/
├── models/
│   └── site_intake.py          # SiteIntake model
├── services/
│   └── intake_service.py       # CRUD + checklist queries
├── routers/
│   └── intake.py               # UI router /ui/sites/{id}/intake
└── templates/
    └── intake/
        ├── form.html           # Full page (extends base.html)
        ├── _tab_access.html    # Tab 1 partial (include)
        ├── _tab_goals.html     # Tab 2 partial
        ├── _tab_analytics.html # Tab 3 partial
        ├── _tab_technical.html # Tab 4 partial
        └── _tab_checklist.html # Tab 5 partial (also HTMX fragment)
```

### Pattern 1: SiteIntake Model (D-15, D-16)

**What:** Single SQLAlchemy model with JSON columns for flexible section data, boolean flags for section completion, and an enum status field.

**Recommended schema:**
```python
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IntakeStatus(str, PyEnum):
    draft = "draft"
    complete = "complete"


class SiteIntake(Base):
    __tablename__ = "site_intakes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1:1 relationship
    )
    status: Mapped[IntakeStatus] = mapped_column(
        SAEnum(IntakeStatus), nullable=False, default=IntakeStatus.draft
    )

    # Section data (JSON fields)
    goals_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Expected: {"main_goal": str, "target_regions": str, "competitors": [str], "notes": str}
    technical_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Expected: {"robots_notes": str}

    # Section completion flags
    section_access: Mapped[bool] = mapped_column(Boolean, default=False)
    section_goals: Mapped[bool] = mapped_column(Boolean, default=False)
    section_analytics: Mapped[bool] = mapped_column(Boolean, default=False)
    section_technical: Mapped[bool] = mapped_column(Boolean, default=False)
    section_checklist: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
```

**Key design choices:**
- `unique=True` on `site_id` enforces 1:1 (D-16)
- Only tabs with editable data get JSON columns (`goals_data`, `technical_data`). Tabs 1, 3, 5 are read-only -- they only need boolean section flags.
- `goals_data` JSON schema: `{"main_goal": str, "target_regions": str, "competitors": list[str], "notes": str}`
- `technical_data` JSON schema: `{"robots_notes": str}`
- Status is on intake record, not Site model (D-14)

### Pattern 2: Service Layer (module-level async functions)

**What:** Follow `client_service.py` pattern exactly -- module-level async functions, keyword-only args, `db.flush()` not `db.commit()`.

```python
# app/services/intake_service.py
async def get_or_create_intake(db: AsyncSession, *, site_id: uuid.UUID) -> SiteIntake:
    """Get existing intake or create new one (implicit creation on first visit, D-16)."""
    result = await db.execute(
        select(SiteIntake).where(SiteIntake.site_id == site_id)
    )
    intake = result.scalar_one_or_none()
    if intake is None:
        intake = SiteIntake(site_id=site_id)
        db.add(intake)
        await db.flush()
    return intake

async def save_goals_section(db: AsyncSession, *, site_id: uuid.UUID, data: dict) -> SiteIntake:
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.goals_data = data
    intake.section_goals = True
    await db.flush()
    return intake

async def get_verification_checklist(db: AsyncSession, *, site_id: uuid.UUID) -> dict:
    """Query platform data for 5 checklist items. Returns dict of statuses."""
    # ... queries across Site, OAuthToken, SitemapEntry, CrawlJob
```

### Pattern 3: HTMX Partial Save with Toast (D-03)

**What:** Each tab's save button POSTs to a section-specific endpoint. Server returns empty body with `HX-Trigger` header.

```python
# Router pattern (from existing crm.py)
from fastapi.responses import HTMLResponse
import json as _json

@router.post("/ui/sites/{site_id}/intake/goals", response_class=HTMLResponse)
async def save_goals(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    form = await request.form()
    data = {
        "main_goal": form.get("main_goal", ""),
        "target_regions": form.get("target_regions", ""),
        "competitors": [v for k, v in form.multi_items() if k == "competitor" and v.strip()],
        "notes": form.get("notes", ""),
    }
    await intake_service.save_goals_section(db, site_id=site_id, data=data)
    resp = HTMLResponse("")
    resp.headers["HX-Trigger"] = _json.dumps({"showToast": "Раздел сохранен"})
    return resp
```

### Pattern 4: Verification Checklist Queries (INTAKE-02, INTAKE-03)

**What:** 5 queries against existing models to derive boolean statuses.

| Checklist Item | Model/Table | Query Logic | Status Mapping |
|----------------|-------------|-------------|----------------|
| WP подключен | `Site.connection_status` | `== ConnectionStatus.connected` | connected/failed/unknown maps directly to 3-state |
| GSC подключен | `OAuthToken` | `EXISTS WHERE site_id=X AND provider='gsc'` | found=connected, not found=not_configured |
| Метрика подключена | `Site.metrika_counter_id` | `IS NOT NULL AND != ''` | present=connected, absent=not_configured |
| Sitemap найден | `SitemapEntry` | `EXISTS WHERE site_id=X` | found=connected, not found=not_configured |
| Краул выполнен | `CrawlJob` | `EXISTS WHERE site_id=X AND status='done'` | found=connected, not found=not_configured |

**3-state mapping (D-09):**
- `connected` -- green check -- condition is met
- `not_configured` -- red X -- condition is explicitly not met
- `unknown` -- gray question mark -- used for WP when `connection_status == 'unknown'` (never tested)

### Pattern 5: Tab Switching JS (reuse from CRM)

**What:** Copy `switchTab()` function from `crm/detail.html` with class name change to `intake-tab` / `intake-tab-panel`.

```javascript
function switchTab(tabName) {
  document.querySelectorAll('.intake-tab-panel').forEach(function(panel) {
    panel.style.display = 'none';
  });
  document.querySelectorAll('.intake-tab').forEach(function(btn) {
    btn.style.borderBottomColor = 'transparent';
    btn.style.color = '#6b7280';
    btn.classList.remove('active');
  });
  document.getElementById('tab-' + tabName).style.display = 'block';
  var tab = document.querySelector('[data-tab="' + tabName + '"]');
  if (tab) {
    tab.style.borderBottomColor = '#4f46e5';
    tab.style.color = '#4f46e5';
    tab.classList.add('active');
  }
}
```

### Pattern 6: Dynamic Competitor List (D-05, client-side JS)

**What:** Add/remove competitor URL inputs via JavaScript. No HTMX. Up to 10 entries.

```javascript
function addCompetitor() {
  var container = document.getElementById('competitors-list');
  if (container.children.length >= 10) return;
  var row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:0.5rem;margin-bottom:0.5rem;';
  row.innerHTML = '<input type="url" name="competitor" placeholder="https://example.com" style="flex:1;padding:0.5rem;border:1px solid #d1d5db;border-radius:6px;">'
    + '<button type="button" onclick="this.parentElement.remove()" style="color:#dc2626;background:none;border:none;cursor:pointer;font-size:1.2rem;">×</button>';
  container.appendChild(row);
}
```

### Anti-Patterns to Avoid
- **Storing checklist statuses in intake record:** Checklist is always derived from live platform data (D-08). Never cache it in the `SiteIntake` model.
- **Using HTMX for tab switching:** Tab switching is pure JS (D-01, Phase 20 pattern). HTMX is only for save and checklist refresh.
- **Adding `intake_status` to Site model:** Status lives on SiteIntake record (D-14). Site list/detail read it via a join or subquery.
- **Making tab save endpoints return HTML:** Use `hx-swap="none"` with `HX-Trigger` toast. No DOM replacement on save.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Form data extraction | Custom request body parser | `request.form()` + `form.multi_items()` | FastAPI form handling covers multi-value fields (competitors) |
| Toast notifications | New notification system | Existing `showToast` JS + `HX-Trigger` header pattern | Already deployed in CRM, sites, dead_content routers |
| Tab switching | HTMX tab loading or custom SPA | Copy `switchTab()` from CRM detail.html | Proven pattern, zero dependencies |
| Badge display | New badge component system | Existing `.badge-connected`, `.badge-failed`, `.badge-unknown` CSS | Already styled in base.html |
| JSON validation | Pydantic models for intake data | Direct dict manipulation | Intake data is simple flat structure; Pydantic adds overhead for 4 string fields |

## Common Pitfalls

### Pitfall 1: Competitors as Multi-Value Form Field
**What goes wrong:** Using a single text input for competitors and trying to parse comma-separated URLs. Or naming inputs `competitor[0]`, `competitor[1]` which requires index management.
**Why it happens:** HTML forms don't natively handle dynamic lists.
**How to avoid:** Use the same `name="competitor"` for all competitor inputs. Access via `form.multi_items()` which returns all values for the same key. Filter out empty strings.
**Warning signs:** Competitor data lost on save, only first competitor saved.

### Pitfall 2: Implicit Intake Creation Race Condition
**What goes wrong:** Two concurrent requests for the same site both try to create a new intake record, causing a unique constraint violation.
**Why it happens:** `get_or_create_intake` has a check-then-act pattern.
**How to avoid:** Use `INSERT ... ON CONFLICT (site_id) DO NOTHING` via SQLAlchemy, or catch `IntegrityError` and retry with a SELECT. In practice, this is a single-user admin tool so the race is extremely unlikely, but handle it gracefully.
**Warning signs:** 500 error on first intake page visit when two tabs open simultaneously.

### Pitfall 3: Badge Query N+1 in Site List
**What goes wrong:** Site list page queries SiteIntake per-row to show badge, causing N+1.
**Why it happens:** Naive approach checks intake status inside a template loop.
**How to avoid:** Pre-fetch intake statuses for all sites on the page in a single query (dict of `site_id -> status`), pass to template context. Same pattern as `site_metrics` already used in `sites/index.html`.
**Warning signs:** Site list page becomes slow with 50+ sites.

### Pitfall 4: JSON Field Update Overwrites
**What goes wrong:** Partial update of `goals_data` JSON field overwrites the entire dict.
**Why it happens:** SQLAlchemy JSON columns replace the entire value on assignment.
**How to avoid:** Always reconstruct the full dict from form data before saving. Since each section POST sends all fields for that section, this is natural. Never try to merge partial updates.
**Warning signs:** Fields disappearing after saving a section.

### Pitfall 5: Missing Model Registration in __init__.py
**What goes wrong:** Alembic autogenerate doesn't detect the new `site_intakes` table.
**Why it happens:** `app/models/__init__.py` must import the new model for Alembic to see it.
**How to avoid:** Add `from app.models.site_intake import SiteIntake` to `app/models/__init__.py`.
**Warning signs:** `alembic revision --autogenerate` produces empty migration.

## Code Examples

### Alembic Migration (0044)

Next migration number is `0044` (after `0043_add_crm_tables.py`). Per STATE.md decision: "0044 intake".

```python
# alembic/versions/0044_add_site_intakes_table.py
def upgrade():
    op.create_table(
        "site_intakes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", sa.dialects.postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.Enum("draft", "complete", name="intakestatus"), nullable=False, server_default="draft"),
        sa.Column("goals_data", sa.dialects.postgresql.JSON, nullable=True),
        sa.Column("technical_data", sa.dialects.postgresql.JSON, nullable=True),
        sa.Column("section_access", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("section_goals", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("section_analytics", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("section_technical", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("section_checklist", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
```

### Router Registration in main.py

```python
# Add to app/main.py imports
from app.routers.intake import router as intake_router
# Add to router includes
app.include_router(intake_router)
```

### Checklist Service Function

```python
async def get_verification_checklist(db: AsyncSession, *, site_id: uuid.UUID) -> list[dict]:
    site = await db.get(Site, site_id)
    if not site:
        return []

    # WP connected
    wp_status = "connected" if site.connection_status == ConnectionStatus.connected else (
        "unknown" if site.connection_status == ConnectionStatus.unknown else "not_configured"
    )

    # GSC connected
    gsc_result = await db.execute(
        select(func.count()).select_from(OAuthToken).where(
            OAuthToken.site_id == site_id, OAuthToken.provider == "gsc"
        )
    )
    gsc_connected = gsc_result.scalar_one() > 0

    # Metrika connected
    metrika_connected = bool(site.metrika_counter_id)

    # Sitemap found
    sitemap_result = await db.execute(
        select(func.count()).select_from(SitemapEntry).where(
            SitemapEntry.site_id == site_id
        )
    )
    sitemap_found = sitemap_result.scalar_one() > 0

    # Crawl done
    crawl_result = await db.execute(
        select(func.count()).select_from(CrawlJob).where(
            CrawlJob.site_id == site_id, CrawlJob.status == CrawlJobStatus.done
        )
    )
    crawl_done = crawl_result.scalar_one() > 0

    return [
        {"label": "WP подключен", "status": wp_status},
        {"label": "GSC подключен", "status": "connected" if gsc_connected else "not_configured"},
        {"label": "Метрика подключена", "status": "connected" if metrika_connected else "not_configured"},
        {"label": "Sitemap найден", "status": "connected" if sitemap_found else "not_configured"},
        {"label": "Краул выполнен", "status": "connected" if crawl_done else "not_configured"},
    ]
```

### HTMX Toast Response Pattern

```python
# Consistent with existing codebase (crm.py, sites.py, dead_content.py)
import json as _json

resp = HTMLResponse("")
resp.headers["HX-Trigger"] = _json.dumps({"showToast": "Раздел сохранен"})
return resp
```

### Site List Badge Query (avoid N+1)

```python
# In the site list endpoint, add intake status prefetch:
intake_query = select(SiteIntake.site_id, SiteIntake.status).where(
    SiteIntake.site_id.in_([s.id for s in sites])
)
intake_result = await db.execute(intake_query)
intake_statuses = {row.site_id: row.status for row in intake_result}
# Pass intake_statuses to template context
```

## State of the Art

No new approaches needed. This phase uses exclusively established patterns from Phase 20.

| Phase 20 Pattern | Phase 21 Reuse | Adaptation |
|------------------|----------------|------------|
| CRM detail page tabs | Intake form tabs | Change class prefix from `crm-tab` to `intake-tab` |
| HTMX modal create/edit | HTMX section save | Simpler: no modal, just `hx-swap="none"` + toast |
| Client badge on site pages | Intake badge on site pages | Same badge CSS classes, different label text |
| Module-level service functions | Intake service functions | Same pattern, fewer functions needed |
| `0043_add_crm_tables.py` migration | `0044_add_site_intakes_table.py` | Same structure, single table |

## Open Questions

1. **Sitemap detection accuracy**
   - What we know: `SitemapEntry` table exists from architecture module. Entries are created during crawls.
   - What's unclear: If a site has never been crawled, sitemap status will always be "not_configured" even if a sitemap exists. This is acceptable per D-08 (static snapshot from platform data).
   - Recommendation: Accept this limitation. The checklist reflects what the platform knows, not ground truth.

2. **Re-opening a completed intake**
   - What we know: D-14 says status lives on intake record and allows re-opening.
   - What's unclear: Should re-opening reset section flags or just the status?
   - Recommendation: Only reset `status` back to `draft`. Keep section flags intact so the user sees what was previously completed.

## Sources

### Primary (HIGH confidence)
- `app/models/site.py` -- Site model fields (connection_status, seo_plugin, metrika_counter_id, yandex_region)
- `app/models/oauth_token.py` -- OAuthToken model (provider, site_id)
- `app/models/crawl.py` -- CrawlJob model (status, site_id)
- `app/models/architecture.py` -- SitemapEntry model (site_id)
- `app/models/client.py` -- Client/ClientContact/ClientInteraction models (pattern reference)
- `app/services/client_service.py` -- Service layer pattern (module-level async, keyword-only args, db.flush)
- `app/routers/crm.py` -- Router pattern (Depends, HTMLResponse, HX-Trigger toast)
- `app/templates/crm/detail.html` -- Tab switching JS pattern, tab bar HTML structure
- `app/templates/sites/index.html` -- Site list table structure (for badge column addition)
- `app/templates/sites/detail.html` -- Site detail page (for intake link/badge addition)
- `app/main.py` -- Router registration pattern
- `app/models/__init__.py` -- Model registration for Alembic
- `.planning/phases/21-site-audit-intake/21-CONTEXT.md` -- All locked decisions
- `.planning/phases/21-site-audit-intake/21-UI-SPEC.md` -- Visual and interaction contracts

### Secondary (MEDIUM confidence)
- `.planning/phases/20-client-crm/20-03-SUMMARY.md` -- CRM detail page implementation details and established patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing
- Architecture: HIGH -- direct reuse of Phase 20 patterns with full codebase evidence
- Pitfalls: HIGH -- derived from concrete codebase analysis (N+1 pattern visible in site_metrics, form multi_items from FastAPI docs)

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- no external dependencies, all patterns established)
