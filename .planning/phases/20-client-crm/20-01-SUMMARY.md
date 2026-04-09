---
phase: 20-client-crm
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, async, crm, postgresql]

requires: []
provides:
  - Client, ClientContact, ClientInteraction SQLAlchemy models
  - Alembic migration 0043 for CRM tables
  - Async service layer with 16 functions (CRUD, search, pagination, site linking)
  - Service layer tests
affects: [20-02, 20-03, 20-04]

tech-stack:
  added: []
  patterns:
    - "CRM soft delete via is_deleted flag (Client model)"
    - "Module-level async service functions (not class-based)"

key-files:
  created:
    - app/models/client.py
    - alembic/versions/0043_add_crm_tables.py
    - app/services/client_service.py
    - tests/services/test_client_service.py
    - tests/models/test_client_models.py
  modified:
    - app/models/site.py
    - app/models/__init__.py

key-decisions:
  - "Soft delete for clients (is_deleted flag), hard delete for contacts and interactions"
  - "No SQLAlchemy relationship() declarations -- service layer uses explicit select() queries"
  - "Site.client_id FK with SET NULL ondelete -- detaching doesn't delete the site"

patterns-established:
  - "CRM service pattern: module-level async functions with AsyncSession first param"
  - "Date range filtering via created_from/created_to date params"

requirements-completed: [CRM-01, CRM-02, CRM-04, CRM-05, CRM-06]

duration: 12min
completed: 2026-04-09
---

# Plan 20-01: CRM Data Layer Summary

**Three CRM models, migration 0043, and 16-function async service layer with full CRUD, search, pagination, date filtering, and site-client linking.**

## What Was Built

1. **Models** (`app/models/client.py`): Client (with soft delete), ClientContact, ClientInteraction -- all using mapped_column pattern consistent with existing models.

2. **Migration** (`alembic/versions/0043_add_crm_tables.py`): Creates clients, client_contacts, client_interactions tables in correct FK order. Adds sites.client_id nullable FK.

3. **Service Layer** (`app/services/client_service.py`): 16 async functions covering:
   - Client CRUD with soft delete
   - list_clients with search (company_name/inn/email ILIKE), manager filter, date range filter, pagination, ordered by company_name ASC
   - Contact CRUD (hard delete)
   - Interaction CRUD with pagination ordered by interaction_date DESC
   - Site attach/detach with conflict detection
   - Unattached site listing with optional search
   - Open task count across client's sites

4. **Tests** (`tests/services/test_client_service.py`): 20 test functions covering all service operations including edge cases (soft delete exclusion, attach conflict, date range filtering).

## Self-Check: PASSED

- [x] Models import correctly
- [x] Service layer imports all 16 functions
- [x] Migration file exists with correct revision chain (0042 -> 0043)
- [x] Site model has client_id FK
- [x] Tests written for all service functions
