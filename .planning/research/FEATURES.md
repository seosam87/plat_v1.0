# Feature Research — v4.0 Mobile & Telegram

**Domain:** Mobile focus apps + Telegram bot for internal SEO management platform
**Researched:** 2026-04-10
**Confidence:** HIGH (platform internals — direct code inspection) / MEDIUM (mobile UX patterns — official docs + community sources) / MEDIUM (Telegram WebApp — official API docs)

---

## Context: What Already Exists

The platform (v3.1) ships a complete backend for all data these mobile apps consume. Mobile apps are **thin UI wrappers over existing APIs** — no new backend data models are required for most apps. The primary build is: mobile-optimized Jinja2 templates, `/m/` routing, `base_mobile.html`, and the Telegram bot/WebApp layers.

| Existing Service / Router | What Mobile Can Call |
|--------------------------|---------------------|
| `morning_digest_service.py` | `build_morning_digest()` — pre-built digest text |
| `positions.py` router | `trigger_position_check`, `latest_positions`, `compare_dates`, `get_active_task` |
| `reports.py` router | `export_pdf`, `site_overview` |
| `audit.py` router | `list_checks`, `fix_apply_and_approve`, `fix_preview` |
| `tasks.py` router | `list_tasks`, `update_task_status` |
| `tools.py` router | `tool_submit`, `tool_job_status`, `tool_results` |
| `monitoring.py` router | `list_alerts`, `send_digest_now` |
| `telegram_service.py` | `send_message`, formatters for change alerts, digests, position drops |
| `traffic_analysis_service.py` | `detect_anomalies`, `analyze_traffic_sources` |
| `client_report_service.py` | existing PDF generation pipeline |

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that every mobile companion to a web platform is expected to have. Missing any = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `base_mobile.html` with bottom navigation | Mobile apps need a container; without it every screen is stranded with no way back | LOW | Tailwind flex-row bottom bar; 4-5 icons; 48px tap targets |
| `/m/` route prefix with auth middleware | Mobile apps must be auth-gated; separate namespace keeps desktop routes clean | LOW | FastAPI `APIRouter(prefix="/m")` with existing JWT dependency |
| Pull-to-refresh on all data screens | Mobile UX convention since iOS 6; users tug down expecting fresh data | LOW | HTMX `hx-trigger="load"` on pull gesture; spinner via `hx-indicator` |
| "Last updated" timestamp on every data card | Without it users cannot tell if they're looking at stale data | LOW | Stored in Celery task result; render in template footer |
| Touch-friendly tap targets (minimum 48px) | Standard mobile accessibility; fat-finger errors on small buttons destroy trust | LOW | Tailwind `min-h-12 min-w-12` applied consistently across all mobile templates |
| Loading skeleton screens | Blank screens feel like crashes; skeleton gives perceived speed | LOW | Tailwind `animate-pulse` gray blocks while HTMX loads content |
| Error states with retry button | Network errors happen on mobile; dead screen with no recovery = abandonment | LOW | HTMX `hx-swap-oob` error target + retry trigger button |
| Site selector (global context switcher) | Managing 20–100 sites requires "which site am I on" to always be visible | MEDIUM | Sticky header dropdown; selection persists in session cookie |
| Digest app — morning summary card | Entry point for the workday; mirrors `morning_digest_service` | LOW | Single GET to existing service; render as mobile cards |
| Positions app — current rankings list | Core SEO metric; first thing every manager checks | LOW | Calls `latest_positions`; sortable by delta |
| Positions app — trigger check button | Can't just read positions; must be able to launch a check from phone | MEDIUM | POST to `trigger_position_check`; poll `get_active_task` for status |
| Site health card — crawl errors + alert count | Single "traffic light" status per site is expected | LOW | Aggregate from `list_alerts` + crawl summary endpoint |
| Pages app — audit list with quick approve | Content pipeline has approve queue; mobile must support it | MEDIUM | Calls `fix_apply_and_approve`; existing service handles WP write |
| Quick task — create task from phone | Managers note issues in the field; must capture immediately | LOW | POST to task router; title + site + priority; no rich editor |
| Telegram bot — /status command | Any DevOps bot answers /status; this is table stakes for ops tooling | LOW | Aggregate: DB ping, Redis ping, Celery worker count, last crawl time |
| Telegram bot — /logs command | Solo dev operating a self-hosted system needs log access from anywhere | MEDIUM | Tail last 50 lines from loguru JSON log; split into chunks if >4096 chars |

