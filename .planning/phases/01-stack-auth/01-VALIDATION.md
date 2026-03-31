---
phase: 1
slug: stack-auth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio + httpx AsyncClient |
| **Config file** | `pyproject.toml` — `asyncio_mode = "auto"` |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01-01 | 1 | INFRA-01 | integration | `docker compose up --build -d && docker compose ps` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01-01 | 1 | INFRA-07 | integration | `docker compose config \| grep CELERY_WORKER_CONCURRENCY` | ❌ W0 | ⬜ pending |
| 1-02-01 | 01-02 | 2 | AUTH-01 | unit | `pytest tests/test_auth.py::test_login_returns_token -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 01-02 | 2 | AUTH-01 | unit | `pytest tests/test_auth.py::test_expired_token_rejected -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 01-02 | 2 | SEC-01 | unit | `pytest tests/test_auth.py::test_password_hashed_with_bcrypt -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 01-03 | 3 | AUTH-02 | unit | `pytest tests/test_users.py::test_admin_can_create_user -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 01-03 | 3 | SEC-04 | unit | `pytest tests/test_rbac.py::test_manager_cannot_access_admin_endpoint -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 01-03 | 3 | SEC-04 | unit | `pytest tests/test_rbac.py::test_service_layer_role_check -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 01-04 | 4 | AUTH-05 | unit | `pytest tests/test_audit.py::test_login_creates_audit_entry -x` | ❌ W0 | ⬜ pending |
| 1-04-02 | 01-04 | 4 | INFRA-05 | unit | `pytest tests/test_logging.py::test_log_output_is_json -x` | ❌ W0 | ⬜ pending |
| 1-04-03 | 01-04 | 4 | SEC-03 | unit | `pytest tests/test_auth.py::test_jwt_expires_after_24h -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — async DB session fixture with per-test rollback isolation; `AsyncClient` fixture pointing at test app; test user fixtures for each role (admin, manager, client)
- [ ] `tests/test_auth.py` — stubs for: `test_login_returns_token`, `test_expired_token_rejected`, `test_password_hashed_with_bcrypt`, `test_jwt_expires_after_24h`
- [ ] `tests/test_users.py` — stubs for: `test_admin_can_create_user`, `test_admin_can_deactivate_user`
- [ ] `tests/test_rbac.py` — stubs for: `test_manager_cannot_access_admin_endpoint`, `test_client_cannot_access_manager_endpoint`, `test_service_layer_role_check`
- [ ] `tests/test_audit.py` — stubs for: `test_login_creates_audit_entry`, `test_user_creation_creates_audit_entry`
- [ ] `tests/test_logging.py` — stubs for: `test_log_output_is_json`
- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker-compose up --build` starts from scratch | INFRA-01 | Requires clean Docker state, not reproducible in pytest | Run `docker compose down -v && docker compose up --build`; verify all 5 containers reach healthy state |
| Three Celery queues routing verified in logs | INFRA-01 | Queue routing requires live Celery worker inspection | Run `docker compose exec celery celery -A app.celery_app inspect active_queues`; confirm `crawl`, `wp`, `default` appear |
| Redis appendonly and maxmemory policy | INFRA-01 | Redis config validation needs live Redis | Run `docker compose exec redis redis-cli config get appendonly`; confirm `yes` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
