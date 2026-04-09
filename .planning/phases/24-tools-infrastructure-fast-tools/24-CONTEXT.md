# Phase 24: Tools Infrastructure & Fast Tools - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Создать раздел "Инструменты" в платформе с общей Job-инфраструктурой и тремя инструментами: Проверка коммерциализации (XMLProxy), Парсер мета-тегов (httpx), Поиск релевантного URL (XMLProxy). Каждый инструмент — отдельная модель Job+Result, Celery-задача, UI (форма ввода + страница результатов), CSV/XLSX экспорт.

</domain>

<decisions>
## Implementation Decisions

### Job UX-паттерн
- **D-01:** Двухстраничный поток: страница 1 — форма ввода + список предыдущих jobs; страница 2 — результаты конкретного job
- **D-02:** URL-схема: `/ui/tools/{slug}/` (список + форма), `/ui/tools/{slug}/{job_id}` (результаты)
- **D-03:** HTMX polling с интервалом 10 секунд при ожидании результата
- **D-04:** Прогресс — простой текстовый статус: "Обработка... 45/200 фраз" + spinner. Без progress bar.

### Результаты и экспорт
- **D-05:** Экспорт в оба формата: CSV + XLSX (openpyxl уже в стеке)
- **D-06:** Хранение jobs без лимита. Ручное удаление через UI. При <20 пользователях объём данных минимальный.

### Навигация и структура
- **D-07:** Один пункт "Инструменты" в сайдбаре → /ui/tools/ (index). Без подпунктов для каждого инструмента.
- **D-08:** Slug-именование: `commercialization`, `meta-parser`, `relevant-url`

### XMLProxy и лимиты
- **D-09:** При исчерпании баланса XMLProxy — partial результат (как SuggestJob). Сохранить уже полученные данные, пометить job как partial.
- **D-10:** Лимиты ввода по ROADMAP: Коммерциализация 200 фраз, Мета-парсер 500 URL, Релевантный URL 100 фраз.
- **D-11:** Rate limiting: 10 запросов/минуту на пользователя (slowapi уже в стеке)

### Claude's Discretion
- Конкретная структура моделей Job+Result (по образцу SuggestJob)
- Распределение по Celery workers (main worker vs crawler)
- Формат таблицы результатов для каждого инструмента
- Конкретный текст UI на русском

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Эталонные паттерны
- `app/models/suggest_job.py` — Эталонная Job-модель с status lifecycle (pending→running→complete|partial|failed)
- `app/tasks/suggest_tasks.py` — Celery-задача с retry и partial-результатом
- `app/services/xmlproxy_service.py` — XMLProxy клиент (используется для Коммерциализации и Релевантного URL)
- `app/routers/keyword_suggest.py` — Пример HTMX polling + job-роутера

### Существующая инфраструктура
- `app/routers/tools.py` — Stub-роутер Phase 19 (заменить на реальный)
- `app/templates/tools/index.html` — Stub-шаблон Phase 19 (заменить на реальный index)
- `app/celery_app.py` — Конфигурация Celery
- `app/tasks/` — Каталог Celery-задач

### Требования
- `.planning/REQUIREMENTS.md` §TOOL-INFRA-01, §TOOL-INFRA-02, §COM-01, §META-01, §REL-01

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SuggestJob` модель — шаблон для всех 3 Tool Job моделей (status lifecycle, user_id FK, timestamps)
- `xmlproxy_service.py` — готовый клиент для Yandex SERP (Коммерциализация + Релевантный URL)
- `openpyxl` — уже в зависимостях для XLSX экспорта
- `empty_state` макрос — Phase 19, уже в tools/index.html
- `slowapi` — rate limiter уже интегрирован в middleware

### Established Patterns
- Job lifecycle: `pending → running → complete | partial | failed`
- Celery tasks: `@shared_task(bind=True, max_retries=3)` с `task_acks_late=True`
- HTMX polling: `hx-trigger="every Ns"` → partial HTML response → `hx-swap`
- Двухстраничный UX: список + форма → detail (как Crawls: `/ui/sites/{id}/crawls` → `/ui/crawls/{crawl_id}`)

### Integration Points
- `app/main.py` — tools router уже зарегистрирован
- `app/templates/base.html` — сайдбар (добавить пункт "Инструменты")
- `tests/_smoke_helpers.py` — новые роуты нужно добавить в PARAM_MAP (tool_slug, tool_job_id)
- `alembic/` — миграции для 3 пар таблиц (Job + Result)

</code_context>

<specifics>
## Specific Ideas

Нет специальных требований — стандартные подходы на основе существующих паттернов.

</specifics>

<deferred>
## Deferred Ideas

None — обсуждение осталось в рамках фазы.

</deferred>

---

*Phase: 24-tools-infrastructure-fast-tools*
*Context gathered: 2026-04-10*
