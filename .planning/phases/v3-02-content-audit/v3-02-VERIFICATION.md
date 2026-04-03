---
phase: v3-02-content-audit
verified: 2026-04-03T08:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
gaps: []
---

# Phase v3-02: Content Audit Engine — Verification Report

**Phase Goal:** Content Audit Engine — WP pages with filters, checklist by type (informational: TOC, author, related; commercial: CTA, schema), auto-fix workflow through existing pipeline (generate → diff → approve → push → verify)
**Verified:** 2026-04-03
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | User can view a per-site audit page showing WP pages with filter controls | ✓ VERIFIED | `app/routers/audit.py` GET `/{site_id}` returns HTML; `app/templates/audit/index.html` has search input, content_type select, status filter, filterTable() JS |
| 2  | Each page shows a checklist status (pass/fail/warning) per content type | ✓ VERIFIED | `run_checks_for_page` in `content_audit_service.py` (287 lines) dispatches 7 checks with applies_to filtering; results_map passed to template |
| 3  | Informational checks (TOC, author, related posts) are distinct from commercial checks (CTA, schema) | ✓ VERIFIED | `AuditCheckDefinition.applies_to` enum (informational/commercial/unknown); 7 seeded checks in migration 0021 with correct applies_to values; engine skips checks that don't match content_type |
| 4  | Content type (informational/commercial/unknown) is assigned per page and editable | ✓ VERIFIED | `ContentType` enum on `Page.content_type` (crawl.py); `classify_content_type()` maps page_type+URL; PUT `/{site_id}/pages/{page_id}/content-type` endpoint; inline edit in template |
| 5  | Schema.org templates are configurable per site with system defaults | ✓ VERIFIED | `schema_service.py` (205 lines): `render_schema_template`, `get_template` with site→default fallback, `create_site_template` upsert; 5 default templates seeded in migration 0021 |
| 6  | CTA template is saved per site and used in auto-fix | ✓ VERIFIED | `Site.cta_template_html` Text field; PUT `/{site_id}/cta` endpoint; `generate_cta_fix()` reads `cta_template` and appends to content |
| 7  | Auto-fix workflow runs through existing pipeline (generate → diff → approve → push) | ✓ VERIFIED | `audit_fix_service.py`: 4 pure fix generators + `verify_html_integrity` + `create_fix_job` (creates WpContentJob in awaiting_approval) + `mark_audit_fixed`; 3 fix endpoints (preview/apply/apply-and-approve) in router |