### Differentiators (Competitive Advantage)

Features that go beyond generic mobile SEO tools and match the platform's specific strengths.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Telegram WebApp wrapper for all focus apps | Zero install; opens inside Telegram; team already uses Telegram — no context switch | MEDIUM | `telegram-web-app.js` in `base_mobile.html`; `themeParams` sync; `MainButton` replaces custom CTAs |
| Pages app — swipe-to-approve gesture | Swipe right/left is 3x faster than tap-menu for reviewing a queue of 20 pages | MEDIUM | Touchstart/touchend delta in ~10 lines vanilla JS; HTMX swap on approval; backend endpoint exists |
| Digest app — overdue task count with deep link | Surfaces accountability; one tap from "3 overdue" to filtered task list | LOW | `task_service` counts overdue; deep link via HTMX `hx-push-url` |
| Positions app — delta badges (▲3 / ▼5) | Visual delta since yesterday is the number managers actually care about | LOW | `compare_dates` returns delta; colored badge render (green up, red down, gray unchanged) |
| Client report app — one-tap send via Telegram | Manager generates and sends to client from phone without opening desktop | MEDIUM | Calls `export_pdf` + `telegram_service.send_message`; orchestrated in a mobile-specific endpoint |
| Traffic comparison app — anomaly highlight | Auto-highlight the period with the biggest drop so user does not have to find it | MEDIUM | `detect_anomalies` from `traffic_analysis_service` exists; highlight anomaly rows in template |
| Telegram bot — Claude Code agent channel | Developer queries Claude to explain errors, suggest fixes, check code — from Telegram | HIGH | `claude-code-telegram` pattern (RichardAtCT/claude-code-telegram); Claude Code channels API; two-way MCP channel; separate subprocess from main bot |
| Telegram bot — /deploy command with confirmation | Trigger git pull + Docker Compose rebuild from phone; critical for solo dev on VPS | HIGH | Shell exec via `subprocess`; MUST be allowlist-gated to admin chat_id; inline keyboard confirm before execution |
| Tools app — one-tap tool launch | 6 SEO tools already built; phone access means zero desktop context switch for quick runs | MEDIUM | Calls `tool_submit`; polls `tool_job_status`; renders results as mobile-optimized card |
| Site health card — 30-second auto-refresh | Real-time feel mirrors existing in-app notification pattern; already proven at scale | LOW | Reuse `hx-trigger="every 30s"` pattern from notifications router |
| Quick task — copywriter brief shortcut | Pre-fills brief template from site context; saves 5 minutes per brief initiation | MEDIUM | Calls `brief_service`; pre-populates task description from site; existing LLM brief pipeline |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full desktop feature parity on mobile | "Why can't I do X on mobile?" | Defeats the focus-app concept; 50+ desktop pages on a phone = cognitive overload; Jinja2 templates don't responsive-collapse cleanly at that scale | Explicit scope: 8 named apps only; every screen shows a "Full view →" link to desktop |
| Real-time WebSocket position updates | Feels dynamic | Positions run as Celery tasks taking minutes, not seconds; WebSocket overhead for data that changes every 10+ minutes is wasteful; Telegram WebApp has 5MB client storage limit | Poll `get_task_status` every 5s while task is active; idle 30s poll otherwise |
| Native push notifications from the web app | "Notify me when positions drop" | The stack has no native app; Telegram bot already handles push alerts via `format_position_drop_alert`; two notification paths double maintenance | Route all push to Telegram bot; mobile web app is pull-only |
| Offline mode / PWA service worker | "Works without internet" | SEO data is live; stale cached positions mislead; service worker adds build complexity incompatible with the Jinja2+HTMX no-build philosophy | Show "Last updated X min ago" prominently; provide retry button on network error |
| In-app chat with Claude on the mobile web | "Feels like a differentiator" | Claude Code Telegram channel serves this better (persistent session, file access, shell); two half-working AI interfaces is worse than one good one | Direct users to Telegram bot for Claude interaction; keep mobile apps data-focused |
| Full keyword management on mobile | Power users want to add/edit keywords from phone | Keyword import requires XLSX upload; semantic clustering requires desktop review; mobile add-one-at-a-time creates data quality issues | Quick task creation only; bulk keyword ops stay desktop |
| Custom dashboard widget reordering | "I want traffic first, not positions" | Personalization adds user_preferences schema, drag-and-drop JS, and maintenance burden; team is 2–3 people who can agree on a fixed layout | Fixed opinionated layout per app; revisit at v5.0 if team grows |
| Telegram bot as full platform API | "Control everything from the bot" | Security surface grows unboundedly; each new command is a new auth-sensitive code path; solo dev cannot maintain 30+ bot commands at acceptable quality | 6–8 ops commands maximum; link to WebApp for data operations |
| /deploy without confirmation dialog | "Saves one tap" | Accidental deploy during a chat scroll is a real risk; one misfire on production = downtime | Inline keyboard with [Deploy] / [Cancel] buttons; require explicit confirmation every time |

