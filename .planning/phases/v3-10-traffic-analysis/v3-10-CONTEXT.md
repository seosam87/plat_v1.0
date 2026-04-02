# Phase 10: Traffic Analysis & Bot Detection - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Traffic analysis and bot detection. Primary source: Yandex Metrika data (already integrated in v3-01). Secondary: server logs and WP plugin for complex cases. Detect bot patterns, traffic injection, anomalies.
</domain>

<decisions>
- **D-01:** Приоритет — данные Метрики (уже интегрирована в v3-01). Логи сервера и WP-плагин — для сложных случаев.
- **D-02:** Анализ: точки входа, источники, паттерны ботов, timeline подлива, влияние на поведенческие.
- **D-03:** UI: дашборд трафика по типам, алерты при аномалиях, фильтрация, сравнение периодов.

### Existing: `metrika_service.py` (fetch daily/page traffic), `MetrikaTrafficDaily/Page` models.
</decisions>

---
*Phase: v3-10-traffic-analysis*
