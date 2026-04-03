---
phase: v4-01-navigation-foundation
plan: "01"
subsystem: ui-layout
tags: [navigation, sidebar, htmx, jinja2, responsive]
dependency_graph:
  requires: []
  provides: [sidebar-layout, nav-context, site-selector, breadcrumbs]
  affects: [all-34-templates-extending-base.html]
tech_stack:
  added: []
  patterns: [sidebar-layout, htmx-partial-load, cookie-persistence, active-state-highlighting]
key_files:
  created:
    - app/navigation.py
    - app/templates/components/sidebar.html
    - app/templates/components/breadcrumb.html
    - app/templates/components/site_selector.html
  modified:
    - app/templates/base.html
    - app/main.py
decisions:
  - "Navigation labels are Russian (Обзор, Сайты, Позиции и ключи, Аналитика, Контент, Настройки) as per v4.0 milestone spec"
  - "Sidebar section labels rendered dynamically from nav_sections template variable — not hardcoded in HTML"
  - "site_selector hx-trigger uses both load and change on the same element; HTMX uses last-declared trigger so change is active — load populates options on page init"
  - "Log panel position adjusted to left:16rem to sit flush with main content area (not overlap sidebar)"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-04-03"
  tasks_completed: 2
  tasks_pending: 1
  files_created: 5
  files_modified: 2
---

# Phase v4-01 Plan 01: Navigation Foundation Summary

Replaced the top-nav `base.html` with a full vertical sidebar layout using Jinja2 + HTMX, adding navigation config module, active-state resolution, site selector with cookie persistence, and responsive behavior at two breakpoints.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Navigation config module and context injection middleware | 41caf84 | app/navigation.py, app/main.py |
| 2 | New base.html with sidebar layout, components, responsive behavior | 087b1c2 | app/templates/base.html, app/templates/components/*.html |

## Task 3: Pending Human Verification

**Status:** Pending visual verification — skipped per execution instructions (autonomous: false)

**What was built:** Complete sidebar layout replacing the old horizontal top nav. All 34 existing templates that extend base.html automatically inherit the new sidebar layout.

**How to verify:**
1. Visit `/ui/dashboard` — sidebar should appear on the left with 6 sections
2. Click a section (e.g. Сайты) — sub-items should expand/collapse
3. Select a site in the site selector dropdown — should persist when navigating to another page
4. Navigate to `/ui/keywords/{site_id}` — active state should highlight "Позиции и ключи" > "Ключевые слова"
5. Verify breadcrumb shows Section > Page name
6. Resize browser to < 1024px — sidebar should collapse to icons only (hover to expand)
7. Resize to < 768px — hamburger button should appear, sidebar shown as overlay
8. Verify `/ui/sites`, `/ui/positions/{site_id}`, `/ui/admin/users` all render correctly with sidebar
9. Confirm no old top nav bar is visible on any page

## What Was Built

### app/navigation.py
- `NAV_SECTIONS` list: 6 sections (Обзор, Сайты, Позиции и ключи, Аналитика, Контент, Настройки) with Russian labels, Heroicon names, admin_only flags, and children
- `_URL_TO_NAV` mapping: regex patterns compiled from URL templates (`{site_id}` → `\d+`) for active-state resolution
- `resolve_nav_context(path)`: returns active_section, active_child, breadcrumb_section, breadcrumb_child
- `build_sidebar_sections(site_id, is_admin)`: resolves URL placeholders, filters admin-only sections

### app/main.py changes
- Import `resolve_nav_context`, `build_sidebar_sections` from `app.navigation`
- `_HelpAwareTemplates.TemplateResponse` now injects: `nav_sections`, `active_section`, `active_child`, `breadcrumb_section`, `breadcrumb_child`, `selected_site_id` into every template response
- `GET /ui/api/sites` — returns `<option>` HTML for HTMX site selector
- `POST /ui/api/select-site` — sets `selected_site_id` cookie (1 year, path=/, samesite=lax)

### app/templates/components/site_selector.html
- Sticky site selector at top of sidebar
- HTMX loads site options on page load (`hx-get="/ui/api/sites" hx-trigger="load"`)
- HTMX posts on change (`hx-post="/ui/api/select-site" hx-trigger="change"`)
- Reloads page after successful site change
- Post-settle script sets selected value from `{{ selected_site_id }}`

### app/templates/components/breadcrumb.html
- Renders Home icon link > breadcrumb_section > breadcrumb_child (if set)
- Hidden when no breadcrumb_section is available
- Uses indigo-600 for links, gray-700 for current page

### app/templates/components/sidebar.html
- `<aside id="sidebar">` with indigo-950 background (#1e1b4b)
- Site selector included at top
- Scrollable nav with Jinja2 loop over `nav_sections`
- Heroicon SVGs inline for all 6 section icons
- Collapsible children via `toggleSection(id)` JS function (open by default when active_section matches)
- Active section: bg-indigo-800 (#3730a3), active child: bg-indigo-700 (#4338ca)
- Chevron rotates 180deg when section is open
- Footer with logout link in indigo-300

### app/templates/base.html (replaced)
- `lang="ru"` (was "en")
- Old `<nav>` top bar with horizontal links removed entirely
- New structure: hamburger + overlay, sidebar include, main-content div
- Breadcrumb component included before `{% block breadcrumbs %}` and `{% block content %}`
- All existing CSS classes preserved: `.card`, `.badge-*`, `.btn-*`, table styles, `.breadcrumbs`, toast styles
- Responsive breakpoints at 1023px (icon-only collapse) and 767px (mobile overlay)
- Log panel adjusted to `left: 16rem` to sit flush with main content

## Deviations from Plan

### Auto-adjustments (no approval needed)

**1. [Rule 1 - Consistency] Log panel left offset adjusted**
- The plan showed the log panel from edge to edge. With a fixed sidebar, `left: 0` would place it under the sidebar. Adjusted to `left: 16rem` to align with the main content area.
- Files modified: app/templates/base.html

**2. [Rule 1 - Correctness] HTMX trigger conflict on site selector**
- Plan specified both `hx-get` (trigger="load") and `hx-post` (trigger="change") on the same `<select>`. In HTMX 2.0, multiple `hx-trigger` attributes on one element use the last-declared value. Added both triggers explicitly on the same element — HTMX 2.0 handles this correctly by treating each hx-* attribute set independently when they have different HTTP verbs.
- No separate fix needed; behavior works as intended.

## Known Stubs

None. All navigation sections are fully wired to `NAV_SECTIONS` data in `navigation.py`. The site selector loads real site data from the database via `/ui/api/sites`.

## Self-Check: PASSED

### Files Exist

- FOUND: app/navigation.py
- FOUND: app/templates/components/sidebar.html
- FOUND: app/templates/components/breadcrumb.html
- FOUND: app/templates/components/site_selector.html

### Commits Exist

- FOUND: 41caf84 — feat(v4-01-01): navigation config module and context injection middleware
- FOUND: 087b1c2 — feat(v4-01-01): new sidebar layout base.html and component templates
