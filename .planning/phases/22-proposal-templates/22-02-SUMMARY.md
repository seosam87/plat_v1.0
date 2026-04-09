---
phase: 22-proposal-templates
plan: 02
subsystem: ui
tags: [fastapi, jinja2, htmx, codemirror, proposal-templates, crm]

requires:
  - phase: 22-01
    provides: ProposalTemplate model, template_service CRUD, template_variable_resolver with SandboxedEnvironment

provides:
  - FastAPI router at /ui/templates with 9 endpoints (list, new, edit, create, update, delete, clone, preview, sites)
  - Template list page with card grid, type badges, admin-only actions, empty state
  - Template editor page with CodeMirror 6 (esm.sh CDN), iframe preview, grouped variable panel (15 vars)
  - Dependent client→site select via HTMX GET /ui/templates/sites
  - Navigation entry "Шаблоны КП" under CRM sidebar section

affects: [22-03, proposal-generation]

tech-stack:
  added: [CodeMirror 6 via esm.sh CDN (@codemirror/basic-setup, @codemirror/lang-html, @codemirror/view)]
  patterns:
    - HTMX dependent select (client→site) via hx-get + hx-target outerHTML swap
    - CodeMirror body sync to hidden input via htmx:configRequest event
    - iframe.srcdoc for preview isolation (no base.html wrapper in preview endpoint)
    - HX-Redirect header for post-action navigation (clone, delete)
    - JSON-encoded initial editor content via script type=application/json to avoid Jinja2 escaping issues

key-files:
  created:
    - app/routers/templates.py
    - app/templates/proposal_templates/index.html
    - app/templates/proposal_templates/edit.html
  modified:
    - app/main.py
    - app/navigation.py
    - app/template_engine.py

key-decisions:
  - "Fixed route ordering: /sites and /preview defined before /{template_id} routes to prevent FastAPI UUID parse errors on literal path segments"
  - "Preview endpoint returns raw HTML with no base.html wrapper — iframe srcdoc isolates styles from platform UI"
  - "CodeMirror initial body encoded as JSON in <script type=application/json> to survive Jinja2 auto-escaping"
  - "Clone and delete use HX-Redirect header for navigation — avoids full page reload pattern inconsistency"

patterns-established:
  - "Proposal template CRUD router: all writes admin-only, reads all-authenticated"
  - "Variable panel click-to-insert via window.insertVariable() bridge to CodeMirror view.dispatch()"

requirements-completed: [TPL-01, TPL-02, TPL-03, TPL-04]

duration: 12min
completed: 2026-04-09
---

# Phase 22 Plan 02: Templates Router + HTML Pages Summary

**FastAPI router with 9 endpoints for proposal template CRUD/clone/preview, three-column CodeMirror 6 editor page, and card grid list page wired into CRM navigation**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-09T18:05:00Z
- **Completed:** 2026-04-09T18:17:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Templates router (`app/routers/templates.py`) with 9 endpoints, correct auth guards, registered in main.py
- List page with card grid (auto-fill 300px columns), type badges (violet/blue/green), admin-only actions (edit/clone/delete), empty state with CTA
- Editor page with three-column flex layout: CodeMirror 6 editor | iframe preview | variable panel (15 vars in 3 groups)
- CodeMirror initializes from JSON-encoded initial content, syncs to hidden input on submit, variable panel inserts at cursor
- Dependent client→site select via HTMX; preview fetches /ui/templates/preview and sets iframe.srcdoc
- Navigation sidebar updated with "Шаблоны КП" entry under CRM; help module mapped

## Task Commits

1. **Task 1: Templates router with all endpoints + app registration** - `bc99f9f` (feat)
2. **Task 2: Template list page + Edit page with CodeMirror and preview** - `deb8300` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/routers/templates.py` — 9-endpoint FastAPI router for template CRUD/clone/preview
- `app/templates/proposal_templates/index.html` — Template list page with card grid
- `app/templates/proposal_templates/edit.html` — Three-column editor with CodeMirror 6, iframe preview, variable panel
- `app/main.py` — Added templates_router registration
- `app/navigation.py` — Added crm-templates sidebar entry
- `app/template_engine.py` — Added /ui/templates help module mapping

## Decisions Made
- Fixed route ordering: literal path segments (/sites, /preview) defined before parameterized /{template_id} routes to prevent FastAPI attempting UUID parsing on "sites"/"preview" strings — follows plan's IMPORTANT routing note exactly
- CodeMirror initial body JSON-encoded via Jinja2 `|tojson` filter inside `<script type="application/json">` tag to avoid double-escaping of HTML entities in template bodies
- Preview endpoint returns raw HTML (no base.html wrapper) — iframe.srcdoc isolates the rendered template from platform CSS

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria verified.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. CodeMirror loads from esm.sh CDN at runtime.

## Next Phase Readiness

Plan 22-03 (PDF generation) can now use the template data and preview infrastructure. The router provides the complete CRUD + clone + preview surface needed for Phase 23 (proposal document generation).

---
*Phase: 22-proposal-templates*
*Completed: 2026-04-09*
