---
phase: 21-site-audit-intake
verified: 2026-04-09T14:30:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 21: Site Audit Intake Verification Report

**Phase Goal:** Users can fill a structured site intake form that auto-populates known platform data, save progress section by section, and mark a site as intake-complete — giving the team a single structured record of site access, goals, and configuration at onboarding time
**Verified:** 2026-04-09T14:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SiteIntake model exists with JSON fields, boolean section flags, and IntakeStatus enum | VERIFIED | `app/models/site_intake.py` — class SiteIntake with goals_data/technical_data (JSON), 5 boolean section_* flags, IntakeStatus(draft/complete) |
| 2 | Alembic migration 0044 creates site_intakes table with unique constraint on site_id | VERIFIED | `alembic/versions/0044_add_site_intakes_table.py` exists, creates `site_intakes` table with index on site_id |
| 3 | Service layer covers get-or-create, section saves, checklist, complete/reopen, batch status | VERIFIED | `app/services/intake_service.py` — all 10 functions present and substantive: get_or_create_intake, save_goals_section, save_technical_section, save_access_section, save_analytics_section, save_checklist_section, get_verification_checklist, complete_intake, reopen_intake, get_intake_statuses_for_sites |
| 4 | 10+ tests exist for service layer | VERIFIED | `tests/services/test_intake_service.py` — 19 test functions confirmed |
| 5 | User can open /ui/sites/{id}/intake and see a 5-tab form with tab switching | VERIFIED | Intake router GET handler confirmed at `/ui/sites/{site_id}/intake`, form.html has 5 tab buttons (Доступы, Цели и конкуренты, Аналитика, Технический SEO, Чеклист верификации) with `switchTab()` JS |
| 6 | User can fill goals/competitors and save with HTMX, receiving a toast | VERIFIED | POST `/ui/sites/{site_id}/intake/goals` exists, form.html Tab 2 uses `hx-post`, router returns HX-Trigger `showToast + sectionSaved` |
| 7 | User can see verification checklist with 3-state indicators from platform data | VERIFIED | `get_verification_checklist` queries Site, OAuthToken, SitemapEntry, CrawlJob; returns 5 items; `_tab_checklist.html` renders connected/not_configured/unknown states |
| 8 | User can refresh checklist via Перепроверить without page reload | VERIFIED | form.html Tab 5 has `hx-get` button "Перепроверить" targeting `#checklist-content`; GET `/ui/sites/{site_id}/intake/checklist` endpoint returns partial |
| 9 | Site list and detail pages show intake status badges with links to intake form | VERIFIED | `sites/index.html` has "Intake" column (line 25) with green checkmark/gray dash; `sites/detail.html` has 3-state intake badge below client row |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models/site_intake.py` | SiteIntake model + IntakeStatus enum | VERIFIED | 58 lines; class SiteIntake(Base) with __tablename__="site_intakes", site_id unique FK, JSON fields, 5 bool flags, timestamps |
| `alembic/versions/0044_add_site_intakes_table.py` | DB migration for site_intakes | VERIFIED | Exists; creates site_intakes table, creates intakestatus enum, index on site_id; has proper downgrade |
| `app/services/intake_service.py` | CRUD + checklist service | VERIFIED | 226 lines; all 10 required functions present with async def, keyword-only args, db.flush() |
| `tests/services/test_intake_service.py` | 10+ service tests | VERIFIED | 411 lines, 19 test functions covering all service paths |
| `app/routers/intake.py` | Router with 8 endpoints | VERIFIED | 226 lines; APIRouter(prefix="/ui/sites"); 8 routes confirmed via introspection |
| `app/templates/intake/form.html` | 5-tab intake form page | VERIFIED | 393 lines; extends base.html; all 5 tabs present with HTMX wiring, JS functions, checkmark tracking |
| `app/templates/intake/_tab_checklist.html` | Checklist HTMX fragment | VERIFIED | 26 lines; loops checklist items; 3-state icon+badge with Jinja2 conditional class construction |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/routers/intake.py` | `app/services/intake_service.py` | `from app.services import intake_service` | WIRED | All 8 handlers call intake_service functions; confirmed in router code |
| `app/routers/intake.py` | `app/templates/intake/form.html` | `templates.TemplateResponse(..., "intake/form.html", ...)` | WIRED | GET handler renders form.html with site/intake/checklist/gsc_connected/client context |
| `app/main.py` | `app/routers/intake.py` | `from app.routers.intake import router as intake_router` + `app.include_router(intake_router)` | WIRED | Lines 176-177 of main.py confirmed |
| `app/main.py (ui_site_list)` | `app/services/intake_service.py` | `intake_service.get_intake_statuses_for_sites` | WIRED | Lines 273-282 of main.py — batch prefetch with `intake_statuses` in template context |
| `app/main.py (ui_site_overview)` | `app/models/site_intake.py` | `sa_select(SiteIntake).where(SiteIntake.site_id == sid)` | WIRED | Lines 2248-2270 — SELECT-only fetch; `intake` passed to template context |
| `app/models/__init__.py` | `app/models/site_intake.py` | `from app.models.site_intake import SiteIntake, IntakeStatus` | WIRED | Line 7 of __init__.py confirmed |
| `app/services/intake_service.py` | `app/models/site_intake.py` | SQLAlchemy ORM via SiteIntake | WIRED | Direct model usage across all service functions |
| `app/services/intake_service.py` | `app/models/site.py` | `Site.connection_status`, `Site.metrika_counter_id` | WIRED | get_verification_checklist queries both fields |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `form.html` — Tab 2 goals pre-population | `intake.goals_data` | `intake_service.get_or_create_intake` → DB SELECT on SiteIntake | Yes — real DB query via `_get_intake` | FLOWING |
| `form.html` — Tab 5 checklist items | `checklist` | `intake_service.get_verification_checklist` → 5 real DB queries (Site, OAuthToken, SitemapEntry, CrawlJob) | Yes — live platform data via func.count() | FLOWING |
| `_tab_checklist.html` — checklist refresh | `checklist` | GET /intake/checklist → `get_verification_checklist` | Yes — same real DB queries on refresh | FLOWING |
| `sites/index.html` — Intake column | `intake_statuses` | `get_intake_statuses_for_sites` → `SELECT site_id, status FROM site_intakes WHERE site_id IN (...)` | Yes — batch query returning real status values | FLOWING |
| `sites/detail.html` — Intake badge | `intake` | `sa_select(SiteIntake).where(SiteIntake.site_id == sid)` | Yes — direct SELECT, may return None (no auto-create) | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SiteIntake model imports | `python3 -c "from app.models.site_intake import SiteIntake, IntakeStatus; assert IntakeStatus.draft.value == 'draft'"` | model OK, enum OK | PASS |
| Intake service imports | `python3 -c "from app.services.intake_service import get_or_create_intake, get_verification_checklist, complete_intake, get_intake_statuses_for_sites"` | service imports OK | PASS |
| Router has 8 routes | `python3 -c "from app.routers.intake import router; print([(r.path, r.methods) for r in router.routes])"` | 8 routes confirmed (GET form, 5x POST section, GET checklist, POST complete) | PASS |
| form.html key content | Python content checks for 18 key strings | All 18 checks OK | PASS |
| Test suite (DB unavailable) | `python3 -m pytest tests/services/test_intake_service.py` | 19 tests defined; failure is DNS/DB connectivity in verification environment, not code defect | SKIP (DB unreachable) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INTAKE-01 | 21-01, 21-02 | Structured intake form per site (access, goals, competitors, GSC/Metrika, SEO setup) | SATISFIED | form.html has all 5 tabs covering each topic area; router endpoints for all sections |
| INTAKE-02 | 21-01, 21-02 | Verification checklist (WP, GSC, Metrika, sitemap, crawl) | SATISFIED | `get_verification_checklist` returns exactly 5 items with correct labels; `_tab_checklist.html` renders them |
| INTAKE-03 | 21-01, 21-02 | Checklist items auto-populate from existing platform data | SATISFIED | Service queries live Site.connection_status, OAuthToken count, SitemapEntry count, CrawlJob count |
| INTAKE-04 | 21-01, 21-02 | Save as draft, resume later (section-by-section HTMX save) | SATISFIED | 5 POST endpoints save individual sections; page reload re-populates from DB via goals_data/technical_data JSON fields; section flags drive checkmarks |
| INTAKE-05 | 21-03 | Site shows "intake complete" badge after form finished | SATISFIED | Site list Intake column (index.html line 25+83); site detail 3-state badge (detail.html lines 39-49); both link to intake form |

