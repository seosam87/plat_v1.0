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

- [ ] **Phase 26: Mobile Foundation** - base_mobile.html, /m/ routing, Telegram WebApp auth, PWA
- [ ] **Phase 27: Digest & Site Health** - утренняя сводка + карточка здоровья сайта
- [ ] **Phase 28: Positions & Traffic** - мобильные приложения позиций и трафика
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
**Plans:** 2/3 plans executed
Plans:
- [x] 26-01-PLAN.md — Mobile foundation: DB migration, base_mobile.html, /m/ router
- [ ] 26-02-PLAN.md — Telegram WebApp auth + profile Telegram linking
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
**Plans**: TBD
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
**Plans**: TBD
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
**Plans**: TBD
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
| 26 | v4.0 | 2/3 | In Progress|  |
| 27 | v4.0 | 0/? | Not started | - |
| 28 | v4.0 | 0/? | Not started | - |
| 29 | v4.0 | 0/? | Not started | - |
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
