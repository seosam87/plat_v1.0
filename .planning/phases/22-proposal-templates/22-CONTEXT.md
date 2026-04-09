# Phase 22: Proposal Templates - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins can create and manage Jinja2-HTML proposal templates with a fixed set of platform-resolved variables; any user can preview a rendered template against real client and site data and clone templates for new variations.

</domain>

<decisions>
## Implementation Decisions

### Template Editor
- **D-01:** Код-редактор **CodeMirror** с подсветкой HTML/Jinja2 синтаксиса, нумерацией строк, автозакрытием тегов
- **D-02:** Расположение **бок о бок** — CodeMirror слева, превью справа. Кнопка «Предпросмотр» обновляет правую панель
- **D-03:** Создание и редактирование шаблона на **отдельной странице** `/ui/templates/{id}/edit` (не в модалке — нужно место для CodeMirror + превью + панель переменных)

### Template Metadata
- **D-04:** Метаданные шаблона: **name** (название), **template_type** (enum: proposal, audit_report, brief), **description** (текстовое описание). Тип нужен Phase 23 для фильтрации документов
- **D-05:** Тип документа — фиксированный enum, не свободный текст

### Variable System
- **D-06:** **Панель переменных справа** от превью — группированный список всех ~15 переменных с описаниями. Клик копирует `{{ variable }}` в буфер или вставляет в позицию курсора CodeMirror
- **D-07:** Неразрешённые переменные в превью отображаются с **жёлтым фоном** — `<span class="unresolved">{{ var_name }}</span>`. Сразу видно что не подставилось
- **D-08:** Переменные группируются по категориям: Клиент (name, legal_name, inn, email, phone, manager), Сайт (url, domain, top_positions_count, audit_errors_count, last_crawl_date), Аналитика (gsc_connected, metrika_id)

### Template List
- **D-09:** Список шаблонов в виде **сетки карточек** — название, тип (бейдж), описание, дата, кнопки (редактировать, клонировать, удалить)
- **D-10:** Кнопка «Создать шаблон» ведёт на страницу создания

### Access Control
- **D-11:** **Только админы** могут создавать, редактировать, клонировать и удалять шаблоны (require_admin). Все пользователи могут просматривать список и открывать превью

### Clone Workflow
- **D-12:** Клонирование создаёт копию с именем «{original_name} (копия)» и сразу открывает страницу редактирования клона

### Preview
- **D-13:** Над панелью превью — **два дропдауна**: Клиент → Сайт (фильтруется по выбранному клиенту, HTMX зависимый select)
- **D-14:** Превью рендерится **в iframe** — HTMX POST отправляет body + client_id + site_id на сервер, Jinja2 рендерит, HTML возвращается в iframe. Изоляция стилей шаблона от стилей платформы
- **D-15:** Превью рендерится < 5 секунд (требование TPL-03)

### Claude's Discretion
- Конкретная версия CodeMirror (5 vs 6) — выбрать по совместимости с проектом
- Способ загрузки CodeMirror (CDN vs бандл)
- Точная структура JSON для хранения шаблонов
- Пагинация списка шаблонов (если нужна при малом количестве)
- Soft delete vs hard delete для шаблонов

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — TPL-01 through TPL-04 acceptance criteria

### Prior Phase Context
- `.planning/phases/20-client-crm/20-CONTEXT.md` — Client model decisions, sidebar CRM section, modal patterns
- `.planning/phases/21-site-audit-intake/21-CONTEXT.md` — Tabbed form patterns, HTMX section save

### Existing Models
- `app/models/client.py` — Client model (company_name, legal_name, inn, kpp, phone, email, manager_id)
- `app/models/site.py` — Site model (url, domain, seo_plugin, etc.)
- `app/models/oauth_token.py` — GSC connection status
- `app/models/crawl.py` — Last crawl data
- `app/models/site_intake.py` — Intake status (from Phase 21)

### Existing Patterns
- `app/routers/crm.py` — CRM router pattern (admin checks, HTMX responses)
- `app/routers/intake.py` — HTMX form pattern with section saves
- `app/templates/crm/` — Card/table layout patterns
- `app/templates/base.html` — Base template for full-page views

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- CRM sidebar section already has sub-items structure — Templates will be added as a sub-link
- `require_admin` / `require_manager_or_above` decorators exist in auth system
- HTMX dependent select pattern used in CRM (client → sites filtering)
- Card component pattern used in dashboard and other list views

### Established Patterns
- Full-page CRUD: separate pages for create/edit (not modals) when content is complex
- HTMX partial responses with HX-Trigger headers for toast notifications
- UUID primary keys across all models
- Soft delete pattern (is_deleted flag) used in Client model
- Server-side Jinja2 rendering for all templates

### Integration Points
- Sidebar navigation: add «Шаблоны» under CRM section
- `app/main.py`: register new templates_router
- Client/Site models: provide data for template variable resolution
- Phase 23 (Document Generator) will consume templates + rendered output

</code_context>

<specifics>
## Specific Ideas

- Трёхколоночная раскладка на странице редактирования: CodeMirror | Превью (iframe) | Панель переменных
- Типы документов (proposal, audit_report, brief) — фиксированный enum, расширяемый при необходимости
- Переменные разрешаются из БД в момент превью, не хранятся в шаблоне

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-proposal-templates*
*Context gathered: 2026-04-09*
