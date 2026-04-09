# Requirements: SEO Management Platform v2.1

**Defined:** 2026-04-08
**Milestone:** v2.1 Onboarding & Project Health
**Core Value:** Платформа объясняет сама себя возвращающемуся пользователю — каждая страница отвечает на "почему пусто?" и "что делать дальше?" без необходимости помнить workflow.

## v2.1 Requirements

### Project Health Widget (PHW) — Phase 18

- [x] **PHW-01**: На Site Overview отображается widget с 7-шаговым чек-листом настройки сайта: (1) Site created, (2) WordPress access (`encrypted_app_password` + `wp_url`), (3) Keywords added, (4) Competitors added, (5) First crawl run, (6) First position check run, (7) Schedule configured (active `CrawlSchedule`/`PositionSchedule` not manual). Metrika/GSC — secondary optional индикатор, не блокирует "fully set up"
- [x] **PHW-02**: Каждый шаг показывает статус ✅/⏳/⚠️ с цветной индикацией (green/gray/amber), вычисляется из существующих моделей (без новой БД)
- [x] **PHW-03**: Для каждого невыполненного шага виден короткий пояснительный текст ("почему это нужно") и кнопка "Сделать сейчас" — ссылка на релевантную страницу
- [x] **PHW-04**: Widget показывает общий прогресс (N/7) и выделяет "следующий шаг" — тот, с которого пользователь должен начать, если зашёл впервые или после перерыва
- [x] **PHW-05**: Status signals добавлены в `site_service.compute_site_health()` — единая функция, возвращающая структуру `{step: {done, message, next_url}}`, переиспользуемая на Overview и в будущих дашбордах
- [x] **PHW-06**: Widget полностью выполнен если все 7 шагов ✅ — отображается свёрнутым с CTA "Показать снова" (не мешает дальнейшей работе)

### Empty States (EMP) — Phase 19

- [x] **EMP-01**: Создан reusable Jinja2-макрос `{% from "macros/empty_state.html" import empty_state %}` с параметрами: `icon`, `title`, `message`, `action_url`, `action_label`, `secondary_url`, `secondary_label`
- [x] **EMP-02**: Макрос применён на всех основных страницах **core workflow**: Keywords, Positions, Clusters, Gap Analysis, Site Overview (когда данных нет)
- [ ] **EMP-03**: Макрос применён на **analytics** страницах: Metrika, Traffic Analysis, Growth Opportunities, Dead Content, Quick Wins
- [ ] **EMP-04**: Макрос применён на **content** страницах: WP Pipeline, Content Plan, Briefs, Client Reports
- [x] **EMP-05**: Каждое empty state объясняет **почему пусто** ("нет данных потому что...") и даёт минимум одну прямую кнопку-действие ("Запустить краул", "Импортировать ключи" и т.д.)
- [x] **EMP-06**: Empty state применён на **tools** страницах (если Phase 24–25 не готов на момент выполнения Phase 19 — tools-половину отложить на after Phase 25 per roadmap)
- [x] **EMP-07**: Smoke-тесты Phase 15.1 не ломаются — все страницы с empty state корректно рендерятся на seed-данных (и пустых, и с данными)

## Future Requirements (deferred)

- **TOUR-01**: Interactive walkthrough (Shepherd.js / introJs) — запланирован в backlog Phase 999.2
- **HINT-01**: Контекстные tooltips при наведении — отдельный паттерн, не блокирует v2.1
- **I18N-01**: Многоязычные onboarding тексты — RU-only решение текущего milestone
- **CLIENT-ONBOARD-01**: Onboarding для клиентов (read-only) — v2.1 фокусируется на соло-разработчика

## Out of Scope

