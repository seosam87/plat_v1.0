---
status: diagnosed
trigger: "UAT Test 4: клик Применить в playbook modal — silence, модал не закрывается, redirect не срабатывает, хотя ProjectPlaybook создаётся в БД"
created: 2026-04-11T21:00:00Z
updated: 2026-04-11T21:10:00Z
---

## Current Focus

hypothesis: HX-Redirect targets the same-origin URL that's already in the address bar (pathname identical, only `#playbook` hash may differ or be identical), so browser performs an in-document anchor jump instead of a full reload — modal DOM stays, user sees nothing change.
test: Traced location state through the user flow and inspected HTMX 2.0.3 HX-Redirect handling (`location.href = val`).
expecting: If hypothesis holds, the URL `/ui/projects/{id}/kanban#playbook` is already the current URL (because `switchProjectTab('playbook')` rewrites the hash via `history.replaceState` when user opens the Playbook tab), and `location.href` assignment to the exact same URL is a no-op.
next_action: Return diagnosis — no fix applied (find_root_cause_only mode).

## Symptoms

expected: Clicking Применить in the apply-playbook modal closes the modal and redirects to `#playbook` tab of the project via HX-Redirect, page reloads, new ProjectPlaybook card appears.
actual: Backend copy-on-apply runs and commits (ProjectPlaybook visible after manual reload), but UI modal stays open, no redirect, no visible feedback.
errors: none (no console error, no server error, no HTTP failure — pure "silence")
reproduction: See .planning/phases/999.8-playbook-builder-reusable-promotion-plan-blocks/999.8-UAT.md Test 4
started: Introduced in commit 034a128 (Plan 04, Task 3 — apply+tab UI)

## Eliminated

- hypothesis: Endpoint returns RedirectResponse instead of HX-Redirect header
  evidence: app/routers/playbooks.py:672-676 returns `HTMLResponse("", status_code=200, headers={"HX-Redirect": ...})` — correct HTMX pattern
  timestamp: 2026-04-11T21:05:00Z
- hypothesis: Form is not wired to HTMX after modal swap
  evidence: Modal is swapped via `hx-swap="innerHTML"` into `#apply-modal-container` (app/templates/projects/_playbook_tab.html:21-26, 34-41); HTMX 2.0 auto-processes swapped content; form uses `hx-post`, which requires HTMX processing. If HTMX weren't processing the form, native browser submit would have navigated away to the empty 200 response body and left a blank page — but user sees the modal still open, which rules this out.
  timestamp: 2026-04-11T21:06:00Z
- hypothesis: Middleware or response class strips HX-Redirect header
  evidence: Grep of app/main.py shows only UIAuthMiddleware which does not touch response headers. Other endpoints (app/routers/tools.py:720, app/routers/templates.py:253, app/main.py:1796,2345) use the same HX-Redirect pattern successfully.
  timestamp: 2026-04-11T21:07:00Z
- hypothesis: require_admin guard blocks the POST
  evidence: User confirmed backend runs and creates ProjectPlaybook row — auth is clearly passing.
  timestamp: 2026-04-11T21:07:00Z

## Evidence

- timestamp: 2026-04-11T21:02:00Z
  checked: app/routers/playbooks.py:652-676 (ui_project_playbook_apply endpoint)
  found: Returns `HTMLResponse("", status_code=200, headers={"HX-Redirect": f"/ui/projects/{project_id}/kanban#playbook"})`. Header format correct, status code correct, pattern matches working HX-Redirect callers elsewhere in codebase.
  implication: Server side of the HTMX contract is honored. Bug lives in what the target URL actually does in the browser.

- timestamp: 2026-04-11T21:03:00Z
  checked: app/templates/projects/kanban.html:149-184 (tab panel + switchProjectTab JS)
  found: switchProjectTab('playbook') — invoked by the tab button `onclick` — rewrites the current URL to include `#playbook` via `history.replaceState(null, '', '#playbook')` (line 174). When the user clicks the Плейбуки tab before opening the apply modal, the browser's address bar is already showing `/ui/projects/{id}/kanban#playbook`.
  implication: By the time the user clicks Применить, the browser's `window.location.href` is ALREADY `/ui/projects/{id}/kanban#playbook` — the exact same URL the server asks HTMX to redirect to.

- timestamp: 2026-04-11T21:04:00Z
  checked: HTMX 2.0.3 source behavior for HX-Redirect (per htmx docs + source)
  found: HTMX handles HX-Redirect by executing `location.href = val`. Assigning `location.href` to the URL the browser is already on (same pathname + same hash) is a no-op — it does NOT reload the document. Assigning to the same pathname with only a hash change performs an in-document anchor jump without a reload.
  implication: Either way (identical URL or hash-only diff), no page reload fires. The modal DOM persists because nothing re-renders, and the Playbook tab's HTMX `intersect once` trigger has already fired so it won't re-fetch. User sees "silence".

- timestamp: 2026-04-11T21:05:00Z
  checked: app/templates/playbooks/_apply_modal.html:40-41 (form attributes)
  found: `<form hx-post=".../apply" hx-swap="none">` — no `hx-on::after-request`, no client-side fallback to force reload or remove the modal. The entire close-and-refresh flow is delegated to HX-Redirect, which fails silently for the reasons above.
  implication: There is no secondary mechanism to close the modal or refresh the tab. The UI has no other path back to a consistent state besides a manual page reload.

- timestamp: 2026-04-11T21:06:00Z
  checked: .planning/phases/999.8-playbook-builder-reusable-promotion-plan-blocks/999.8-04-apply-and-project-tab-SUMMARY.md:34-35, 212
  found: Plan explicitly documents "HX-Redirect on apply POST so modal closes client-side and page reloads with #playbook hash" and the walkthrough step 6: "browser reloads to /ui/projects/{id}/kanban#playbook". Developer assumed HX-Redirect to a hash-only-different URL would trigger a full reload. This is the false assumption behind the bug.
  implication: Design intent was full reload. Implementation delivers no reload when the browser is already on that URL (which it always is in the documented flow, because Plan 04's own `switchProjectTab` writes the hash before the user can click Apply).

## Resolution

root_cause: |
  The apply endpoint returns `HX-Redirect: /ui/projects/{project_id}/kanban#playbook`
  (app/routers/playbooks.py:675), but by the time the user clicks Применить,
  `window.location.href` in the browser is already `/ui/projects/{id}/kanban#playbook` —
  `switchProjectTab('playbook')` in kanban.html:174 has already rewritten the hash via
  `history.replaceState` when the user opened the Playbook tab in step 3 of the flow.
  HTMX 2.0 processes HX-Redirect via `location.href = value`; assigning the browser's
  current URL to itself is a no-op (or at best a hash-only anchor jump), so no page
  reload fires, the modal DOM is never replaced, and the user sees "silence" even though
  the POST succeeded and the row was committed to the database.
fix: (not applied — diagnose-only mode)
verification: (not applied — diagnose-only mode)
files_changed: []
