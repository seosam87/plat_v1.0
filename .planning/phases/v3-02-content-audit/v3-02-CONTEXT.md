# Phase 2: Content Audit Engine - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Per-site Content Audit UI: browse WP pages with filters, run type-aware checklists (info vs commercial), detect missing elements (TOC, author, related posts, CTA, schema), propose fixes through the existing pipeline with user approval, and track audit history. Schema templates are user-customizable with system defaults.

</domain>

<decisions>
## Implementation Decisions

### Page Classification
- **D-01:** Добавить поле `content_type` на модель Page: `informational` / `commercial` / `unknown`. Автоматическая классификация по правилам (URL-паттерны, page_type маппинг) + ручная правка в UI аудита.

### Checklist
- **D-02:** Настраиваемый чеклист в БД. Пользователь может добавлять/убирать/редактировать проверки через UI. Система поставляется с набором стандартных проверок, которые можно изменить.

### CTA Block
- **D-03:** Один CTA-шаблон HTML на сайт. Хранится в настройках сайта (новое поле на модели Site). Вставляется всегда в конец контента. HTML генерируется пользователем вне системы.

### Schema Templates
- **D-04:** Пользователь выбирает тип schema и редактирует шаблон. Система предоставляет стандартные шаблоны (Article, Service, Product, LocalBusiness, FAQ), которые можно доработать и сохранить как свои. Система подставляет данные страницы в шаблон.

### Detection Method
- **D-05:** Проверка блока автора и related posts — через парсинг HTML отрендеренной страницы (данные краула / WP REST API rendered content). Не через metadata WP.

### Fix Workflow
- **D-06:** При провале проверки — ставится статус (fail/warning). Для TOC: система генерирует вариант, пользователь может выбрать "Добавить TOC" → pipeline добавляет → проверка что страница не сломалась → сохраняется запись о добавлении. Аналогично для других авто-фиксируемых проверок. Ручные проблемы — только статус и рекомендация.

### UI Structure
- **D-07:** Аудит на уровне сайта. Кнопка "Аудит" на странице сайта → список WP-страниц этого сайта с фильтрами и результатами проверок. Без глобального обзора всех сайтов.

### Claude's Discretion
- Audit check result storage model design
- Default check rules and their parameters
- HTML parsing selectors for author/related posts detection
- Schema template field mapping logic
- Pagination and sorting defaults for audit page list

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Content pipeline (existing)
- `app/services/content_pipeline.py` — TOC injection, schema Article generation, internal links, diff computation
- `app/tasks/wp_content_tasks.py` — Pipeline orchestrator (run_content_pipeline), push_to_wp, rollback_job
- `app/routers/wp_pipeline.py` — 10 pipeline endpoints (run, approve, reject, rollback, batch, bulk)
- `app/models/wp_content_job.py` — WpContentJob model with status flow (pending→processing→awaiting_approval→approved→pushed)

### WP integration (existing)
- `app/services/wp_service.py` — get_posts_sync, get_pages_sync, verify_connection, detect_seo_plugin
- `app/models/site.py` — Site model (needs cta_template_html field added)

### Crawl data (existing)
- `app/models/crawl.py` — Page model with has_toc, has_schema, has_noindex, page_type enum (category/article/landing/product/unknown)

### UI patterns
- `app/templates/pipeline/jobs.html` — Existing pipeline UI (diff modal, approve/reject)
- `app/templates/sites/detail.html` — Site detail page (widget integration point for audit button)

### Roadmap
- `.planning/ROADMAP-v3.md` §Phase 2 — phase scope

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `content_pipeline.py` — extract_headings(), generate_toc_html(), inject_toc(), add_heading_ids(), generate_schema_article(), has_schema_ld(), inject_schema(), find_link_opportunities(), insert_links(), compute_content_diff()
- `wp_content_tasks.py` — full pipeline chain with job status management
- `wp_pipeline.py` — batch endpoint already triggers pipeline for pages missing TOC/schema
- `wp_service.py` — WP REST API client with auth
- `crawl.py` Page model — has_toc, has_schema, has_noindex, page_type already tracked per page

### Established Patterns
- Pipeline job flow: create job → process → diff → await approval → push/rollback
- WP content fetch: GET /wp-json/wp/v2/posts/{id} → content.rendered
- WP content push: POST /wp-json/wp/v2/posts/{id} with {content: html}
- Celery tasks on `wp` queue with retry=3, soft_time_limit=120
- HTMX partial updates for list/table UI

### Integration Points
- Site model — add `cta_template_html` (Text) field
- Page model — add `content_type` enum field
- Site detail page — add "Аудит" button/link
- Navigation — audit is per-site, no global nav entry needed
- Alembic — new migration for added fields + audit tables

### Key Gaps to Fill
- No audit results/findings storage model
- No configurable check definitions in DB
- Schema generation only supports Article — need Service, Product, LocalBusiness, FAQ templates
- No CTA detection or injection logic
- No author block or related posts detection
- No content_type classification on Page model

</code_context>

<specifics>
## Specific Ideas

- **Schema template engine:** System ships default JSON-LD templates for Article, Service, Product, LocalBusiness, FAQ. User can customize and save per-site. Template uses placeholders like `{{title}}`, `{{url}}`, `{{description}}` that the system fills from page data.
- **TOC fix flow:** User sees "No TOC" status → clicks "Add TOC" → system generates TOC from headings → shows preview/diff → user approves → push to WP → audit record updated to "TOC added, date".
- **Author/related detection:** Parse rendered HTML for common patterns: `.author-box`, `.post-author`, `rel="author"`; `.related-posts`, `.yarpp-related`, `.jp-relatedposts`.

</specifics>

<deferred>
## Deferred Ideas

- Global cross-site audit overview (only per-site for now per D-07)
- Automatic content_type classification via ML/NLP (start with rules + manual)
- Audit scheduling (periodic re-audit) — manual trigger only for now

</deferred>

---

*Phase: v3-02-content-audit*
*Context gathered: 2026-04-02*
