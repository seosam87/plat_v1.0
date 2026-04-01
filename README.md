# SEO Management Platform

Internal SEO management platform for a team managing 20–100 WordPress sites.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env: set SECRET_KEY, FERNET_KEY, and optionally API keys

# 2. Start all services
docker compose up --build -d

# 3. Create admin user
docker compose exec api python scripts/seed_admin.py

# 4. Open
# App:    http://localhost:8000
# Flower: http://localhost:5555 (admin:changeme)
# Docs:   http://localhost:8000/docs
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| api | 8000 | FastAPI web app + API |
| worker | — | Celery worker (wp + default queues) |
| crawler | — | Celery worker (crawl queue, Playwright) |
| beat | — | Celery Beat (redbeat scheduler) |
| flower | 5555 | Celery task monitoring UI |
| postgres | 5432 | PostgreSQL 16 |
| redis | 6379 | Redis 7.2 (broker + cache) |

## Features

- **Site Management**: Add WordPress sites, verify WP REST API connection, Fernet-encrypted credentials
- **Crawling**: Playwright-based crawler, sitemap parsing, SEO data extraction, change feed with diffs
- **Crawl Scheduling**: Daily/weekly/manual via redbeat, survives Redis flush (DB-backed)
- **File Import**: Topvisor, Key Collector, Screaming Frog parsers with auto column detection
- **Keywords**: Manual entry + bulk import, keyword groups (KC nesting supported), 100k keywords per project
- **Position Tracking**: Partitioned table (monthly), delta computation, Chart.js 90-day graphs, Telegram drop alerts
- **API Integrations**: Google Search Console (OAuth2), DataForSEO (SERP + volume), Yandex Webmaster
- **Semantics**: Keyword clusters, SERP auto-clustering, cannibalization detection, CSV export
- **WP Pipeline**: TOC generation, schema.org injection, internal linking, mandatory diff approval, rollback
- **Projects**: Kanban board, content plan with one-click WP draft, page briefs from clusters
- **Reports**: Dashboard, Excel export, ad traffic upload with period comparison
- **Security**: JWT auth (3 roles), rate limiting (slowapi), client invite links, audit logging

## Tech Stack

Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, PostgreSQL 16, Redis 7.2, Celery 5.4, Playwright, Jinja2 + HTMX 2.0

## Environment Variables

See `.env.example` for all available settings. Required:
- `SECRET_KEY` — JWT signing key
- `FERNET_KEY` — WP password encryption key
- `POSTGRES_*` — Database credentials

Optional (enable features):
- `GSC_CLIENT_ID/SECRET` — Google Search Console
- `DATAFORSEO_LOGIN/PASSWORD` — DataForSEO API
- `YANDEX_WEBMASTER_TOKEN` — Yandex Webmaster
- `TELEGRAM_BOT_TOKEN/CHAT_ID` — Position drop alerts
