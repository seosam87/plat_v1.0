# Phase 29: Reports & Tools — Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Мобильные экраны `/m/reports` и `/m/tools` в v4.0 Mobile & Telegram. Пользователь со смартфона генерирует PDF-отчёт клиенту (brief или detailed) и одним тапом отправляет его в Telegram или email. Пользователь запускает любой из 6 SEO-инструментов (commercialization, meta-parser, relevant-url, brief, wordstat-batch, paa), видит progress через HTMX polling, получает in-app уведомление по завершении, и открывает mobile-friendly summary результата с опцией скачать XLSX.

**Delivers:**
- `/m/reports/new` — single-page form (проект select + тип radio-cards + кнопка Создать), inline result block с 3 CTA [Скачать][Telegram][Email]
- `/m/tools` — single-column card list всех 6 инструментов с OAuth-badge для wordstat-batch
- `/m/tools/{slug}/run` — tool entry screen (textarea + опциональный file upload, domain/region поля по необходимости, CTA)
- `/m/tools/{slug}/jobs/{job_id}` — mobile result view (summary card + top-20 rows + "Скачать XLSX" + "Показать все" модал)
- Новый `send_document_sync` НЕ создаётся — Telegram delivery идёт через link-based approach (token download endpoint + `send_message_sync(text_with_link)`)
- Новый endpoint `GET /reports/download/{token}` — token-protected, expires in ~7 дней (настраивается конфигом)
- HTMX polling `every 3s` + дублирующий `notify()` in-app при завершении tool-job (double-safety)

**Out of scope (block if suggested):**
- Scheduled reports / регулярная отправка → Phase 36+ (recurring jobs)
- Кастомные шаблоны отчётов → отдельная фаза
- Batch-отправка одного отчёта нескольким клиентам → defer
- PDF preview на мобильном → defer (download сразу)
- Расширение TOOL_REGISTRY (добавление новых tools) → отдельная фаза
- SeoAgent / AI-помощник внутри tool → Phase 33 claude-code-agent-spike
- Третий тип отчёта (client_instructions.html) — остаётся только для desktop в MVP
- Mobile OAuth flow для wordstat-batch — desktop OAuth handshake используется как есть
- Site→project auto-resolution magic — проект выбирается явно
- История отправок (`ReportDelivery` model) — defer, сейчас fire-and-forget

</domain>

<decisions>
## Implementation Decisions

### Gray Area 1 — Scope отчёта
- **D-01:** Wizard шаг 1 = **Проект** (1:1 с desktop). `generate_pdf_report(project_id, report_type)` используется без изменений. Проект select подтягивается из `project_service.list_projects_for_user`.
- **D-02:** **2 типа** отчётов в мобильном wizard'е — `brief` (1-2 стр.) и `detailed` (5-10 стр.). `client_instructions.html` остаётся только на desktop в MVP (не покрыто REP-01/02).

### Gray Area 2 — Wizard UX
- **D-03:** **Single-page form** — одна страница `/m/reports/new` с проект-селектом + radio-cards типа + кнопкой "Создать". Кнопка disabled пока не выбраны оба поля. НЕТ multi-step wizard, НЕТ HTMX swap между шагами. Весь submit через обычный form POST (или HTMX inline если нужна плавность).

### Gray Area 3 — Delivery (REP-02)
- **D-04:** После POST "Создать" пользователь остаётся на том же экране. Result-блок появляется inline под формой: `[Скачать PDF] [Отправить в Telegram] [Отправить email]`. Reveal через HTMX swap либо server-side render при наличии `?report_id=...` в URL — planner решает.
- **D-05:** Recipient source — flat `<select>` из Client CRM с фильтром `email IS NOT NULL OR telegram_username IS NOT NULL`. НЕТ ручного ввода, НЕТ привязки через проект. Простая логика: все клиенты с контактами.
- **D-06:** **Telegram delivery = link-based**.
  - Новый endpoint `GET /reports/download/{token}` (token-protected, expires 7 дней, токен хранится в Redis с TTL)
  - `telegram_service.send_message_sync` используется как есть — отправляет текст + ссылку
  - `send_document_sync` **НЕ создаётся** — не требуется в MVP
  - Email delivery = `send_email_with_attachment_sync` (PDF attachment уже поддерживается)
- **D-07:** Feedback = `showToast()` pattern из Phase 28.
  - success: `showToast("Отчёт отправлен")`
  - error: `showToast("Ошибка: клиент не привязан к Telegram", level='error')`