| Feature | Reason |
|---------|--------|
| Interactive tour/walkthrough (Shepherd.js) | Запланировано в Phase 999.2 backlog, не блокирует v2.1 |
| Контекстные hints / tooltips при наведении | Отдельный паттерн, можно добавить позже |
| Многоязычные onboarding тексты | RU-only, английский не нужен |
| Onboarding для клиентов (read-only роль) | v2.1 фокус — соло-разработчик; клиенты позже |
| Analytics событий (сколько юзеров завершили onboarding) | Нет нужды в аналитике для соло-юзера |
| Новая БД для хранения прогресса onboarding | Всё вычисляется из существующих моделей — no migrations |

### Scenario Runner (SCN) — Phase 19.1

- **SCN-01** — Custom pytest collector (`pytest_collect_file`) that discovers `scenarios/*.yaml` as `pytest.Item`s and routes them through the async executor
- **SCN-02** — Pydantic v2 `Scenario` model with discriminated-union `Step` (open/click/fill/wait_for/expect_text/expect_status) + reserved 19.2 types (say/highlight/wait_for_click) accepted and skipped with warning
- **SCN-03** — Session-scoped async Playwright Chromium + per-scenario `BrowserContext` constructed from cached `storage_state.json` (programmatic login once per session against seeded smoke_admin)
- **SCN-04** — HTMX-aware wait/expect helpers built on `expect(locator).to_be_visible(timeout=N)` + locator auto-detect (role/text/label/testid/css) from a single `target:` field
- **SCN-05** — Out-of-process idempotent live-stack seed (`tests/fixtures/scenario_runner/seed.py`) importing refactored `seed_core`/`seed_extended` from `smoke_seed.py`, runnable via `python -m` inside the `api` container
- **SCN-06** — `docker-compose.ci.yml` overlay with `tester` service (`mcr.microsoft.com/playwright/python:v1.47.0-jammy`) and worker healthcheck (`celery inspect ping`); CI entry command using `docker compose up --wait`
- **SCN-07** — Failure artifact capture: full-page screenshot + `trace.zip` (from `context.tracing`) written under `artifacts/scenarios/{scenario_name}/`; `artifacts/` gitignored
- **SCN-08** — P0 scenario YAML: `scenarios/01-suggest-to-results.yaml` — submit suggest job, HTMX poll, assert result rows render (HTMX polling pattern)
- **SCN-09** — P0 scenario YAML: `scenarios/02-site-form-submit.yaml` — create-site happy path (synchronous form)
- **SCN-10** — `scenarios/README.md` documenting YAML schema, step types, reserved types, local run command, and how 19.2 tour player will consume the same files

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PHW-01 | Phase 18 (1 plan) | Complete |
| PHW-02 | Phase 18 (1 plan) | Complete |
| PHW-03 | Phase 18 (1 plan) | Complete |
| PHW-04 | Phase 18 (1 plan) | Complete |
| PHW-05 | Phase 18 (1 plan) | Complete |
| PHW-06 | Phase 18 (1 plan) | Complete |
| EMP-01 | Phase 19-01 | Complete |
| EMP-02 | Phase 19-01 | Complete |
| EMP-03 | Phase 19-02 | Pending |
| EMP-04 | Phase 19-02 | Pending |
| EMP-05 | Phase 19-01, 19-02 | Complete |
| EMP-06 | Phase 19-03 (deferred after Phase 25 if tools not ready) | Complete |
| EMP-07 | Phase 19-03 | Complete |
| SCN-01 | Phase 19.1-02 | Complete |
| SCN-02 | Phase 19.1-02 | Complete |
| SCN-03 | Phase 19.1-03 | Complete |
| SCN-04 | Phase 19.1-03 | Complete |
| SCN-05 | Phase 19.1-03 | Complete |
| SCN-06 | Phase 19.1-04 | Complete |
| SCN-07 | Phase 19.1-03 | Complete |
| SCN-08 | Phase 19.1-05 | Complete |
| SCN-09 | Phase 19.1-05 | Complete |
| SCN-10 | Phase 19.1-05 | Complete |

**Coverage:**
- v2.1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
