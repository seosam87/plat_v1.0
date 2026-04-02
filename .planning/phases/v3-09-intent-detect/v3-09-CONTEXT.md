# Phase 9: Intent Auto-Detect - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

SERP parsing via Playwright with proxy+anticaptcha for volume (50-100 pages/day), analyze TOP-10 for commercial vs informational intent, semi-auto workflow (propose → confirm), batch processing, update cluster intent.
</domain>

<decisions>
- **D-01:** Playwright + прокси + антикапча для снятия ограничения <50 req/day. Нужно 50-100 страниц/день.
- **D-02:** Прокси конфигурация: env vars PROXY_URL, ANTICAPTCHA_KEY. Ротация прокси.
- **D-03:** Полуавтомат: система предлагает intent, специалист подтверждает.
- **D-04:** Пакетная обработка: запустить для всех некластеризованных ключей.
- **D-05:** Кэш SERP из v3-04 SessionSerpResult переиспользуется где доступен, новые запросы через Playwright+proxy.

### Existing: `serp_parser_service.py` (Playwright), `classify_site_type()`, `KeywordCluster.intent` enum.
</decisions>

---
*Phase: v3-09-intent-detect*