### Gray Area 4 — Tools list layout
- **D-08:** `/m/tools` = **single-column card list** (consistency с Phase 28 card pattern, не 2-col grid как `/m/index.html`). Весь card tappable, переход на `/m/tools/{slug}/run`.
- **D-09:** Каждая карточка показывает: `name` (крупно), `description` (мелко), `limit` (справа мелким), `badge` **«Требует Wordstat»** только для tool с `needs_oauth: "wordstat"` (wordstat-batch).
- **D-10:** OAuth handling — карточка **tappable даже без токена**. При тапе: backend проверяет OAuth → если нет → 302 redirect на `/ui/integrations/wordstat/auth?return_to=/m/tools/wordstat-batch/run` (desktop OAuth flow с return URL). Пользователь проходит OAuth handshake на desktop и возвращается на mobile.

### Gray Area 5 — Tool run UX (TLS-01 + TLS-02)
- **D-11:** Input — **textarea + опциональный file upload (TXT/XLSX)**. Оба доступны одновременно. Desktop limits сохраняются (не снижаются для мобильного). Textarea для ручного ввода 5-20 фраз, file upload для батч-запусков. Если оба заполнены — server отдаёт ошибку "Используйте одно из двух".
- **D-12:** Progress = **HTMX polling `every 3s` + дублирующий in-app notification**. Точная копия D-04 pattern из Phase 28: toast "Запущено", progress-блок "Проверено X из Y", кнопка "Показать результаты" при завершении. Плюс `notify()` вызывается в Celery task при `status=done` — safety net если пользователь закрыл экран.
- **D-13:** Result view = **summary top card + первые 20 строк компактной таблицы + "Скачать XLSX" CTA + "Показать все" (HTMX модал с pagination)**. Top-20 даёт quick glance, XLSX для полных данных, "Показать все" — опциональная глубина.
- **D-14:** Notification `link_url` = `/m/tools/{slug}/jobs/{job_id}` (новый mobile result endpoint). Mobile result view — отдельный template, не переиспользует desktop result.

### Claude's Discretion
- Service layer — новый `mobile_reports_service.py` и `mobile_tools_service.py`, либо расширить существующие `report_service.py` / `tools router`. Planner решает.
- Token generation для download — `secrets.token_urlsafe(32)` + Redis `SETEX reports:dl:{token} 604800 {report_id}`. Если Redis недоступен для токенов — fallback в БД table `report_download_tokens`. Planner решает.
- Форма single-page — full form POST или HTMX boost. Planner решает.
- Pagination / "Показать все" результатов — HTMX модал с load-more или обычная pagination. Planner решает.
- HTMX polling endpoint для tools — переиспользовать существующий endpoint из Phase 24 или создать mobile-specific. Planner решает.
- File upload парсинг (TXT vs XLSX) — использовать `openpyxl` для XLSX, `.splitlines()` для TXT. Стандартно.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Reports System (existing — переиспользуется)
- `app/services/report_service.py` — `generate_pdf_report(project_id, report_type='brief'|'detailed')` возвращает PDF bytes через WeasyPrint; `generate_excel_report` для XLSX. Всё переиспользуется.
- `app/templates/reports/brief.html` — 1-2 стр. template (позиции + задачи + top movers)
- `app/templates/reports/detailed.html` — 5-10 стр. template (полная таблица keywords + задачи + изменения сайта)
- `app/routers/reports.py` — desktop endpoints `/reports/projects/{project_id}/pdf?type=...`, `/reports/projects/{project_id}/excel`

### Delivery System (existing)
- `app/services/smtp_service.py` — `send_email_sync(to, subject, body_html)`, `send_email_with_attachment_sync(to, subject, body_html, attachment_bytes, attachment_filename)` — используется для email-delivery REP-02
- `app/services/telegram_service.py` — `send_message_sync(text)` уже работает, используется для link-based Telegram delivery
- `app/models/client.py` — `Client` с полями `email`, `telegram_username` — источник recipient select'а (D-05)
- `app/services/client_service.py` — `list_clients(db, with_contacts=True)` — helper для filter `email NOT NULL OR telegram_username NOT NULL` (planner создаст если ещё нет)

### Tools System (existing — переиспользуется)
- `app/routers/tools.py` — `TOOL_REGISTRY` dict с metadata для 6 инструментов (name, description, input_type, limit, cta, has_domain_field, needs_oauth)
- `app/services/notifications.py` — `notify(db, user_id, title, body, link_url)` — in-app уведомления (D-12)
- `app/models/notification.py` — `Notification` model
- Celery tasks: `app/tasks/commerce_check_tasks.py`, `meta_parse_tasks.py`, `relevant_url_tasks.py`, `brief_tasks.py` (4-step chain), `wordstat_batch_tasks.py`, `paa_tasks.py` — все с `Job.status` полем
- `app/models/commerce_check_job.py`, `meta_parse_job.py`, `relevant_url_job.py`, `brief_job.py`, `wordstat_batch_job.py`, `paa_job.py` — ORM models для jobs и results

