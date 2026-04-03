# v4-01 Known Issues (from manual testing 2026-04-03)

## 500 Internal Server Error

### /ui/competitors/{site_id}
- **Status:** 500
- **Likely cause:** Runtime error in competitor_service or template rendering (imports OK)
- **Needs:** Server-side error log to diagnose

### /audit/{site_id}
- **Status:** 500
- **Likely cause:** Runtime error in content_audit_service.get_audit_results_for_site or template variable
- **Needs:** Server-side error log to diagnose

## 404 / Wrong Data

### /ui/projects/{site_id}/plan
- **Status:** "Project not found"
- **Cause:** URL takes project_id, not site_id. Sidebar links substitute site_id into {project_id} placeholder which is wrong — projects have their own UUIDs
- **Fix:** Projects/Kanban/Content-plan links should not use site_id; need project picker or list

## Action needed

1. Check Docker logs for the 500 errors: `docker compose logs web --tail=100 | grep -i error`
2. Fix project link resolution in navigation.py (projects are not site-scoped)
