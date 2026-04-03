# Phase v4-07: Settings Section - Research

**Researched:** 2026-04-04
**Domain:** Jinja2/HTMX template migration, FastAPI role-based access control, Tailwind CSS
**Confidence:** HIGH

## Summary

Phase v4-07 is a pure visual migration and navigation restructuring phase — no new backend features, no DB migrations. The task is to migrate 6 templates (plus 2 partials) to Tailwind CSS, split the combined settings.html into separate Прокси and Параметры pages, and extend `build_sidebar_sections()` in navigation.py to support per-child `admin_only` filtering so managers can see a subset of Settings children.

All patterns required are established and proven across v4-02 through v4-06. The most technically novel work is the per-child access control change in `navigation.py` and the settings.html split into two separate templates. The template_engine.py already reads the JWT role cookie and passes `is_admin` to `build_sidebar_sections()` — the infrastructure is in place; only the filtering logic needs extension.

**Primary recommendation:** Extend `build_sidebar_sections()` to check per-child `admin_only`, update `NAV_SECTIONS` settings children with per-child flags, create `admin/proxy.html` and `admin/parameters.html` from the split of `admin/settings.html`, add a new `/ui/admin/parameters` route in `main.py`, and migrate all remaining templates to Tailwind following the established v4-04/v4-05/v4-06 patterns.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Split "Прокси и настройки" (currently one page at /ui/admin/settings) into two sidebar children: "Прокси" (proxy pool, XMLProxy/rucaptcha credentials, balance widgets) and "Параметры" (remaining platform settings). This requires either two separate templates or a tab-based single page with two sidebar entries pointing to anchors.
- **D-02:** Final sidebar children order (7 items): Пользователи, Группы, Источники данных, Прокси, Параметры, Задачи платформы, Журнал аудита.
- **D-03:** Remove `admin_only: True` from the entire "settings" section in `navigation.py`. Instead, add per-child `admin_only` flags:
  - **Admin-only:** Пользователи (users), Группы (groups), Журнал аудита (audit-log)
  - **Manager + Admin:** Прокси (proxy), Источники данных (datasources), Параметры (parameters), Задачи платформы (issues)
- **D-04:** `build_sidebar_sections()` in navigation.py must be updated to support per-child filtering (currently only checks section-level `admin_only`). Non-admin users see "Настройки" section but only with their permitted children.
- **D-05:** Backend route guards must match: manager accessing /ui/admin/users or /ui/admin/groups or /ui/admin/audit gets 403. Existing admin.py already has role checks — verify they cover all endpoints.
- **D-06:** Pure Tailwind migration for all 6 templates (admin/users, admin/groups, admin/settings→split, admin/issues, admin/audit, datasources/index) + 2 partials (proxy_row, proxy_section). Zero `style=` attributes. Follow v4-02 through v4-06 established patterns.
- **D-07:** Consistent with prior phases: bg-white rounded-lg shadow-sm cards, indigo/emerald/red palette, classList toggle for modals (hidden/flex), min-w-full tables with divide-y.

### Claude's Discretion

- **D-08:** Plan splitting strategy — Claude decides based on template size and logical groupings (e.g., users+groups in one plan, proxy/settings split + datasources in another, issues+audit in a third).
- **D-09:** How to implement the Proxy/Parameters split — either two separate templates or a single template with sections. Claude decides based on current settings.html structure.
- **D-10:** All Tailwind class choices, badge colors, form styling — follow established patterns from v4-04/v4-05/v4-06.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CFG-V4-01 | Users, groups, data sources, proxies, parameters, and audit log management via sidebar sub-items under «Настройки» | Navigation.py per-child filtering + 7 sidebar children (D-02) + split of settings.html into proxy.html + parameters.html with new /ui/admin/proxy and /ui/admin/parameters routes |
| CFG-V4-02 | «Настройки» section visible only to users with admin role | Contradicted by CONTEXT.md D-03: section-level admin_only is REMOVED; instead per-child filtering applies. Managers see Прокси, Источники данных, Параметры, Задачи платформы. Only Пользователи, Группы, Журнал аудита are admin-only children |
</phase_requirements>

## Standard Stack

