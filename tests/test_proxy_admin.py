"""Tests for the proxy admin router endpoints."""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.proxy import Proxy, ProxyStatus, ProxyType  # noqa: F401
from app.models.service_credential import ServiceCredential  # noqa: F401
from app.services.service_credential_service import get_credential_sync


# ---------------------------------------------------------------------------
# Sync SQLite fixture (shared across tests in a module-level engine)
# ---------------------------------------------------------------------------

SYNC_TEST_URL = "sqlite:///:memory:"


@pytest.fixture()
def sync_db() -> Generator[Session, None, None]:
    """In-memory SQLite sync session with Proxy + ServiceCredential tables."""
    engine = create_engine(SYNC_TEST_URL, echo=False, connect_args={"check_same_thread": False})
    Base.metadata.create_all(
        engine,
        tables=[Proxy.__table__, ServiceCredential.__table__],
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@contextmanager
def _make_sync_db_ctx(session: Session):
    """Context manager that yields the given session (no-op commit/rollback)."""
    try:
        yield session
    except Exception:
        session.rollback()
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_sync_db(session: Session):
    """Return a patch context for app.database.get_sync_db using *session*."""
    return patch(
        "app.routers.proxy_admin.get_sync_db",
        lambda: _make_sync_db_ctx(session),
    )


# ---------------------------------------------------------------------------
# Tests: Proxy CRUD
# ---------------------------------------------------------------------------


def test_create_proxy(sync_db: Session) -> None:
    """POST /admin/proxies creates a Proxy in DB."""
    from app.routers.proxy_admin import create_proxy

    from unittest.mock import MagicMock
    request = MagicMock()
    request.url.path = "/admin/proxies"

    with _patch_sync_db(sync_db):
        # Import after patching to pick up the mock
        import app.routers.proxy_admin as mod
        original = mod.get_sync_db
        mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
        try:
            mod.create_proxy(request, url="http://proxy.example.com:8080", proxy_type="http")
        finally:
            mod.get_sync_db = original

    proxy = sync_db.query(Proxy).filter_by(url="http://proxy.example.com:8080").first()
    assert proxy is not None
    assert proxy.proxy_type == ProxyType.http
    assert proxy.status == ProxyStatus.unchecked


def test_update_proxy(sync_db: Session) -> None:
    """PUT /admin/proxies/{id} updates proxy URL and type in DB."""
    import app.routers.proxy_admin as mod
    from unittest.mock import MagicMock

    # Seed a proxy
    proxy = Proxy(url="http://old.example.com:3128", proxy_type=ProxyType.http)
    sync_db.add(proxy)
    sync_db.commit()
    proxy_id = str(proxy.id)

    request = MagicMock()
    request.url.path = f"/admin/proxies/{proxy_id}"

    original = mod.get_sync_db
    mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
    try:
        mod.update_proxy(
            proxy_id,
            request,
            url="socks5://new.example.com:1080",
            proxy_type="socks5",
        )
    finally:
        mod.get_sync_db = original

    sync_db.expire(proxy)
    updated = sync_db.get(Proxy, proxy.id)
    assert updated.url == "socks5://new.example.com:1080"
    assert updated.proxy_type == ProxyType.socks5


def test_delete_proxy(sync_db: Session) -> None:
    """DELETE /admin/proxies/{id} removes proxy from DB."""
    import app.routers.proxy_admin as mod

    proxy = Proxy(url="http://todelete.example.com:8080", proxy_type=ProxyType.http)
    sync_db.add(proxy)
    sync_db.commit()
    proxy_id = str(proxy.id)

    original = mod.get_sync_db
    mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
    try:
        mod.delete_proxy(proxy_id)
    finally:
        mod.get_sync_db = original

    assert sync_db.get(Proxy, proxy.id) is None


# ---------------------------------------------------------------------------
# Tests: Credentials
# ---------------------------------------------------------------------------


def test_save_xmlproxy_credentials(sync_db: Session) -> None:
    """POST /admin/proxies/credentials/xmlproxy saves credentials to DB."""
    import app.routers.proxy_admin as mod

    original = mod.get_sync_db
    mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
    try:
        mod.save_xmlproxy_credentials(user="myuser", key="mykey")
    finally:
        mod.get_sync_db = original

    result = get_credential_sync(sync_db, "xmlproxy")
    assert result is not None
    assert result["user"] == "myuser"
    assert result["key"] == "mykey"


def test_save_rucaptcha_credentials(sync_db: Session) -> None:
    """POST /admin/proxies/credentials/rucaptcha saves rucaptcha key."""
    import app.routers.proxy_admin as mod

    original = mod.get_sync_db
    mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
    try:
        mod.save_rucaptcha_credentials(key="rucaptcha_api_key_123")
    finally:
        mod.get_sync_db = original

    result = get_credential_sync(sync_db, "rucaptcha")
    assert result is not None
    assert result["key"] == "rucaptcha_api_key_123"


def test_save_anticaptcha_credentials(sync_db: Session) -> None:
    """POST /admin/proxies/credentials/anticaptcha saves anticaptcha key."""
    import app.routers.proxy_admin as mod

    original = mod.get_sync_db
    mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
    try:
        mod.save_anticaptcha_credentials(key="anticaptcha_key_xyz")
    finally:
        mod.get_sync_db = original

    result = get_credential_sync(sync_db, "anticaptcha")
    assert result is not None
    assert result["key"] == "anticaptcha_key_xyz"


# ---------------------------------------------------------------------------
# Tests: Balance endpoints
# ---------------------------------------------------------------------------


def test_xmlproxy_balance_not_configured(sync_db: Session) -> None:
    """GET /admin/proxies/xmlproxy-balance returns error when no credentials."""
    import app.routers.proxy_admin as mod

    original = mod.get_sync_db
    mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
    try:
        response = mod.get_xmlproxy_balance()
    finally:
        mod.get_sync_db = original

    assert response.status_code == 200
    import json
    data = json.loads(response.body)
    assert "error" in data
    assert data["error"] == "not configured"


def test_xmlproxy_balance_configured(sync_db: Session) -> None:
    """GET /admin/proxies/xmlproxy-balance returns balance when credentials exist."""
    import app.routers.proxy_admin as mod

    # Save credentials first
    from app.services.service_credential_service import save_credential_sync
    save_credential_sync(sync_db, "xmlproxy", {"user": "testuser", "key": "testkey"})

    original_db = mod.get_sync_db
    mod.get_sync_db = lambda: _make_sync_db_ctx(sync_db)
    try:
        with patch(
            "app.routers.proxy_admin.fetch_balance_sync",
            return_value={"data": 5.0, "cur_cost": 0.01, "max_cost": 10.0},
        ):
            response = mod.get_xmlproxy_balance()
    finally:
        mod.get_sync_db = original_db

    import json
    data = json.loads(response.body)
    assert data["balance"] == 5.0
    assert data["cur_cost"] == 0.01
    assert data["max_cost"] == 10.0
