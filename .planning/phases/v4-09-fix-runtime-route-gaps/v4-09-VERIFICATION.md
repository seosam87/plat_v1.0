---
phase: v4-09-fix-runtime-route-gaps
verified: 2026-04-04T17:30:00Z
status: passed
score: 3/3 must-haves verified
re_verification: false
---

# Phase v4-09: Fix Runtime Route Gaps Verification Report

**Phase Goal:** Fix 2 runtime-broken routes found by milestone audit -- crawl schedule save (405) and back-to-site navigation (405 in 13 templates). Delete orphaned admin/settings.html.
**Verified:** 2026-04-04T17:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Crawl schedule form submits without 405 error | VERIFIED | `schedule.html` line 19 uses `hx-post="/ui/sites/{{ site.id }}/schedule"` matching backend `@app.post("/ui/sites/{site_id}/schedule")` in `app/main.py:367`. Zero `hx-put` matches remain. |
| 2 | Back-to-site links in all templates navigate to /ui/sites without 405 | VERIFIED | All 14 templates contain `href="/ui/sites"`. Zero matches for `href="/ui/sites/{{ site.id }}"` or `href="/ui/sites/{{ site_id }}"` anywhere in `app/templates/`. |
| 3 | Orphaned admin/settings.html no longer exists | VERIFIED | File does not exist on disk. `grep -r "admin/settings.html" app/` returns zero matches -- no dangling references. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/templates/sites/schedule.html` | Crawl schedule form with hx-post | VERIFIED | Line 19: `hx-post="/ui/sites/{{ site.id }}/schedule"` |
| `app/templates/analytics/index.html` | Back-to-site links pointing to /ui/sites | VERIFIED | 2 occurrences at lines 4 and 16 |
| `app/templates/audit/index.html` | href="/ui/sites" | VERIFIED | Line 12 |
| `app/templates/architecture/index.html` | href="/ui/sites" | VERIFIED | Line 6 |
| `app/templates/bulk/index.html` | href="/ui/sites" | VERIFIED | Line 6 |
| `app/templates/clusters/index.html` | href="/ui/sites" | VERIFIED | Line 4 |
| `app/templates/gap/index.html` | href="/ui/sites" | VERIFIED | Line 6 |
| `app/templates/intent/index.html` | href="/ui/sites" | VERIFIED | Lines 6-7 |
| `app/templates/keywords/index.html` | href="/ui/sites" | VERIFIED | Line 4 |
| `app/templates/metrika/index.html` | href="/ui/sites" | VERIFIED | Line 4 |
| `app/templates/monitoring/index.html` | href="/ui/sites" | VERIFIED | Line 6 |
| `app/templates/pipeline/publish.html` | href="/ui/sites" | VERIFIED | Line 4 |
| `app/templates/positions/index.html` | href="/ui/sites" | VERIFIED | Line 4 |
| `app/templates/traffic_analysis/index.html` | href="/ui/sites" | VERIFIED | Line 6 |
| `app/templates/sites/edit.html` | href="/ui/sites" on Cancel button | VERIFIED | Line 56 |
| `app/templates/admin/settings.html` | Deleted | VERIFIED | File does not exist; no references in codebase |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/templates/sites/schedule.html` | `@app.post /ui/sites/{site_id}/schedule` | hx-post attribute | WIRED | Template `hx-post` pattern matches backend route at `app/main.py:367` |
| All 14 templates | `GET /ui/sites` | href attribute | WIRED | All templates use `href="/ui/sites"` which resolves to the sites list page |

### Data-Flow Trace (Level 4)

Not applicable -- this phase is a bug-fix phase correcting HTML attributes. No dynamic data rendering was added or changed.

### Behavioral Spot-Checks

Step 7b: SKIPPED (templates are not independently runnable -- require running FastAPI server for behavioral testing)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SITE-V4-02 | v4-09-01-PLAN.md | Crawl history/schedules per site (schedule save 405 fix) | SATISFIED | `hx-post` matches `@app.post` route; zero `hx-put` in schedule.html |
| SITE-V4-03 | v4-09-01-PLAN.md | Site detail removed (back-to-site 405 fix) | SATISFIED | All 14 templates link to `/ui/sites` instead of `/ui/sites/{id}` |

No orphaned requirements found -- ROADMAP.md maps exactly SITE-V4-02 and SITE-V4-03 to this phase, matching the PLAN frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No anti-patterns detected in modified files |

### Human Verification Required

### 1. Crawl Schedule Save End-to-End

**Test:** Navigate to a site's schedule page, change the crawl schedule dropdown, observe network tab
**Expected:** HTMX POST request to `/ui/sites/{id}/schedule` returns 200, schedule updates without page reload
**Why human:** Requires running server and browser interaction to confirm full HTMX round-trip

### 2. Back-to-Site Navigation

**Test:** Visit any site-scoped page (e.g., keywords, positions, analytics) and click the back-to-site link/breadcrumb
**Expected:** Navigates to `/ui/sites` (sites list page) without 405 error
**Why human:** Requires running server to confirm GET /ui/sites responds correctly

### Gaps Summary

No gaps found. All three must-have truths are verified at the code level:
1. Schedule form uses `hx-post` matching the backend `@app.post` route
2. All 14 templates link to `/ui/sites` with zero old-style `{site.id}` or `{site_id}` links remaining
3. Orphaned `admin/settings.html` is deleted with no dangling references

Both commits (168e671, 481e9c8) exist in the git history.

---

_Verified: 2026-04-04T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
