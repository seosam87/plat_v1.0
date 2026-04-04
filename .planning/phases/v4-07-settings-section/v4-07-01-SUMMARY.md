---
phase: v4-07-settings-section
plan: 01
subsystem: ui
tags: [navigation, routing, fastapi, sidebar, role-based-access]

# Dependency graph
requires:
  - phase: v4-01-navigation-foundation
    provides: "NAV_SECTIONS structure and build_sidebar_sections() function"
provides:
  - "Per-child admin_only filtering in build_sidebar_sections()"
  - "7 settings children in NAV_SECTIONS with correct admin_only flags"
  - "/ui/admin/proxy route (admin + manager)"
  - "/ui/admin/parameters route (admin + manager)"
  - "/ui/admin/settings 301 redirect to /ui/admin/parameters"
  - "Issues route (GET + POST) accessible to manager role"
  - "/ui/datasources auth guard added (admin + manager)"
affects: [v4-07-02, v4-07-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-child admin_only dict key in NAV_SECTIONS children enables granular sidebar filtering"
    - "child.get('admin_only', False) default-False pattern ensures existing non-flagged children remain visible"
    - "Role guard pattern: current_user.role.value not in ('admin', 'manager') for manager-accessible routes"

key-files:
  created: []
  modified:
    - app/navigation.py
    - app/main.py

key-decisions:
  - "Settings section-level admin_only changed to False so managers can see the Settings section in sidebar"
  - "Per-child admin_only flag (not section-level) controls which settings children managers see"
  - "Old ui_admin_settings split into ui_admin_parameters (settings data) and ui_admin_proxy (proxy pool + creds)"
  - "Old /ui/admin/settings URL preserved as 301 redirect to /ui/admin/parameters for backward compat"
  - "Issues route guards updated from 'must be logged in' to 'must be admin or manager'"
  - "/ui/datasources was unprotected — added admin+manager guard (Rule 2 deviation)"

patterns-established:
  - "Per-child admin_only filtering: child.get('admin_only', False) and not is_admin — continue"
  - "Manager-accessible route guard: role.value not in ('admin', 'manager')"

requirements-completed:
  - CFG-V4-01
  - CFG-V4-02

# Metrics
duration: 5min
completed: 2026-04-04
---

# Phase v4-07 Plan 01: Settings Navigation Infrastructure Summary

**Settings section split into 7 per-child admin_only children with proxy+parameters routes and manager role access**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-04T15:20:00Z
- **Completed:** 2026-04-04T15:25:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- NAV_SECTIONS settings section restructured: `admin_only=False` at section level, 7 children with individual `admin_only` flags (users/groups/audit-log=True, others=False)
- `build_sidebar_sections()` updated to filter children by `child.get("admin_only", False)` — manager sees 4 children, admin sees all 7
- `/ui/admin/settings` handler split into `/ui/admin/parameters` (settings config) and `/ui/admin/proxy` (proxy pool + credentials), each with admin+manager access
- Old `/ui/admin/settings` URL returns HTTP 301 redirect to `/ui/admin/parameters`
- Issues route (GET + POST) role guard upgraded from login-only check to admin+manager check

## Task Commits

Each task was committed atomically:

1. **Task 1: Update navigation.py — per-child admin_only filtering and 7 settings children** - `2a1a2db` (feat)
2. **Task 2: Split settings route into proxy + parameters routes in main.py** - `b480912` (feat)

## Files Created/Modified

- `app/navigation.py` - Settings section updated: section-level admin_only=False, 7 children with per-child admin_only flags; build_sidebar_sections() adds child-level filtering
- `app/main.py` - ui_admin_settings split into ui_admin_parameters + ui_admin_proxy + ui_admin_settings_redirect (301); issues GET/POST guards fixed; datasources guard added

## Decisions Made

- Settings section-level `admin_only` changed from `True` to `False` — managers need to see the section in sidebar (per D-03 from research)
- Per-child `admin_only` flag used rather than a separate "manager_children" list — simpler and self-documenting
- Old `/ui/admin/settings` kept as 301 redirect (not removed) for backward compatibility with any existing bookmarks/links
- Issues route upgraded from login-only check to admin+manager check to match its new non-admin-only sidebar position

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added auth guard to /ui/datasources**
- **Found during:** Task 2 (reviewing datasources route guard)
- **Issue:** `/ui/datasources` handler had no authentication or authorization check — any unauthenticated user could access it
- **Fix:** Added `current_user` check and role guard (`role.value not in ("admin", "manager")`) matching the route's intended manager-accessible status
- **Files modified:** `app/main.py`
- **Verification:** Guard added at top of handler, same pattern as other manager-accessible routes
- **Committed in:** `b480912` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical security check)
**Impact on plan:** Security fix for unprotected route. No scope creep.

## Issues Encountered

None — both tasks executed cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Navigation and routing infrastructure complete for Settings section
- Plans 02 and 03 can now proceed: proxy.html and parameters.html templates need to be created/migrated
- `admin/proxy.html` and `admin/parameters.html` templates referenced in new routes but not yet created (handled in plans 02/03)

---
*Phase: v4-07-settings-section*
*Completed: 2026-04-04*
