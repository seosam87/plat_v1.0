---
status: partial
phase: 17-in-app-notifications
source:
  - 17-01-SUMMARY.md
  - 17-02-SUMMARY.md
  - 17-03-SUMMARY.md
started: 2026-04-08T13:15:00Z
updated: 2026-04-08T13:20:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Холодный старт (Cold Start Smoke Test)
expected: |
  Полный перезапуск: docker compose down → up → alembic upgrade head.
  Все контейнеры (api/worker/beat/postgres/redis) поднимаются без ошибок,
  миграция 0042 создаёт таблицу notifications + 3 индекса,
  Celery Beat регистрирует задачу 'notifications-cleanup-nightly' на 03:00,
  любая страница возвращает 200 и колокольчик отрисован в сайдбаре.
result: pass

### 2. Колокольчик в сайдбаре + HTMX-поллинг
expected: Бейдж рендерится, HTMX-поллинг работает, красный цвет при error — всё по логике ОК.
result: issue
reported: "бейдж появился с цифрой 2, но не выравнен по высоте, выглядит неаккуратно"
severity: cosmetic

### 3. Дропдаун последних 10 + авто-mark-read (D-05)
expected: Дропдаун открывается, показывает уведомления, автоматически mark-read, бейдж исчезает.
result: pass
note: "Проверено на 2 уведомлениях (не 10) — поведение корректное"

### 4. Полная страница /notifications
expected: |
  Переход по /notifications открывает полноценную страницу (extends base.html,
  с основным layout-ом проекта), содержит:
    • панель фильтров сверху: выбор сайта, выбор kind, табы по статусу
      прочтения (все / непрочитанные / прочитанные)
    • список уведомлений, сгруппированных по kind (D-08) — заголовок группы
      + её уведомления
    • пагинация по 50 штук на страницу (D-09)
    • кнопка "Отметить все прочитанными" сверху
    • на каждой строке — кнопка удаления (dismiss)
result: pass

### 5. Работа фильтров и пагинации
expected: |
  • Выбор конкретного сайта в фильтре — в списке остаются только уведомления
    этого сайта (site_id match).
  • Выбор kind (например, llm_brief.ready) — остаются только такие.
  • Таб "непрочитанные" — показывает только is_read=false.
  • Если записей > 50, внизу видна пагинация; переход на стр. 2 возвращает
    следующие 50 без ошибок.
  • Сброс фильтров возвращает полный список.
result: pass

### 6. Массовое "Отметить все прочитанными"
expected: |
  Клик по кнопке "Отметить все прочитанными" отправляет POST
  /notifications/mark-all-read, HTMX обновляет только блок #notif-list
  (без перезагрузки страницы). Все уведомления пользователя становятся
  is_read=true в БД. На следующем 30-секундном поллинге бейдж колокольчика
  обнуляется.
result: pass

### 7. Удаление одиночного уведомления (dismiss)
expected: Строка должна исчезать из DOM через HTMX-свап сразу после клика.
result: issue
reported: "строка удалилась только после перезагрузки страницы"
severity: major
root_cause_hypothesis: |
  Эндпойнт POST /notifications/{id}/dismiss возвращает HTTP 204 No Content.
  HTMX по спеке на 204 НЕ делает swap вообще — поэтому в DOM ничего не
  меняется до перезагрузки. Нужно либо вернуть 200 с пустым телом и
  hx-swap="outerHTML" на кнопке/строке (с hx-target указывающим на <tr>/<li>),
  либо добавить на кнопку hx-on::after-request для удаления closest элемента.

### 8. Уведомление об успехе LLM-брифа (llm_brief.ready)
expected: Создание notification kind=llm_brief.ready после успешного LLM-обогащения.
result: blocked
blocked_by: third-party
reason: "У пользователя не настроен ключ Anthropic API — happy-path недоступен"

### 9. Уведомление об ошибке LLM-брифа (llm_brief.failed)
expected: Создание notification kind=llm_brief.failed severity=error при permanent-ошибке Anthropic.
result: blocked
blocked_by: third-party
reason: "Без настроенного ключа задача может упасть до точки вызова notify(); проверять только с заведомо невалидным ключом"

### 10. D-02 Guard: остальные Celery-задачи не падают без user_id
expected: Задачи выполняются штатно, новых notifications не создают.
result: pass
note: "crawl_site запущен через celery call (6405f47c...) — отработал 21s, pages_crawled=12, статус done. Таблица notifications не пополнилась (только test.info/test.error). Guard работает."

### 11. Ночной cleanup старых уведомлений
expected: Задача зарегистрирована в Beat на 03:00 + корректно удаляет записи >30 дней.
result: issue
reported: "Логика задачи корректна (ручной вызов deleted_count=1, свежие записи сохранены), но задача НЕ зарегистрирована в Beat schedule — не запустится автоматически в 03:00"
severity: major
note: "Gap уже задокументирован выше (test 11): beat_schedule={}, в RedBeat Redis нет ключа notifications-cleanup-nightly"