---

## Feature Dependencies

```
[base_mobile.html + /m/ routing]
    └──required by──> ALL 8 focus apps
    └──required by──> Telegram WebApp wrapper

[telegram-web-app.js in base_mobile.html]
    └──required by──> Telegram WebApp themeParams sync
    └──enables──> MainButton CTA replacement
    └──enables──> HapticFeedback on approve actions
    └──enables──> ClosingConfirmation on Pages approve queue

[Telegram bot Application (python-telegram-bot 21)]
    └──required by──> /status, /logs, /digest, /test, /deploy, /report commands
    └──required by──> Telegram WebApp button delivery (bot sends WebApp button)
    └──webhook required for production (polling acceptable only for dev)

[Claude Code agent channel]
    └──requires──> running Claude Code session on VPS (manual setup)
    └──requires──> MCP channel server (claude-code-telegram pattern)
    └──independent from──> main Telegram bot (separate process recommended)

[existing telegram_service.send_message()]
    └──already used by──> reports, monitoring, document generator
    └──reused by──> Client report app one-tap send
    └──reused by──> Telegram bot /digest and /report commands

[Celery task polling pattern]
    └──used by──> Positions app (trigger + poll active_task)
    └──used by──> Tools app (tool_submit + tool_job_status)
    └──pattern already established in──> desktop position check UI

[existing fix_apply_and_approve endpoint]
    └──required by──> Pages app approve queue
    └──no changes needed to backend

[existing morning_digest_service.build_morning_digest()]
    └──required by──> Digest app
    └──no changes needed to backend

[existing client_report_service + export_pdf]
    └──required by──> Client report app
    └──no changes needed to backend
```

### Dependency Notes

- **`base_mobile.html` is Phase 1.** Every app depends on it. Build it first with bottom nav, site switcher, pull-to-refresh skeleton, and Telegram WebApp script injection. All 8 apps inherit from it.
- **Telegram bot is independent of mobile web apps.** Bot commands run server-side via python-telegram-bot 21 `Application`; they do not touch the Jinja2 stack. Can be built in parallel with focus apps, but integrate into the same Docker Compose stack.
- **Claude Code agent channel requires an operational decision.** Running `claude` CLI as a subprocess from a bot handler is the simplest integration (per `claude-code-telegram` repo). Requires Claude Code installed on VPS with a valid Anthropic API key. This is the highest-risk feature — HIGH complexity, non-trivial security surface.
- **/deploy is the highest-risk bot command.** Must verify caller chat_id against allowlist (`TELEGRAM_ALLOWED_CHAT_IDS` env var) AND require inline keyboard confirmation before executing any shell command. Log every execution to the `audit_log` table. Do not implement until all read-only commands (/status, /logs) are working and tested.
- **Pages app swipe gesture.** HTMX natively handles click/focus events; swipe requires approximately 10 lines of vanilla JS (touchstart + touchend delta calculation). This does not conflict with the Jinja2+HTMX no-build philosophy — keep JS inline in the template.
- **Telegram WebApp auth bridge.** When user opens a WebApp from a bot button, Telegram provides `initData` in the JS API. Validate this server-side with HMAC-SHA-256 against the bot token. Issue a short-lived JWT on successful validation. This is the only new auth flow required.

