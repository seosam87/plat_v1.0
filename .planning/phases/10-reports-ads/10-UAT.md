---
status: testing
phase: 10-reports-ads
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md]
started: "2026-04-05T18:30:00Z"
updated: "2026-04-05T18:30:00Z"
---

## Current Test

number: 1
name: Дашборд — таблица проектов
expected: |
  Открыть /ui/dashboard. Видна таблица проектов с колонками: Проект, Сайт, TOP-3, TOP-10, TOP-30, Открытые задачи, В работе, Статус, Действия. Статус — цветные бейджи (зелёный=active, жёлтый=paused, серый=completed). Кнопки: Kanban, Report.
awaiting: user response

## Tests

### 1. Дашборд — таблица проектов
expected: Открыть /ui/dashboard. Видна таблица проектов с колонками: Проект, Сайт, TOP-3, TOP-10, TOP-30, Открытые задачи, В работе, Статус, Действия. Статус — цветные бейджи. Кнопки: Kanban, Report.
result: [pending]

### 2. Дашборд — стартовая страница
expected: После логина пользователь попадает на /ui/dashboard (а не на /ui/sites как раньше).
result: [pending]

### 3. Генерация PDF-отчёта (краткий)
expected: Открыть /ui/reports/{project_id}. Выбрать "Краткий". Нажать скачать. Получить PDF файл (1-2 страницы) с трендами позиций, задачами и изменениями сайта.
result: [pending]

### 4. Генерация PDF-отчёта (подробный)
expected: Открыть /ui/reports/{project_id}. Выбрать "Подробный". Нажать скачать. Получить PDF файл (5-10 страниц) с полной таблицей ключевых слов, графиками и всеми задачами.
result: [pending]

### 5. Настройка расписания отчётов
expected: Открыть /ui/admin/report-schedule. Видна форма настройки: утренний дайджест (вкл/выкл, время), еженедельный отчёт (вкл/выкл, день недели). Сохранение работает.
result: [pending]

### 6. Загрузка CSV рекламного трафика
expected: Открыть /ui/ads/{site_id}. Загрузить CSV файл (source, date, sessions, conversions, cost). Данные появляются на странице.
result: [pending]

### 7. Сравнение периодов рекламного трафика
expected: На странице /ui/ads/{site_id} выбрать два периода через date-picker. Нажать сравнить. Появляется таблица с колонками: sessions, conversions, CR%, cost-per-conversion — и дельты (% и абсолютные).
result: [pending]

### 8. График трендов рекламного трафика
expected: На странице /ui/ads/{site_id} виден Chart.js график с трендами по неделям/месяцам. Переключатель weekly/monthly работает.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps

[none yet]