### Mobile Foundation (existing — обязательное reuse)
- `app/templates/base_mobile.html` — mobile base template с bottom nav, HTMX 2.0.3, `showToast()` JS. НЕ использует `template_engine.templates` (no sidebar injection).
- `app/routers/mobile.py` — mobile router `/m/`, использует `mobile_templates = Jinja2Templates(directory="app/templates")` (plain, без nav injection). Новые endpoints /m/reports/* и /m/tools/* добавляются сюда либо в новый `app/routers/mobile_reports_tools.py` (planner решает).
- `app/templates/mobile/partials/task_form.html` — пример inline HTMX form partial из Phase 27 (reference pattern для /m/reports/new)
- `app/templates/mobile/partials/position_progress.html` — пример progress-polling partial из Phase 28 (reference pattern для tool run progress)
- `app/templates/mobile/positions.html`, `traffic.html`, `digest.html`, `health.html` — существующие mobile page patterns для card/list layouts

### Auth / Session (existing)
- `app/auth/dependencies.py` — `get_current_user`, `require_any_authenticated` — mobile endpoints используют `get_current_user`
- `app/main.py::UIAuthMiddleware` — automatically redirects `/m/*` unauthenticated → login. Новые `/m/reports`, `/m/tools` автоматически защищены.
- `app/auth/telegram_auth.py` — Telegram WebApp auth, уже работает

### OAuth Integration (existing)
- `app/routers/integrations.py` (или похожий) — `/ui/integrations/wordstat/auth` — desktop OAuth handshake для Wordstat. Принимает `return_to` query param. Используется D-10 для mobile fallback.
- `app/services/wordstat_service.py` (или похожий) — OAuth token storage, refresh logic

### Redis (existing)
- `app/dependencies.py` — Redis client уже инжектируется в endpoints. Используется для token storage D-06.
- Pattern: `await redis.setex(f"reports:dl:{token}", 604800, str(report_id))` (7 дней TTL)

</canonical_refs>

<reviewed_todos>
## Reviewed but NOT folded

Проверены через `todo match-phase 29` — оба матча слабые (score 0.6, только ключевое слово "app"), не по смыслу фазы. Отмечены чтобы не всплывали повторно в последующих фазах.

- **2026-04-02-fix-position-check-ignores-keyword-engine-preference.md** — Phase 28 territory, не Phase 29
- **2026-04-02-proxy-management-xmlproxy-integration-and-health-checker.md** — Phase 06.1 territory, отдельная backlog

</reviewed_todos>

<deferred_ideas>
## Deferred for future phases

- **Scheduled reports / regular delivery** — Phase 36+ (recurring jobs infrastructure)
- **Custom report templates** — отдельная фаза когда появится запрос
- **Batch multi-client send** — defer
- **Client instructions type в mobile wizard** — defer, в MVP только desktop
- **ReportDelivery модель (история отправок)** — defer, сейчас fire-and-forget
- **Mobile OAuth flow** — defer, desktop OAuth handshake достаточно
- **Mobile PDF preview** — defer, download сразу
- **Новые tools в TOOL_REGISTRY** — отдельные фазы
- **Telegram send_document_sync (binary attachment)** — defer пока link-based работает

</deferred_ideas>

<success_criteria_mapping>
## Success Criteria → Decisions

| ROADMAP success criterion | Realized via |
|---|---|
| `/m/reports` формирует PDF за 3 шага (сайт → тип → создать) | D-01 (проект-select вместо сайта — эквивалент), D-02 (2 типа), D-03 (single-page form) — wizard ощущается как "3 шага" даже на одной странице |
| Отправка отчёта клиенту в Telegram или email одной кнопкой | D-04 (inline result-block), D-05 (flat CRM select), D-06 (link-based Telegram, attachment email), D-07 (showToast feedback) |
| `/m/tools` показывает все 6 инструментов в мобильном формате | D-08 (single-column cards), D-09 (name+description+limit+badge), D-10 (OAuth via desktop redirect) |
| After tool completion: in-app notification + mobile result view | D-12 (polling + notify double-safety), D-13 (summary + top-20 + XLSX), D-14 (link_url → /m/tools/{slug}/jobs/{job_id}) |

</success_criteria_mapping>
