---
phase: 23-document-generator
plan: 01
subsystem: backend
tags: [celery, weasyprint, pdf, smtp, sqlalchemy, alembic]

requires:
  - phase: 22-proposal-templates
    provides: ProposalTemplate model, TemplateType enum, template_service, template_variable_resolver, subprocess_pdf

provides:
  - GeneratedDocument model with FK constraints to clients/sites/proposal_templates
  - Alembic migration 0046 (generated_documents table, enum reuse)
  - document_service with CRUD, 3-version cap, type/date filters, filename builder
  - generate_document_pdf Celery task (subprocess PDF, template resolution)
  - send_document Celery task (Telegram text + SMTP with attachment)
  - SMTP send_email_with_attachment_sync extension

affects: [23-02, 23-03]

tech-stack:
  added: []
  patterns: [templatetype enum reuse with create_type=False, sync DB session in send task, async session in generate task]

key-files:
  created:
    - app/models/generated_document.py
    - alembic/versions/0046_add_generated_documents.py
    - app/services/document_service.py
    - app/tasks/document_tasks.py
    - tests/test_document_service.py
  modified:
    - app/models/__init__.py
    - app/services/smtp_service.py
    - app/celery_app.py

key-decisions:
  - "Reuse existing templatetype enum with create_type=False to prevent duplicate type error"
  - "Version cap = MAX_VERSIONS - 1 deletion on enforce_version_cap to make room for new document"
  - "generate_document_pdf uses AsyncSessionLocal; send_document uses get_sync_db (follows client_report_tasks pattern)"
  - "Telegram sends text link only (not sendDocument API) per D-10 decision"

patterns-established:
  - "Enum reuse across tables: SAEnum(EnumClass, name='enumname', create_type=False)"
  - "Document lifecycle: pending -> processing -> ready | failed"

requirements-completed: [DOC-01, DOC-03, DOC-04, DOC-05]

duration: 4min
completed: 2026-04-09
---

# Phase 23 Plan 01: Document Generator Backend Summary

**GeneratedDocument model + migration + CRUD service with 3-version cap + Celery tasks for PDF generation (subprocess WeasyPrint) and delivery (Telegram text + SMTP attachment)**

## What Was Built

### Task 1: Model, Migration, Service, Tests
- **GeneratedDocument model** with FK to clients (CASCADE), sites (SET NULL), proposal_templates (SET NULL), templatetype enum reuse
- **Migration 0046** creating generated_documents table with ix_gd_client_created and ix_gd_template_id indexes
- **document_service** with create, get, list (type/date filters), delete (blocks active jobs), enforce_version_cap (3-version limit), build_filename utility
- **11 unit tests** covering CRUD operations, version cap enforcement, filename generation edge cases

### Task 2: Celery Tasks, SMTP Extension
- **generate_document_pdf** task: resolves template variables, renders HTML via render_template_preview, generates PDF via render_pdf_in_subprocess, updates document status lifecycle, retry=3
- **send_document** task: email channel uses send_email_with_attachment_sync, telegram channel sends text link, retry=3
- **SMTP attachment extension**: send_email_with_attachment_sync and _send_email_with_attachment_async added to smtp_service.py without modifying existing send_email_sync
- **celery_app.py** updated to include app.tasks.document_tasks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Checked out Phase 22 dependency files from master**
- **Found during:** Task 1
- **Issue:** Worktree lacked app/models/proposal_template.py, app/services/template_service.py, app/services/template_variable_resolver.py (Phase 22 files not yet in worktree)
- **Fix:** git checkout b731509 -- for missing dependency files
- **Files added:** app/models/proposal_template.py, app/services/template_service.py, app/services/template_variable_resolver.py, app/models/client.py

**2. [Rule 2 - Missing] Added celery_app.py registration**
- **Found during:** Task 2
- **Issue:** Plan did not explicitly mention updating celery_app.py include list
- **Fix:** Added "app.tasks.document_tasks" to celery_app include list
- **Files modified:** app/celery_app.py

## Verification Results

| Check | Result |
|-------|--------|
| Model import | PASS |
| Service import (all functions) | PASS |
| Tasks import (both) | PASS |
| SMTP extension import | PASS |
| Filename function assertion | PASS |
| Test count (>=8) | PASS (11) |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 3c8cd1d | Model, migration, service, tests |
| 2 | bf1bbfa | Celery tasks, SMTP extension |

## Known Stubs

None - all functions are fully implemented with real logic.

## Self-Check: PASSED
