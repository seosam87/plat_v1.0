# Phase 7: Bulk Operations Hub - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Bulk keyword operations: batch move between groups/clusters, batch assign target_url (manual selection in UI), batch delete by filter, export filtered results as CSV/Excel, import with merge (skip/update/replace) with audit logging. Select-all + batch action pattern on keyword tables.

</domain>

<decisions>
## Implementation Decisions

- **D-01:** Массовое назначение target_url — вручную в UI: выбрал ключи → ввёл URL → применить. Паттерн-правила запланировать на будущую версию (обсудить и посмотреть как в других сервисах).
- **D-02:** Import с merge использует существующий `on_duplicate: skip|update|replace`. При update/replace — писать в audit_log запись о массовом обновлении ключей, чтобы можно было отследить причину испорченных данных.
- **D-03:** Компактная фаза — 2 плана: service + router/UI.

### Claude's Discretion
- Bulk service function signatures
- Export format (CSV vs XLSX vs both)
- UI layout for bulk operations page
- Audit log message format for bulk imports

</decisions>

<canonical_refs>
## Canonical References

- `app/models/keyword.py` — Keyword, KeywordGroup
- `app/services/keyword_service.py` — bulk_add_keywords (on_duplicate), CRUD
- `app/routers/keywords.py` — existing keyword endpoints
- `app/services/analytics_service.py` — filter_keywords (advanced filter), export_session_keywords_csv
- `app/services/audit_service.py` — log_action() for audit logging

</canonical_refs>

<deferred>
## Deferred Ideas

- Pattern-based target_url assignment (regex/substring → URL rule engine) — обсудить в следующей версии
- Undo/rollback for bulk operations
- Bulk operations history with diff

</deferred>

---

*Phase: v3-07-bulk-operations*
*Context gathered: 2026-04-02*
