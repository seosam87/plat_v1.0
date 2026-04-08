# Phase 17: In-app Notifications — Context

**Gathered:** 2026-04-08
**Status:** Ready for planning
**Source:** /gsd:discuss-phase (interactive)

<domain>
## Phase Boundary

Bell icon in sidebar with live unread count and a notification feed for async task completion events (crawls, position checks, PDF generation, monitoring alerts, keyword suggest, audit, client PDF, LLM brief). HTMX polling every 30s. Additive to existing Telegram notifications — does not replace them.

**Out of scope** (already locked in ROADMAP/STATE, not up for debate):
- SSE/WebSockets (polling is the chosen transport)
- Soft-delete (dismissed = hard-deleted)
- Retention beyond 30 days (Celery Beat cleanup task)
- Telegram replacement (stays as-is, additive only)
- Beat-scheduled digest tasks (`app/tasks/report_tasks.py::send_morning_digest`, `send_weekly_summary_report`) — no user scope, stay Telegram/email only
- Adding `owner_id` (or any user FK) to the `Site` model — scope creep

</domain>

<decisions>
## Implementation Decisions

### D-01 — Event emission mechanism
**Decision:** Shared helper `notify(user_id, kind, title, body, link_url, site_id, severity)` in `app/services/notifications.py`. Every Celery task that wants to emit a notification calls this helper at finalization.

**Rationale:** Explicit and testable; no signal magic; consistent text formatting; one place to change cross-cutting behaviour (deduplication, throttling).

### D-02 — User scoping (REVISED 2026-04-08 after checker feedback)
**Decision:** Per-initiator — `notifications.user_id` references the user who triggered the task.

Fallback behaviour (revised — the original plan referenced `Site.owner_id`, which does not exist on the Site model, so the original fallback was dead code):
- If the task signature has a `user_id` arg → pass it to `notify()`.
- If the task has no `user_id` arg → SKIP the in-app notification and emit `logger.debug("no user scope; skipping in-app notification", ...)`. Telegram/email paths continue to fire unchanged.
- We do NOT add `owner_id` (or any user FK) to the `Site` model in Phase 17 — that is explicit scope creep.
- Consequence: most existing Celery tasks today do not carry `user_id`, so in-app notifications for them will only light up once callers are updated to pass `user_id` (either in this plan where trivially possible, or in follow-up phases). This is accepted — the scaffold, helper, feed UI, bell, and polling still ship in Phase 17, and real notifications progressively fill in as call sites grow a user scope.
- The monitoring alert dispatcher (`app/services/change_monitoring_service.py::dispatch_immediate_alerts()`) also has no user scope today. It will log the debug skip and leave a `TODO(Phase 18)` comment pointing at plumbing `user_id` via `ChangeAlertRule.owner_id` once monitoring gains per-user rules.

**Rationale:** Smaller team (under 20 users) but each has their own workflow — a personal feed keeps noise down. Global fan-out would drown every user in other people's crawl reports. The revised fallback is honest about the current state of the codebase instead of silently AttributeError-ing on a non-existent column.

### D-03 — Notification model schema
**Decision:** Standard set of fields:
```
notifications
  id              UUID PK
  user_id         UUID FK → users.id (indexed)
  kind            VARCHAR(64)        -- 'crawl.completed', 'position_check.completed', 'pdf.ready', 'monitoring.alert', 'audit.completed', 'keyword_suggest.ready', 'client_pdf.ready', 'llm_brief.ready', ...
  title           VARCHAR(200)
  body            TEXT
  link_url        VARCHAR(500)       -- where clicking takes the user
  site_id         UUID FK → sites.id NULLABLE (for global/system events)
  severity        VARCHAR(16)        -- 'info' | 'warning' | 'error'
  is_read         BOOLEAN NOT NULL DEFAULT false
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```
Indexes: `(user_id, is_read)`, `(user_id, created_at DESC)`, `(site_id)`.

**Rationale:** Covers all ROADMAP success criteria without over-engineering. `kind` is machine-readable so filters and icon mapping are deterministic. `link_url` gives click-through without embedding routing logic in the template.

### D-04 — Bell UI layout
**Decision:** Dropdown panel anchored to the bell in the sidebar/topbar (shows last 10 entries, flat list) + a full-history page at `/notifications` accessible via a footer link inside the dropdown ("Все уведомления →").

**Rationale:** Fast access for the common case (just-finished task), full page for retrospective review. One bell location only (sidebar), not duplicated in topbar.

### D-05 — Read/unread mechanics
**Decision:** Auto-mark-read when the user opens the dropdown (all currently-visible entries flip to `is_read=true` atomically). Additionally a "Отметить все прочитанными" button on the full page for bulk cleanup of older entries beyond the dropdown window.

**Rationale:** Minimum friction — users don't want to click each entry. The bulk button covers the rare case where someone ignored the bell for a week and has 200 unread.

### D-06 — Arrival behaviour during polling
**Decision:** Silent badge update only. When the 30s HTMX poll returns new items, the badge count updates in place — no toast, no sound, no flash. Telegram already handles the "push" channel.

**Rationale:** In-app is a dashboard reference, not an attention-grabber. Toasts on every crawl completion would be more distracting than useful for this workflow. Errors still stand out visually via severity color in the dropdown.

### D-07 — Severity levels
**Decision:** Three levels — `info` (green), `warning` (yellow), `error` (red). Each notification row has a 3px left border in its severity color and a matching icon. The bell badge flips to red if any unread error exists, otherwise defaults to blue/gray.

**Rationale:** Three levels match the Tailwind palette already used elsewhere in the UI (per memory). Two levels (success/error) would collapse warnings into one bucket and lose signal.

