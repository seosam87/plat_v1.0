# Roadmap: SEO Management Platform

## Milestones

- **v1.0 MVP** — 16 phases (shipped 2026-04-06) — [details](milestones/v1.0-ROADMAP.md)
- **v2.0 SEO Insights & AI** — 7 phases (shipped 2026-04-08) — [details](milestones/v2.0-ROADMAP.md)
- **v2.1 Onboarding & Project Health** — 4 phases (shipped 2026-04-10) — [details](milestones/v2.1-ROADMAP.md)
- **v3.0 Client & Proposal** — 4 phases (shipped 2026-04-10) — [details](milestones/v3.0-ROADMAP.md)
- **v3.1 SEO Tools** — 2 phases (shipped 2026-04-10) — [details](milestones/v3.1-ROADMAP.md)
- **v4.0 Mobile & Telegram** — 8 phases (active)

## Phases

<details>
<summary>v1.0 MVP (16 phases) — SHIPPED 2026-04-06</summary>

- [x] Phase 1: Stack & Auth (4 plans)
- [x] Phase 2: Site Management (3 plans)
- [x] Phase 3: Crawler Core (4 plans)
- [x] Phase 4: Crawl Scheduling (3 plans)
- [x] Phase 4.1: Test Backfill — INSERTED
- [x] Phase 5: Keyword Import & File Parsers (5 plans)
- [x] Phase 6: Position Tracking (3 plans)
- [x] Phase 6.1: Proxy Management & XMLProxy — INSERTED (3 plans)
- [x] Phase 7: Semantics (3 plans)
- [x] Phase 8: WP Pipeline (4 plans)
- [x] Phase 9: Projects & Tasks (3 plans)
- [x] Phase 9.1: Fix Project UI Bugs — INSERTED (2 plans)
- [x] Phase 9.2: Fix Position Check Diagnostics — INSERTED (1 plan)
- [x] Phase 10: Reports & Ads (4 plans)
- [x] Phase 11: Hardening (4 plans)
- [x] Phase v4-09: Fix Runtime Route Gaps (1 plan)

v3.x analytics phases and v4.x UI overhaul phases also completed within v1.0.

</details>

<details>
<summary>v2.0 SEO Insights & AI (7 phases) — SHIPPED 2026-04-08</summary>

- [x] Phase 12: Analytical Foundations (3 plans)
- [x] Phase 13: Impact Scoring & Growth Opportunities (3 plans)
- [x] Phase 14: Client Instructions PDF (3 plans)
- [x] Phase 15: Keyword Suggest (3 plans)
- [x] Phase 15.1: UI Smoke Crawler — INSERTED (5 plans)
- [x] Phase 16: AI/GEO Readiness & LLM Briefs (4 plans)
- [x] Phase 17: In-app Notifications (3 plans)

</details>

<details>
<summary>v2.1 Onboarding & Project Health (4 phases) — SHIPPED 2026-04-10</summary>

- [x] Phase 18: Project Health Widget (1 plan)
- [x] Phase 19: Empty States Everywhere (3 plans)
- [x] Phase 19.1: UI Scenario Runner — Playwright (5 plans)
- [x] Phase 19.2: Interactive Tour Player (4 plans)

</details>

<details>
<summary>v3.0 Client & Proposal (4 phases) — SHIPPED 2026-04-10</summary>

- [x] Phase 20: Client CRM (4 plans)
- [x] Phase 21: Site Audit Intake (3 plans)
- [x] Phase 22: Proposal Templates & Tariffs (3 plans)
- [x] Phase 23: Document Generator (3 plans)

</details>

<details>
<summary>v3.1 SEO Tools (2 phases) — SHIPPED 2026-04-10</summary>

- [x] Phase 24: Tools Infrastructure & Fast Tools (5 plans)
- [x] Phase 25: SERP Aggregation Tools (5 plans)

</details>

### v4.0 Mobile & Telegram (active)

- [x] **Phase 26: Mobile Foundation** - base_mobile.html, /m/ routing, Telegram WebApp auth, PWA (completed 2026-04-10)
- [x] **Phase 27: Digest & Site Health** - утренняя сводка + карточка здоровья сайта (completed 2026-04-10)
- [x] **Phase 28: Positions & Traffic** - мобильные приложения позиций и трафика (completed 2026-04-10)
- [ ] **Phase 29: Reports & Tools** - генерация отчётов и запуск инструментов с телефона
- [ ] **Phase 30: Errors & Quick Task** - ошибки Яндекса + быстрое создание задач и ТЗ
- [ ] **Phase 31: Pages App** - approve queue, quick fix, массовые операции над контентом
- [ ] **Phase 32: Telegram Bot** - отдельный Docker-сервис, команды, Mini App кнопки
- [ ] **Phase 33: Claude Code Agent** - spike: задача боту → Claude Code → diff на утверждение

