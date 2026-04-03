# Phase v4-07: Settings Section (Настройки) - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate the Settings section pages (users, groups, data sources, proxies, parameters, audit log, platform issues) to the new sidebar layout with Tailwind CSS. Split the combined "Прокси и настройки" page into separate Proxy and Parameters sub-items. Implement per-child access control so managers can access Proxy, Data Sources, Parameters, and Platform Issues while Users, Groups, and Audit Log remain admin-only. Pure visual migration + navigation restructuring — no new backend features.

</domain>

<decisions>
## Implementation Decisions

### Navigation Structure
- **D-01:** Split "Прокси и настройки" (currently one page at /ui/admin/settings) into two sidebar children: "Прокси" (proxy pool, XMLProxy/rucaptcha credentials, balance widgets) and "Параметры" (remaining platform settings). This requires either two separate templates or a tab-based single page with two sidebar entries pointing to anchors.
- **D-02:** Final sidebar children order (7 items): Пользователи, Группы, Источники данных, Прокси, Параметры, Задачи платформы, Журнал аудита.

### Access Control
- **D-03:** Remove `admin_only: True` from the entire "settings" section in `navigation.py`. Instead, add per-child `admin_only` flags:
  - **Admin-only:** Пользователи (users), Группы (groups), Журнал аудита (audit-log)
  - **Manager + Admin:** Прокси (proxy), Источники данных (datasources), Параметры (parameters), Задачи платформы (issues)
- **D-04:** `build_sidebar_sections()` in navigation.py must be updated to support per-child filtering (currently only checks section-level `admin_only`). Non-admin users see "Настройки" section but only with their permitted children.
- **D-05:** Backend route guards must match: manager accessing /ui/admin/users or /ui/admin/groups or /ui/admin/audit gets 403. Existing admin.py already has role checks — verify they cover all endpoints.

### Tailwind Migration
- **D-06:** Pure Tailwind migration for all 6 templates (admin/users, admin/groups, admin/settings→split, admin/issues, admin/audit, datasources/index) + 2 partials (proxy_row, proxy_section). Zero `style=` attributes. Follow v4-02 through v4-06 established patterns.
- **D-07:** Consistent with prior phases: bg-white rounded-lg shadow-sm cards, indigo/emerald/red palette, classList toggle for modals (hidden/flex), min-w-full tables with divide-y.

### Claude's Discretion
- **D-08:** Plan splitting strategy — Claude decides based on template size and logical groupings (e.g., users+groups in one plan, proxy/settings split + datasources in another, issues+audit in a third).
- **D-09:** How to implement the Proxy/Parameters split — either two separate templates or a single template with sections. Claude decides based on current settings.html structure.
- **D-10:** All Tailwind class choices, badge colors, form styling — follow established patterns from v4-04/v4-05/v4-06.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Navigation System
- `app/navigation.py` — NAV_SECTIONS config; `build_sidebar_sections()` needs per-child admin_only support
- `app/template_engine.py` — Template injection of nav context

### Settings Templates (migration targets)
- `app/templates/admin/users.html` — Users management (191 lines, 53 style=)
- `app/templates/admin/groups.html` — Site groups management (167 lines, 48 style=)
- `app/templates/admin/settings.html` — Proxy + settings combined (200 lines, 74 style=) — TO BE SPLIT
- `app/templates/admin/issues.html` — Platform issues (86 lines, 21 style=)
- `app/templates/admin/audit.html` — Audit log (64 lines, 14 style=)
- `app/templates/datasources/index.html` — Data sources (66 lines, 22 style=)
- `app/templates/admin/partials/proxy_row.html` — Proxy table row partial
- `app/templates/admin/partials/proxy_section.html` — Proxy section partial

### Backend (access control verification)
- `app/routers/admin.py` — Admin router with role checks
- `app/routers/proxy_admin.py` — Proxy admin endpoints

### Prior Phase Patterns
- `.planning/phases/v4-06-section-content/v4-06-CONTEXT.md` — Tailwind migration patterns and decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_sidebar_sections()` in navigation.py already filters `admin_only` sections — needs extension for per-child filtering
- admin/partials/proxy_row.html and proxy_section.html — partial templates for proxy CRUD, will need Tailwind migration
- Established modal pattern: classList toggle hidden/flex (from v4-04/v4-05/v4-06)

### Established Patterns
- Tailwind migration: replace all style= with utility classes, bg-white rounded-lg shadow-sm cards
- Tables: min-w-full divide-y divide-gray-200
- Badges: inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
- Modals: fixed inset-0 hidden (toggle to flex via classList)
- Forms: Tailwind form classes, indigo-600 submit buttons

### Integration Points
- `navigation.py` — per-child admin_only filtering
- `admin.py` routes — verify role guards match new access model
- `base.html` / sidebar template — already renders sections from build_sidebar_sections()

</code_context>

<specifics>
## Specific Ideas

No specific requirements — follow established v4-02 through v4-06 Tailwind migration patterns. The only structural change is the Proxy/Parameters split and per-child access control.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: v4-07-settings-section*
*Context gathered: 2026-04-04*