---

## Per-App Feature Breakdown

### App 1: Digest

**Table stakes:**
- Summary cards: positions up/down counts, alert count, overdue task count
- Last check timestamp per site
- "Send to Telegram" button (reuse `telegram_service.send_message`)

**Differentiators:**
- Overdue task count is a deep link to tasks list pre-filtered for overdue
- Color-coded status icons (green/yellow/red) matching `_status_icon()` from existing service

**Anti-feature:** Do not add digest configuration on mobile — settings stay on desktop.

**Backend reuse:** `morning_digest_service.build_morning_digest()` already exists. Mobile template consumes the same data.

---

### App 2: Positions

**Table stakes:**
- Keyword list with current position + delta badge (▲3 green / ▼5 red / unchanged gray)
- Filter by site; search by keyword
- "Run check now" button with Celery progress indicator
- Last check timestamp

**Differentiators:**
- Progress bar while check runs (poll `get_active_task` every 5s; idle state falls back to 30s)
- Top-10 keyword count badge in header

**Anti-feature:** Do not show full position history chart on mobile — too small to be useful; provide "Full view →" link to desktop.

**Backend reuse:** `latest_positions`, `compare_dates`, `trigger_position_check`, `get_active_task` all exist in `positions.py` router.

---

### App 3: Client Report

**Table stakes:**
- Site selector
- "Generate PDF" button → spinner → download link or inline send
- "Send via Telegram" button

**Differentiators:**
- Single-flow: generate → send without leaving the app
- Status polling while PDF generates (existing Celery task pattern)

**Anti-feature:** Do not add report template editing on mobile; use desktop.

**Backend reuse:** `export_pdf` and `telegram_service.send_message` exist. Wire together in a thin mobile endpoint.

---

### App 4: Site Health Card

**Table stakes:**
- Traffic light indicator per site (green/yellow/red)
- Crawl error count, last crawl time
- Active alert count
- 30-second auto-refresh

**Differentiators:**
- Inline sparkline of last 7 days positions average (single `<svg>`, no chart library dependency)
- Tap to jump to desktop site detail

**Anti-feature:** Do not replicate the full analytics dashboard; this is a status card only.

**Backend reuse:** Aggregate from `list_alerts`, crawl status endpoint, `latest_positions` average.

---

### App 5: Traffic Comparison

**Table stakes:**
- Period A vs Period B selector (last 7d vs prior 7d as default)
- Organic sessions delta, top/bottom pages
- Anomaly flag when `detect_anomalies` returns a result

**Differentiators:**
- Auto-select the period containing the detected anomaly
- Color-highlight on anomaly rows

**Anti-feature:** Do not show full Metrika funnel charts on mobile; link to desktop analytics workspace.

**Backend reuse:** `traffic_analysis_service.detect_anomalies`, `analyze_traffic_sources`, existing Metrika data endpoints.

---

### App 6: Pages (Audit + Approve Queue)

**Table stakes:**
- List of pages pending approval from audit fix queue
- Per-page: title, URL, fix type (title/meta/schema/TOC), diff preview
- Approve / Reject buttons
- Batch approve selected

**Differentiators:**
- Swipe right = approve, swipe left = reject (~10 lines vanilla JS for touchstart/touchend)
- Quick inline fix editor for title/meta (single input, POST, HTMX partial reload)

**Anti-feature:** Do not support schema.org editing on mobile — too complex for a small screen; push to desktop.

**Backend reuse:** `list_checks`, `fix_apply_and_approve`, `fix_preview` in `audit.py` router all exist.

---

### App 7: Quick Task

**Table stakes:**
- Title input + site selector + priority picker (High/Med/Low)
- Optional description (collapsible textarea)
- Submit with confirmation toast

**Differentiators:**
- "From this site" context pre-fill when opened from site health card
- Copywriter brief shortcut: one-tap creates brief task with template pre-filled from site context

