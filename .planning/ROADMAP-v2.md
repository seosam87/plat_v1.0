# Roadmap v2.0: Module Deep-Dive — SEO Management Platform

## Концепция

Каждая фаза = один модуль системы. В каждой фазе три ключевые точки:

1. **СПРАВКА** — описание возможностей блока (что умеет, интерфейсы, ограничения). **Встраивается в UI модуля** — иконка `?` в заголовке каждой страницы открывает справку в модальном окне. Справки хранятся как markdown-файлы в `app/templates/help/` и рендерятся через общий компонент, чтобы их можно было перечитывать из интерфейса в любой момент.
2. **РАСШИРЕНИЕ** — сравнение с реальными сервисами (Ahrefs, Serpstat, TopVisor, Screaming Frog), gap-анализ, доработки по примерам пользователя
3. **ПРАКТИКА** — реальный пример работы модуля на сайте `poly-msk.ru` (парсинг, занесение данных, результат)

## Инфраструктура справок

Перед началом Phase 1 создаём:
- `app/templates/help/_modal.html` — переиспользуемый компонент модального окна справки (включается через `{% include %}`)
- `app/templates/help/*.md` — markdown-файлы справок по модулям (sites.md, keywords.md, positions.md, ...)
- `/ui/help/{module}` — API-эндпоинт, отдающий отрендеренный markdown в HTML
- В `base.html` — JS для открытия/закрытия модала по клику на `?`
- Каждая страница модуля включает `{% include "help/_modal.html" %}` с параметром `help_module`

Справки пишутся на **русском**, в формате: что это → что можно делать → как использовать → ограничения.

## Фазы

- [ ] **Phase 1: Site Management** — Регистрация сайтов, WP-подключение, группы, статус
- [ ] **Phase 2: Keyword Management** — Ключевые слова, группы, импорт, bulk-операции
- [ ] **Phase 3: Position Tracking** — Отслеживание позиций, дельты, графики, расписания
- [ ] **Phase 4: Crawling & Technical Audit** — Краулинг, SEO-сигналы, снапшоты, дифф
- [ ] **Phase 5: Clusters & Semantics** — Кластеризация, каннибализация, SERP-пересечения
- [ ] **Phase 6: Content Pipeline & WP** — TOC, schema.org, внутренние ссылки, approve/rollback
- [ ] **Phase 7: Data Sources** — DataForSEO, GSC, Yandex Webmaster, SERP-парсер
- [ ] **Phase 8: Projects & Tasks** — Проекты, Kanban, контент-план, брифы
- [ ] **Phase 9: Reports & Analytics** — Дашборд, Excel, ad-трафик, сравнение периодов
- [ ] **Phase 10: Admin & Access Control** — Пользователи, роли, группы, инвайты, аудит
- [ ] **Phase 11: Competitors** — Конкуренты сайта, сравнение позиций, SERP-пересечения, visibility

## Phase Details

### Phase 1: Site Management
**Модуль:** `sites` — routers/sites.py, services/site_service.py, models/site.py, templates/sites/

**Точка 1 — СПРАВКА:**
Описание всех интерфейсов модуля: CRUD сайтов, WP-верификация, группы, enable/disable, connection status. Документация текущих возможностей.

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: как в Serpstat/Ahrefs добавляются проекты (домен + регион + поисковик)
- Что добавить: привязка регионов (Москва/СПб), целевой поисковик (google.ru / yandex.ru), SEO-плагин (Yoast/RankMath) — автоопределение
- Health score сайта (агрегат из crawl + positions)
- Мультиязычность (hreflang)

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Добавить poly-msk.ru как сайт через UI
- Верифицировать WP-подключение
- Показать реальный ответ WP REST API `/wp-json/wp/v2/users/me`
- Определить SEO-плагин через `/wp-json/wp/v2/posts?per_page=1` (поля yoast_head / rank_math)

---