## Phase Details

### Phase 26: Mobile Foundation
**Goal**: Пользователь может открыть платформу с телефона через браузер или Telegram WebApp и получить touch-friendly интерфейс без sidebar
**Depends on**: Phase 25 (existing platform)
**Requirements**: MOB-01, MOB-02, MOB-03
**Success Criteria** (what must be TRUE):
  1. Пользователь открывает `/m/` на телефоне и видит bottom navigation вместо sidebar — страница загружается без горизонтального скролла
  2. Пользователь открывает ссылку в Telegram (через WebApp кнопку) и автоматически авторизуется без ввода пароля
  3. Пользователь нажимает "Добавить на главный экран" в браузере и приложение устанавливается как PWA с иконкой и splash screen
  4. Все существующие /m/ страницы наследуют base_mobile.html и рендерятся без ошибок Jinja2
**Plans:** 3/3 plans complete
Plans:
- [x] 26-01-PLAN.md — Mobile foundation: DB migration, base_mobile.html, /m/ router
- [x] 26-02-PLAN.md — Telegram WebApp auth + profile Telegram linking
- [x] 26-03-PLAN.md — PWA manifest, service worker, icons
**UI hint**: yes

### Phase 27: Digest & Site Health
**Goal**: Пользователь видит утреннюю сводку и карточку здоровья сайта, может перейти к проблеме одним тапом
**Depends on**: Phase 26
**Requirements**: DIG-01, DIG-02, HLT-01, HLT-02
**Success Criteria** (what must be TRUE):
  1. Пользователь открывает `/m/digest` и видит ТОП изменения позиций, новые ошибки краулера, сработавшие алерты и просроченные задачи в одном экране
  2. Из любого элемента дайджеста пользователь попадает на нужный раздел платформы одним тапом
  3. Пользователь открывает `/m/health/{site_id}` и видит карточку: доступность, свежие ошибки, статус краулинга, резкие изменения позиций
  4. С карточки здоровья пользователь может запустить краулинг или поставить задачу на ошибку — действие подтверждается тостом
**Plans:** 2/2 plans complete
Plans:
- [x] 27-01-PLAN.md — Digest service layer + /m/digest page (DIG-01, DIG-02)
- [ ] 27-02-PLAN.md — Health card page + actions (HLT-01, HLT-02)
**UI hint**: yes

### Phase 28: Positions & Traffic
**Goal**: Пользователь может запустить проверку позиций и сравнить трафик по двум периодам с телефона и создать задачи на просевшие данные
**Depends on**: Phase 26
**Requirements**: POS-01, POS-02, POS-03, TRF-01, TRF-02
**Success Criteria** (what must be TRUE):
  1. Пользователь открывает `/m/positions` и запускает проверку позиций для выбранного сайта — Celery-задача стартует, прогресс обновляется через HTMX-поллинг
  2. После завершения проверки пользователь видит позиции, тренды и изменения за выбранный период в мобильном формате
  3. Пользователь видит просевшие ключи и создаёт задачу в проект прямо из списка результатов
  4. Пользователь открывает `/m/traffic` и видит сравнение трафика за два периода с выделением просевших и выросших страниц
  5. На просевшую страницу пользователь создаёт ТЗ одной кнопкой
**Plans:** 2/2 plans complete
Plans:
- [x] 28-01-PLAN.md — Positions: service, Celery progress, router, templates (POS-01, POS-02, POS-03)
- [x] 28-02-PLAN.md — Traffic: service, router, templates (TRF-01, TRF-02)
**UI hint**: yes

### Phase 29: Reports & Tools
**Goal**: Пользователь может сформировать PDF-отчёт для клиента и запустить любой SEO-инструмент с телефона
**Depends on**: Phase 26
**Requirements**: REP-01, REP-02, TLS-01, TLS-02
**Success Criteria** (what must be TRUE):
  1. Пользователь открывает `/m/reports` и формирует PDF-отчёт клиенту через три шага: выбор сайта → тип отчёта → создать
  2. Готовый отчёт пользователь отправляет клиенту в Telegram или email одной кнопкой прямо с телефона
  3. Пользователь открывает `/m/tools` и видит все 6 SEO-инструментов в мобильном формате, запускает любой из них
  4. После завершения инструмента пользователь получает in-app уведомление и видит результаты в мобильном представлении
