---
phase: 32-telegram-bot
plan: "02"
subsystem: infra
tags: [docker, nginx, telegram-bot, python-telegram-bot, webhook]

requires:
  - phase: 32-telegram-bot-01
    provides: "Bot directory structure and plan context"

provides:
  - "Dockerfile.bot: slim Python 3.12 image for bot service"
  - "bot/requirements.txt: python-telegram-bot[webhooks]>=21.0,<22.0"
  - "docker-compose.yml: bot service independent of api, depends only on postgres+redis"
  - "nginx/conf.d/app.conf: /webhook/tg location proxying to bot:8443"

affects:
  - 32-telegram-bot-03
  - 32-telegram-bot-04

tech-stack:
  added:
    - python-telegram-bot[webhooks]>=21.0,<22.0
  patterns:
    - "Bot container uses python:3.12-slim with gcc+libpq-dev for asyncpg compilation"
    - "Bot depends only on postgres+redis, not on api service (graceful degradation)"
    - "Nginx upstream bot_upstream proxies /webhook/tg to bot:8443"

key-files:
  created:
    - Dockerfile.bot
    - bot/requirements.txt
  modified:
    - docker-compose.yml
    - nginx/conf.d/app.conf

key-decisions:
  - "Bot container does NOT depend on api service (D-04) — graceful degradation if API is down"
  - "Bot listens on port 8443, Nginx proxies /webhook/tg to bot_upstream"
  - "python:3.12-slim base (not Playwright image) — bot does not need Chromium"
  - "Main requirements.txt installed first, bot/requirements.txt adds PTB on top"

patterns-established:
  - "Bot service pattern: separate Dockerfile + requirements.txt, shared app/ code via COPY"

requirements-completed: [BOT-03]

duration: 8min
completed: 2026-04-12
---

# Phase 32 Plan 02: Docker Infrastructure Summary

**Bot container (python:3.12-slim) with independent docker-compose service, Nginx proxying /webhook/tg to bot:8443, isolated from api service for graceful degradation**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-12T13:17:00Z
- **Completed:** 2026-04-12T13:25:46Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created Dockerfile.bot using python:3.12-slim with asyncpg build deps, installs shared requirements.txt then bot-specific PTB
- Created bot/requirements.txt pinning python-telegram-bot[webhooks]>=21.0,<22.0
- Added bot service to docker-compose.yml, depending only on postgres+redis (not api) with restart:unless-stopped
- Added bot_upstream and /webhook/tg location block to nginx config routing Telegram webhooks to bot:8443

## Task Commits

1. **Task 1: Dockerfile.bot + bot/requirements.txt** - `6017561` (feat)
2. **Task 2: docker-compose bot service + Nginx webhook proxy** - `7aac5bf` (feat)

## Files Created/Modified

- `Dockerfile.bot` - Slim Python 3.12 image; installs main deps + PTB; copies app/ and bot/; CMD runs bot.main
- `bot/requirements.txt` - Bot-specific dependency: python-telegram-bot[webhooks]>=21.0,<22.0
- `docker-compose.yml` - Added bot service with Dockerfile.bot, TELEGRAM_BOT_PORT=8443, depends_on postgres+redis
- `nginx/conf.d/app.conf` - Added bot_upstream (bot:8443) and location /webhook/tg proxy block

## Decisions Made

- Bot container does NOT depend on api service per decision D-04: if the FastAPI api goes down, the bot continues handling Telegram messages
- Port 8443 chosen for webhook listener (standard Telegram webhook port for HTTPS)
- gcc + libpq-dev included in Dockerfile.bot to enable asyncpg compilation from source (no pre-built wheels in slim)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. `docker compose config` validated without errors after changes.

## User Setup Required

None - no external service configuration required. Bot service will start with `docker compose up bot`.

## Next Phase Readiness

- Dockerfile.bot and docker-compose bot service are ready for Plan 03 (bot entry point: bot/main.py)
- Nginx is ready to route Telegram webhook callbacks once the bot registers the webhook URL
- `docker compose up bot` will work as soon as bot/main.py exists (Plan 03)

---
*Phase: 32-telegram-bot*
*Completed: 2026-04-12*
