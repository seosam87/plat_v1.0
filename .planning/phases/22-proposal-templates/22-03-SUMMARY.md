---
phase: 22-proposal-templates
plan: 03
subsystem: ui
tags: [verification, bugfix, codemirror, jinja2, htmx]

requires:
  - phase: 22-proposal-templates
    plan: 01
    provides: ProposalTemplate model, service, variable resolver
  - phase: 22-proposal-templates
    plan: 02
    provides: Router, HTML pages, CodeMirror editor

provides:
  - Human-verified proposal template CRUD (create, edit, clone, delete)
  - Working CodeMirror 6 editor with ESM bundle
  - Variable insertion with correct Jinja2 delimiters
  - Template body persistence via HTMX save
  - Preview with client/site variable resolution

affects: [23-proposals]

tech-stack:
  fixed:
    - CodeMirror bundle rebuilt as ESM (was IIFE — dynamic import got no exports)
    - Jinja2 {% raw %} block around JS to prevent server-side {{ }} interpolation
    - htmx:configRequest writes body to evt.detail.parameters (hidden input timing bug)
    - crawl_jobs SQL uses started_at not created_at
---

<what_was_done>
Human verification of proposal templates feature with 3 bugs found and fixed inline.

### Bugs Fixed
1. **Variable resolver SQL error** — `created_at` column doesn't exist in `crawl_jobs`, changed to `started_at`
2. **CodeMirror not loading** — bundle was built as IIFE, not ESM; `await import()` got no exports. Rebuilt with `esbuild --format=esm`
3. **Variables inserted as literal "varName"** — Jinja2 server-side rendering consumed `{{ ' + varName + ' }}` in JS. Wrapped script block in `{% raw %}`
4. **Template body not persisting on save** — `htmx:configRequest` set hidden input value too late; HTMX already collected params. Fixed to write `evt.detail.parameters['body']` directly

### Verification Results (11 checks)
| # | Check | Result |
|---|-------|--------|
| 1 | Sidebar "Шаблоны КП" under CRM | PASS |
| 2 | Empty state | PASS |
| 3 | Create template | PASS |
| 4 | Variable panel click-to-insert | PASS (after fix) |
| 5 | Preview with client/site data | PASS (after fix) |
| 6 | Clone with "(копия)" suffix | PASS |
| 7 | Edit + save persistence | PASS (after fix) |
| 8 | Delete with confirmation | PASS |
| 9 | Type badges (violet/blue/green) | DEFERRED (user unclear on requirement) |
| 10 | Preview < 5s performance | DEFERRED |
| 11 | Non-admin access control | DEFERRED (will verify across whole system later) |

8/11 verified, 3 deferred (non-blocking — cosmetic/performance/cross-system RBAC).
</what_was_done>

<key_files>
created: []
modified:
  - app/services/template_variable_resolver.py (started_at fix)
  - app/static/js/codemirror.bundle.js (ESM rebuild)
  - app/templates/proposal_templates/edit.html (raw block, htmx fix, editor label)
</key_files>

<decisions>
- D-16: Deferred items 9/10/11 are non-blocking for phase completion — will surface in UAT audit
</decisions>

<issues>
None blocking.
</issues>
