# Phase 8: Cannibalization Resolver - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend existing cannibalization detection with resolution proposals (merge/canonical/redirect/split), action plan tasks, and resolution tracking. All four resolution types equally important.
</domain>

<decisions>
- **D-01:** Все 4 типа решений одинаково важны: merge content, canonical, 301 redirect, split keywords.
- **D-02:** Создаётся задача (SeoTask) с конкретным action plan.
- **D-03:** Отслеживание: после действий повторная проверка показывает resolved/unresolved.

### Existing: `cluster_service.detect_cannibalization()`, cannibalization UI page, TaskType.cannibalization.
</decisions>

---
*Phase: v3-08-cannibalization*
