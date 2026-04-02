"""Unit tests for proxy health service."""
import httpx
import respx

from app.services.proxy_health_service import check_proxy_sync, HEALTH_CHECK_URL


@respx.mock
def test_active_proxy():
    """HTTP proxy that returns 200 is reported as active with a positive ms."""
    respx.get(HEALTH_CHECK_URL).mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow:")
    )
    status, ms = check_proxy_sync("http://proxy.example.com:8080")
    assert status == "active"
    assert isinstance(ms, int)
    assert ms >= 0


@respx.mock
def test_dead_proxy():
    """Proxy that raises a connection error is reported as dead."""
    respx.get(HEALTH_CHECK_URL).mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    status, ms = check_proxy_sync("http://dead.proxy:9999")
    assert status == "dead"
    assert ms is None
