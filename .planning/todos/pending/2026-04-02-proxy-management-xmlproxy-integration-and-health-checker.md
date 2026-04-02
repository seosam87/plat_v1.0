---
created: 2026-04-02T20:19:26.011Z
title: Proxy management, XMLProxy integration and health checker
area: api
files:
  - app/services/proxy_serp_service.py
  - app/services/serp_parser_service.py
  - app/tasks/position_tasks.py
  - app/config.py
  - app/celery_app.py
---

## Problem

Position checking currently has no working data source:
- DataForSEO is not configured (decided against it)
- Playwright SERP parser was broken (routed to wrong queue — fixed)
- No proxy management UI — PROXY_URL is env-only, no pool, no rotation, no health checks
- User has XMLProxy.ru account with limits (used in KeyCollector) — not integrated
- User has anti-captcha service limits — partially integrated but not exposed in admin

XMLProxy.ru is a Yandex XML limit exchange (not a proxy). API is wire-compatible with Yandex XML.
Key gotcha: async API returns -55 error, needs retry after 5-10 min, repeat within 12h is free.
Price: ~0.02 RUB/query.

## Solution

1. **XMLProxy service** (`xmlproxy_service.py`) — HTTP client for Yandex XML API via xmlproxy.ru endpoint, handle -55 retries, balance check
2. **Proxy model in DB** — table for managing proxy pool (url, type, status, last_check, response_time)
3. **Admin proxy UI** — list proxies, add/remove, health check button, XMLProxy balance display
4. **Health checker** — verify proxy liveness, measure response time, mark dead proxies
5. **Update position_tasks** — priority: XMLProxy (Yandex) → Playwright+proxy (Google) → Playwright bare (fallback)
6. **Anti-captcha settings** — expose ANTICAPTCHA_KEY config in admin UI
