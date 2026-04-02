# Phase 6: Site Architecture - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

SF import into Page model, URL tree visualization (D3.js), sitemap.xml comparison (fetch + upload), page type architecture mapping (Pillar → Services → Subservices → Articles + Trigger + Authority + Link Accelerator) based on internal link relationships NOT URL structure, and inlinks diff between crawls.

</domain>

<decisions>
## Implementation Decisions

### SF Import
- **D-01:** SF данные сохраняются в существующую модель `Page` с полем `source` (crawl/sf_import). SF как альтернативный источник данных наряду с Playwright-краулом.

### Tree Visualization
- **D-02:** D3.js (или подобная библиотека) для интерактивного дерева URL-иерархии.

### Sitemap
- **D-03:** Оба варианта: парсинг sitemap.xml с сайта через HTTP fetch + загрузка файла пользователем.

### Architecture Model
- **D-04:** Архитектура — это НЕ про URL-структуру, а про типы страниц и перелинковку между ними:
  - **Pillar** — главные хабы тем
  - **Service** — страницы услуг
  - **Subservice** — подуслуги
  - **Article** — информационный контент
  - **Trigger** — конверсионные страницы
  - **Authority** — страницы доверия (отзывы, кейсы, сертификаты)
  - **Link Accelerator** — страницы для привлечения ссылок
  
  Система автоматически определяет типы по page_type + эвристикам, пользователь корректирует. Идеальная структура — это граф перелинковки между типами, а не URL-дерево.

### Scope
- **D-05:** Максимум: SF import + URL дерево + sitemap comparison + architecture mapping + inlinks diff.

### Claude's Discretion
- D3.js tree layout specifics
- Sitemap XML parsing approach
- Architecture type auto-detection heuristics
- Inlinks diff format and storage

</decisions>

<canonical_refs>
## Canonical References

### Existing crawl infrastructure
- `app/models/crawl.py` — Page (url, title, h1, meta, status, depth, internal_link_count, inlinks_count, page_type, has_toc, has_schema, has_noindex)
- `app/parsers/screaming_frog_parser.py` — parse_screaming_frog() with Internal/External/PageTitles/Meta/H1 tab support
- `app/services/diff_service.py` — compute_diff(), build_snapshot()
- `app/services/change_monitoring_service.py` — detects changes after crawl

### Page type
- `app/models/crawl.py` — PageType enum (category, article, landing, product, unknown)
- `app/models/crawl.py` — ContentType enum (informational, commercial, unknown)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable
- `screaming_frog_parser.py` — full SF parsing, returns pages with url/status/title/h1/word_count/inlinks
- `Page` model already has all needed fields; just need `source` field
- `diff_service.py` — can extend for inlinks diff
- `PageSnapshot` — stores field-level diffs

### New Components
- `source` field on Page model (crawl vs sf_import)
- `SitemapPage` model or comparison logic (temporary, not persisted)
- `ArchitectureRole` enum — pillar/service/subservice/article/trigger/authority/link_accelerator
- `architecture_role` field on Page model
- `architecture_service.py` — SF import, sitemap comparison, architecture mapping, inlinks analysis
- `app/routers/architecture.py` — router
- `app/templates/architecture/` — tree visualization, sitemap comparison, architecture map

</code_context>

<deferred>
## Deferred Ideas

- Manual link graph editor
- Architecture health score
- Auto-detection of link accelerator pages via backlink data

</deferred>

---

*Phase: v3-06-site-architecture*
*Context gathered: 2026-04-02*