### Core (fixed by CLAUDE.md)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.x | Runtime | Project constraint |
| FastAPI | 0.115.x | ASGI web framework | Project constraint |
| Jinja2 | 3.1.x | Server-side HTML templating | Project constraint |
| HTMX | 2.0.x | Partial page updates | Project constraint |
| Tailwind CSS | (CDN, existing) | Utility-first CSS | Established in v4-01 |

### No new packages required
This phase is a pure template migration + navigation logic change. No new pip installs needed.

## Architecture Patterns

### Recommended Project Structure — affected files
```
app/
├── navigation.py                     # Modify: per-child admin_only filtering
├── main.py                           # Modify: add /ui/admin/proxy route; update /ui/admin/settings → /ui/admin/parameters; update role guard on issues
└── templates/
    ├── admin/
    │   ├── users.html                # Migrate: 191 lines, 53 style= → Tailwind
    │   ├── groups.html               # Migrate: 167 lines, 48 style= → Tailwind
    │   ├── settings.html             # SPLIT into proxy.html + parameters.html (200 lines, 74 style=)
    │   ├── proxy.html                # NEW: proxy pool + credentials section from settings.html
    │   ├── parameters.html           # NEW: crawler/SERP settings + integrations from settings.html
    │   ├── issues.html               # Migrate: 86 lines, 21 style= → Tailwind
    │   ├── audit.html                # Migrate: 64 lines, 14 style= → Tailwind
    │   └── partials/
    │       ├── proxy_row.html        # Migrate: inline style= → Tailwind
    │       └── proxy_section.html   # Migrate: inline style= → Tailwind
    └── datasources/
        └── index.html               # Migrate: 66 lines, 22 style= → Tailwind
```

### Pattern 1: Tailwind Card (established across v4-02 through v4-06)
**What:** Replace `.card` CSS class + `style=` with explicit Tailwind utility card
**When to use:** Every content container
```html
<!-- Before -->
<div class="card" style="margin-bottom:1.5rem">

<!-- After -->
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
```

### Pattern 2: Modal with classList toggle (v4-04/v4-05/v4-06 established)
**What:** Replace `style.display='flex'/'none'` with `classList.remove('hidden')` / `classList.add('hidden')`
**When to use:** All modal show/hide interactions

```html
<!-- Overlay div — starts hidden -->
<div id="add-user-modal"
     class="hidden fixed inset-0 bg-black/50 z-50 items-center justify-content-center flex-col">
  <div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
    ...
  </div>
</div>

<script>
// Open
document.getElementById('add-user-modal').classList.remove('hidden');
document.getElementById('add-user-modal').classList.add('flex');
// Close
document.getElementById('add-user-modal').classList.add('hidden');
document.getElementById('add-user-modal').classList.remove('flex');
</script>
```

**Key detail:** Modal div uses `class="hidden fixed inset-0 ..."` — `hidden` is the default state; toggled to `flex` on open.

### Pattern 3: Tables (established v4-03/v4-04/v4-05/v4-06)
```html
<div class="overflow-x-auto">
  <table class="min-w-full divide-y divide-gray-200 text-sm">
    <thead class="bg-gray-50">
      <tr>
        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Column</th>
      </tr>
    </thead>
    <tbody class="bg-white divide-y divide-gray-100">
      <tr>
        <td class="px-4 py-3 text-gray-700">Value</td>
      </tr>
    </tbody>
  </table>
</div>
```

### Pattern 4: Badges (established across all v4 phases)
```html
<!-- Role badges -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">admin</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">manager</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">client</span>

<!-- Status badges (users) -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">Active</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">Inactive</span>

<!-- Proxy status badges -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">active</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">dead</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">unknown</span>

<!-- Issue status badges -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">open</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">in progress</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">resolved</span>
```

### Pattern 5: Form inputs (established v4-04/v4-05/v4-06)
```html
<label class="block text-sm font-medium text-gray-700 mb-1">Label</label>
<input type="text" name="field" required
       class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
<select name="role"
        class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
<textarea name="desc" rows="3"
          class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm resize-vertical focus:outline-none focus:ring-2 focus:ring-indigo-500"></textarea>
```

