---
status: diagnosed
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
passed: 1
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
  root_cause: "dashboard_service.py:75 передаёт status как SQLAlchemy enum объект, Jinja2 сравнение p.status == 'active' не срабатывает, fallback рендерит plain text"
  artifacts:
    - path: "app/services/dashboard_service.py"
      issue: "line 75 — status enum не конвертируется в строку"
    - path: "app/templates/dashboard/index.html"
      issue: "lines 150-158 — badge условия не матчатся с enum значением"
  missing:
    - "Конвертировать enum в строку: row['status'].value if hasattr(row['status'], 'value') else str(row['status'])"
  debug_session: ""

- truth: "PDF подробный отчёт скачивается без ошибок (5-10 страниц с таблицей ключевых слов, графиками, задачами)"
  status: failed
  reason: "User reported: Тоже 500 ошибка internal server error"
  severity: blocker
  test: 4
  root_cause: "report_service.py:139 обращается к site.domain, но Site модель имеет site.url и site.name — атрибут domain не существует"
  artifacts:
    - path: "app/services/report_service.py"
      issue: "line 139 — site.domain → AttributeError"
    - path: "app/models/site.py"
      issue: "Site model has .name (line 24) and .url (line 25), no .domain"
  missing:
    - "Заменить site.domain на site.name или site.url в report_service.py:139"
  debug_session: ""

- truth: "Страница настройки расписания отчётов имеет аккуратный, красивый внешний вид"
  status: failed
  reason: "User reported: всё работает, но внешний вид очень плохой, надо сделать красивее"
  severity: cosmetic
  test: 5
  root_cause: "Шаблон admin/report_schedule.html использует минимальные Tailwind классы — нет card-обёрток, нет визуальной иерархии секций, нет focus-стилей на input-ах"
  artifacts:
    - path: "app/templates/admin/report_schedule.html"
      issue: "Минимальная стилизация: plain border контейнеры, нет bg-цветов, нет hover/focus состояний"
  missing:
    - "Добавить bg-slate-50 на секции, space-y-4 для form groups, focus:ring-2 на inputs, transition-colors на кнопки"
  debug_session: ""

- truth: "Страница /ui/ads/{site_id} открывается и позволяет загрузить CSV рекламного трафика"
  status: failed
  reason: "User reported: ошибка Site not found, 404"
  severity: blocker
  test: 6
  root_cause: "Роут ads в main.py:2525-2545 вызывает get_site(db, sid) — сайт не найден. Возможно отсутствует проверка доступа пользователя к сайту, либо site_id не существует в БД для текущего пользователя"
  artifacts:
    - path: "app/main.py"
      issue: "lines 2525-2545 — ads route handler, site lookup возвращает None"
    - path: "app/services/site_service.py"
      issue: "lines 16-18 — get_site запрашивает Site.id == site_id без фильтра по пользователю"
  missing:
    - "Проверить что site_id существует в БД и доступен текущему пользователю"
    - "Добавить access control если отсутствует"
  debug_session: ""

- truth: "PDF краткий отчёт скачивается без ошибок (1-2 страницы с трендами, задачами, изменениями)"
  status: failed
  reason: "User reported: Иконки размазаны на всю страницу, по нажатию на pdf вылетает 500 ошибка"
  severity: blocker
  test: 3
  root_cause: "Та же ошибка что Test 4 — report_service.py:139 site.domain AttributeError. Иконки размазаны — проблема CSS в PDF шаблоне"
  artifacts:
    - path: "app/services/report_service.py"
      issue: "line 139 — site.domain не существует"
    - path: "app/templates/"
      issue: "PDF шаблон — иконки без ограничения размера, растягиваются на всю страницу"
  missing:
    - "Исправить site.domain → site.name в report_service.py:139"
    - "Ограничить размер иконок в PDF шаблоне (max-width/max-height)"
  debug_session: ""
