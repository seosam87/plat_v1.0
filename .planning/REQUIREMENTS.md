# Requirements: SEO Management Platform v2.1

**Defined:** 2026-04-08
**Milestone:** v2.1 Onboarding & Project Health
**Core Value:** Платформа объясняет сама себя возвращающемуся пользователю — каждая страница отвечает на "почему пусто?" и "что делать дальше?" без необходимости помнить workflow.

## v2.1 Requirements

### Project Health Widget (PHW) — Phase 18

- [ ] **PHW-01**: На Site Overview отображается widget с 7-шаговым чек-листом настройки сайта: (1) WP creds, (2) первый краул, (3) ключи импортированы, (4) позиции проверены, (5) Яндекс Метрика подключена, (6) аудит запущен, (7) контент-pipeline использован хотя бы раз
- [ ] **PHW-02**: Каждый шаг показывает статус ✅/⏳/⚠️ с цветной индикацией (green/gray/amber), вычисляется из существующих моделей (без новой БД)
- [ ] **PHW-03**: Для каждого невыполненного шага виден короткий пояснительный текст ("почему это нужно") и кнопка "Сделать сейчас" — ссылка на релевантную страницу
- [ ] **PHW-04**: Widget показывает общий прогресс (N/7) и выделяет "следующий шаг" — тот, с которого пользователь должен начать, если зашёл впервые или после перерыва
- [ ] **PHW-05**: Status signals добавлены в `site_service.compute_site_health()` — единая функция, возвращающая структуру `{step: {done, message, next_url}}`, переиспользуемая на Overview и в будущих дашбордах
- [ ] **PHW-06**: Widget полностью выполнен если все 7 шагов ✅ — отображается свёрнутым с CTA "Показать снова" (не мешает дальнейшей работе)

### Empty States (EMP) — Phase 19

- [ ] **EMP-01**: Создан reusable Jinja2-макрос `{% from "macros/empty_state.html" import empty_state %}` с параметрами: `icon`, `title`, `message`, `action_url`, `action_label`, `secondary_url`, `secondary_label`
- [ ] **EMP-02**: Макрос применён на всех основных страницах **core workflow**: Keywords, Positions, Clusters, Gap Analysis, Site Overview (когда данных нет)
- [ ] **EMP-03**: Макрос применён на **analytics** страницах: Metrika, Traffic Analysis, Growth Opportunities, Dead Content, Quick Wins
- [ ] **EMP-04**: Макрос применён на **content** страницах: WP Pipeline, Content Plan, Briefs, Client Reports
- [ ] **EMP-05**: Каждое empty state объясняет **почему пусто** ("нет данных потому что...") и даёт минимум одну прямую кнопку-действие ("Запустить краул", "Импортировать ключи" и т.д.)
- [ ] **EMP-06**: Empty state применён на **tools** страницах (если Phase 24–25 не готов на момент выполнения Phase 19 — tools-половину отложить на after Phase 25 per roadmap)
- [ ] **EMP-07**: Smoke-тесты Phase 15.1 не ломаются — все страницы с empty state корректно рендерятся на seed-данных (и пустых, и с данными)

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

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PHW-01 | Phase 18 (1 plan) | Pending |
| PHW-02 | Phase 18 (1 plan) | Pending |
| PHW-03 | Phase 18 (1 plan) | Pending |
| PHW-04 | Phase 18 (1 plan) | Pending |
| PHW-05 | Phase 18 (1 plan) | Pending |
| PHW-06 | Phase 18 (1 plan) | Pending |
| EMP-01 | Phase 19-01 | Pending |
| EMP-02 | Phase 19-01 | Pending |
| EMP-03 | Phase 19-02 | Pending |
| EMP-04 | Phase 19-02 | Pending |
| EMP-05 | Phase 19-01, 19-02 | Pending |
| EMP-06 | Phase 19-03 (deferred after Phase 25 if tools not ready) | Pending |
| EMP-07 | Phase 19-03 | Pending |

**Coverage:**
- v2.1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