### Pattern 6: Buttons (established across all v4 phases)
```html
<!-- Primary -->
<button class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md">Action</button>
<!-- Small primary -->
<button class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium px-3 py-1.5 rounded">Action</button>
<!-- Danger small -->
<button class="bg-red-500 hover:bg-red-600 text-white text-xs font-medium px-3 py-1.5 rounded">Delete</button>
<!-- Neutral small -->
<button class="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-medium px-3 py-1.5 rounded">Cancel</button>
```

### Pattern 7: Per-child admin_only in navigation.py
**Current state:** `build_sidebar_sections()` only checks section-level `admin_only`. Children have no `admin_only` key.

**Required change:**
```python
# In NAV_SECTIONS settings children — add admin_only key:
{"id": "users", "label": "Пользователи", "url": "/ui/admin/users", "admin_only": True},
{"id": "groups", "label": "Группы", "url": "/ui/admin/groups", "admin_only": True},
{"id": "datasources", "label": "Источники данных", "url": "/ui/datasources", "admin_only": False},
{"id": "proxy", "label": "Прокси", "url": "/ui/admin/proxy", "admin_only": False},
{"id": "parameters", "label": "Параметры", "url": "/ui/admin/parameters", "admin_only": False},
{"id": "issues", "label": "Задачи платформы", "url": "/ui/admin/issues", "admin_only": False},
{"id": "audit-log", "label": "Журнал аудита", "url": "/ui/admin/audit", "admin_only": True},

# In build_sidebar_sections() — add child filtering:
for child in section["children"]:
    child_admin_only = child.get("admin_only", False)
    if child_admin_only and not is_admin:
        continue  # skip this child for non-admin users
    ... # rest of existing URL resolution logic
```

**Important:** Section-level `admin_only` on "settings" must be set to `False` so managers see the section at all. The per-child filtering then limits what they see inside it.

**Backward compatibility:** Other sections' children have no `admin_only` key — the `child.get("admin_only", False)` default preserves all existing behavior.

### Pattern 8: Settings split strategy
**Current settings.html** (200 lines) contains two logically separate areas:
1. **Parameters section** (lines 1-75): Crawler settings, SERP parser settings, External Integrations Status, env-var note → goes to `admin/parameters.html` at `/ui/admin/parameters`
2. **Proxy section** (lines 77-199): Proxy table, add proxy form, XMLProxy credentials, rucaptcha credentials, anticaptcha credentials → goes to `admin/proxy.html` at `/ui/admin/proxy`

**Route changes in main.py:**
- `/ui/admin/settings` GET handler: redirect to `/ui/admin/parameters` (or repurpose as parameters handler)
- Add `/ui/admin/proxy` GET handler: extract proxy-loading logic from the settings handler
- The `/ui/admin/parameters` handler: serves settings_data without proxy data

**Recommended:** Keep `/ui/admin/settings` as-is for backward compatibility (301 redirect to `/ui/admin/parameters`), or simply rename the handler to serve `parameters.html`. The proxy_admin router already handles POST endpoints at `/admin/proxies/*` — no changes needed there.

### Anti-Patterns to Avoid
- **style= attributes in templates:** Zero `style=` in final output. The only documented exception (from STATE.md) is `style=width:X%` for Jinja2-computed dynamic bar widths — not applicable here.
- **style.display in JavaScript:** Use `classList.remove('hidden') / classList.add('flex')` instead of `element.style.display = 'flex'/'none'`.
- **Mixing old .btn/.card CSS with Tailwind utilities:** All these templates currently use `.btn`, `.card`, `.badge` CSS classes. They must be replaced wholesale with Tailwind utilities.
- **Section-level admin_only left True:** If `admin_only: True` remains on the settings section, `build_sidebar_sections()` will hide the whole section from managers even after per-child filtering is added. Must set to `False`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Role-based auth | Custom role checks | `require_admin` / `require_manager_or_above` from `app/auth/dependencies.py` | Already tested, raises 403 correctly |
| Per-child nav filtering | New filtering system | Extend existing `build_sidebar_sections()` with `child.get("admin_only", False)` check | Minimal change to battle-tested function |
| Proxy credential forms | New credential system | Existing `/admin/proxies/credentials/{service}` endpoints in `proxy_admin.py` | Already handles Fernet encryption |
| Modal JS | Custom show/hide library | `classList.remove('hidden') / classList.add('flex')` pattern | Established pattern, zero dependencies |

