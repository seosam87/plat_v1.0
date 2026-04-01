"""Tests for crawler_service and the crawl trigger API endpoint."""
import uuid

import pytest
import pytest_asyncio
import respx
from httpx import ConnectError, Response

from app.services.crawler_service import classify_page_type, parse_sitemap


@pytest_asyncio.fixture
async def admin_token(db_session):
    from app.auth.jwt import create_access_token
    from app.auth.password import hash_password
    from app.models.user import UserRole
    from app.services.user_service import create_user

    user = await create_user(
        db_session, "admin_crawl", "admin_crawl@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about/</loc></url>
  <url><loc>https://example.com/blog/post-1/</loc></url>
</urlset>"""


# ---------------------------------------------------------------------------
# parse_sitemap
# ---------------------------------------------------------------------------

@respx.mock
def test_parse_sitemap_returns_urls():
    """parse_sitemap extracts all <loc> URLs from a valid sitemap."""
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=Response(200, text=SITEMAP_XML, headers={"content-type": "application/xml"})
    )
    urls = parse_sitemap("https://example.com")
    assert "https://example.com/" in urls
    assert "https://example.com/about/" in urls
    assert "https://example.com/blog/post-1/" in urls
    assert len(urls) == 3


@respx.mock
def test_parse_sitemap_empty_on_connect_error():
    """parse_sitemap returns [] when a ConnectError is raised."""
    respx.get("https://unreachable.example/sitemap.xml").mock(side_effect=ConnectError("refused"))
    urls = parse_sitemap("https://unreachable.example")
    assert urls == []


@respx.mock
def test_parse_sitemap_empty_on_http_error():
    """parse_sitemap returns [] on a non-2xx response."""
    respx.get("https://example.com/sitemap.xml").mock(return_value=Response(404))
    urls = parse_sitemap("https://example.com")
    assert urls == []


# ---------------------------------------------------------------------------
# classify_page_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url, h1, expected",
    [
        ("https://example.com/category/news/", "", "category"),
        ("https://example.com/tag/python/", "", "category"),
        ("https://example.com/product/widget/", "", "product"),
        ("https://example.com/shop/widget/", "Buy now and save", "product"),
        ("https://example.com/", "", "landing"),
        ("https://example.com", "", "landing"),
        ("https://example.com/blog/my-post/", "A Great Post", "article"),
    ],
)
def test_classify_page_type(url, h1, expected):
    assert classify_page_type(url, h1) == expected


# ---------------------------------------------------------------------------
# POST /sites/{site_id}/crawl endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_crawl_job(client, db_session, admin_token):
    """POST /sites/{site_id}/crawl returns 202 with task_id for a real site."""
    from app.models.site import Site
    from app.services.crypto_service import encrypt

    # Create a site so the endpoint finds it
    site = Site(
        id=uuid.uuid4(),
        name="Test Site",
        url="https://test-crawl.example.com",
        wp_username="admin",
        encrypted_app_password=encrypt("secret"),
        is_active=True,
    )
    db_session.add(site)
    await db_session.commit()

    # Patch crawl_site.delay to avoid actually dispatching a Celery task
    import unittest.mock as mock
    fake_task = mock.MagicMock()
    fake_task.id = "fake-task-id-1234"

    headers = {"Authorization": f"Bearer {admin_token}"}
    with mock.patch("app.routers.sites._crawl_site_task") as mock_task:
        mock_task.delay.return_value = fake_task
        resp = await client.post(f"/sites/{site.id}/crawl", headers=headers)

    assert resp.status_code == 202
    data = resp.json()
    assert "task_id" in data
    assert data["site_id"] == str(site.id)


@pytest.mark.asyncio
async def test_create_crawl_job_missing_site(client, db_session, admin_token):
    """POST /sites/{site_id}/crawl returns 404 when site does not exist."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.post(f"/sites/{uuid.uuid4()}/crawl", headers=headers)
    assert resp.status_code == 404
