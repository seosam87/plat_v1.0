import uuid

import httpx
import pytest
import respx

from app.models.site import ConnectionStatus, Site
from app.services.crypto_service import encrypt
from app.services.wp_service import detect_seo_plugin, verify_connection


def _make_site(url: str = "https://example.com") -> Site:
    site = Site()
    site.id = uuid.uuid4()
    site.url = url
    site.wp_username = "admin"
    site.encrypted_app_password = encrypt("secret")
    site.seo_plugin = "unknown"
    return site


@respx.mock
async def test_verify_connected():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/users/me").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(200, json=[{"id": 10, "title": "Hello"}])
    )
    status, plugin = await verify_connection(site)
    assert status == ConnectionStatus.connected
    assert plugin == "unknown"


@respx.mock
async def test_verify_failed_non_200():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/users/me").mock(
        return_value=httpx.Response(401)
    )
    status, plugin = await verify_connection(site)
    assert status == ConnectionStatus.failed


@respx.mock
async def test_verify_failed_network_error():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/users/me").mock(
        side_effect=httpx.ConnectError("refused")
    )
    status, plugin = await verify_connection(site)
    assert status == ConnectionStatus.failed


# --- SEO plugin detection tests ---


@respx.mock
async def test_detect_yoast():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "yoast_head": "<meta ...>"}])
    )
    async with httpx.AsyncClient() as client:
        result = await detect_seo_plugin(client, site, "Basic xxx")
    assert result == "yoast"


@respx.mock
async def test_detect_yoast_json():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "yoast_head_json": {}}])
    )
    async with httpx.AsyncClient() as client:
        result = await detect_seo_plugin(client, site, "Basic xxx")
    assert result == "yoast"


@respx.mock
async def test_detect_rankmath():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "rank_math_title": "Test"}])
    )
    async with httpx.AsyncClient() as client:
        result = await detect_seo_plugin(client, site, "Basic xxx")
    assert result == "rankmath"


@respx.mock
async def test_detect_no_plugin():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "title": "Plain post"}])
    )
    async with httpx.AsyncClient() as client:
        result = await detect_seo_plugin(client, site, "Basic xxx")
    assert result == "unknown"


@respx.mock
async def test_detect_no_posts():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(200, json=[])
    )
    async with httpx.AsyncClient() as client:
        result = await detect_seo_plugin(client, site, "Basic xxx")
    assert result == "unknown"


@respx.mock
async def test_detect_api_error():
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(403)
    )
    async with httpx.AsyncClient() as client:
        result = await detect_seo_plugin(client, site, "Basic xxx")
    assert result == "unknown"


@respx.mock
async def test_verify_connected_detects_yoast():
    """verify_connection should return detected plugin on success."""
    site = _make_site()
    respx.get(f"{site.url}/wp-json/wp/v2/users/me").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    respx.get(f"{site.url}/wp-json/wp/v2/posts?per_page=1").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "yoast_head": "<meta>"}])
    )
    status, plugin = await verify_connection(site)
    assert status == ConnectionStatus.connected
    assert plugin == "yoast"
