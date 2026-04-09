---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Client & Proposal
status: verifying
stopped_at: Phase 22 context gathered
last_updated: "2026-04-09T14:31:16.688Z"
last_activity: 2026-04-09
progress:
  total_phases: 42
  completed_phases: 37
  total_plans: 120
  completed_plans: 112
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-09)

**Core value:** A team member or client can open the platform and immediately see the SEO health of any site — positions, recent changes, pending tasks — without switching between GSC, spreadsheets, and WP admin.
**Current focus:** Phase 21 — site-audit-intake

## Current Position

Phase: 999.3
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-04-09

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity (v2.1 reference):**

- Total plans completed (v2.1): 13
- Average duration: ~6 min/plan
- Recent trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Key Decisions (v3.0)

| Decision | Rationale |
|----------|-----------|
| Client CRM first (Phase 20) | All other v3.0 features require clients table + client_id FK — hard dependency |
| Separate Client entity from User | Client = company (CRM); User role=client = auth; different tables; never conflate |
| SandboxedEnvironment for proposal templates | User-authored Jinja2 must not access config.SECRET_KEY or app globals |
| WeasyPrint via subprocess_pdf.py only | Direct weasyprint.HTML().write_pdf() causes OOM kills (D-12 decision) |
| require_manager_or_above for CRM writes | require_admin locks out managers; require_any_authenticated causes IDOR on client data |
| Three sequential Alembic migrations | 0043 clients, 0044 intake, 0045 proposals — run alembic check before each --autogenerate |
| Phase 21-site-audit-intake P01 | 4 | 2 tasks | 5 files |
| Phase 21-site-audit-intake P03 | 4 | 2 tasks | 3 files |
| Phase 21-site-audit-intake P02 | 2 | 2 tasks | 4 files |

### Pending Todos

- Phase 20 planning: confirm Client vs User schema ADR before first migration
- Phase 20 planning: define RBAC rules per endpoint (manager_or_above + row-level client_id check for client-role reads)
- Phase 22 planning: confirm variable resolver scope (static ~15 vars for v3.0; live aggregate queries deferred)
- Phase 23 planning: confirm PDF storage strategy (DB bytes with 3-version cap vs filesystem path reference)

### Blockers/Concerns

None. Research confidence HIGH. All patterns have established codebase precedents.

## Session Continuity

Last session: 2026-04-09T14:31:16.682Z
Stopped at: Phase 22 context gathered
Resume file: .planning/phases/22-proposal-templates/22-CONTEXT.md
