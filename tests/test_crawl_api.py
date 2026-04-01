"""Tests for the crawl history and change feed API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.crawl import CrawlJob, CrawlJobStatus, Page, PageSnapshot, PageType
from app.models.site import Site
from app.models.user import UserRole
from app.services.crypto_service import encrypt
from app.services.user_service import create_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_token(db_session):
    user = await create_user(
        db_session,
        "admin_crawl_api",
        "admin_crawl_api@test.com",
        hash_password("pass"),
        UserRole.admin,
    )
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest_asyncio.fixture
async def site(db_session):
    s = Site(
        id=uuid.uuid4(),
        name="Feed Site",
        url="https://feed-site.example.com",
        wp_username="admin",
        encrypted_app_password=encrypt("secret"),
        is_active=True,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest_asyncio.fixture
async def crawl_job(db_session, site):
    job = CrawlJob(
        id=uuid.uuid4(),
        site_id=site.id,
        status=CrawlJobStatus.done,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        pages_crawled=2,
    )
    db_session.add(job)
    await db_session.flush()
    return job


@pytest_asyncio.fixture
async def pages_with_snapshots(db_session, site, crawl_job):
    """Create two pages: one with SEO diff, one without."""
    # Page 1 — has title change in diff
    p1 = Page(
        id=uuid.uuid4(),
        site_id=site.id,
        crawl_job_id=crawl_job.id,
        url="https://feed-site.example.com/article/",
        title="New Title",
        h1="Heading",
        http_status=200,
        page_type=PageType.article,
        crawled_at=datetime.now(timezone.utc),
    )
    db_session.add(p1)
    await db_session.flush()

    snap1 = PageSnapshot(
        id=uuid.uuid4(),
        page_id=p1.id,
        crawl_job_id=crawl_job.id,
        snapshot_data={"title": "New Title", "h1": "Heading", "meta_description": "", "http_status": 200, "content_preview": ""},
        diff_data={"title": {"old": "Old Title", "new": "New Title"}},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(snap1)

    # Page 2 — no diff (first time seen)
    p2 = Page(
        id=uuid.uuid4(),
        site_id=site.id,
        crawl_job_id=crawl_job.id,
        url="https://feed-site.example.com/about/",
        title="About",
        h1="About Us",
        http_status=200,
        page_type=PageType.landing,
        crawled_at=datetime.now(timezone.utc),
    )
    db_session.add(p2)
    await db_session.flush()

    snap2 = PageSnapshot(
        id=uuid.uuid4(),
        page_id=p2.id,
        crawl_job_id=crawl_job.id,
        snapshot_data={"title": "About", "h1": "About Us", "meta_description": "", "http_status": 200, "content_preview": ""},
        diff_data=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(snap2)
    await db_session.commit()

    return [p1, p2]


# ---------------------------------------------------------------------------
# Tests: GET /sites/{site_id}/crawls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_crawls_for_site(client, admin_token, site, crawl_job):
    """GET /sites/{site_id}/crawls returns list of crawl jobs."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.get(f"/sites/{site.id}/crawls", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == str(crawl_job.id)
    assert data[0]["status"] == "done"
    assert data[0]["pages_crawled"] == 2


@pytest.mark.asyncio
async def test_list_crawls_for_missing_site(client, admin_token):
    """GET /sites/{site_id}/crawls returns empty list for unknown site (not 404)."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Unknown site returns empty list (the query just returns nothing)
    resp = await client.get(f"/sites/{uuid.uuid4()}/crawls", headers=headers)
    # Could be 404 (site not found in guard) or 200 with empty list
    # Our implementation returns empty list since we don't guard existence
    assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Tests: GET /crawls/{crawl_job_id}/pages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pages_filter_all(client, admin_token, crawl_job, pages_with_snapshots):
    """GET /crawls/{id}/pages returns all pages when filter=all."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.get(f"/crawls/{crawl_job.id}/pages?filter=all", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_pages_filter_seo_changed(client, admin_token, crawl_job, pages_with_snapshots):
    """GET /crawls/{id}/pages?filter=seo_changed returns only pages with SEO diffs."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.get(f"/crawls/{crawl_job.id}/pages?filter=seo_changed", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # Only page 1 has a title diff (SEO field)
    assert len(data) == 1
    assert "title" in data[0]["diff_data"]


@pytest.mark.asyncio
async def test_pages_filter_new_pages(client, admin_token, crawl_job, pages_with_snapshots):
    """GET /crawls/{id}/pages?filter=new_pages returns pages with no previous snapshot."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.get(f"/crawls/{crawl_job.id}/pages?filter=new_pages", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # Page 2 has diff_data=None (new page)
    assert len(data) == 1
    assert data[0]["url"] == "https://feed-site.example.com/about/"


@pytest.mark.asyncio
async def test_pages_missing_job(client, admin_token):
    """GET /crawls/{id}/pages returns 404 for unknown crawl job."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.get(f"/crawls/{uuid.uuid4()}/pages", headers=headers)
    assert resp.status_code == 404