**Score: 7/7 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models/audit.py` | AuditCheckDefinition, AuditResult, SchemaTemplate models | ✓ VERIFIED | 107 lines; all 3 models present with correct table names and constraints |
| `app/models/crawl.py` | ContentType enum + Page.content_type | ✓ VERIFIED | ContentType(str, PyEnum) at line 36; content_type mapped_column at line 105 |
| `app/models/site.py` | cta_template_html field | ✓ VERIFIED | `Mapped[str \| None] = mapped_column(Text, nullable=True)` at line 40 |
| `alembic/versions/0021_add_content_audit_tables.py` | Migration creating all audit tables, fields, seed data | ✓ VERIFIED | 392 lines; revision=0021, down_revision=0020; creates 3 tables, 2 columns, 7 check seeds, 5 schema template seeds; downgrade reverses all |
| `app/services/content_audit_service.py` | Check engine, detection functions, classifier, DB helpers | ✓ VERIFIED | 287 lines; 14 functions (detect_author_block, detect_related_posts, detect_cta_block, classify_content_type, run_checks_for_page + 8 async DB helpers) |
| `app/services/audit_service.py` | Audit logging (pre-existing) + check engine functions | ✓ VERIFIED | 385 lines; extended with same check engine functions; pre-existing log_action preserved |
| `app/services/schema_service.py` | Schema template engine and CRUD | ✓ VERIFIED | 205 lines; render_schema_template, generate_schema_tag, get_page_data_for_schema, select_schema_type_for_page, async CRUD |
| `app/services/audit_fix_service.py` | Fix generators and pipeline integration | ✓ VERIFIED | 179 lines; generate_toc_fix, generate_cta_fix, generate_schema_fix, generate_links_fix, verify_html_integrity, create_fix_job, mark_audit_fixed |
| `app/routers/audit.py` | FastAPI audit router with 13+ endpoints | ✓ VERIFIED | 546 lines; 16 `@router` decorators; prefix="/audit"; require_admin on all endpoints |
| `app/tasks/audit_tasks.py` | Celery batch audit task | ✓ VERIFIED | run_site_audit Celery task with asyncio.new_event_loop() pattern |
| `app/templates/audit/index.html` | Full audit UI with filters, checklist, CTA, schema sections | ✓ VERIFIED | 299 lines; extends base.html; filter bar, summary stats, pages table, CTA textarea, schema template modal |
| `app/templates/audit/_fix_preview.html` | Fix preview partial with diff display | ✓ VERIFIED | Предпросмотр исправления header, diff_text display, applyFix/applyAndApprove buttons |
| `tests/test_audit_models.py` | Model unit tests | ✓ VERIFIED | 54 lines; 6 tests — all pass |
| `tests/test_audit_service.py` | Detection + check engine unit tests | ✓ VERIFIED | 319 lines; 28 tests — all pass |
| `tests/test_schema_service.py` | Schema template engine unit tests | ✓ VERIFIED | 92 lines; 12 tests — all pass |
| `tests/test_audit_fix_service.py` | Fix generator unit tests | ✓ VERIFIED | 122 lines; 13 tests — all pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/routers/audit.py` | `app/services/content_audit_service.py` | `import content_audit_service as cas` | ✓ WIRED | get_audit_results_for_site, get_check_definitions, update_content_type all called |
| `app/routers/audit.py` | `app/services/schema_service.py` | `import schema_service as ss` | ✓ WIRED | get_all_templates, render_schema_for_page, create_site_template, delete_site_template called |
| `app/routers/audit.py` | `app/services/audit_fix_service.py` | `import audit_fix_service as afs` | ✓ WIRED | verify_html_integrity at line 456; mark_audit_fixed at lines 507, 539 |
| `app/main.py` | `app/routers/audit.py` | `from app.routers.audit import router as audit_router` + `app.include_router(audit_router)` | ✓ WIRED | Lines 35 and 173 |
| `app/celery_app.py` | `app/tasks/audit_tasks.py` | `"app.tasks.audit_tasks"` in include list | ✓ WIRED | Line 17 |
| `app/templates/sites/detail.html` | `/audit/{site_id}` | `<a href="/audit/{{ site.id }}">Аудит контента</a>` | ✓ WIRED | Line 45; red button in Quick Actions |
| `audit_fix_service.create_fix_job` | `WpContentJob` pipeline | Creates job with `awaiting_approval` status; `apply-and-approve` dispatches `push_to_wp.delay()` | ✓ WIRED | Reuses existing pipeline approve/push flow |
| `content_audit_service.save_audit_results` | `audit_results` table | `INSERT ... ON CONFLICT (site_id, page_url, check_code) DO UPDATE` | ✓ WIRED | Upsert pattern at line 228 of audit_service.py |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `audit/index.html` | `pages` | DB query: `select(Page).where(site_id=site_id, http_status=200)` in router | Yes — SQLAlchemy query against crawled pages | ✓ FLOWING |
| `audit/index.html` | `audit_results` / `results_map` | `cas.get_audit_results_for_site(db, site_id, page_urls)` → DB query on audit_results table | Yes — SQLAlchemy query | ✓ FLOWING |
| `audit/index.html` | `check_defs` | `cas.get_check_definitions(db)` → DB query on audit_check_definitions | Yes — seeded by migration 0021 | ✓ FLOWING |
| `audit/index.html` | `schema_templates` | `ss.get_all_templates(db, site_id)` → DB query on schema_templates | Yes — seeded by migration 0021 | ✓ FLOWING |
| `audit/index.html` | summary stats (pages_with_issues, pages_all_pass, pages_unchecked) | Computed in router from real query results | Yes — derived from DB data | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 59 audit tests pass | `pytest tests/test_audit_models.py tests/test_audit_service.py tests/test_schema_service.py tests/test_audit_fix_service.py -x -q` | 59 passed in 0.11s | ✓ PASS |
| Migration chain is correct (0020→0021) | `grep "revision\|down_revision" alembic/versions/0021_add_content_audit_tables.py` | revision="0021", down_revision="0020" | ✓ PASS |
| Router has 16 endpoints (plan required 13+, then 3 more fix endpoints) | `grep -c "@router" app/routers/audit.py` | 16 | ✓ PASS |
| TOC fix generator returns dict with processed_html | `test_generate_toc_fix_with_headings` in test suite | passes | ✓ PASS |

