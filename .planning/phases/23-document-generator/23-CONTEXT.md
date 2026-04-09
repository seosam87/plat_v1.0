# Phase 23: Document Generator - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can generate a PDF document from any proposal template (Phase 22) combined with client and site data, view generated documents per client, download them, regenerate (new version), and send via Telegram or SMTP.

</domain>

<decisions>
## Implementation Decisions

### PDF Generation & Storage
- **D-01:** PDF хранится в PostgreSQL (bytea), максимум **3 версии** на документ. При перегенерации старейшая версия удаляется если лимит превышен
- **D-02:** Генерация через **Celery task** с использованием существующего `subprocess_pdf.py` (subprocess-isolated WeasyPrint, Phase 14 D-12)
- **D-03:** Статус генерации показывается через **HTMX polling** (2-3 сек) — устоявшийся паттерн из позиций и краулера
- **D-04:** Кнопка **"Перегенерировать"** на документе — создаёт новую версию из того же шаблона + актуальных данных

### UI Documents
- **D-05:** Точка входа — страница документов клиента `/ui/crm/clients/{id}/documents`. Кнопка "Создать документ" с формой выбора шаблона + сайта
- **D-06:** Список документов — **таблица**: название, тип (бейдж), сайт, дата, статус, действия (скачать/отправить/перегенерировать). Фильтры: тип + дата
- **D-07:** Документы привязаны к клиенту — **таб "Документы"** в карточке клиента (рядом с Сайты, Контакты, История)

### Sending (Telegram/SMTP)
- **D-08:** Кнопка "Отправить" на строке документа → **дропдаун** с выбором канала: Telegram / Email. Адрес берётся из CRM (email/телефон клиента)
- **D-09:** Перед отправкой — **confirm-диалог**: "Отправить КП на info@client.com через Email?" — OK/Отмена
- **D-10:** Отправка через существующие `telegram_service.send_message_sync()` и `smtp_service.send_email_sync()` в Celery task

### Access Control
- **D-11:** Генерация и отправка — **require_manager_or_above** (как в CRM). Клиент-роль не видит генератор

### Claude's Discretion
- Модель GeneratedDocument: конкретные поля, индексы, FK
- Именование PDF файла при скачивании
- Формат статусов Celery task (pending/processing/ready/failed)
- Пагинация списка документов (если нужна)
- Порядок отображения документов (по дате desc по умолчанию)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — DOC-01 through DOC-05 acceptance criteria
- `.planning/REQUIREMENTS.md` — DOC-06/07/08 explicitly deferred to future

### Prior Phase Artifacts
- `.planning/phases/22-proposal-templates/22-CONTEXT.md` — template editor decisions, variable system
- `.planning/phases/22-proposal-templates/22-01-SUMMARY.md` — ProposalTemplate model, template_service, variable_resolver

### Existing Code Patterns
- `app/services/subprocess_pdf.py` — WeasyPrint subprocess isolation (reuse directly)
- `app/services/client_report_service.py` — HTML→PDF generation pattern (Phase 14)
- `app/tasks/client_report_tasks.py` — Celery task for PDF generation
- `app/tasks/report_tasks.py` — Telegram + SMTP sending pattern in Celery
- `app/services/telegram_service.py` — Telegram bot message sending
- `app/services/smtp_service.py` — SMTP email with attachments

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `subprocess_pdf.render_pdf_in_subprocess()` — subprocess-isolated WeasyPrint, solves OOM leak
- `template_variable_resolver.resolve_template_variables()` — resolves ~15 vars from DB
- `template_variable_resolver.render_template_preview()` — Jinja2 SandboxedEnvironment render
- `telegram_service.send_message_sync()` + `is_configured()` — Telegram push
- `smtp_service.send_email_sync()` — SMTP with attachment support
- `template_service.get_template()` — fetch ProposalTemplate by ID

### Established Patterns
- Celery tasks: `@celery_app.task(bind=True, max_retries=3)`, `task_acks_late=True`
- HTMX polling: `hx-trigger="every 3s"` for status updates (crawl jobs, position checks)
- Client detail tabs: existing tab structure in `/ui/crm/clients/{id}` (Сайты, Контакты, История)
- Type badges: violet/blue/green for proposal/audit_report/brief (Phase 22 pattern)
- Confirm dialogs: `if (!confirm(...)) return;` pattern used in delete operations

### Integration Points
- Client detail page: add "Документы" tab to existing tab navigation
- ProposalTemplate model: FK from GeneratedDocument to template
- Client model: FK from GeneratedDocument to client
- Site model: FK from GeneratedDocument to site
- Sidebar: no new sidebar entry needed (documents live inside client detail)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following established codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

- **DOC-06:** Variable overrides at generation time (v3.x)
- **DOC-07:** Auto-generate proposal after intake completion (v3.x)
- **DOC-08:** Document audit trail via audit_log (v3.x)
- Общий список всех документов /ui/documents (отдельная страница + сайдбар) — если нужен, добавить как Phase 23.1

</deferred>

---

*Phase: 23-document-generator*
*Context gathered: 2026-04-09*