**Plans:** 2/3 plans executed
Plans:
- [x] 29-01-reports-mobile-PLAN.md — Mobile reports: APP_BASE_URL, mobile_reports_service, /m/reports/new + delivery endpoints (REP-01, REP-02)
- [x] 29-02-tools-list-run-PLAN.md — Mobile tools: /m/tools list + /m/tools/{slug}/run + HTMX progress polling (TLS-01)
- [ ] 29-03-tool-result-notify-PLAN.md — Mobile tool result view + notify() in 6 tool tasks (TLS-02, completes TLS-01)
**UI hint**: yes

### Phase 30: Errors & Quick Task
**Goal**: Пользователь видит ошибки из Yandex Webmaster API и Метрики, может создать задачу или ТЗ на любую проблему
**Depends on**: Phase 26
**Requirements**: ERR-01, ERR-02, TSK-01, TSK-02
**Success Criteria** (what must be TRUE):
  1. Пользователь открывает `/m/errors` и видит ошибки индексации, краулинга и санкции из Yandex Webmaster API сгруппированными по типу
  2. Из списка ошибок пользователь составляет ТЗ на исправление и сохраняет его — ТЗ привязывается к конкретной ошибке
  3. Пользователь открывает `/m/tasks/new` и создаёт задачу в нужный проект: текст + приоритет + проект — три поля, одна кнопка
  4. Пользователь создаёт ТЗ копирайтеру из аналитических данных и отправляет его в Telegram или email
**Plans**: TBD
**UI hint**: yes

### Phase 31: Pages App
**Goal**: Пользователь управляет контентом сайта с телефона: просматривает статус страниц, одобряет WP Pipeline изменения и выполняет quick fix
**Depends on**: Phase 26
**Requirements**: PAG-01, PAG-02, PAG-03, PAG-04
**Success Criteria** (what must be TRUE):
  1. Пользователь открывает `/m/pages/{site_id}` и видит список страниц с аудит-статусом: индексация, позиции, ошибки — в мобильном формате с фильтрацией
  2. Пользователь видит очередь ожидающих изменений WP Pipeline и одобряет или отклоняет каждое изменение через 2-tap confirmation
  3. Пользователь выбирает страницу и выполняет quick fix (обновить title/meta/schema/TOC) одной кнопкой — изменение отправляется в WP и подтверждается тостом
  4. Пользователь запускает массовую операцию (обновить Schema на всех статьях или добавить TOC) с экраном подтверждения и прогресс-индикатором
**Plans**: TBD
**UI hint**: yes

### Phase 32: Telegram Bot
**Goal**: Отдельный Docker-сервис принимает команды от авторизованных пользователей и открывает Mini App кнопки
**Depends on**: Phase 26
**Requirements**: BOT-01, BOT-02, BOT-03
**Success Criteria** (what must be TRUE):
  1. Бот отвечает только на сообщения от Telegram ID из allowlist — неизвестные пользователи получают "Доступ запрещён" без выполнения команды
  2. Пользователь отправляет /status, /logs, /test или /deploy — бот запрашивает подтверждение и выполняет операцию, возвращая результат в чат
  3. Бот отвечает inline-кнопками, открывающими Mini App: дайджест, отчёт, позиции — каждая кнопка ведёт на соответствующий /m/ маршрут
  4. Telegram Bot работает как отдельный контейнер в docker-compose.yml и не падает при недоступности основного FastAPI сервиса
**Plans**: TBD

### Phase 33: Claude Code Agent (Spike)
**Goal**: Пользователь может отправить текстовую задачу боту, которая выполняется через Claude Code с diff-подтверждением
**Depends on**: Phase 32
**Requirements**: AGT-01, AGT-02
**Success Criteria** (what must be TRUE):
  1. Пользователь отправляет текстовую задачу боту — задача принимается, бот подтверждает получение и сообщает о начале выполнения
  2. После выполнения Claude Code бот присылает diff изменений — пользователь отвечает "да" или "нет" для применения или отката
  3. Spike задокументирован: решение о production-использовании принято на основе результатов эксперимента
