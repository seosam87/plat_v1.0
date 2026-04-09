---
phase: 21-site-audit-intake
plan: "01"
subsystem: backend
tags: [model, migration, service, tests, intake]
dependency_graph:
  requires:
    - "0043_add_crm_tables (clients + sites.client_id FK)"
    - "app/models/site.py (ConnectionStatus, metrika_counter_id)"
    - "app/models/oauth_token.py (OAuthToken, provider)"
    - "app/models/crawl.py (CrawlJob, CrawlJobStatus)"
    - "app/models/architecture.py (SitemapEntry, site_id)"
  provides:
    - "app/models/site_intake.py (SiteIntake model, IntakeStatus enum)"
    - "alembic/versions/0044_add_site_intakes_table.py (DB migration)"
    - "app/services/intake_service.py (10 service functions)"
    - "tests/services/test_intake_service.py (19 tests)"
  affects:
    - "app/models/__init__.py (SiteIntake registered for Alembic autogenerate)"
    - "Plan 21-02 (UI routes depend on intake_service functions)"
    - "Plan 21-03 (HTMX tabs depend on get_verification_checklist and section saves)"
tech_stack:
  added: []
  patterns:
    - "SiteIntake model with JSON fields + boolean section flags (same pattern as Page model)"
    - "IntakeStatus str enum (same pattern as ConnectionStatus, CrawlJobStatus)"
    - "get_or_create pattern with IntegrityError retry for race-safe creation"
    - "Verification checklist: 5-query pattern across 4 models using func.count()"
    - "Batch status query (get_intake_statuses_for_sites) for N+1 avoidance on site list"
key_files:
  created:
    - app/models/site_intake.py
    - alembic/versions/0044_add_site_intakes_table.py
    - app/services/intake_service.py
    - tests/services/test_intake_service.py
  modified:
    - app/models/__init__.py
decisions:
  - "IntakeStatus draft/complete (not draft/in_progress/complete) — RESEARCH.md D-15"
  - "JSON fields goals_data/technical_data on the model itself (not separate tables) — D-16"
  - "reopen_intake keeps section flags intact — RESEARCH.md open question 2 recommendation"
  - "get_or_create_intake handles IntegrityError with SELECT retry for race safety"
metrics:
  duration_minutes: 4
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
  tests_added: 19
  tests_passing: 19
  completed_date: "2026-04-09"
requirements:
  - INTAKE-01
  - INTAKE-02
  - INTAKE-03
  - INTAKE-04
---

# Phase 21 Plan 01: Site Audit Intake — Backend Foundation Summary

**One-liner:** SiteIntake model with JSON sections + 5-item verification checklist service querying Site, OAuthToken, SitemapEntry, CrawlJob via 10 async service functions and 19 passing tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SiteIntake model, migration, and model registration | e57efd7 | app/models/site_intake.py, app/models/__init__.py, alembic/versions/0044_add_site_intakes_table.py |
| 2 | Intake service layer with verification checklist and section save functions | 9685a39 | app/services/intake_service.py, tests/services/test_intake_service.py |

## What Was Built

### SiteIntake Model (`app/models/site_intake.py`)
- UUID primary key, `site_id` FK with `unique=True` and `ondelete="CASCADE"` to sites table
- `IntakeStatus` str enum: `draft` / `complete`
- JSON fields: `goals_data` (main_goal, target_regions, competitors, notes), `technical_data` (robots_notes)
- Five boolean section flags: `section_access`, `section_goals`, `section_analytics`, `section_technical`, `section_checklist` (all default False)
- `created_at` / `updated_at` DateTime(timezone=True)

### Alembic Migration 0044
- Creates `site_intakes` table with all columns
- `intakestatus` PostgreSQL enum type (draft/complete)
- `server_default="draft"` for status, `server_default=false` for all boolean flags
- Index on `site_id`, unique constraint via column definition
- Proper downgrade with enum type cleanup

### Intake Service Layer (`app/services/intake_service.py`)
- `get_or_create_intake`: race-safe with IntegrityError retry
- `save_goals_section`, `save_technical_section`: store JSON data + set section flags
- `save_access_section`, `save_analytics_section`, `save_checklist_section`: flag-only (read-only/derived tabs)
- `get_verification_checklist`: 5-item list with labels in Russian (WP подключен, GSC подключен, Метрика подключена, Sitemap найден, Краул выполнен) — each item has `status` in ("connected", "not_configured", "unknown")
- `complete_intake`, `reopen_intake`: status transitions (reopen preserves section flags)
- `get_intake_statuses_for_sites`: batch `IN` query returning `{site_id: status_value}` dict

### Tests (`tests/services/test_intake_service.py`)
19 tests covering all service functions, all passing.

## Deviations from Plan

None — plan executed exactly as written. The test DB required applying the `client_id` FK column from migration 0043 (applied directly since test DB uses `create_all` pattern without tracked alembic versions). This was a test environment setup issue, not a code deviation.

## Self-Check: PASSED

- `app/models/site_intake.py` — exists, verified
- `alembic/versions/0044_add_site_intakes_table.py` — exists, verified
- `app/services/intake_service.py` — exists, verified
- `tests/services/test_intake_service.py` — exists, verified
- `app/models/__init__.py` — updated, verified
- Commits e57efd7 and 9685a39 — verified in git log
- All 19 tests passing — verified with pytest output