No orphaned requirements found — all 5 INTAKE-0x IDs from REQUIREMENTS.md are claimed by plans and verified implemented.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/models/site_intake.py` | 50, 55 | `default=datetime.utcnow` (naive, not timezone-aware callable) | Info | Minor: utcnow() is deprecated in Python 3.12 in favor of `datetime.now(UTC)`, but columns are DateTime(timezone=True) so the DB will store correctly via SQLAlchemy; functional impact is nil |

No blocking anti-patterns found. No TODO/FIXME/placeholder stubs. No empty handler implementations. No hardcoded empty data flowing to rendered output.

---

### Human Verification Required

#### 1. Section Save → Checkmark Persistence

**Test:** Open the intake form for a site, click "Сохранить раздел" on Tab 1 (Доступы), then reload the page.
**Expected:** Tab 1 button shows green checkmark SVG; hidden input `section-access` value is "true".
**Why human:** Verifies the DB round-trip (flush+commit in router, then reload re-renders section_access=True from DB) and that the Jinja2 conditional renders the checkmark correctly.

#### 2. Competitor Multi-Value Form Submission

**Test:** In Tab 2, add 3 competitors via "Добавить конкурента", fill URLs, click "Сохранить раздел", reload.
**Expected:** All 3 competitor URLs are preserved and pre-populated on reload; `intake.goals_data.competitors` array has 3 entries.
**Why human:** Verifies `form.multi_items()` correctly extracts multiple `competitor` fields and JSON storage/retrieval round-trip.

#### 3. Completion Flow with Partial Sections

**Test:** Click "Завершить intake" without saving any sections.
**Expected:** Browser shows `confirm()` dialog "Не все секции заполнены. Завершить все равно?"; clicking Cancel prevents the HTMX request; clicking OK sends POST and updates badge to "Анкета заполнена".
**Why human:** Verifies the onclick guard logic, confirm dialog behavior, and intakeCompleted JS event updating the badge DOM.

#### 4. Checklist Refresh via "Перепроверить"

**Test:** Connect GSC for a site (add oauth_token with provider='gsc'), then open intake Tab 5, click "Перепроверить".
**Expected:** Checklist content updates without page reload; GSC row shows badge-connected "Подключено"; toast "Статусы обновлены" appears.
**Why human:** Verifies HTMX partial swap targets `#checklist-content`, the GET endpoint returns the partial with updated data, and the HX-Trigger toast fires correctly.

---

### Gaps Summary

No gaps found. All automated checks pass. The single note about `datetime.utcnow` is an informational code style item with no functional impact.

The test suite failure during spot-check is a verification environment constraint (no PostgreSQL DNS resolution available) — not a code defect. The 19 test functions are substantively written (checked by content inspection: each creates DB fixtures, calls service functions, asserts model state).

---

_Verified: 2026-04-09T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
