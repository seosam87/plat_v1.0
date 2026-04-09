# Phase 21: Site Audit Intake - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Structured onboarding form per site: 5 tabbed sections with auto-populated platform data, section-by-section save, verification checklist with 3-state status indicators, and "intake complete" badge visible in site list and site detail.

</domain>

<decisions>
## Implementation Decisions

### Form Structure
- **D-01:** Tabbed layout (consistent with CRM detail page from Phase 20) -- 5 tabs on a single page
- **D-02:** 5 sections/tabs: Доступы, Цели и конкуренты, Аналитика (GSC/Метрика), Технический SEO, Чеклист верификации
- **D-03:** Explicit "Сохранить раздел" button at the bottom of each tab -- HTMX POST saves only that section, toast confirmation

### Tab 1: Доступы (Access)
- **D-04:** Minimal approach -- show existing Site model data as read-only (WP connection status, login) + link to site settings for editing. No additional credential fields in intake form.

### Tab 2: Цели и конкуренты (Goals & Competitors)
- **D-05:** Fields: главная цель (textarea), целевые регионы (text), список конкурентов (dynamic list of URLs, up to 10, add/remove), заметки (textarea)

### Tab 3: Аналитика (Analytics Setup)
- **D-06:** Show GSC connection status (from oauth_tokens), Метрика counter ID status, yandex_region setting. Read-only indicators + links to connect/configure.

### Tab 4: Технический SEO (Technical SEO)
- **D-07:** Show current SEO plugin (from Site.seo_plugin), sitemap detection status, robots.txt notes. Mix of auto-populated read-only and user-editable fields.

### Tab 5: Чеклист верификации (Verification Checklist)
- **D-08:** Static snapshot -- statuses pulled from DB on page load. "Перепроверить" button refreshes all items via HTMX.
- **D-09:** 3 states per checklist item: Подключено (green check), Не настроено (red X), Не проверено (gray question mark)
- **D-10:** Checklist items: WP подключен, GSC подключен, Метрика подключена, Sitemap найден, Краул выполнен

### Progress Indication
- **D-11:** Checkmark on saved/completed tabs (Access checkmark, Goals checkmark, Analytics, Tech, Checklist). No progress bar.

### Completion Flow
- **D-12:** "Завершить intake" button always active. If not all sections saved -- shows warning "Не все секции заполнены. Завершить всё равно?" with confirm/cancel.
- **D-13:** Badge "Анкета заполнена" shown in both site list (column or icon) and site detail page (near client badge from Phase 20)
- **D-14:** Completion sets a status field on the intake record (not on Site model directly) -- allows re-opening if needed

### Data Model
- **D-15:** New `SiteIntake` model with JSON fields per section (goals, competitors, notes, etc.) + section completion flags + overall status (draft/complete)
- **D-16:** One intake per site (1:1 relationship via site_id FK). Creating intake is implicit on first visit to the intake page for a site.

### Claude's Discretion
- Exact JSON schema for intake section data
- Pagination/filtering in intake list (if needed)
- Error handling for verification checklist items

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 20 Patterns (reuse)
- `.planning/phases/20-client-crm/20-CONTEXT.md` -- tabbed layout pattern (D-01), HTMX partial save pattern
- `.planning/phases/20-client-crm/20-02-SUMMARY.md` -- CRM router pattern, modal pattern, HTMX partials
- `.planning/phases/20-client-crm/20-03-SUMMARY.md` -- detail page tab switching JS pattern

### Models & Services
- `app/models/site.py` -- Site model (connection_status, seo_plugin, metrika_counter_id, client_id)
- `app/models/oauth_token.py` -- OAuth tokens (GSC connection status)
- `app/services/site_service.py` -- existing site service functions

### Requirements
- `.planning/REQUIREMENTS.md` section "Site Audit Intake" -- INTAKE-01 through INTAKE-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Tab switching JS from `app/templates/crm/detail.html` -- can copy pattern for intake tabs
- HTMX partial save pattern from CRM contacts inline edit
- Toast notification pattern from CRM create/edit modal
- Empty state macro from `app/templates/macros/empty_state.html`

### Established Patterns
- Module-level async service functions (not class-based) -- follow `client_service.py`
- Router pattern with `Depends(get_db)` and `Depends(require_manager_or_above)`
- Template inheritance from `base.html` with block content

### Integration Points
- Site detail page (`app/templates/sites/detail.html`) -- add "Intake" link/button
- Site list page -- add intake status column/icon
- CRM sidebar -- Intake sub-item already anticipated (Phase 20, D-05)
- `app/main.py` -- register intake router

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches matching existing codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

- INTAKE-06: Auto-generate baseline crawl on intake completion (future enhancement)
- INTAKE-07: Intake answers pre-populate proposal template variables (Phase 22 dependency)

</deferred>

---

*Phase: 21-site-audit-intake*
*Context gathered: 2026-04-09*
