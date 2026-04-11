---
status: diagnosed
trigger: "UAT Test 7 — hint-badges невидимы на вкладке плейбука, кружок не кликабельный, 'Перейти к шагу' ничего не делает"
created: 2026-04-11T21:00:00Z
updated: 2026-04-11T21:10:00Z
---

## Current Focus

hypothesis: Hints всегда пустые потому что step.opened_at=None (никто никогда не вызвал open_step_action), а Test 5 (navigate + status click) сломан MissingGreenlet'ом — без рабочего open-action никакие hints никогда не появятся
test: Trace opened_at write path + HTMX script execution in swapped content
expecting: Подтвердить что opened_at никогда не ставится, что hints всегда возвращают False, и что Test 5's поломка блокирует Test 7
next_action: Verify HTMX script execution in swapped content

## Symptoms

expected: |
  На вкладке плейбука для open-шагов с выполненным действием рендерится
  amber pill "Похоже, выполнено ✓" + кнопка "Подтвердить"
actual: |
  Пользователь не видит никаких hint badges.
  Параллельно: кружок статуса не кликабельный, "Перейти к шагу" тихо ничего не делает.
  Кнопка "Архивировать" работает (скрывает лишние плейбуки).
errors: "no visible error to user, but Test 5 reported 500 MissingGreenlet on circle click"
reproduction: "Apply demo playbook → open Playbook tab → observe: steps list rendered but no amber hints"
started: "2026-04-11 UAT commit 11067db"

## Eliminated

## Evidence

- timestamp: 2026-04-11T21:00:00Z
  checked: app/services/playbook_hints.py:47-50
  found: |
    check_step_hint() first check: `if step.opened_at is None: return False`.
    opened_at is the ONLY anchor for hint queries.
  implication: |
    Если opened_at=None для всех шагов, hints={step_id: False} всегда.
    Пользователь никогда не увидит amber badge.

- timestamp: 2026-04-11T21:00:00Z
  checked: app/services/playbook_service.py:870-888 (open_step_action)
  found: |
    open_step_action() — единственное место, где пишется step.opened_at.
    Вызывается только из endpoint POST /api/project-playbook-steps/{step_id}/open-action.
  implication: |
    Единственный способ получить opened_at != None — успешно вызвать этот endpoint.

- timestamp: 2026-04-11T21:00:00Z
  checked: app/templates/projects/_playbook_project_step.html:115-161 (openPlaybookStep JS)
  found: |
    JS handler openPlaybookStep fires-and-forgets POST /open-action, затем
    GET /playbook-step-route, затем window.location.href = data.url.
    Определён в <script> теге внизу partial, защищён
    `if (typeof window.openPlaybookStep === 'undefined')`.
  implication: |
    Скрипт inline в swapped innerHTML. HTMX должен его выполнить при swap,
    но если не выполняет — window.openPlaybookStep остаётся undefined,
    onclick="openPlaybookStep(...)" бросает ReferenceError (тихо в onclick),
    navigation не происходит → opened_at никогда не ставится → hints всегда False.

- timestamp: 2026-04-11T21:00:00Z
  checked: app/templates/projects/kanban.html:149-155 (#tab-playbook lazy-load)
  found: |
    Tab panel: <div id="tab-playbook" style="display:none;"
       hx-get="/ui/projects/{id}/playbook-tab"
       hx-trigger="intersect once"
       hx-target="this"
       hx-swap="innerHTML">
  implication: |
    Content loaded via innerHTML swap. HTMX 2.0 по умолчанию НЕ выполняет
    скрипты в innerHTML swap: для этого нужно hx-swap="innerHTML script" 
    или htmx.config.allowScriptTags=true ИЛИ переключение на outerHTML.
    Это отличается от HTMX 1.x.

- timestamp: 2026-04-11T21:00:00Z
  checked: app/templates/base.html:7
  found: "HTMX 2.0.3 loaded from CDN, no explicit config, no htmx.config.allowScriptTags"
  implication: |
    HTMX 2.0.3 default: <script> tags within swapped innerHTML content
    ARE executed by default (via processScripts in htmx 2.x). But behavior
    depends on swap strategy. Need to verify.

- timestamp: 2026-04-11T21:00:00Z
  checked: app/routers/playbooks.py:754-772 (api_project_step_status)
  found: |
    cycle_step_status() → set_step_status() → db.flush() + db.refresh(step).
    db.refresh(step) EXPIRES all attributes and reloads only column attrs.
    Relationships (step.block, step.block.category, step.block.expert_source,
    step.block.media, step.project_playbook, step.project_playbook.steps)
    are NOT in the default refresh load — they become LAZY-loadable.
    Then templates.TemplateResponse renders _playbook_project_step.html,
    which accesses step.block.action_kind, step.block.category,
    step.block.expert_source, step.block.media, step.project_playbook.name,
    step.project_playbook.steps | length.
  implication: |
    После db.refresh() sync Jinja2 context тригерит async lazy-load ->
    sqlalchemy.exc.MissingGreenlet. Это корневая причина Test 5 circle-500.
    Статус endpoint падает ДАЖЕ если HTMX wiring корректный.

- timestamp: 2026-04-11T21:00:00Z
  checked: app/services/playbook_service.py:815-832 (get_project_step)
  found: |
    get_project_step() eager-loads step.block+category+expert_source+media
    + step.project_playbook (single-object), НО НЕ ЗАГРУЖАЕТ
    step.project_playbook.steps (коллекция).
  implication: |
    Template reads step.project_playbook.steps | length (line 106)
    — это вторая точка lazy-load после refresh.
    Даже если убрать refresh, этот доступ всё равно выстрелит lazy-load.

## Resolution

root_cause: |
  ПРЯМАЯ причина невидимости hint-badges: step.opened_at=None для всех шагов
  демо-плейбука, потому что функция open_step_action() никогда не вызывалась
  успешно. check_step_hint (playbook_hints.py:47-50) возвращает False как
  первый guard при opened_at=None, поэтому compute_hints_for_playbook
  отдаёт {step.id: False} для всех шагов, и в _playbook_project_step.html
  условие {% if hint and status != 'done' %} (line 46) никогда не True.

  ИСТОЧНИК недостижимости open_step_action:
  (a) Test 5 "Перейти к шагу" не работает — скорее всего потому что
      HTMX не выполняет <script> блок внутри swapped innerHTML контента
      _playbook_project_step.html, поэтому window.openPlaybookStep остаётся
      undefined, onclick бросает тихий ReferenceError, никакой fetch
      не отправляется и opened_at не ставится.
  (b) Параллельно блокирующая проблема: endpoint /status (POST cycle) 
      падает MissingGreenlet после db.refresh(step) экспайрит relationships,
      и Jinja2 (sync) пытается лениво загрузить step.block.*/step.project_playbook.*.

fix:
verification:
files_changed: []
