# Requirements: SEO Management Platform v2.0

**Defined:** 2026-04-06
**Milestone:** v2.0 SEO Insights & AI
**Core Value:** Превратить собранные данные в actionable insights + AI-возможности + расширение семантики

## v2.0 Requirements

### SEO Insights — Analytical Surfaces

- [x] **QW-01**: Пользователь видит список страниц с позициями 4–20, у которых есть хотя бы одна нерешённая SEO-проблема (нет TOC, нет schema, мало ссылок, тонкий контент)
- [x] **QW-02**: Каждая страница в Quick Wins имеет opportunity score = (21 - позиция) x недельный трафик, список отсортирован по score
- [x] **QW-03**: Пользователь может запустить батч-фикс выбранных страниц (TOC/schema/ссылки) через существующий content pipeline
- [x] **DEAD-01**: Пользователь видит страницы с 0 визитов за 30 дней (из Метрики) и/или падением позиций > 10 за 30 дней
- [x] **DEAD-02**: Каждая мёртвая страница имеет рекомендацию: merge, redirect, rewrite или delete — на основе наличия ключей и трафика
- [x] **IMP-01**: Все ошибки (404, noindex, нет schema) имеют impact_score = severity_weight x месячный трафик страницы
- [x] **IMP-02**: Задачи в Kanban можно сортировать по impact_score; самые критичные ошибки видны первыми
- [x] **GRO-01**: Дашборд Growth Opportunities агрегирует: gap-ключи (кол-во + потенциальный трафик), потерянные позиции, каннибализации, visibility тренд
- [x] **GRO-02**: Пользователь может drill-down из карточки Opportunities в соответствующий раздел (gap analysis, positions, clusters)

### AI/GEO Readiness

- [ ] **GEO-01**: Каждая страница получает GEO-score 0–100 на основе проверок: FAQPage schema, Article/Author schema, BreadcrumbList, answer-first структура, дата обновления
- [ ] **GEO-02**: Новые проверки добавляются в существующую систему audit_check_definitions как `geo_*` коды
- [ ] **GEO-03**: Пользователь видит GEO readiness в таблице аудита с фильтром по score и типу проверки

### Client Instructions PDF

- [x] **CPDF-01**: Пользователь может сгенерировать PDF-отчёт для владельца сайта с пошаговыми инструкциями по исправлению проблем
- [x] **CPDF-02**: Отчёт объединяет Quick Wins + ошибки + рекомендации в понятном формате (проблема -> решение -> шаги в WP admin)
- [x] **CPDF-03**: Для каждого типа ошибки существует шаблон инструкции на русском языке

### Keyword Suggest

- [ ] **SUG-01**: Пользователь может получить подсказки ключей через Яндекс Suggest по seed-ключу с алфавитным перебором (200+ результатов)
- [ ] **SUG-02**: Google Suggest работает как дополнительный источник (простой endpoint, без авторизации)
- [ ] **SUG-03**: Wordstat API интеграция (opt-in, требует OAuth токен Яндекс Директ) для частотности
- [ ] **SUG-04**: Результаты suggest кэшируются в Redis (TTL 24h); повторный запрос не делает внешних вызовов

### LLM Briefs

- [ ] **LLM-01**: Пользователь может сгенерировать AI-бриф через Claude API (opt-in, кнопка видна только при настроенном API key)
- [ ] **LLM-02**: AI-бриф получает контекст: позиции, gap-ключи, GEO-score, каннибализация, конкуренты из аналитики
- [ ] **LLM-03**: Шаблонный бриф всегда генерируется как fallback; AI-бриф дополняет, не заменяет
- [ ] **LLM-04**: Жёсткий лимит токенов (input ~2000, output ~800) и circuit breaker при недоступности API

### In-app Notifications

- [ ] **NOTIF-01**: В sidebar отображается иконка уведомлений с badge-счётчиком непрочитанных
- [ ] **NOTIF-02**: Лента уведомлений показывает: завершение краула, проверка позиций, генерация PDF, алерты мониторинга
- [ ] **NOTIF-03**: Уведомления работают параллельно с Telegram (не заменяют); HTMX polling каждые 30 секунд

### Infrastructure

- [x] **INFRA-V2-01**: `normalize_url()` унифицирует URL при JOIN между pages, metrika, positions (trailing slash, http/https, UTM)
- [x] **INFRA-V2-02**: `keyword_latest_positions` flat-таблица для быстрых запросов без сканирования всех партиций

## Future Requirements (deferred)

- **INT-01**: GSC URL Inspection API — обнаружение деиндексированных страниц
- **INT-02/03/04**: Прямые API Google Ads, Yandex Direct, Facebook Ads
- **PLAT-V2-01**: White-label branding
- **PLAT-V2-02**: 2FA (TOTP) — отложено из v2.0
- **CONT-V2-02**: Scheduled content plan reminders

## Out of Scope

| Feature | Reason |
|---------|--------|
| Сложные Google API интеграции (Ads, URL Inspection) | Пользователь решил не подключать сложные Google-сервисы |
| 2FA (TOTP) | Отложено — не приоритет для текущего milestone |
| Real-time WebSocket/SSE | HTMX polling достаточен для текущего масштаба |
| NLP/spaCy для анализа контента | DOM-инспекция через bs4+lxml достаточна для GEO проверок |
| Автофикс без подтверждения | Нарушает существующий контракт diff-approval |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-V2-01 | Phase 12 | Complete |
| INFRA-V2-02 | Phase 12 | Complete |
| QW-01 | Phase 12 | Complete |
| QW-02 | Phase 12 | Complete |
| QW-03 | Phase 12 | Complete |
| DEAD-01 | Phase 12 | Complete |
| DEAD-02 | Phase 12 | Complete |
| IMP-01 | Phase 13 | Complete |
| IMP-02 | Phase 13 | Complete |
| GRO-01 | Phase 13 | Complete |
| GRO-02 | Phase 13 | Complete |
| CPDF-01 | Phase 14 | Complete |
| CPDF-02 | Phase 14 | Complete |
| CPDF-03 | Phase 14 | Complete |
| SUG-01 | Phase 15 | Pending |
| SUG-02 | Phase 15 | Pending |
| SUG-03 | Phase 15 | Pending |
| SUG-04 | Phase 15 | Pending |
| GEO-01 | Phase 16 | Pending |
| GEO-02 | Phase 16 | Pending |
| GEO-03 | Phase 16 | Pending |
| LLM-01 | Phase 16 | Pending |
| LLM-02 | Phase 16 | Pending |
| LLM-03 | Phase 16 | Pending |
| LLM-04 | Phase 16 | Pending |
| NOTIF-01 | Phase 17 | Pending |
| NOTIF-02 | Phase 17 | Pending |
| NOTIF-03 | Phase 17 | Pending |

**Coverage:**
- v2.0 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-04-06*
*Traceability updated: 2026-04-06 — roadmap created*