**Plans**: TBD

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1–11 + v3.x + v4.x | v1.0 | 56/56 | Complete | 2026-04-06 |
| 12–17 + 15.1 | v2.0 | 24/24 | Complete | 2026-04-08 |
| 18–19.2 | v2.1 | 13/13 | Complete | 2026-04-10 |
| 20–23 | v3.0 | 13/13 | Complete | 2026-04-10 |
| 24–25 | v3.1 | 10/10 | Complete | 2026-04-10 |
| 26 | v4.0 | 3/3 | Complete    | 2026-04-10 |
| 27 | v4.0 | 1/2 | Complete    | 2026-04-10 |
| 28 | v4.0 | 2/2 | Complete    | 2026-04-10 |
| 29 | v4.0 | 2/3 | In Progress|  |
| 30 | v4.0 | 0/? | Not started | - |
| 31 | v4.0 | 0/? | Not started | - |
| 32 | v4.0 | 0/? | Not started | - |
| 33 | v4.0 | 0/? | Not started | - |

**Total: 45 phases shipped, 8 phases planned for v4.0**

## Backlog

### Phase 999.3: Smart Route Discovery (response_class filter) (BACKLOG — COMPLETE)

Extends `discover_routes` to auto-filter by `response_class=HTMLResponse`. 2/2 plans complete.

### Phase 999.5: Repo ↔ Deployment Sync Strategy (BACKLOG)

Two deployment-drift incidents caught — no automated sync between git repo and running deployment. Context gathered, no plans yet.

### Phase 999.6: LLM API Integration & Live Verification (BACKLOG)

Complete human-verify checkpoint deferred from Phase 16-04. Requires real Anthropic API key for live testing.

### Phase 999.7: Remove server log from mobile UI (BACKLOG)

**Goal:** Убрать или настроить server log в мобильном интерфейсе — виден в Telegram Mini App, бесполезен для пользователя. Проверить base_mobile.html, digest.html и все /m/ шаблоны на предмет отладочных элементов.
**Requirements:** TBD
**Plans:** 0 plans

### Phase 999.8: Playbook Builder — инструмент сборки плана продвижения из переиспользуемых блоков (BACKLOG)

**Goal:** Каркас управления SEO-методологиями через переиспользуемые «кубики». Каждый `PlaybookBlock` привязан к `ExpertSource` (Шестаков, Шакин, агентство) и к медиа-материалам (ссылки на видео, статьи — без транскриптов, только URL). `Playbook` — шаблон из блоков, `ProjectPlaybook` — применённая копия с живым чеклистом на странице проекта. Шаги playbook ведут пользователя через существующие экраны системы (крауль, ключи, конкуренты, коммерческие страницы).

Высокий приоритет. Планируемые фазы:
- P1: модели `ExpertSource`, `BlockCategory`, `PlaybookBlock`, `BlockMedia` + админ-CRUD
- P2: `Playbook` + `PlaybookStep` + drag-and-drop билдер (HTMX + Sortable.js)
- P3: `ProjectPlaybook` + живой чеклист на странице проекта + переходы по UI с плашкой текущего шага
- P4: медиа-привязки (ссылки на видео/статьи), страницы экспертов, FTS по `summary_md`

**Requirements:** TBD (backlog — not mapped to v4.0 requirement IDs)
**Plans:** 6/6 plans complete

Plans:
- [x] 999.8-01-data-foundation-PLAN.md — Models, Alembic 0054, markdown filter, sidebar, router skeleton (Wave 1)
- [x] 999.8-02-admin-crud-PLAN.md — Block + Expert admin CRUD, filter dropdowns, media fieldset (Wave 2)
- [x] 999.8-03-playbook-builder-PLAN.md — Template list, drag-drop builder with Sortable.js@1.15.0, clone (Wave 2)
- [x] 999.8-04-apply-and-project-tab-PLAN.md — Apply flow, kanban tab refactor, step checklist, hint service (Wave 3)
- [x] 999.8-05-banner-and-seed-PLAN.md — Global banner, step API endpoints, idempotent demo seed (Wave 3)
- [x] 999.8-06-uat-fixes-PLAN.md — UAT gap closure: category filter 422, apply HX-Refresh, openPlaybookStep JS extraction, MissingGreenlet eager-load (Wave 4)

### Phase 999.9: Prompt Library — каркас AI-агентов через библиотеку промптов (BACKLOG)