### 12. Smoke-тесты Phase 15.1 покрывают новые роуты
expected: Все smoke-тесты зелёные, 3 notification-роута включены.
result: issue
reported: "2 failed: /notifications/bell и /notifications/dropdown падают с AssertionError 'full page missing <title>'. Это HTMX-фрагменты без <title> — smoke-хелпер должен считать их partials, а он считает full pages. /notifications (полная страница) проходит."
severity: major
root_cause_hypothesis: |
  В tests/_smoke_helpers.py функция, определяющая is_partial, не знает
  о новых роутах bell/dropdown — они попали в UI_PREFIXES как full-page.
  Нужно либо добавить их в список partial-роутов, либо отделить эндпойнт-
  фрагменты от полной страницы.

## Summary

total: 12
passed: 6
issues: 4
pending: 0
skipped: 0
blocked: 2
skipped: 0

## Diagnoses

**Gap 2 (cosmetic — badge alignment):**
- Root cause: badge имеет `position:absolute` относительно full-width кнопки (flex, justify-center), поэтому прилетает в правый верхний угол кнопки (у края сайдбара), далеко от иконки.
- Fix: обернуть SVG в inline `position:relative` контейнер, badge привязать к нему.
- Files: `app/templates/notifications/_bell.html`

**Gap 7 (major — dismiss doesn't swap):**
- Root cause: роутер возвращает HTTP 204 → HTMX по спеке НЕ делает swap при 204. Шаблон уже имеет `hx-target="closest .notif-row"` и `hx-swap="outerHTML"` — но outerHTML требует тело ответа.
- Fix (минимальный): `hx-swap="outerHTML"` → `hx-swap="delete"` в `_list.html:48`. `delete` не требует тела и работает при 204.
- Files: `app/templates/notifications/_list.html:48`

**Gap 11 (major — beat schedule not registered):**
- Root cause: RedBeat scheduler игнорирует статический `celery_app.conf.beat_schedule` — работают только entries, сохранённые через `RedBeatSchedulerEntry.save()`. Другие schedule регистрируются в `beat_init` хуке через `restore_*_from_db()` функции.
- Fix: добавить `register_notifications_cleanup_schedule()` в `notification_tasks.py` (создаёт/обновляет `RedBeatSchedulerEntry` для `crontab(hour=3, minute=0)`), вызвать из `beat_init` хука в `celery_app.py:restore_crawl_schedules`. Удалить dead-config lines 49-54.
- Files: `app/tasks/notification_tasks.py`, `app/celery_app.py:49-54,103-126`
- Pattern: аналогично `app/tasks/report_tasks.py::_register_or_remove_beat`

**Gap 12 (major — smoke tests fail for HTMX fragments):**
- Root cause: `tests/_smoke_helpers.py::is_partial()` (lines 239-260) — hardcoded substring-список маркеров partial-роутов. `/notifications/bell` и `/notifications/dropdown` не матчатся, считаются full pages, падают на `<title>` check.
- Fix: добавить exact-match entries `path == "/notifications/bell"` и `path == "/notifications/dropdown"` в `is_partial()`.
- Files: `tests/_smoke_helpers.py:248-260`

## Gaps

- truth: "Бейдж уведомлений должен быть аккуратно выровнен по центру колокольчика"
  status: failed
  reason: "User reported: бейдж появился с цифрой 2, но не выравнен по высоте, выглядит неаккуратно"
  severity: cosmetic
  test: 2
  artifacts: []
  missing: []

- truth: "При клике на dismiss строка должна исчезать из DOM без перезагрузки"
  status: failed
  reason: "User reported: строка удалилась только после перезагрузки страницы. Эндпойнт возвращает 204 — HTMX на 204 не делает swap."
  severity: major
  test: 7
  artifacts:
    - app/routers/notifications.py:307 (return Response(status_code=204))
    - app/templates/notifications/_list.html (hx-target/hx-swap на кнопке dismiss)
  missing:
    - Либо сменить 204 → 200 с пустым телом + hx-swap="outerHTML" на строку
    - Либо добавить hx-swap="delete" и hx-target="closest [row-selector]"

- truth: "Smoke-тесты должны классифицировать /notifications/bell и /dropdown как HTMX-partials"
  status: failed
  reason: "2 smoke-теста падают на AssertionError 'full page missing <title>' — хелпер считает HTMX-фрагменты полными страницами"
  severity: major
  test: 12
  artifacts:
    - tests/_smoke_helpers.py:234 (is_partial detection + title assertion)
    - app/templates/notifications/_bell.html (фрагмент без <title>)
    - app/templates/notifications/_dropdown.html (фрагмент без <title>)
  missing:
    - Добавить /notifications/bell и /notifications/dropdown в список partial-роутов в _smoke_helpers.py

- truth: "Задача cleanup_old_notifications должна быть зарегистрирована в Celery Beat на 03:00"
  status: failed
  reason: "beat_schedule в runtime пустой ({}), в RedBeat Redis нет ключа notifications-cleanup-nightly — задача не запустится автоматически"
  severity: major
  test: 11
  artifacts:
    - app/celery_app.py:49-54 (статический beat_schedule определён корректно)
    - "redis-cli KEYS 'redbeat*' — только crawl-schedule, report:morning-digest"
  missing:
    - "Регистрация через RedBeatSchedulerEntry(...).save() в beat_init-хуке (как restore_crawl_schedules/restore_report_schedules), т.к. RedBeat не импортирует static beat_schedule автоматически"
