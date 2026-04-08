---
phase: 16
phase_name: AI/GEO Readiness & LLM Briefs
created: 2026-04-08
mode: discuss
---

# Phase 16 — AI/GEO Readiness & LLM Briefs — CONTEXT

## Domain

Каждая crawled-страница получает GEO readiness score 0–100 (rule-based DOM checks, без ML), видимый и фильтруемый в audit table. Дополнительно: opt-in AI-улучшение существующего template-брифа через Anthropic API. Никакая новая audit-инфраструктура не вводится — GEO-чеки переиспользуют `audit_check_definitions` с префиксом `geo_*`.

## Carried Forward (locked from prior phases / STATE)

- Template brief всегда генерируется первым; LLM — только enhancement, никогда не блокирует доставку брифа
- LLM Briefs co-located с GEO Readiness в одной фазе (STATE decision)
- Anthropic SDK — выбранный vendor, без альтернатив (OpenAI/Gemini не рассматриваются)
- Token caps: input ~2000, output ~800 (success criteria #6)
- Кнопка «Generate AI brief» видна только если у пользователя сконфигурирован API-ключ

## Decisions

### D-01: Модель Anthropic

**Решение:** `claude-haiku-4-5-20251001` (Haiku 4.5).
**Хранение:** захардкожена в `app/services/llm/config.py` как константа `ANTHROPIC_MODEL`.
**Mandatory note:** в коде, в админ-доках и в UI рядом с кнопкой «Generate AI brief» **должна быть видимая пометка**: "Powered by Claude Haiku 4.5 — для апгрейда до Sonnet/Opus отредактируй ANTHROPIC_MODEL и пересобери".
**Why:** ×10–20 дешевле Opus, ~3× быстрее, качество достаточно для расширения готового шаблона. Self-hosted платформа с per-user биллингом — экономия критична.
**How to apply:** планировщик ставит `ANTHROPIC_MODEL` в одном месте; researcher-агент проверяет актуальность model ID и pricing на момент реализации.

### D-02: Хранение Anthropic API-ключа

**Решение:** **per-user** ключи. Каждый пользователь вводит свой Anthropic API key в профиле.
**Хранение:** Fernet-зашифровано (тот же паттерн, что WP-credentials и `ServiceCredential`).
**Где:** новая колонка `anthropic_api_key_encrypted` (nullable) в таблице `users`, ИЛИ отдельная таблица `user_credentials` если есть смысл расширять под другие per-user интеграции — researcher решит, где чище.
**UX:** страница «Профиль» (если её нет — создать минимальную), поле «Anthropic API Key» с маской ввода, кнопка «Validate» (делает дешёвый тест-запрос), кнопка «Remove».
**Why:** биллинг на стороне пользователя, каждый видит свой расход, никто не платит за чужие генерации, нет риска одного бита-ключа на всю команду.
**How to apply:** кнопка «Generate AI brief» отображается через `current_user.has_anthropic_key` — Jinja-условие в шаблоне брифа.

### D-03: Что именно LLM добавляет к template-брифу

**Решение:** **3 блока «AI Suggestions»** в одном брифе:
1. **Expanded sections** — абзацы под H2/H3 шаблона (LLM расширяет каждый существующий заголовок коротким контентом-черновиком)
2. **FAQ block** — 5–8 Q&A на основе кластера запросов брифа
3. **Title/Meta variants** — 3 варианта title и 3 варианта meta description

**Один LLM-запрос** возвращает JSON со всеми тремя секциями (структурированный output). В шаблоне брифа три сворачиваемые секции, юзер копирует то, что нужно.
**Why:** минимум магии, максимум полезности; один токен-бюджет на всё; юзер не ждёт три отдельных запроса.
**How to apply:** prompt template с явной JSON-схемой ответа; парсинг через pydantic-модель `LLMBriefEnhancement`.

### D-04: UX триггера «Generate AI brief»

**Решение:** **async через Celery + HTMX polling** с preview/accept/regenerate.

Поток:
1. Юзер на странице брифа жмёт «Generate AI brief»
2. POST `/briefs/{brief_id}/llm-enhance` → создаётся `LLMBriefJob` (status=pending), возвращается job_id
3. Celery таска `generate_llm_brief_enhancement(job_id)` забирает job, делает запрос к Anthropic, парсит ответ, пишет результат в `output_json`, status=done (или failed + error)
4. UI делает `hx-get` на `/briefs/llm-jobs/{job_id}` каждые 2–3 сек (HTMX polling), показывает «генерация…»
5. По готовности — preview-блок с тремя секциями + кнопки **Accept** и **Regenerate**
6. **Accept** → POST `/briefs/llm-jobs/{job_id}/accept` → секции вмердживаются в брифа
7. **Regenerate** → создаётся новый job с тем же контекстом

**Why:** согласовано с уже работающим паттерном (suggest jobs, PDF generation), не блокирует UI, естественно ложится на existing Celery-инфраструктуру, легко добавлять observability и лимиты.
**How to apply:** новая модель `LLMBriefJob`, новый router, HTMX-polling шаблон по образцу `suggest_jobs`.

### D-05: GEO-чеклист — конкретные правила и веса

**Решение:** 9 rule-based чеков, сумма весов ровно **100**. Все на BeautifulSoup + regex, без ML/NER.

| # | Код | Вес | Что проверяем |
|---|---|---|---|
| 1 | `geo_faq_schema` | 15 | На странице есть `FAQPage` JSON-LD |
| 2 | `geo_article_author` | 15 | `Article` + `Author` (или `Person`) schema |
| 3 | `geo_breadcrumbs` | 10 | `BreadcrumbList` schema |
| 4 | `geo_answer_first` | 15 | Первый абзац после H1 ≤ 60 слов и содержит глагол (прямой ответ) |
| 5 | `geo_update_date` | 10 | `time[datetime]` или `dateModified` в JSON-LD |
| 6 | `geo_h2_questions` | 10 | ≥30% H2-заголовков сформулированы как вопросы (Who/What/How/Why/When/Что/Как/Почему/Когда/Где) |
| 7 | `geo_external_citations` | 10 | ≥2 outbound link на whitelist авторитетных доменов (gov/edu/peer media) |
| 8 | `geo_ai_robots` | 10 | `robots.txt` / meta не блокирует GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot, Google-Extended |
| 9 | `geo_summary_block` | 5 | Явный TL;DR / summary блок до первого H2 (помечен `summary` / `tldr` / `key-takeaways`) |

**Не вошло в MVP (backlog):**
- `geo_statistics` — слишком много false positives на ценах/датах/телефонах, добавить позже с whitelist единиц
- `geo_quotations` — сложно отличить блоки-цитаты от стилизованного blockquote
- `geo_named_entities` — требует NER (spaCy), отдельная фаза
- `geo_published_modified`, `geo_lang_attr`, `geo_canonical_self`, `geo_word_count`, `geo_definition_lists`, `geo_llms_txt` — низкий ROI для MVP, при необходимости добавить отдельным мини-фазой

**Why (теоретическое обоснование recommended optionals):**
- `external_citations` — Princeton GEO study (Aggarwal et al., 2024) показал +30–40% visibility в LLM-ответах; chain-of-trust эвристика
- `ai_robots` — без этого страница вообще не попадает в обучение/индекс AI-движков; критичный gate
- `h2_questions` — match с user-query patterns в AI-search; user-decision: повышен с 2 до 10
- `summary_block` — Perplexity явно предпочитает страницы с TL;DR

**How to apply:** researcher должен подтвердить актуальные User-Agent строки AI-ботов на момент имплементации (они меняются); веса захардкожены в `audit_check_definitions` через Alembic-миграцию.

### D-06: Token usage tracking

**Решение:** полное usage tracking + страница «Usage» в профиле.

**Таблица `llm_usage`:**
```
id              bigserial pk
user_id         fk -> users
brief_id        fk -> briefs (nullable, на случай tests/admin)
job_id          fk -> llm_jobs
model           varchar  (ANTHROPIC_MODEL на момент запроса — для будущих миграций)
input_tokens    int
output_tokens   int
cost_usd        numeric(10,6)  (вычисляется при записи из pricing constants)
status          varchar  (success / failed)
error_message   text     (nullable)
created_at      timestamptz
```

**Pricing constants:** `app/services/llm/pricing.py` — Haiku 4.5 input/output $/MTok как константы; функция `compute_cost(model, in_tok, out_tok) -> Decimal`.

**Profile page Usage tab:** расход за «сегодня / 7 дней / 30 дней», количество запросов, success rate, список последних 20 запросов с timestamp/cost/status.

**Без hard-лимитов в MVP** — token cap (input 2000 / output 800) + circuit breaker уже защищают. Hard-лимит per-user/день добавляется в одно поле в `users` если понадобится.

**Circuit breaker — per-user (НЕ глобальный).** Логика: 3 подряд `failed` запроса от одного пользователя → LLM-кнопка для этого пользователя отключается на 15 минут (или до успешного manual reset). Один пользователь с битым ключом не должен ломать LLM для всех. Хранение состояния — Redis ключ `llm:cb:user:{id}` с TTL.

**Why:** прозрачность для self-hosted команды, доверие к платформе, готовность к регулированию расходов, возможность апсейла «расход слишком высокий → перейди на свой ключ Sonnet».

## Folded todos

- `2026-04-02-fix-position-check-ignores-keyword-engine-preference` — НЕ относится к Phase 16, оставлен в pending
- `2026-04-02-proxy-management-xmlproxy-integration-and-health-checker` — НЕ относится к Phase 16, оставлен в pending
- Pending todo «Phase 16: Confirm LLM model — claude-3-5-haiku-20241022 vs claude-opus-4-6» — **закрыт через D-01** (выбран Haiku 4.5 — `claude-haiku-4-5-20251001`, более новая версия)

## Deferred (out-of-scope, backlog)

- GEO-чеки за пределами MVP-9: `geo_statistics`, `geo_quotations`, `geo_named_entities`, `geo_published_modified`, `geo_lang_attr`, `geo_canonical_self`, `geo_word_count`, `geo_definition_lists`, `geo_llms_txt`
- LLM-генерация **полного** контента страницы (не enhancement брифа) — out of scope per PROJECT.md
- Hard daily/monthly лимиты на пользователя
- Admin-override модели через UI (захардкожена в коде осознанно, см. D-01 mandatory note)
- Multiple LLM-providers (OpenAI/Gemini/Mistral) — Anthropic only
- Streaming/SSE для preview (выбран polling в D-04)
- `/llms.txt` на уровне сайта — отдельная фаза, концептуально другая сущность

## Canonical Refs

- `.planning/PROJECT.md` — стек, constraints, current state
- `.planning/ROADMAP.md` § Phase 16 — success criteria 1-6, requirements GEO-01..03 / LLM-01..04
- Princeton "GEO: Generative Engine Optimization" (Aggarwal et al., 2024) — обоснование `external_citations`, `statistics`, `quotations` весов; researcher-агент должен найти и зафиксировать DOI/arxiv URL
- Anthropic Messages API docs — для researcher (актуальная цена Haiku 4.5, актуальный model ID, structured output JSON mode)
- Anthropic `llms.txt` standard — anthropic.com/news/llms-txt (для будущей deferred-фазы)
- Существующий `app/services/audit/` — паттерн `audit_check_definitions`, как добавлять новые `*_*` чеки
- Существующий `app/services/briefs/` — куда вмердживать AI Suggestions
- Существующий `app/services/credentials/` (или WP credentials encryption) — паттерн Fernet для D-02
- Существующий `app/templates/keywords/suggest_*.html` — паттерн HTMX polling jobs для D-04
