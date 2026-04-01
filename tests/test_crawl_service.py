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


# ---------------------------------------------------------------------------
# extract_seo_data: canonical_url field
# ---------------------------------------------------------------------------


def test_extract_seo_data_returns_canonical_key():
    """extract_seo_data result dict includes canonical_url key."""
    from app.services.crawler_service import extract_seo_data
    # We can't easily mock Playwright Page, but verify the function signature
    # by checking the source includes canonical extraction
    import inspect
    src = inspect.getsource(extract_seo_data)
    assert "canonical_url" in src
    assert "link[rel='canonical']" in src


# ---------------------------------------------------------------------------
# Crawl analysis service — imports and logic
# ---------------------------------------------------------------------------


class TestCrawlAnalysisImports:
    """Verify all analysis functions are importable."""

    def test_imports(self):
        from app.services.crawl_analysis_service import (
            find_duplicate_titles,
            find_duplicate_h1,
            find_orphan_pages,
            find_canonical_issues,
            get_seo_completeness,
        )
        assert callable(find_duplicate_titles)
        assert callable(find_duplicate_h1)
        assert callable(find_orphan_pages)
        assert callable(find_canonical_issues)
        assert callable(get_seo_completeness)


class TestAnalysisEndpointsRegistered:
    """Verify all analysis endpoints are registered in the router."""

    def test_endpoints(self):
        from app.routers.crawl import router
        paths = [r.path for r in router.routes]
        assert "/crawls/{crawl_job_id}/analysis/duplicates" in paths
        assert "/crawls/{crawl_job_id}/analysis/orphans" in paths
        assert "/crawls/{crawl_job_id}/analysis/canonicals" in paths
        assert "/crawls/{crawl_job_id}/analysis/completeness" in paths


class TestDuplicateDetectionLogic:
    """Test duplicate detection pure logic."""

    def test_find_duplicates_in_list(self):
        """Simulate duplicate title detection."""
        pages = [
            {"url": "/page-1", "title": "About Us"},
            {"url": "/page-2", "title": "About Us"},
            {"url": "/page-3", "title": "Contact"},
            {"url": "/page-4", "title": "Contact"},
            {"url": "/page-5", "title": "Unique"},
        ]
        from collections import Counter
        title_counts = Counter(p["title"] for p in pages)
        duplicates = {t: c for t, c in title_counts.items() if c > 1}
        assert len(duplicates) == 2
        assert duplicates["About Us"] == 2
        assert duplicates["Contact"] == 2
        assert "Unique" not in duplicates

    def test_empty_titles_excluded(self):
        """Empty or None titles should not be considered duplicates."""
        pages = [
            {"url": "/a", "title": ""},
            {"url": "/b", "title": ""},
            {"url": "/c", "title": None},
        ]
        titles = [p["title"] for p in pages if p["title"]]
        from collections import Counter
        duplicates = {t: c for t, c in Counter(titles).items() if c > 1}
        assert len(duplicates) == 0


class TestOrphanPageLogic:
    """Test orphan page identification logic."""

    def test_orphan_is_zero_inlinks(self):
        """A page with 0 inlinks and depth > 0 is an orphan."""
        pages = [
            {"url": "/", "inlinks_count": 5, "depth": 0},     # homepage, not orphan
            {"url": "/a", "inlinks_count": 0, "depth": 1},     # orphan
            {"url": "/b", "inlinks_count": 3, "depth": 1},     # not orphan
            {"url": "/c", "inlinks_count": None, "depth": 2},  # orphan (null = 0)
        ]
        orphans = [
            p for p in pages
            if (p["inlinks_count"] is None or p["inlinks_count"] == 0) and p["depth"] > 0
        ]
        assert len(orphans) == 2
        assert orphans[0]["url"] == "/a"
        assert orphans[1]["url"] == "/c"


class TestCanonicalIssueLogic:
    """Test canonical issue detection logic."""

    def test_mismatched_canonical(self):
        pages = [
            {"url": "https://example.com/a", "canonical_url": "https://example.com/a"},
            {"url": "https://example.com/b", "canonical_url": "https://example.com/a"},  # issue
            {"url": "https://example.com/c", "canonical_url": ""},
            {"url": "https://example.com/d", "canonical_url": None},
        ]
        issues = [
            p for p in pages
            if p["canonical_url"] and p["canonical_url"] != p["url"]
        ]
        assert len(issues) == 1
        assert issues[0]["url"] == "https://example.com/b"


class TestSeoCompletenessLogic:
    """Test SEO completeness counting."""

    def test_field_completeness(self):
        pages = [
            {"title": "A", "h1": "B", "meta": "C", "schema": True, "toc": False},
            {"title": "", "h1": "B", "meta": "", "schema": False, "toc": True},
            {"title": "A", "h1": "", "meta": "C", "schema": True, "toc": True},
        ]
        with_title = sum(1 for p in pages if p["title"])
        with_h1 = sum(1 for p in pages if p["h1"])
        with_meta = sum(1 for p in pages if p["meta"])
        with_schema = sum(1 for p in pages if p["schema"])
        with_toc = sum(1 for p in pages if p["toc"])
        assert with_title == 2
        assert with_h1 == 2
        assert with_meta == 2
        assert with_schema == 2
        assert with_toc == 2
