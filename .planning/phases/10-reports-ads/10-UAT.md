---
status: partial
phase: 10-reports-ads
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md]
started: "2026-04-05T18:30:00Z"
updated: "2026-04-05T19:15:00Z"
---

## Current Test

[testing paused — 2 blocked items outstanding]

## Tests

### 1. Дашборд — таблица проектов
expected: Открыть /ui/dashboard. Видна таблица проектов с колонками: Проект, Сайт, TOP-3, TOP-10, TOP-30, Открытые задачи, В работе, Статус, Действия. Статус — цветные бейджи. Кнопки: Kanban, Report.
result: issue
reported: "статус не цветные бейджи, а слово Активен"
severity: cosmetic

### 2. Дашборд — стартовая страница
expected: После логина пользователь попадает на /ui/dashboard (а не на /ui/sites как раньше).
result: [pending]

### 3. Генерация PDF-отчёта (краткий)
expected: Открыть /ui/reports/{project_id}. Выбрать "Краткий". Нажать скачать. Получить PDF файл (1-2 страницы) с трендами позиций, задачами и изменениями сайта.
result: issue
reported: "Иконки размазаны на всю страницу, по нажатию на pdf вылетает 500 ошибка. Flower logs: tornado.web.HTTPError 401 Unauthorized в get_current_user, ValueError: not enough values to unpack"
severity: blocker

### 4. Генерация PDF-отчёта (подробный)
expected: Открыть /ui/reports/{project_id}. Выбрать "Подробный". Нажать скачать. Получить PDF файл (5-10 страниц) с полной таблицей ключевых слов, графиками и всеми задачами.
result: issue
reported: "Тоже 500 ошибка internal server error. Postgres logs показывают password authentication failed for user seo_user"
severity: blocker

### 5. Настройка расписания отчётов
expected: Открыть /ui/admin/report-schedule. Видна форма настройки: утренний дайджест (вкл/выкл, время), еженедельный отчёт (вкл/выкл, день недели). Сохранение работает.
result: issue
reported: "всё свиду работает, но внешний вид очень плохой, надо сделать красивее. Также в логах worker ImportError: cannot import name async_session_factory from app.database (не относится к этой странице)"
severity: cosmetic

### 6. Загрузка CSV рекламного трафика
expected: Открыть /ui/ads/{site_id}. Загрузить CSV файл (source, date, sessions, conversions, cost). Данные появляются на странице.
result: issue
reported: "Ошибка Site not found, 404. Также в логах: AttributeError: 'Site' object has no attribute 'domain' в report_service.py:139"
severity: blocker

### 7. Сравнение периодов рекламного трафика
expected: На странице /ui/ads/{site_id} выбрать два периода через date-picker. Нажать сравнить. Появляется таблица с колонками: sessions, conversions, CR%, cost-per-conversion — и дельты (% и абсолютные).
result: blocked
blocked_by: prior-phase
reason: "страница /ui/ads не работает (Test 6 — Site not found 404)"

### 8. График трендов рекламного трафика
expected: На странице /ui/ads/{site_id} виден Chart.js график с трендами по неделям/месяцам. Переключатель weekly/monthly работает.
result: blocked
blocked_by: prior-phase
reason: "страница /ui/ads не работает (Test 6 — Site not found 404)"

## Summary

total: 8
passed: 0
issues: 5
pending: 0
skipped: 0
blocked: 2

## Gaps

- truth: "Статус проектов отображается цветными бейджами (зелёный=active, жёлтый=paused, серый=completed)"
  status: failed
  reason: "User reported: статус не цветные бейджи, а слово Активен"
  severity: cosmetic
  test: 1
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "PDF подробный отчёт скачивается без ошибок (5-10 страниц с таблицей ключевых слов, графиками, задачами)"
  status: failed
  reason: "User reported: Тоже 500 ошибка internal server error. Postgres: password authentication failed for user seo_user"
  severity: blocker
  test: 4
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "Страница настройки расписания отчётов имеет аккуратный, красивый внешний вид"
  status: failed
  reason: "User reported: всё работает, но внешний вид очень плохой, надо сделать красивее"
  severity: cosmetic
  test: 5
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "Страница /ui/ads/{site_id} открывается и позволяет загрузить CSV рекламного трафика"
  status: failed
  reason: "User reported: ошибка Site not found, 404. Также AttributeError: Site has no attribute domain в report_service.py:139"
  severity: blocker
  test: 6
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "PDF краткий отчёт скачивается без ошибок (1-2 страницы с трендами, задачами, изменениями)"
  status: failed
  reason: "User reported: Иконки размазаны на всю страницу, по нажатию на pdf вылетает 500 ошибка. Flower 401 Unauthorized в get_current_user"
  severity: blocker
  test: 3
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
