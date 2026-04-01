import uuid

import httpx
import pytest
import respx

from app.models.site import ConnectionStatus, Site
from app.services.crypto_service import encrypt
from app.services.wp_service import verify_connection


def _make_site(url: str = "https://example.com") -> Site:
    site = Site()
    site.id = uuid.uuid4()
    site.url = url
    site.wp_username = "admin"
    site.encrypted_app_password = encrypt("secret")
    return site


@respx.mock
async def test_verify_connected():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/users/me").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    result = await verify_connection(site)
    assert result == ConnectionStatus.connected


@respx.mock
async def test_verify_failed_non_200():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/users/me").mock(
        return_value=httpx.Response(401)
    )
    result = await verify_connection(site)
    assert result == ConnectionStatus.failed


@respx.mock
async def test_verify_failed_network_error():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/users/me").mock(
        side_effect=httpx.ConnectError("refused")
    )
    result = await verify_connection(site)
    assert result == ConnectionStatus.failed