**Goal:** Каркас «AI-агентов» без реальной интеграции с LLM API. Каталог промптов, сгруппированных по `ExpertSource` (Шестаков, Шакин, агентства) и категориям (ТЗ для текста, проверка свежести, fact-check, ссылочная стратегия, GEO/AEO). Пользователь подставляет переменные, копирует финальный промпт, прогоняет во внешнем сервисе (ChatGPT/Claude/Gemini), возвращает результат текстом/файлом обратно в систему. Результаты копятся как `PromptRun` и привязываются к шагам `ProjectPlaybook` из фазы 999.8.

Средний приоритет — делаем после того, как Playbook Builder (999.8) даст каркас блоков и экспертов. Планируемые фазы:
- P5: модели `PromptTemplate` + `PromptRun` + UI библиотеки промптов
- P6: сшивка с Playbook — поле `PlaybookBlock.prompt_template_id`, кнопка «Запустить промпт» внутри шага playbook'а, история прогонов в контексте проекта

Когда появится бюджет и решение о живой LLM-интеграции — `PromptRun` эволюционирует в `AgentRun` без миграции данных (просто добавляется автоисполнение через LangGraph/Pydantic AI).

**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.10: QA Surface Tracker — десктоп, мобилка, Telegram (BACKLOG)

**Goal:** Retroactive audit system. Таблица `FeatureSurface` — реестр живых фич системы с привязкой к поверхности (`desktop` / `mobile` / `telegram`), URL или команде входа, необязательной ссылке на Playwright-сценарий из Phase 19.1, last_checked_at / last_checked_commit / last_checked_result, retest_policy (N коммитов затрагивающих определённые пути ИЛИ M дней). Дашборд `/ui/qa/surfaces` с фильтрами «stale / never tested / broken / works», цветовая индикация. Git-хук помечает затронутые фичи как stale после коммита. Ручная отметка «проверил» для mobile и Telegram (автоматизация этих поверхностей — дорого и хрупко). Решает боль: «слишком много придумываю и не тестирую, непонятна работоспособность системы».

Высокий приоритет. Планируемые части:
- Модель `FeatureSurface` + Alembic миграция + seed ~30 ключевых фич
- Страница `/ui/qa/surfaces` с таблицей и фильтрами
- Ручная отметка проверки + заметки
- Git post-commit хук: сопоставление изменённых файлов с зависимыми фичами → stale flag
- Интеграция с существующим `scenario_runner` (Phase 19.1): при наличии `scenario_yaml_path` auto-run фиксирует результат в `FeatureSurface.last_checked_result`
- Политики stale: `{"max_days": N}`, `{"watched_paths": [...]}`, комбинация

**Out of scope (deferred):**
- Auto-run Playwright из хука (ручной запуск в MVP)
- Скрины / видео-доказательства
- Метрики uptime фич по неделям
- Интеграция с Sentry / prod-логами

**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.11: SEO-курс на основе Playbook-данных и открытых материалов (BACKLOG — SEED)

**Goal:** Коммерческий SEO-курс на своей исследовательской базе. Используются только:
- Собственная статистика из `ProjectPlaybook` / `ProjectPlaybookStep` — сколько проектов, какие блоки давали результат, средние сроки
- Собственные примеры из реальных сайтов в платформе (с анонимизацией)
- Ссылки на открытые материалы других специалистов (уже закреплено в `BlockMedia` как URL-only — без хранения транскриптов и контента)
- Описание «как сделать этот шаг через мои сервисы» — платформа сама становится инструментом курса

**Политика контента (строго):**
- Ничего из серой зоны: не скачиваем, не парсим, не сохраняем чужие курсы/транскрипты/тексты
- Ничего из красной зоны: не перепродаём чужой контент, не выдаём чужую методологию за свою
- Только ссылки + собственные заметки своими словами + собственные данные + собственные примеры

**Когда активировать:** не раньше чем через 6 месяцев реального использования Playbook Builder (999.8) — нужна накопленная статистика применения блоков. Seed-идея с триггером «когда в системе ≥ 20 завершённых ProjectPlaybook и ≥ 6 месяцев данных».

**Что потребуется в платформе (для будущей фазы):**
- Аналитика по PlaybookBlock: применения, успех, сроки
- Связка «шаг → результат»: сопоставление выполненных шагов с изменением позиций/трафика в тот же период
- Экспорт «отчёт по методологии» в pdf/markdown с анонимизированными данными
- Модуль курса: уроки, примеры, ссылки на собственные инструменты системы

Низкий приоритет. Созревает с данными.

**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