## Common Pitfalls

### Pitfall 1: Forgetting to remove section-level admin_only on settings
**What goes wrong:** After adding per-child `admin_only` flags, the section-level `admin_only: True` remains, so `build_sidebar_sections()` skips the entire settings section for managers before per-child filtering runs.
**Why it happens:** The existing code checks section-level before iterating children. D-03 explicitly says to remove section-level admin_only.
**How to avoid:** In NAV_SECTIONS, change `"admin_only": True` on the settings section dict to `"admin_only": False`.
**Warning signs:** Manager user sees no Settings section at all in the sidebar.

### Pitfall 2: Issues route missing role guard for manager access
**What goes wrong:** `/ui/admin/issues` currently has no role guard (confirmed: only checks `if not current_user` redirects to /ui/login). D-05 says managers should access this route.
**Why it happens:** Route was implemented before per-role access model was finalized.
**How to avoid:** Change the issues route guard from `if not current_user` to `if not current_user or current_user.role.value not in ("admin", "manager")`.
**Warning signs:** Anonymous users can access the issues page.

### Pitfall 3: Proxy URL change breaks HTMX targets in proxy_row.html
**What goes wrong:** proxy_row.html uses `hx-put="/admin/proxies/{{ p.id }}"` and `hx-delete="/admin/proxies/{{ p.id }}"` and `hx-post="/admin/proxies/{{ p.id }}/check"`. The proxy_admin router is at `/admin/proxies` prefix (not `/ui/admin/proxies`). These HTMX endpoints are backend API routes, not UI routes — they must not change.
**Why it happens:** Confusion between `/ui/admin/...` (UI pages served by main.py) and `/admin/...` (HTMX action endpoints in proxy_admin.py).
**How to avoid:** Only the GET page routes change (/ui/admin/settings → split into /ui/admin/proxy + /ui/admin/parameters). HTMX form targets in templates remain unchanged.
**Warning signs:** Proxy add/delete/check operations return 404 after migration.

### Pitfall 4: proxy_section.html partial uses style= that renders as HTMX response
**What goes wrong:** `proxy_section.html` is a partial rendered as HTMX response body (hx-target="#proxy-section"). It currently has multiple `style=` attributes. After migration it must also be zero `style=`.
**Why it happens:** Partials are easy to miss since they don't extend base.html.
**How to avoid:** Migrate both partials (`proxy_row.html` and `proxy_section.html`) with the same Tailwind standards as full templates.

### Pitfall 5: users.html modal uses style.display not classList
**What goes wrong:** `users.html` uses `document.getElementById('add-user-modal').style.display='flex'` / `.style.display='none'`. If the Tailwind modal uses `class="hidden flex ..."`, `style.display` will override `hidden` class inconsistently.
**Why it happens:** Original template uses inline style JS before Tailwind migration.
**How to avoid:** Replace all `.style.display='flex'` with `.classList.remove('hidden'); .classList.add('flex')` and `.style.display='none'` with `.classList.add('hidden'); .classList.remove('flex')` in the JS sections.

### Pitfall 6: groups.html modal opened from JS with style.display
**What goes wrong:** Same as Pitfall 5 — groups.html `openEditGroupModal()` uses `style.display='flex'`.
**Why it happens:** Pre-Tailwind JS modal pattern.
**How to avoid:** Same fix as Pitfall 5 — rewrite modal open/close to use classList.

### Pitfall 7: datasources/index.html has progress bar with dynamic style=width
**What goes wrong:** `datasources/index.html` line 52 uses `style="width:{{ pct|round(1) }}%"` for the SERP usage progress bar.
**Why it happens:** Dynamic Jinja2 percentage cannot be expressed with static Tailwind class.
**How to avoid:** Per established project exception (STATE.md: "Distribution bar dynamic widths kept as style=width:X% — only permitted style= exception for dynamic Jinja2 calculations"), this ONE `style=width:X%` is the permitted exception. Leave it as-is.

