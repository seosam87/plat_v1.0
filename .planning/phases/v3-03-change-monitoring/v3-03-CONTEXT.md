# Phase 3: Change Monitoring - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the crawl pipeline to detect SEO-critical changes between crawls, send Telegram alerts by severity, and generate a weekly digest per site on a configurable Beat schedule. Global alert rules (same for all sites), Telegram-only notifications.

</domain>

<decisions>
## Implementation Decisions

### Notifications
- **D-01:** Один глобальный Telegram-чат для всех алертов. Один `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (уже настроен).
- **D-02:** Только Telegram в этой фазе. Email откладывается.

### Rules
- **D-03:** Глобальные правила (одинаковые для всех сайтов). Таблица `change_alert_rules` с типом изменения, severity, вкл/выкл. Без per-site настройки.
- **D-04:** Дефолтные правила:
  - **error** (алерт сразу): 404 появился, noindex добавлен, schema удалена
  - **warning** (в дайджест): title изменён, H1 изменён, canonical изменён, meta description изменено
  - **info** (только в feed): content changed, new page
- **D-05:** Архитектура должна поддерживать расширение (много типов изменений в будущем), но сейчас реализуем только предложенные дефолтные правила.

### Digest
- **D-06:** Еженедельный дайджест через Celery Beat + кнопка в UI. Beat-расписание per-site: дата и время настраиваются в настройках сайта.
- **D-07:** Дайджест собирает все изменения за неделю по одному сайту, форматирует в одно Telegram-сообщение.

### Claude's Discretion
- Change detector function signatures and granularity
- Telegram message formatting (emoji, structure)
- Digest schedule model design (extend existing ScheduleType or new model)
- How to hook into existing crawl pipeline (extend create_auto_tasks or separate function)

</decisions>

<canonical_refs>
## Canonical References

### Crawl diff infrastructure (existing)
- `app/services/diff_service.py` — `compute_diff()`, `build_snapshot()`, SNAPSHOT_FIELDS
- `app/models/crawl.py` — Page (has_toc, has_schema, has_noindex, canonical_url), PageSnapshot (diff_data)
- `app/tasks/crawl_tasks.py:185-187` — calls `create_auto_tasks()` after crawl
- `app/services/task_service.py` — `create_auto_tasks()` (404, noindex flip detection)

### Telegram (existing)
- `app/services/telegram_service.py` — `send_message_sync()`, `format_position_drop_alert()`, `is_configured()`
- `app/config.py:50-53` — TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

### Change feed UI (existing)
- `app/templates/crawl/feed.html` — feed with filters (seo_changed, content_changed, new_pages, status_changed)

### Scheduling (existing)
- `app/models/schedule.py` — CrawlSchedule, PositionSchedule (pattern for new DigestSchedule)
- `app/services/schedule_service.py` — redbeat integration for crawl/position schedules

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `diff_service.compute_diff()` — already computes field-level diffs
- `telegram_service.send_message_sync()` — ready to use from Celery tasks
- `task_service.create_auto_tasks()` — hook point after crawl completion
- `CrawlSchedule` / `PositionSchedule` models — pattern for DigestSchedule
- `schedule_service.py` — redbeat upsert/restore patterns

### What Needs Extension
- `diff_service.py` — add canonical_url, has_schema, has_toc to SNAPSHOT_FIELDS
- `task_service.py` — add new detectors (canonical changed, schema removed)
- `telegram_service.py` — add formatters for change alerts and digest
- `crawl_tasks.py` — hook change alert dispatch after create_auto_tasks()

### New Components
- `change_alert_rules` table + model — global rules with severity
- `change_alerts` table + model — alert history (what was sent, when)
- `DigestSchedule` model — per-site Beat schedule for weekly digest
- `change_monitoring_service.py` — detect changes, match rules, dispatch alerts
- `digest_tasks.py` — Celery Beat task for weekly digest
- UI: alert rules management, digest schedule per site

</code_context>

<deferred>
## Deferred Ideas

- Per-site notification rules (global only for now per D-03)
- Email notifications (Telegram only per D-02)
- Per-site Telegram chat IDs
- In-app notification center
- Alert history UI with read/unread status

</deferred>

---

*Phase: v3-03-change-monitoring*
*Context gathered: 2026-04-02*
