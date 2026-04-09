---
phase: 23-document-generator
plan: 02
subsystem: frontend
tags: [fastapi, jinja2, htmx, router, templates, pdf]

requires:
  - phase: 23-document-generator
    plan: 01
    provides: GeneratedDocument model, document_service, document_tasks, template_service

provides:
  - Documents router with 7 endpoints at /ui/crm/clients/{id}/documents
  - Documents tab in client detail page with generate form, filters, table
  - HTMX polling status partial for generation progress
  - Document row partial with type badges, status indicators, action buttons

affects: [23-03]

tech-stack:
  added: []
  patterns: [HTMX afterbegin swap for new items, refreshDocList custom event trigger, active_tab context variable for tab state]

key-files:
  created:
    - app/routers/documents.py
    - app/templates/crm/_documents_tab.html
    - app/templates/crm/documents/_doc_row.html
    - app/templates/crm/documents/_gen_status.html
  modified:
    - app/main.py
    - app/templates/crm/detail.html

key-decisions:
  - "Router returns HTMLResponse for all endpoints; download returns raw PDF Response"
  - "Send endpoint returns inline toast HTML instead of redirect for HTMX compatibility"
  - "Delete endpoint returns empty body with HX-Trigger header for table refresh"
  - "detail.html uses active_tab context variable to support direct navigation to documents tab"

patterns-established:
  - "HX-Trigger: refreshDocList for cross-component table refresh after status change or delete"
  - "Native confirm() dialogs for destructive actions (delete, send, regenerate)"
  - "toggleSendMenu with click-outside handler for dropdown menus"

requirements-completed: [DOC-01, DOC-02, DOC-03, DOC-04, DOC-05]

duration: 4min
completed: 2026-04-09
---

# Phase 23 Plan 02: Document Generator UI & Router Summary

**Documents router with 7 endpoints + 3 Jinja2 templates + detail.html integration for generate/list/download/send/regenerate/delete with HTMX polling and type/date filters**

## What Was Built

### Task 1: Documents Router with All Endpoints
- **7 endpoint handlers** mounted at `/ui/crm/clients/{client_id}/documents`
- **GET /** returns documents tab with filters (type, date_from, date_to); supports HTMX partial and full page render
- **POST /generate** creates document + dispatches `generate_document_pdf.delay`; returns gen_status partial
- **GET /{doc_id}/status** HTMX polling endpoint; returns HX-Trigger: refreshDocList when ready
- **GET /{doc_id}/download** returns PDF with Content-Disposition attachment header
- **POST /{doc_id}/send** validates channel (email/telegram), checks client email, dispatches `send_document.delay`
- **POST /{doc_id}/regenerate** creates new version with enforce_version_cap, dispatches task
- **POST /{doc_id}/delete** hard deletes document, returns HX-Trigger for table refresh
- All endpoints protected with `require_manager_or_above`
- Router registered in `app/main.py`

### Task 2: Jinja2 Templates + Detail Page Integration
- **_documents_tab.html** — Generate form (template + site selects), type/date filter controls with HTMX, documents table with row includes, empty state with document SVG icon, flatpickr initialization, JS functions (toggleSendMenu, confirmSend, confirmRegenerate)
- **_doc_row.html** — Table row with file name (truncated 40 chars), type badges (violet/blue/green matching Phase 22), site, date DD.MM.YYYY, status badges (4 states), action buttons (download, send dropdown, regenerate, delete with confirm)
- **_gen_status.html** — Three-state polling partial: generating (hx-trigger="load delay:3s"), ready (terminal, no polling), failed (terminal, shows error_message)
- **detail.html** — Added "Документы" tab button with active_tab conditional styling, tab panel with _documents_tab.html include, toast-container div, updated sites tab to respect active_tab variable

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Checked out dependency files from master**
- **Found during:** Task 1
- **Issue:** Worktree lacked Plan 01 output files and CRM templates
- **Fix:** `git checkout master --` for models, services, tasks, and template files
- **Files added:** Multiple dependency files from Phase 22 and Plan 01

## Verification Results

| Check | Result |
|-------|--------|
| Router syntax valid | PASS |
| documents_router in main.py | PASS |
| All 4 template files exist | PASS |
| detail.html has documents tab | PASS |
| No hx-trigger in terminal states | PASS |
| Type badge colors match Phase 22 | PASS |
| Confirm dialog strings match UI-SPEC | PASS |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 3205d5f | Documents router with 7 endpoints + main.py registration |
| 2 | 05cfc74 | Jinja2 templates for documents tab, row partial, status polling |

## Known Stubs

None - all templates render real data from router context, all endpoints connect to real services and tasks.

## Self-Check: PASSED
