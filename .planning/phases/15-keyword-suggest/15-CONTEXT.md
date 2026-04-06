# Phase 15: Keyword Suggest - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can enter a seed keyword and retrieve 200+ keyword suggestions from Yandex (primary) and Google (secondary), with results cached in Redis (TTL 24h). Optionally load Yandex Wordstat frequency data for each suggestion via Yandex Direct OAuth token.

Also includes 2 folded todos: fix position check ignoring keyword engine preference, and proxy management/XMLProxy health checker improvements.

</domain>

<decisions>
## Implementation Decisions

### Источники и маршрутизация
- **D-01:** Яндекс Suggest API напрямую (suggest.yandex.ru) через существующий пул прокси (5 шт.), не через XMLProxy
- **D-02:** Google Suggest API напрямую (suggestqueries.google.com) с сервера без прокси
- **D-03:** Все внешние вызовы через Celery-таски с retry=3, не inline в request handler
- **D-04:** Оба todo включены в скоп фазы: (1) fix position check ignores keyword engine preference, (2) proxy management, XMLProxy integration and health checker
- **D-05:** Использовать общий пул прокси (те же 5 что для позиций) для Яндекс Suggest
- **D-06:** При бане/429 — ротация прокси с паузой 30с и повтором (макс 3 попытки), при исчерпании — отдать частичные результаты с предупреждением пользователю
- **D-07:** Google Suggest напрямую с сервера без прокси

### Отображение и взаимодействие
- **D-08:** Таблица с фильтрацией: колонки — подсказка, источник (Я/G), частотность. Поиск по тексту, сортировка по колонкам
- **D-09:** Только экспорт (CSV/копирование), без добавления подсказок в трекинг ключевых слов
- **D-10:** Отдельный раздел в сайдбаре с иконкой (как Client Reports)
- **D-11:** HTMX polling каждые 3с: спиннер → прогресс-бар → результаты (паттерн из Client Reports)

### Частотность Wordstat
- **D-12:** OAuth-токен Яндекс.Директ хранить в ServiceCredential (Fernet-шифрование), как XMLProxy/GSC
- **D-13:** Колонка "Частотность" в таблице результатов с сортировкой. Скрыта если токен не настроен
- **D-14:** Баннер-подсказка "Настройте токен Я.Директ в настройках для частотности" (можно закрыть) когда токен не настроен
- **D-15:** Отдельная кнопка "Загрузить частотность" после получения подсказок (не автоматически). Экономит лимиты API

### Стратегия расширения
- **D-16:** Расширение seed по русскому алфавиту А-Я (33 буквы): seed + а, seed + б, ..., seed + я. Единый режим без выбора пользователем
- **D-17:** Последовательные запросы к Яндекс Suggest с паузой 200-500мс (безопаснее чем параллельные)
- **D-18:** Google Suggest — тот же алфавитный расширение А-Я

### Claude's Discretion
- Конкретный endpoint suggest.yandex.ru vs suggest-ya.ru (выбрать работающий)
- Формат ответа и парсинг JSON/XML от обоих API
- Структура Celery-таска (одна задача на весь алфавит или чейн)
- Паттерн Redis-кэширования (ключ, формат, сериализация)
- Формат CSV экспорта (разделитель, кодировка, заголовки)
- Yandex Direct API v5 — конкретные методы для Wordstat

### Folded Todos
- **Fix position check ignores keyword engine preference** — При проверке позиций не учитывается выбранный движок ключевого слова. Связано с keyword/engine routing
- **Proxy management, XMLProxy integration and health checker** — Улучшение управления прокси и health-check XMLProxy. Связано с proxy pool

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Существующие сервисы
- `app/services/xmlproxy_service.py` — XMLProxy клиент, паттерн sync HTTP через httpx, обработка ошибок
- `app/tasks/position_tasks.py` — Celery-таски с retry, работа с прокси, rate-limit handling
- `app/config.py` — Settings с REDIS_URL и другими ENV
- `app/main.py` — slowapi rate limiter конфигурация
- `app/services/dashboard_service.py` — Паттерн Redis-кэширования через aioredis

### Модели и credentials
- `app/models/` — SQLAlchemy 2.0 Mapped модели (паттерн для новой модели)
- `app/routers/proxy_admin.py` — CRUD для XMLProxy credentials (паттерн для Я.Директ токена)

### UI паттерны
- `app/navigation.py` — Навигация сайдбара, паттерн добавления раздела
- `app/templates/components/sidebar.html` — SVG иконки разделов
- `app/templates/client_reports/` — Паттерн HTMX polling + прогресс (из Phase 14)

### Todos
- `.planning/todos/2026-04-02-fix-position-check-ignores-keyword-engine-preference.md`
- `.planning/todos/2026-04-02-proxy-management-xmlproxy-integration-and-health-checker.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `xmlproxy_service.py` — sync HTTP client pattern, можно скопировать для suggest_service
- `dashboard_service.py` — async Redis cache pattern (`aioredis.from_url`)
- `position_tasks.py` — Celery task с proxy rotation, retry, error handling
- `slowapi` limiter — уже настроен в main.py, нужно только добавить декоратор на новый эндпоинт
- `ServiceCredential` модель — Fernet encryption для хранения токенов

### Established Patterns
- Sync HTTP в Celery-тасках (httpx.Client), async в роутерах (httpx.AsyncClient)
- Redis cache через aioredis с TTL
- Rate limiting через slowapi декоратор
- Навигация: добавить секцию в navigation.py + SVG иконку в sidebar.html
- HTMX polling: hx-trigger="load delay:3s" для статуса

### Integration Points
- `app/main.py` — регистрация нового роутера
- `app/navigation.py` — добавление раздела keyword-suggest
- `app/celery_app.py` — автодискавери новых тасков
- `app/config.py` — новые настройки (если нужны)

</code_context>

<specifics>
## Specific Ideas

- Кнопка "Загрузить частотность" появляется только после получения подсказок (не до)
- Баннер про Я.Директ токен должен быть закрываемым (dismiss), не навязчивым
- Частичные результаты при бане — показать сколько собрано + предупреждение
- При повторном запросе того же seed — мгновенный ответ из Redis (24h TTL)
- Endpoint rate limit: 10 req/min (как в success criteria)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

### Reviewed Todos (not folded)
None — оба найденных todo включены в скоп фазы

</deferred>

---

*Phase: 15-keyword-suggest*
*Context gathered: 2026-04-06*