**Anti-feature:** No task assignment, due date picker, or file attachment on mobile — desktop only.

**Backend reuse:** `tasks.py` router for task creation + `brief_service` for brief shortcut.

---

### App 8: Tools

**Table stakes:**
- List of 6 tools from `TOOL_REGISTRY` with name, description, last run status
- "Run" button per tool with minimal parameter form (1–2 inputs)
- Job progress indicator while tool runs
- Results preview (top 5 rows; "Full results →" link to desktop)

**Differentiators:**
- Recent runs list per tool (last 3 runs with timestamps)
- "Copy result" button for single-value outputs (meta tags, URL suggestions)

**Anti-feature:** Do not render full results tables on mobile — too wide; show summary only.

**Backend reuse:** `tool_landing`, `tool_submit`, `tool_job_status`, `tool_results` in `tools.py` router all exist.

---

### App 9: Telegram Bot

**Table stakes:**
- /start — welcome message + command list
- /status — system health (DB ping, Redis ping, Celery worker alive, last crawl timestamp)
- /logs — last 50 lines of app.log formatted as code block (split into multiple messages if content exceeds 4096 chars)
- /digest — call `morning_digest_service` and send result to chat
- Authentication: restrict ALL commands to allowlist of chat_ids (`TELEGRAM_ALLOWED_CHAT_IDS` env var)

**Differentiators:**
- /test — run smoke test suite (`smoke_tasks.py`), return pass/fail summary
- /deploy — git pull + `docker compose up -d --build` with inline keyboard confirmation; log to audit_log; admin chat_id only
- /report [site_name] — generate and send PDF report for named site
- Inline keyboard confirmation on every destructive command

**Anti-feature:** Do not make the bot a full CRUD API. 6–8 commands maximum. Link to WebApp for data operations.

**Implementation:**
- python-telegram-bot 21 `Application` with webhook (not polling) in production
- Webhook registered at `/telegram/webhook/{SECRET_TOKEN}`
- `Application` started inside FastAPI lifespan (shared event loop)
- Commands registered with `setMyCommands` on startup

---

### App 10: Telegram WebApp Wrapper

**Table stakes:**
- Each mobile app accessible as a Telegram WebApp button in the bot
- `Telegram.WebApp.ready()` called on load; `expand()` for full height
- `themeParams` sync: CSS custom properties set from `Telegram.WebApp.themeParams` object
- JWT auth bridge: validate `initData` with HMAC-SHA-256 against bot token; issue short-lived JWT

**Differentiators:**
- `MainButton` replaces bottom CTA for primary actions (e.g., "Approve All", "Run Check", "Send Report")
- `HapticFeedback.notificationOccurred('success')` on approve and send actions
- `ClosingConfirmation` enabled on Pages app approve queue to guard against accidental close mid-review

**Anti-feature:** Do not use Telegram Payments or Stars — internal tool with no monetization layer.

**Technical constraint:** `sendData()` maximum 4096 bytes; use only for simple confirmations; use server-side endpoints for all data operations.

---

## MVP Definition

### Launch With (Phase 1 — Mobile Foundation)

Minimum required for any other app to function:

- [ ] `base_mobile.html` with bottom navigation, site switcher, Telegram WebApp script — prerequisite for everything
- [ ] `/m/` route prefix with auth middleware
- [ ] Digest app — morning summary cards (zero new backend work)
- [ ] Site health card — status aggregate (zero new backend work)
- [ ] Positions app — rankings list with delta badges + trigger check button

### Add In Phase 2 — Action Apps

- [ ] Pages app — audit list + swipe-to-approve
- [ ] Quick task — mobile task creation
- [ ] Client report app — generate PDF + send via Telegram
- [ ] Traffic comparison app — period comparison with anomaly highlight
- [ ] Tools app — launch tools + poll results

### Add In Phase 3 — Telegram Layer

- [ ] Telegram bot — /status, /logs, /digest, /test commands
- [ ] Telegram WebApp — wrap mobile app URLs as WebApp buttons in bot
- [ ] Telegram bot — /deploy with confirmation keyboard (implement after /status is stable)
- [ ] Claude Code agent channel — after all other bot commands are stable and tested

