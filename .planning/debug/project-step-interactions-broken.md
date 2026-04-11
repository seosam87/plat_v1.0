---
status: investigating
trigger: "UAT Test 5 — 'Перейти к шагу' silent + 500 MissingGreenlet on status circle click"
created: 2026-04-11T00:00:00Z
updated: 2026-04-11T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — Issue B: step.project_playbook.steps not eager-loaded in get_project_step(); Issue A: tojson output inside double-quoted onclick attribute breaks HTML parsing
test: Read endpoint, service, template, run Jinja2 repro for tojson
expecting: Both confirmed with direct evidence
next_action: Return diagnosis

## Symptoms

expected: |
  A) Click "Перейти к шагу" → JS → sessionStorage + POST /open-action → fetch /api/playbook-step-route → redirect + sticky banner
  B) Click status circle → POST /api/project-playbook-steps/{id}/status → outerHTML swap → re-rendered step
actual: |
  A) Nothing happens; no redirect, no banner
  B) HTTP 500 with sqlalchemy.exc.MissingGreenlet
errors: |
  sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
    can't call await_only() here. Was IO attempted in an unexpected place?
reproduction: UAT Test 5 (999.8-UAT.md)
started: 2026-04-11 UAT against commit 11067db

## Eliminated

## Evidence

- checked: app/routers/playbooks.py:745-772 /api/project-playbook-steps/{id}/status
  found: After svc.cycle_step_status(db, step_id) the endpoint renders _playbook_project_step.html with context {"step": step, ...}. Template accesses step.project_playbook.steps at line 106.
  implication: Need that relationship chain eagerly loaded before Jinja renders

- checked: app/services/playbook_service.py:815-832 get_project_step()
  found: selectinload chains: block→category, block→expert_source, block→media, project_playbook. BUT NO selectinload(ProjectPlaybook.steps) — step.project_playbook.steps is NOT eagerly loaded
  implication: Line 106 of the partial (pp_total = step.project_playbook.steps|length) triggers a lazy-load on `.steps` in the sync Jinja context → MissingGreenlet

- checked: app/templates/projects/_playbook_project_step.html:104-112
  found: Block {% if action_kind != "manual_note" %} ... pp_total = step.project_playbook.steps|length ... only renders for non-manual_note steps. Demo first step is run_crawl → triggers.
  implication: Confirms the crash path is hit for exactly the demo Test 5 scenario

- checked: app/database.py:22-25
  found: expire_on_commit=False — not the cause (this was a red herring from initial hints)
  implication: Root cause is NOT session expire; it is a missing selectinload chain on get_project_step()

- checked: SA 2.0.48 Session.refresh docs
  found: refresh() DOES re-load relationships that were originally eager-loaded. So set_step_status's db.refresh(step) is fine — it reloads block/category/media/project_playbook. But it cannot reload a chain that was never eager-loaded in the first place (project_playbook.steps).
  implication: Fix must extend selectinload in get_project_step, not change refresh behavior

- checked: app/templates/projects/_playbook_project_step.html:107-111 "Перейти к шагу" button
  found: onclick="openPlaybookStep('{{ step.id }}', ..., {{ step.block.title | tojson }}, ..., {{ pp_name | tojson }}, ...)" — HTML attribute uses DOUBLE quotes but tojson output contains literal double quotes
  implication: HTML parser terminates the onclick attribute at the first " inside the tojson payload

- checked: Jinja2 tojson repro — rendered "onclick=\"openPlaybookStep({{ title | tojson }})\"" with title='SEO для коммерческих страниц (демо)'
  found: Output: onclick="openPlaybookStep("SEO \u0434\u043b\u044f ... (\u0434\u0435\u043c\u043e)")" — Cyrillic is \u-escaped, parens are preserved, BUT the surrounding double quotes of the JSON string are NOT escaped
  implication: The effective onclick value after HTML parsing is just `openPlaybookStep(` — the `(` is part of an unterminated function call. Click either does nothing or throws a silent SyntaxError. This is the root cause of Issue A.

- checked: app/routers/playbooks.py:775-793 /open-action and 796-825 /playbook-step-route
  found: Both endpoints are correctly wired and eager-load what they need (/playbook-step-route uses get_project_step which has block and project_playbook). Neither would raise 500 for a valid step.
  implication: Endpoints are fine; the bug is upstream in the onclick that never fires

## Resolution

root_cause: |
  Issue B (500 MissingGreenlet on status toggle):
  get_project_step() at app/services/playbook_service.py:818-830 does not selectinload(ProjectPlaybook.steps) alongside the ProjectPlaybookStep.project_playbook chain. When /api/project-playbook-steps/{id}/status renders _playbook_project_step.html, line 106 evaluates step.project_playbook.steps|length — that `.steps` collection is unloaded, Jinja2 triggers a lazy load from a sync rendering context, and asyncpg raises sqlalchemy.exc.MissingGreenlet.

  Issue A ("Перейти к шагу" silent):
  _playbook_project_step.html:108 writes onclick="openPlaybookStep('...', {{ step.block.title | tojson }}, ..., {{ pp_name | tojson }}, ...)" — Jinja2's |tojson produces a JSON string wrapped in literal double quotes (e.g. "SEO ..."). Because the onclick attribute itself is wrapped in double quotes, the HTML parser terminates the attribute at the first " inside the tojson payload, so the effective handler is just "openPlaybookStep(" — an unterminated call that either throws a silent SyntaxError or does nothing on click.
fix:
verification:
files_changed: []
