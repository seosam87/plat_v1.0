---
phase: 19-empty-states-everywhere
plan: "01"
subsystem: templates
tags: [empty-states, jinja2, macros, ux]
dependency_graph:
  requires: []
  provides: [empty_state_macro, core_workflow_empty_states]
  affects: [keywords, positions, crawl, competitors, clusters, gap]
tech_stack:
  added: []
  patterns: [jinja2-macro-with-caller, details-summary-collapsible]
key_files:
  created:
    - app/templates/macros/empty_state.html
  modified:
    - app/templates/keywords/index.html
    - app/templates/positions/index.html
    - app/templates/crawl/history.html
    - app/templates/competitors/index.html
    - app/templates/clusters/index.html
    - app/templates/clusters/cannibalization.html
    - app/templates/gap/index.html
key_decisions:
  - "caller() guard prevents UndefinedError when macro called without {% call %} block"
  - "clusters/index.html was missing {% if clusters %} guard — added as part of migration"
  - "gap/index.html gets two separate empty states: keywords section and proposals section"
metrics:
  duration_minutes: 2
  completed_date: "2026-04-09"
  tasks_completed: 2
  files_changed: 8
---

# Phase 19 Plan 01: Empty State Macro + Core Workflow Pages Summary

**One-liner:** Reusable Jinja2 `empty_state` macro with `caller()` support, applied to 7 core workflow pages replacing ad-hoc bare text messages.

## What Was Built

### Task 1: empty_state Jinja2 macro (`app/templates/macros/empty_state.html`)

Created a single-macro file following existing `macros/health.html` pattern:
- Parameters: `reason` (str), `cta_label` (str), `cta_url` (str), `secondary_label` (optional), `secondary_url` (optional), `docs_url` (reserved)
- Outer card: `bg-white rounded-lg shadow-sm border border-gray-200 p-6 my-4`
- Reason text: `text-gray-700 font-medium mb-3`
- Collapsible how-to via `<details>/<summary>` with "Как использовать" label
- `{% if caller is defined %}` guard prevents `UndefinedError` when called without `{% call %}` block
- Primary CTA: `bg-blue-600 text-white` button
- Optional secondary link: `text-indigo-600 hover:underline`
- No icons, no inline styles, Tailwind classes only

### Task 2: Applied to 7 core workflow templates

| Template | Change | CTA |
|----------|--------|-----|
| `keywords/index.html` | Replaced "No keywords yet" | Import → /ui/uploads |
| `positions/index.html` | Replaced "No position data yet" | Run check (+ secondary: import) |
| `crawl/history.html` | Replaced "No crawl jobs yet" | Start crawl |
| `competitors/index.html` | Replaced "No competitors yet" | Add competitor |
| `clusters/index.html` | Added missing `{% if clusters %}` guard + empty state | Auto-cluster |
| `clusters/cannibalization.html` | Replaced positive "No cannibalization" message | Check positions (+ secondary: clusters) |
| `gap/index.html` | TWO empty states: keywords section + proposals section | Import gap keys / Create proposals |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all empty states have real CTAs pointing to live routes.

## Self-Check: PASSED

All 8 files confirmed present on disk. Both task commits confirmed in git log:
- `9b2684d` feat(19-01): create reusable empty_state Jinja2 macro
- `7f0614e` feat(19-01): apply empty_state macro to 7 core workflow templates
