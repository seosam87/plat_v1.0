# Milestones

## v1.0 MVP (Shipped: 2026-04-06)

**Timeline:** 2026-03-31 — 2026-04-06 (6 days)
**Scope:** 16 phases, 427 commits, 559 files, 35,402 LOC Python

**Key accomplishments:**

- Full Docker Compose stack (FastAPI 0.115 + PostgreSQL 16 + Redis 7 + Celery 5.4 + redbeat) with JWT auth, 3 roles, audit logging
- WordPress site management with Fernet-encrypted credentials, Playwright crawler with snapshot diffs and change feed
- Keyword import (Topvisor/KC/SF), position tracking with monthly-partitioned table, XMLProxy integration for Yandex SERP
- Semantic clustering (SERP intersection), cannibalization detection, keyword-to-page mapping with auto-task creation
- WP content pipeline: TOC generation, schema.org injection, internal linking, mandatory diff approval, rollback
- SEO projects with Kanban board, content plan, one-click WP draft, WeasyPrint PDF briefs
- Dashboard with cross-project aggregation, PDF/Excel reports, scheduled Telegram/SMTP delivery, ad traffic module
- Rate limiting, RBAC audit, client invite links, health endpoint, Flower, HTTPS via Nginx, full README
- Sidebar UI overhaul (v4.0): 6-section navigation, Tailwind CSS migration across 35+ templates, smoke test agent
- Yandex Metrika integration, content audit engine, change monitoring with weekly digests, analytics workspace, gap analysis, site architecture, traffic analysis

**Known gaps (deferred to v2.0):**

- VIS-02: Dark mode toggle not implemented
- MIG-01/02/03: Formal migration audit (page regrouping, 301 redirects, HTMX audit) not performed

**Archives:** [ROADMAP](milestones/v1.0-ROADMAP.md) | [REQUIREMENTS](milestones/v1.0-REQUIREMENTS.md) | [AUDIT](milestones/v1.0-MILESTONE-AUDIT.md)

---