---

### Requirements Coverage

No explicit requirement IDs were assigned to this phase in REQUIREMENTS.md. Coverage verified against ROADMAP-v3.md Phase 2 description:

| ROADMAP Item | Status | Evidence |
|-------------|--------|----------|
| List of WP pages with filters (search, date, type) | ✓ SATISFIED | GET /{site_id} with search/content_type/status query params; filterTable() client-side JS |
| Checklist per page (depends on content type) | ✓ SATISFIED | run_checks_for_page with applies_to filtering; 7 default checks seeded |
| Informational: TOC, author block, related posts, schema, internal links | ✓ SATISFIED | toc_present/author_block/related_posts/schema_present/internal_links checks; HTML regex detection functions |
| Commercial: CTA block, schema (Service/Product/LocalBusiness/FAQ), internal links | ✓ SATISFIED | cta_present check; schema_service with 5 schema types; inject_cta fix action |
| Type-aware pipeline (different actions for info vs commercial) | ✓ SATISFIED | applies_to enum on AuditCheckDefinition; classifier maps page_type→content_type |
| CTA injection endpoint | ✓ SATISFIED | PUT /{site_id}/cta + generate_cta_fix + inject_cta fix_action |
| Auto-fix through existing pipeline (generate → diff → approve → push → verify) | ✓ SATISFIED | 3 fix endpoints; create_fix_job creates WpContentJob(awaiting_approval); mark_audit_fixed on completion |

---

### Anti-Patterns Found

No blockers or warnings found.

| File | Pattern | Severity | Notes |
|------|---------|----------|-------|
| `schema_service.py:17` | `_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")` | ℹ Info | Regex for `{{placeholder}}` substitution — this is intentional feature code, not a stub |

---

### Human Verification Required

#### 1. Batch audit Celery task end-to-end

**Test:** Configure a site with active crawl data, navigate to `/audit/{site_id}`, click "Запустить аудит"
**Expected:** Celery task processes pages (up to 200), audit results appear in the table, summary stats update
**Why human:** Requires live DB with crawled pages, running Celery worker, and WP REST API connectivity

#### 2. Fix workflow preview → apply → pipeline

**Test:** Find a page with a failed TOC check, click "Исправить", review diff in preview modal, click "Применить и отправить на проверку"
**Expected:** Pipeline job created in awaiting_approval status; appears in Content Pipeline; after approve+push, audit result shows "fixed"
**Why human:** Requires live WP site with REST API access and running Celery worker

#### 3. Schema template customization per site

**Test:** Open schema templates section, edit the Article template for a specific site, save, then trigger audit on an informational page
**Expected:** Custom site template used for schema injection instead of system default
**Why human:** Requires DB with site data and full audit run

#### 4. Content type inline edit

**Test:** On audit page, click on a page's content type badge, change from "unknown" to "commercial", verify the CTA check now appears for that page on re-audit
**Expected:** PUT request updates content_type; re-audit run uses new type for check filtering
**Why human:** Requires live UI interaction and re-audit execution

---

### Gaps Summary

No gaps. All 7 observable truths verified. All 16 artifacts pass all levels (exists, substantive, wired, data-flowing). 59 unit tests pass in 0.11s. The phase goal is achieved.

**Notable architectural decision verified:** The router imports `content_audit_service` (dedicated check engine module) not `audit_service` (which handles audit_log writes for the existing audit trail feature). Both modules exist and serve distinct purposes — this is by design, documented in v3-02-04 SUMMARY.

---

_Verified: 2026-04-03_
_Verifier: Claude (gsd-verifier)_