### Phase 2: Keyword Management
**Модуль:** `keywords` — routers/keywords.py, services/keyword_service.py, parsers/*, models/keyword.py, templates/keywords/

**Точка 1 — СПРАВКА:**
Все интерфейсы: add/delete/list, bulk import, groups, count, parsers (Topvisor/KC/SF).

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: TopVisor позволяет импортировать из буфера/файла с частотностью + регионом
- Что добавить: дедупликация при импорте, merge-стратегии (skip/update/replace)
- Intent-классификация (коммерческий / информационный / навигационный)
- Keyword difficulty score (из DataForSEO)
- Inline edit target_url и группы

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Импорт ключевых слов из реального файла TopVisor для poly-msk.ru
- Ручное добавление 5-10 ключей: «полимерные полы москва», «наливные полы цена», «эпоксидный пол купить»
- Показать группировку и подсчёт

---

### Phase 3: Position Tracking
**Модуль:** `positions` — routers/positions.py, services/position_service.py, tasks/position_tasks.py, models/position.py, templates/positions/

**Точка 1 — СПРАВКА:**
Запись позиций, дельты, партиционирование, history для Chart.js, расписания, multi-source (DataForSEO/GSC/Yandex/Playwright).

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: TopVisor показывает TOP-3/10/30 распределение, средние позиции, visibility score
- Что добавить: visibility index, distribution chart (TOP-3/10/30/100), trend aggregates
- Lost/gained keywords detection
- Position alerts с настраиваемым порогом
- Сравнение позиций между двумя датами
- Фильтр по URL (какие ключи ранжируются на конкретной странице)

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Проверить позиции для 5 ключевых слов poly-msk.ru через DataForSEO
- Показать результат: keyword → position → URL → delta
- Построить график истории для одного ключа
- Настроить расписание ежедневной проверки

---

### Phase 4: Crawling & Technical Audit
**Модуль:** `crawl` — routers/crawl.py, services/crawler_service.py, diff_service.py, tasks/crawl_tasks.py, models/crawl.py, templates/crawl/

**Точка 1 — СПРАВКА:**
Playwright BFS-краулер, sitemap parsing, page data extraction, snapshots, diffs, change feed, auto-tasks (404/lost-indexation).

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: Screaming Frog показывает response codes, canonicals, redirects, hreflang, robots directives, structured data errors
- Что добавить: canonical URL tracking, redirect chain detection, robots.txt проверка, duplicate title/H1 detection
- Orphan pages (есть в sitemap, но нет внутренних ссылок)
- Page speed lite (TTFB из Playwright)
- Image audit (broken images, missing alt)

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Запустить краулинг poly-msk.ru
- Показать список страниц: URL, title, H1, status, page type
- Показать change feed после второго краула
- Найти страницы без schema.org и без TOC

---

### Phase 5: Clusters & Semantics
**Модуль:** `clusters` — routers/clusters.py, services/cluster_service.py, models/cluster.py, templates/clusters/

**Точка 1 — СПРАВКА:**
Auto-clustering по SERP-пересечениям, ручные кластеры, каннибализация, CSV-export, missing pages.

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: Serpstat умеет кластеризовать по «мягкой» и «жёсткой» схеме (TOP-10 vs TOP-30)
- Что добавить: threshold для кластеризации (настраиваемый min_shared)
- Keyword-to-page mapping score (насколько хорошо кластер покрыт контентом)
- Cluster gaps — ключи без страниц-кандидатов
- Визуализация кластеров (группировка по target_url)

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Запустить auto-clustering для ключей poly-msk.ru
- Показать предложенные кластеры: target URL + keywords
- Обнаружить каннибализацию (если есть)
- Экспортировать CSV

---

### Phase 6: Content Pipeline & WP
**Модуль:** `wp_pipeline` — routers/wp_pipeline.py, services/content_pipeline.py, wp_service.py, tasks/wp_content_tasks.py, models/wp_content_job.py, templates/pipeline/

**Точка 1 — СПРАВКА:**
TOC-генерация, schema.org injection, internal links, diff/approve/rollback workflow, batch processing.

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: Surfer SEO показывает keyword density, NLP entities, content score
- Что добавить: просмотр diff в UI (before/after), content score (word count vs competitors)
- Breadcrumb schema.org (не только Article)
- FAQ schema для FAQ-блоков
- Open Graph meta injection
- Bulk approve/reject

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Запустить pipeline для 1-2 страниц poly-msk.ru
- Показать diff: что добавлено (TOC, schema, links)
- Approve → push → verify на сайте
- Rollback одной страницы

---

### Phase 7: Data Sources
**Модуль:** `dataforseo`, `gsc`, `yandex` — routers/dataforseo.py, gsc.py, yandex.py, services/*_service.py

**Точка 1 — СПРАВКА:**
DataForSEO SERP/volume, GSC OAuth + Search Analytics, Yandex Webmaster, Playwright SERP fallback.

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: Serpstat/Ahrefs дают backlink index, referring domains, DR/DA
- Что добавить: Yandex Metrika интеграция (органический трафик на страницу)
- GSC URL Inspection API (indexed/not indexed)
- DataForSEO backlinks endpoint
- SERP features tracking (featured snippets, PAA, video, images)

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Подключить GSC OAuth для poly-msk.ru (если есть доступ)
- Fetch GSC data за 28 дней → показать top queries
- Проверить SERP через DataForSEO для «полимерные полы москва»
- Показать позицию poly-msk.ru в выдаче

---

### Phase 8: Projects & Tasks
**Модуль:** `projects` — routers/projects.py, services/project_service.py, task_service.py, models/project.py, task.py, content_plan.py, templates/projects/

**Точка 1 — СПРАВКА:**
Проекты, Kanban (5 колонок), контент-план, брифы, комменты, access control, auto-tasks из crawler.

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: Asana/Monday показывают timeline, workload, dependencies
- Что добавить: task priorities (P1-P4), task comments, time estimates
- Content plan → auto-generate brief → create WP draft (цепочка)
- Task notifications (Telegram/email при смене статуса)
- Фильтры задач по site, type, assignee, date range

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Создать проект «SEO poly-msk.ru Q2 2026»
- Добавить контент-план: 3 страницы (услуга, статья, landing)
- Сгенерировать brief из кластера
- Создать задачу: «Исправить 404 на /services/old-page»

---

### Phase 9: Reports & Analytics
**Модуль:** `reports` — routers/reports.py, services/report_service.py, models/ad_traffic.py, templates/dashboard/

**Точка 1 — СПРАВКА:**
Dashboard stats, Excel export, ad traffic import/compare.

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: Serpstat даёт visibility trend, position distribution chart, domain comparison
- Что добавить: site overview page (позиции + трафик + задачи в одном месте)
- PDF-отчёт (WeasyPrint) с графиками
- Email-рассылка отчётов по расписанию
- Графики: visibility trend, TOP distribution, keyword growth

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Показать dashboard с данными poly-msk.ru
- Экспортировать Excel-отчёт
- Загрузить ad traffic CSV (Яндекс.Директ)
- Сравнить два месяца по трафику

---

### Phase 10: Admin & Access Control
**Модуль:** `admin` — routers/admin.py, site_groups.py, invites.py, services/user_service.py, audit_service.py, models/user.py, invite.py, templates/admin/

**Точка 1 — СПРАВКА:**
Пользователи, роли (admin/manager/client), группы сайтов, инвайты, аудит лог.

**Точка 2 — РАСШИРЕНИЕ:**
- Сравнение: корпоративные SaaS имеют SSO, 2FA, API keys, permission matrix
- Что добавить: audit log UI (фильтрация, поиск по действию/пользователю)
- Password change UI
- User activity dashboard (последние действия, количество сессий)
- API key management для headless-доступа

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Создать пользователя «client-poly» с ролью client
- Назначить в группу с poly-msk.ru
- Отправить инвайт-ссылку
- Посмотреть audit log: кто что делал

---

### Phase 11: Competitors
**Модуль:** `competitors` — новый модуль

**Точка 1 — СПРАВКА:**
Хранение списка конкурентов по сайту, отображение сравнительных данных.

**Точка 2 — РАСШИРЕНИЕ:**
- Список доменов-конкурентов привязан к сайту (хранится в Sites, управляется здесь)
- Сравнение позиций по общим ключевым словам (данные из Positions)
- SERP-пересечения с конкурентами (данные из Clusters)
- Visibility конкурентов vs свой сайт (данные из Reports)
- Авто-обнаружение конкурентов по SERP-выдаче

**Точка 3 — ПРАКТИКА (poly-msk.ru):**
- Добавить 2-3 конкурента для poly-msk.ru
- Сравнить позиции по общим ключам
- Показать где конкурент в TOP-10, а мы нет

---

> **Заметки к обсуждению (не забыть):**
>
> - **Phase 8 (Projects & Tasks):** реализовать простой наглядный список «что сейчас делается по сайту» — без ответственных и статусов, просто перечень актуальных задач. Виджет в карточке сайта.
> - **Phase 4 (Crawl):** обсудить change feed — список изменений, обнаруженных краулером
> - **Phase 6 (Content Pipeline):** обсудить историю внесённых изменений контента (diff/approve/rollback лог)
> - **Phase 9 (Reports):** обсудить сравнение периодов и visibility с учётом данных конкурентов

---

## Порядок работы

Для каждой фазы:
1. Пользователь говорит «начинаем Phase N»
2. Claude формирует СПРАВКУ → записывает в `app/templates/help/{module}.md` → добавляет иконку `?` в UI модуля → справка читаема из интерфейса
3. Пользователь приводит примеры из других сервисов, формулирует задачи
4. Claude отвечает: что уже готово, что нужно доработать, предлагает план
5. Вместе реализуем доработки
6. Claude обновляет справку с учётом новых возможностей
7. Claude демонстрирует ПРАКТИКУ на poly-msk.ru — реальный парсинг/данные
8. Коммит, переход к следующей фазе

**Правило:** справка всегда актуальна — после каждого расширения модуля обновляется `.md`-файл.
