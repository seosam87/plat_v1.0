# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v2.1 — Onboarding & Project Health

**Shipped:** 2026-04-09
**Phases:** 4 | **Plans:** 13 | **Commits:** 143

### What Was Built
- 7-step project health checklist on Site Overview with DB-derived status signals (no new models/migrations)
- Reusable `empty_state` Jinja2 macro applied across 17+ pages with Russian contextual help
- YAML-based Playwright scenario runner as pytest plugin with CI docker-compose overlay and 2 P0 scenarios
- Shepherd.js interactive tour player consuming the same scenario YAMLs — single source of truth for tests and tours

### What Worked
- Small milestone scope (4 phases) with clear UX goal kept focus tight
- Phase 19.1/19.2 promoted from backlog mid-milestone — backlog system worked as intended for opportunistic insertion
- YAML schema reservation (tour step types in test schema) enabled seamless Phase 19.2 consumption of Phase 19.1 files
- Empty state macro pattern: single macro + `{% call %}` blocks = zero logic in macro, all content in templates

### What Was Inefficient
- Phase 19.2 plans generated before execution — 4 plan files exist as untracked git files, suggesting planning happened outside normal flow
- `roadmap analyze` CLI returned 0 phases for v2.1 (missing_phase_details) — tool didn't parse decimal phase numbers correctly

### Patterns Established
- Empty state pattern: `{% from "macros/empty_state.html" import empty_state %}` with icon, title, message, action CTA
- Scenario YAML dual-use: same files power both Playwright E2E tests and Shepherd.js onboarding tours
- Health widget pattern: compute_site_health() returns structured dict, reusable across pages

### Key Lessons
1. Read-path-only phases (no migrations, no new models) ship extremely fast — Phase 18 was 1 plan, 1 session
2. Backlog promotion works well when the promoted item has a clear dependency on in-flight work (19.1→19.2)
3. Macro-based empty states are more maintainable than per-page components — content stays in templates where translators/editors expect it

### Cost Observations
- Model mix: ~80% opus, ~20% sonnet (executor agents)
- Sessions: ~4 sessions across 2 days
- Notable: Fastest milestone to date (2 days for 4 phases, 13 plans)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Duration | Key Change |
|-----------|--------|-------|----------|------------|
| v1.0 | 16+ | 50+ | ~4 days | Full MVP build, analytics, UI overhaul |
| v2.0 | 7 | 24 | ~2 days | Analytical features + AI integration |
| v2.1 | 4 | 13 | ~2 days | UX polish + testing infrastructure |

### Top Lessons (Verified Across Milestones)

1. Small, focused milestones with clear UX goals ship faster than large feature bundles
2. Inserted phases (decimal numbering) work well for urgent fixes and opportunistic additions
3. Reusable patterns (macros, services) established early pay off across subsequent phases