### Defer to v5.0

- [ ] Personalized mobile dashboard layouts
- [ ] Offline/PWA mode
- [ ] Full keyword management on mobile

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `base_mobile.html` + `/m/` routing | HIGH | LOW | P1 |
| Telegram WebApp script in base template | HIGH | LOW | P1 |
| Digest app | HIGH | LOW | P1 |
| Site health card | HIGH | LOW | P1 |
| Positions app (view + trigger) | HIGH | MEDIUM | P1 |
| Pages app (approve queue + swipe) | HIGH | MEDIUM | P1 |
| Quick task creation | MEDIUM | LOW | P1 |
| Client report app (PDF + Telegram send) | HIGH | MEDIUM | P1 |
| Traffic comparison app | MEDIUM | MEDIUM | P2 |
| Tools app (mobile launch) | MEDIUM | MEDIUM | P2 |
| Telegram bot /status + /logs | HIGH | MEDIUM | P1 |
| Telegram bot /deploy (with confirm) | MEDIUM | HIGH | P2 |
| Telegram WebApp wrapping | MEDIUM | MEDIUM | P2 |
| Claude Code agent channel | MEDIUM | HIGH | P3 |

**Priority key:** P1 = must have for milestone; P2 = strong value, include in same milestone; P3 = exploratory, separate phase or spike

---

## Complexity Summary by App

| App | Backend Work | Frontend Work | New Infrastructure | Overall |
|-----|-------------|---------------|-------------------|---------|
| Digest | None (service exists) | 1 mobile template | None | LOW |
| Positions | None (endpoints exist) | 2 templates + 5s poll | None | LOW-MEDIUM |
| Client Report | Thin orchestration endpoint | 1 template | None | LOW |
| Site Health Card | Aggregate endpoint | 1 template + SVG sparkline | None | LOW |
| Traffic Comparison | None (service exists) | 1 template | None | LOW-MEDIUM |
| Pages (approve queue) | None (endpoint exists) | 2 templates + swipe JS | None | MEDIUM |
| Quick Task | None (endpoint exists) | 1 template | None | LOW |
| Tools | None (endpoints exist) | 2 templates | None | MEDIUM |
| Telegram Bot | python-telegram-bot 21 App | N/A | Webhook route, startup registration | MEDIUM |
| Telegram WebApp | initData auth bridge | CSS vars + WebApp.js | None | MEDIUM |
| Claude Code channel | Subprocess management, MCP server | N/A | Claude Code on VPS, API key | HIGH |

---

## Sources

- Telegram Mini Apps official API docs: https://core.telegram.org/bots/webapps (HIGH confidence — official)
- Telegram Mini App native UX guide: https://turumburum.com/blog/telegram-mini-app-beyond-the-standard-ui-designing-a-truly-native-experience (MEDIUM confidence — community)
- claude-code-telegram integration: https://github.com/RichardAtCT/claude-code-telegram (MEDIUM confidence — open source project)
- Claude Code channels docs: https://code.claude.com/docs/en/channels (HIGH confidence — official Anthropic)
- python-telegram-bot v21 inline keyboard docs: https://docs.python-telegram-bot.org/en/v21.9/telegram.inlinekeyboardbutton.html (HIGH confidence — official)
- Docker Telegram bot command patterns: https://medium.com/@satish.verma/managing-docker-containers-with-telegram-bot-a-devops-automation-tool-699c34d11a29 (LOW confidence — community)
- Mobile UX patterns (swipe, pull-to-refresh, bottom nav): https://procreator.design/blog/mobile-app-design-patterns-boost-retention/ (MEDIUM confidence — community)
- SEMrush mobile position tracking: https://www.semrush.com/news/271383-position-tracking-on-the-go/ (MEDIUM confidence — competitor)
- Platform internals: `/opt/seo-platform/app/routers/` and `/opt/seo-platform/app/services/` — direct code inspection (HIGH confidence)

---

*Feature research for: v4.0 Mobile focus apps + Telegram bot*
*Researched: 2026-04-10*