### D-08 — Feed grouping
**Decision:** Group by `kind` on the `/notifications` page — sections like "Crawls (12)", "PDF reports (4)", "Monitoring alerts (2)" — each section internally sorted by `created_at DESC`. Dropdown remains flat (latest 10 in chronological order).

**Rationale:** User explicitly chose `kind` grouping over day grouping. For retrospective review it's easier to find "all crawl events" than to remember which day something happened. Dropdown stays chronological because it's the "what just happened" view.

### D-09 — Filters on /notifications page
**Decision:** Three filter controls in a filter bar at the top of `/notifications`:
1. Site selector (dropdown with all sites the user has notifications for + "Все сайты")
2. Kind selector (dropdown of distinct kinds present in the user's history + "Все типы")
3. Read state (tabs: "Все" / "Непрочитанные")
All filters are GET query params, composable, preserved across HTMX updates. Pagination: 50 per page.

**Rationale:** User explicitly opted for all three. For 100+ notifications the filter combination turns the page into a mini-search tool without resorting to full-text search.

### Claude's Discretion
- Exact dropdown width and max-height (responsive breakpoints)
- Icon mapping per `kind` (crawl → spider glyph, pdf → document, etc.) — pick from Heroicons or similar
- Exact wording of Russian titles/bodies in the helper for each `kind` (consistent template strings)
- HTMX polling endpoint URL structure (likely `/notifications/bell` returning a fragment)
- Nightly Celery Beat task name and schedule (e.g. `notifications.cleanup_expired`, daily at 03:00)
- Indexes beyond the three listed above (only add if EXPLAIN shows need)
- Whether to deduplicate notifications within a short time window (e.g. suppress 5 "crawl completed" for the same site within 10s) — decide during implementation if it becomes annoying in testing

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### HTMX polling pattern
- `app/templates/analytics/_brief_ai_block.html` — reference HTMX polling implementation from Phase 16-04 (status poll every 2s, swap outerHTML on completion)
- `app/routers/llm_briefs.py` — reference pattern for returning HTMX fragments vs full pages

### Celery task finalization hook
- `app/tasks/` — tasks that should emit notifications need a `notify(...)` call at the end of the happy path and in the exception handler, guarded by "is `user_id` in scope?" per revised D-02
- In-scope tasks for Phase 17: `app/tasks/crawl_tasks.py`, `app/tasks/position_tasks.py` (including `_send_drop_alerts`), `app/tasks/client_report_tasks.py`, `app/tasks/audit_tasks.py`, `app/tasks/suggest_tasks.py`, `app/tasks/llm_tasks.py`
- Monitoring dispatcher in scope: `app/services/change_monitoring_service.py::dispatch_immediate_alerts()` (the real dispatcher — `app/services/monitoring_alerts.py` does NOT exist)
- Out of scope: `app/tasks/report_tasks.py` (Beat-scheduled `send_morning_digest` + `send_weekly_summary_report`) — no user scope, Telegram/email only

### UI color palette
- Memory: `feedback_ui_colors.md` — Tailwind CSS hex colors used consistently across templates. Use standard Tailwind `green-500 / yellow-500 / red-500` for severity.

### Existing audit log
- Phase 18 CRM (not yet built) will use the same audit log infrastructure. Phase 17 does NOT need audit logging — notifications themselves are the log.

### Sidebar navigation
- `app/templates/_sidebar.html` (or equivalent) — bell icon needs to be placed here. Check existing badge patterns (e.g. task counts) for visual consistency.

</canonical_refs>

<specifics>
## Specific Ideas

- Russian UI labels throughout ("Уведомления", "Отметить все прочитанными", "Все сайты", "Все типы", "Непрочитанные", "Пока нет уведомлений").
- `kind` values use dotted namespace: `crawl.completed`, `crawl.failed`, `position_check.completed`, `pdf.ready`, `client_pdf.ready`, `audit.completed`, `keyword_suggest.ready`, `llm_brief.ready`, `monitoring.alert`.
- Helper signature:
  ```python
  async def notify(
      db: AsyncSession,
      user_id: UUID,
      kind: str,
      title: str,
      body: str,
      link_url: str,
      site_id: UUID | None = None,
      severity: Literal["info", "warning", "error"] = "info",
  ) -> Notification
  ```
- Cleanup task: `app/tasks/notification_tasks.py::cleanup_old_notifications` — deletes rows where `created_at < now() - interval '30 days'`. Scheduled via existing Celery Beat infra.

</specifics>

<deferred>
## Deferred Ideas

- **Real-time SSE/WebSocket delivery** — deferred. Polling @ 30s is the locked decision; revisit only if real-time becomes a hard requirement.
- **Notification preferences UI** (per-user opt-out per `kind`) — nice-to-have, deferred to a backlog phase. For now everyone gets everything their tasks produce.
- **Email digest of unread notifications** — out of scope; Telegram already covers the push channel.
- **Deduplication / throttling** — implement only if testing shows it's noisy.
- **Mobile/responsive dropdown** — style defensively but don't block on it; desktop first.
- **Plumbing `user_id` into tasks that currently lack it** (crawl, position, audit, suggest, llm, monitoring rules) — progressively handled as each caller is updated; not a Phase 17 blocker.
- **Adding `owner_id` to `Site` model** — rejected; scope creep.

</deferred>

---

*Phase: 17-in-app-notifications*
*Context gathered: 2026-04-08 via /gsd:discuss-phase*
*D-02 revised 2026-04-08 after checker feedback (Site.owner_id does not exist; fallback is "skip silently")*
