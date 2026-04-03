---
phase: v4-06-section-content
plan: "02"
subsystem: templates/pipeline
tags: [tailwind, migration, pipeline, htmx, modal, tabs]
dependency_graph:
  requires: []
  provides: [pipeline-jobs-tailwind, pipeline-publish-tailwind]
  affects: [pipeline-section-ui]
tech_stack:
  added: []
  patterns: [tailwind-badges, classList-modal-toggle, classList-tab-toggle]
key_files:
  created: []
  modified:
    - app/templates/pipeline/jobs.html
    - app/templates/pipeline/publish.html
decisions:
  - "Diff modal uses classList toggle (hidden/flex) not style.display — consistent with v4-04/v4-05 patterns"
  - "Tab panel show/hide uses classList.add/remove('hidden') not style.display — consistent with zero inline style constraint"
  - "JS diff line coloring in innerHTML uses class= not inline style= — matches v4-05-01 pattern"
metrics:
  duration: "164s"
  completed: "2026-04-04"
  tasks: 2
  files: 2
---

# Phase v4-06 Plan 02: Pipeline Templates Tailwind Migration Summary

**One-liner:** Migrated pipeline/jobs.html and pipeline/publish.html to pure Tailwind — zero inline style= attributes, classList-based diff modal and tab viewer, all HTMX/form interactions preserved.

## What Was Done

Converted two 133-line pipeline templates (WP Pipeline jobs viewer and DOCX Publisher) from inline CSS to pure Tailwind utility classes. Both templates now have zero `style=` attributes.

### Task 1: pipeline/jobs.html

- Header flex bar, bulk action buttons, table, status badges, action row buttons all migrated to Tailwind
- Status badges use conditional Tailwind classes: `bg-emerald-100/text-emerald-700` (pushed), `bg-amber-100/text-amber-700` (awaiting_approval), `bg-red-100/text-red-700` (failed), `bg-gray-100/text-gray-700` (other)
- Diff modal rewritten: backdrop uses `hidden fixed inset-0 bg-black/50 z-50 justify-center items-center` toggled to flex via classList
- `showDiff()` JS updated to use `classList.remove('hidden'); classList.add('flex')` instead of `style.display = 'flex'`
- Backdrop click handler uses `classList.add('hidden'); classList.remove('flex')`
- Diff line coloring in innerHTML uses `class="text-emerald-600 bg-emerald-50"` and `class="text-red-600 bg-red-50"` not inline styles
- All HTMX: hx-post (4 matches), hx-swap, hx-confirm (1 rollback confirm) preserved exactly

### Task 2: pipeline/publish.html

- Upload form container migrated from complex inline flex+padding+background styles to `class="flex gap-4 items-end flex-wrap mb-6 p-6 bg-gray-50 rounded-lg border border-dashed border-gray-300"`
- All form inputs/selects use standard Tailwind pattern: `px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-indigo-500 focus:border-indigo-500`
- Tab bar uses classList-based toggle: active tab gets `border-b-2 border-indigo-600 -mb-0.5 bg-white text-indigo-600 font-semibold`, inactive gets `bg-gray-50 text-gray-500`
- `showTab()` fully rewritten to use classList not style properties
- HTML source and Schema.org panels start `class="hidden"` instead of `style="display:none"`
- Code preview panels use `bg-gray-900 text-gray-200` (dark theme)
- Recent jobs table uses same badge palette as jobs.html
- TOC check/cross uses `class="text-emerald-600"` / `class="text-red-600"`
- Both upload form (POST to `/ui/content-publish/{site.id}/upload`) and publish form (POST to `/ui/content-publish/{site.id}/publish`) preserved

## Verification Results

| Check | Result |
|-------|--------|
| `style=` count in jobs.html | 0 |
| `style=` count in publish.html | 0 |
| hx-post/hx-swap/hx-confirm count in jobs.html | 5 |
| classList matches in jobs.html | 4 |
| diff-modal references in jobs.html | 5 |
| showTab matches in publish.html | 4 |
| classList matches in publish.html | 2 |
| upload form action preserved | yes |
| publish form method="post" preserved | yes |
| bg-gray-900 (code panels) | 2 |
| border-indigo-600 (active tab) | 2 |

## Commits

| Task | File | Commit |
|------|------|--------|
| 1 | app/templates/pipeline/jobs.html | 30d56de |
| 2 | app/templates/pipeline/publish.html | 666329d |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both templates render real data from context variables (jobs, preview, site).

## Self-Check: PASSED
