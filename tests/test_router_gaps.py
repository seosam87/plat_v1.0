"""Integration tests covering router gaps: tasks PATCH/filter, sites GET/PUT/verify, crawl filters."""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.crawl import CrawlJob, CrawlJobStatus, Page, PageSnapshot, PageType
from app.models.task import SeoTask, TaskStatus, TaskType
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(
        db_session, "gap_admin", "gap@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def admin_user(db_session):
    user = await create_user(
        db_session, "gap_admin2", "gap2@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    return user


@pytest.fixture
async def site(db_session, admin_user):
    s = await create_site(
        db_session,
        name="Gap Test Site",
        url="https://gap.example.com",
        wp_username="admin",
        app_password="secret",
        actor_id=admin_user.id,
    )
    await db_session.flush()
    return s


# ---------------------------------------------------------------------------
# Tasks router: PATCH status + filtering
# ---------------------------------------------------------------------------


class TestTasksRouter:
    async def test_patch_task_status(self, client: AsyncClient, admin_token, db_session, site):
        task = SeoTask(
            site_id=site.id,
            task_type=TaskType.page_404,
            url="https://gap.example.com/missing",
            title="404: /missing",
        )
        db_session.add(task)
        await db_session.flush()

        resp = await client.patch(
            f"/tasks/{task.id}/status?new_status=resolved",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_patch_task_not_found(self, client: AsyncClient, admin_token):
        resp = await client.patch(
            f"/tasks/{uuid.uuid4()}/status?new_status=resolved",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_list_tasks_filter_by_status(self, client: AsyncClient, admin_token, db_session, site):
        t1 = SeoTask(site_id=site.id, task_type=TaskType.page_404, url="https://a.com/1", title="T1")
        t2 = SeoTask(
            site_id=site.id, task_type=TaskType.lost_indexation, url="https://a.com/2",
            title="T2", status=TaskStatus.resolved,
        )
        db_session.add_all([t1, t2])
        await db_session.flush()

        resp = await client.get(
            "/tasks?status=open",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["status"] == "open" for t in data)

    async def test_list_tasks_filter_by_site(self, client: AsyncClient, admin_token, db_session, site):
        t1 = SeoTask(site_id=site.id, task_type=TaskType.page_404, url="https://a.com/x", title="Site task")
        db_session.add(t1)
        await db_session.flush()

        resp = await client.get(
            f"/tasks?site_id={site.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(t["site_id"] == str(site.id) for t in data)


# ---------------------------------------------------------------------------
# Sites router: GET single, PUT update, verify
# ---------------------------------------------------------------------------


class TestSitesRouterGaps:
    async def test_get_single_site(self, client: AsyncClient, admin_token, site):
        resp = await client.get(
            f"/sites/{site.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Gap Test Site"

    async def test_get_single_site_not_found(self, client: AsyncClient, admin_token):
        resp = await client.get(
            f"/sites/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_update_site(self, client: AsyncClient, admin_token, site):
        resp = await client.put(
            f"/sites/{site.id}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_update_site_not_found(self, client: AsyncClient, admin_token):
        resp = await client.put(
            f"/sites/{uuid.uuid4()}",
            json={"name": "Nope"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    @patch("app.services.wp_service.verify_connection")
    async def test_verify_site_returns_badge(self, mock_verify, client: AsyncClient, admin_token, site):
        from app.models.site import ConnectionStatus

        mock_verify.return_value = (ConnectionStatus.connected, "unknown")
        resp = await client.post(
            f"/sites/{site.id}/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert "connected" in resp.text

    async def test_list_site_crawls(self, client: AsyncClient, admin_token, db_session, site):
        job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.done,
            started_at=datetime.now(timezone.utc),
            pages_crawled=5,
        )
        db_session.add(job)
        await db_session.flush()

        resp = await client.get(
            f"/sites/{site.id}/crawls",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["pages_crawled"] == 5


# ---------------------------------------------------------------------------
# Crawl router: content_changed and status_changed filters
# ---------------------------------------------------------------------------


class TestCrawlFilterGaps:
    @pytest.fixture
    async def crawl_data(self, db_session, site):
        """Create a crawl job with pages having various diff types."""
        job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.done,
            started_at=datetime.now(timezone.utc),
            pages_crawled=3,
        )
        db_session.add(job)
        await db_session.flush()

        # Page with content change
        p1 = Page(
            site_id=site.id, crawl_job_id=job.id, url="https://gap.example.com/content",
            http_status=200, depth=0, internal_link_count=0,
            page_type=PageType.article, has_toc=False, has_schema=False, has_noindex=False,
            crawled_at=datetime.now(timezone.utc),
        )
        # Page with status change
        p2 = Page(
            site_id=site.id, crawl_job_id=job.id, url="https://gap.example.com/status",
            http_status=404, depth=0, internal_link_count=0,
            page_type=PageType.article, has_toc=False, has_schema=False, has_noindex=False,
            crawled_at=datetime.now(timezone.utc),
        )
        # Page with no changes
        p3 = Page(
            site_id=site.id, crawl_job_id=job.id, url="https://gap.example.com/same",
            http_status=200, depth=0, internal_link_count=0,
            page_type=PageType.article, has_toc=False, has_schema=False, has_noindex=False,
            crawled_at=datetime.now(timezone.utc),
        )
        db_session.add_all([p1, p2, p3])
        await db_session.flush()

        s1 = PageSnapshot(
            page_id=p1.id, crawl_job_id=job.id,
            snapshot_data={"title": "T", "content_preview": "new text"},
            diff_data={"content_preview": {"old": "old text", "new": "new text"}},
            created_at=datetime.now(timezone.utc),
        )
        s2 = PageSnapshot(
            page_id=p2.id, crawl_job_id=job.id,
            snapshot_data={"title": "T", "http_status": 404},
            diff_data={"http_status": {"old": 200, "new": 404}},
            created_at=datetime.now(timezone.utc),
        )
        s3 = PageSnapshot(
            page_id=p3.id, crawl_job_id=job.id,
            snapshot_data={"title": "T"},
            diff_data={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add_all([s1, s2, s3])
        await db_session.flush()

        return job

    async def test_filter_content_changed(self, client: AsyncClient, admin_token, crawl_data):
        resp = await client.get(
            f"/crawls/{crawl_data.id}/pages?filter=content_changed",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "content" in data[0]["url"]

    async def test_filter_status_changed(self, client: AsyncClient, admin_token, crawl_data):
        resp = await client.get(
            f"/crawls/{crawl_data.id}/pages?filter=status_changed",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "status" in data[0]["url"]