## Code Examples

### Per-child admin_only filtering in build_sidebar_sections()
```python
# Source: app/navigation.py — modified build_sidebar_sections()
def build_sidebar_sections(site_id: str | None, is_admin: bool) -> list[dict]:
    result = []
    for section in NAV_SECTIONS:
        if section["admin_only"] and not is_admin:
            continue
        resolved_section = {
            "id": section["id"],
            "label": section["label"],
            "icon": section["icon"],
            "url": section["url"],
            "admin_only": section["admin_only"],
            "children": [],
        }
        for child in section["children"]:
            # NEW: per-child admin_only filtering
            if child.get("admin_only", False) and not is_admin:
                continue
            raw_url = child.get("url") or "#"
            needs_site = "{site_id}" in raw_url or "{project_id}" in raw_url
            if site_id is not None:
                resolved_url = raw_url.replace("{site_id}", str(site_id))
                resolved_url = resolved_url.replace("{project_id}", str(site_id))
                disabled = False
            elif needs_site:
                resolved_url = "#"
                disabled = True
            else:
                resolved_url = raw_url
                disabled = False
            resolved_section["children"].append(
                {
                    "id": child["id"],
                    "label": child["label"],
                    "url": resolved_url,
                    "disabled": disabled,
                }
            )
        result.append(resolved_section)
    return result
```

### Settings section NAV_SECTIONS update
```python
# Source: app/navigation.py — settings section in NAV_SECTIONS
{
    "id": "settings",
    "label": "Настройки",
    "icon": "cog-6-tooth",
    "url": None,
    "admin_only": False,  # CHANGED from True — managers must see this section
    "children": [
        {"id": "users",       "label": "Пользователи",   "url": "/ui/admin/users",       "admin_only": True},
        {"id": "groups",      "label": "Группы",          "url": "/ui/admin/groups",      "admin_only": True},
        {"id": "datasources", "label": "Источники данных","url": "/ui/datasources",       "admin_only": False},
        {"id": "proxy",       "label": "Прокси",          "url": "/ui/admin/proxy",       "admin_only": False},
        {"id": "parameters",  "label": "Параметры",       "url": "/ui/admin/parameters",  "admin_only": False},
        {"id": "issues",      "label": "Задачи платформы","url": "/ui/admin/issues",      "admin_only": False},
        {"id": "audit-log",   "label": "Журнал аудита",   "url": "/ui/admin/audit",       "admin_only": True},
    ],
},
```

### New /ui/admin/proxy route (main.py)
```python
@app.get("/ui/admin/proxy", response_class=HTMLResponse)
async def ui_admin_proxy(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.database import get_sync_db as _get_sync_db
    from app.models.proxy import Proxy as _Proxy
    from app.services.service_credential_service import get_credential_sync as _get_cred
    from sqlalchemy import select as _select

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value not in ("admin", "manager"):
        return RedirectResponse("/ui/dashboard", status_code=303)

    proxies = []
    xmlproxy_creds = None
    anticaptcha_creds = None
    rucaptcha_creds = None
    try:
        with _get_sync_db() as sync_db:
            proxies = sync_db.execute(_select(_Proxy)).scalars().all()
            xmlproxy_creds = _get_cred(sync_db, "xmlproxy")
            anticaptcha_creds = _get_cred(sync_db, "anticaptcha")
            rucaptcha_creds = _get_cred(sync_db, "rucaptcha")
    except Exception:
        pass

    return templates.TemplateResponse(request, "admin/proxy.html", {
        "proxies": proxies,
        "xmlproxy_creds": xmlproxy_creds,
        "anticaptcha_creds": anticaptcha_creds,
        "rucaptcha_creds": rucaptcha_creds,
    })
```

### Repurposed /ui/admin/settings → /ui/admin/parameters route
```python
@app.get("/ui/admin/parameters", response_class=HTMLResponse)
async def ui_admin_parameters(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.config import settings as app_settings

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value not in ("admin", "manager"):
        return RedirectResponse("/ui/dashboard", status_code=303)

    settings_data = {
        "crawler_delay_ms": app_settings.CRAWLER_DELAY_MS,
        "crawler_max_pages": app_settings.CRAWLER_MAX_PAGES,
        "serp_max_daily": app_settings.SERP_MAX_DAILY_REQUESTS,
        "serp_delay_ms": app_settings.SERP_DELAY_MS,
        "gsc_configured": bool(app_settings.GSC_CLIENT_ID),
        "yandex_configured": bool(app_settings.YANDEX_WEBMASTER_TOKEN),
        "dataforseo_configured": bool(app_settings.DATAFORSEO_LOGIN and app_settings.DATAFORSEO_PASSWORD),
    }
    return templates.TemplateResponse(request, "admin/parameters.html", {"settings": settings_data})


# Old URL: redirect for backward compatibility
@app.get("/ui/admin/settings", response_class=HTMLResponse)
async def ui_admin_settings_redirect(request: Request) -> HTMLResponse:
    return RedirectResponse("/ui/admin/parameters", status_code=301)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Section-level admin_only only | Per-child admin_only support | Phase v4-07 | Managers can see Settings section with limited children |
| Combined proxy+settings page at /ui/admin/settings | Two separate pages: /ui/admin/proxy + /ui/admin/parameters | Phase v4-07 | Cleaner IA, matches sidebar children 1:1 |
| Old-style `.card`, `.btn`, `.badge` CSS classes | Tailwind utilities only | Phase v4-07 (completing the migration) | Zero inline style=, consistent with all other sections |

## Open Questions

1. **settings.html backward compatibility**
   - What we know: The old `/ui/admin/settings` URL is referenced in settings.html itself (links to /ui/admin/users, /ui/admin/groups, /ui/admin/audit in the header) and possibly bookmarked.
   - What's unclear: Are there any non-template code references to `/ui/admin/settings` that a 301 redirect would break?
   - Recommendation: Add a 301 redirect from `/ui/admin/settings` to `/ui/admin/parameters`. Check for any hardcoded references in templates before removing the old route.

2. **issues.html role guard for manager access**
   - What we know: Current `/ui/admin/issues` GET handler only checks `if not current_user` (redirects to login), does not check role. POST handler also only checks `if not current_user`.
   - What's unclear: Should managers be able to create issues (POST) or only view (GET)?
   - Recommendation: Both GET and POST should allow manager role (D-03 lists Задачи платформы as manager-accessible). Update both handlers to check `role.value not in ("admin", "manager")`.

3. **datasources route already at /ui/datasources (not /ui/admin/datasources)**
   - What we know: The existing route is at `/ui/datasources` — not under `/ui/admin/`. The navigation child URL is already correct.
   - What's unclear: Is there a role guard on `/ui/datasources`?
   - Recommendation: Verify the route handler guards match the new manager-accessible intent. Check line 804+ in main.py.

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — pure template migration + Python logic change, no new tools or services required).

## Validation Architecture

nyquist_validation is explicitly `false` in .planning/config.json — this section is skipped.

## Sources

### Primary (HIGH confidence)
- `/projects/test/app/navigation.py` — Complete source of `NAV_SECTIONS` and `build_sidebar_sections()` — read directly
- `/projects/test/app/main.py` — All UI route handlers for admin pages — read directly
- `/projects/test/app/auth/dependencies.py` — Role guard helpers — read directly
- `/projects/test/app/template_engine.py` — How `is_admin` is computed and passed to `build_sidebar_sections()` — read directly
- All 6 templates + 2 partials — read directly, line counts and style= counts confirmed

### Secondary (MEDIUM confidence)
- STATE.md accumulated decisions — established patterns from v4-04/v4-05/v4-06 phases
- v4-06-CONTEXT.md — confirmed Tailwind migration patterns are stable

## Metadata

**Confidence breakdown:**
- Navigation change: HIGH — read the exact code that needs modification
- Template migration: HIGH — patterns established across 5 prior phases
- Route splitting: HIGH — existing handler code read, split is straightforward
- Access control: HIGH — `require_manager_or_above` exists, and the `is_admin` JWT check in template_engine.py is confirmed

**Research date:** 2026-04-04
**Valid until:** Stable (no external dependencies; valid until codebase changes)
