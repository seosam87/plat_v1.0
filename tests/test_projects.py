"""Unit tests for project, content plan, and brief generation."""
import uuid

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.content_plan import ContentPlanItem, ContentStatus
from app.models.project import Project, ProjectStatus
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(db_session, "proj_admin", "proj@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def site(db_session):
    user = await create_user(db_session, "proj_admin2", "proj2@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    s = await create_site(db_session, name="Proj Site", url="https://proj.example.com", wp_username="admin", app_password="secret", actor_id=user.id)
    await db_session.flush()
    return s


async def test_project_model(db_session, site):
    p = Project(site_id=site.id, name="Test Project")
    db_session.add(p)
    await db_session.flush()
    assert p.status == ProjectStatus.active


async def test_content_plan_item_model(db_session, site):
    p = Project(site_id=site.id, name="Plan Project")
    db_session.add(p)
    await db_session.flush()

    item = ContentPlanItem(project_id=p.id, proposed_title="How to SEO")
    db_session.add(item)
    await db_session.flush()
    assert item.status == ContentStatus.idea


async def test_create_project_endpoint(client: AsyncClient, admin_token, site):
    resp = await client.post(
        "/projects",
        json={"site_id": str(site.id), "name": "API Project"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "API Project"


async def test_list_projects_endpoint(client: AsyncClient, admin_token, db_session, site):
    p = Project(site_id=site.id, name="Listed")
    db_session.add(p)
    await db_session.flush()

    resp = await client.get("/projects", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_update_project_endpoint(client: AsyncClient, admin_token, db_session, site):
    p = Project(site_id=site.id, name="Original")
    db_session.add(p)
    await db_session.flush()

    resp = await client.put(
        f"/projects/{p.id}",
        json={"name": "Updated", "status": "paused"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
    assert resp.json()["status"] == "paused"


async def test_add_plan_item_endpoint(client: AsyncClient, admin_token, db_session, site):
    p = Project(site_id=site.id, name="Plan Test")
    db_session.add(p)
    await db_session.flush()

    resp = await client.post(
        f"/projects/{p.id}/plan",
        json={"proposed_title": "New Article"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["proposed_title"] == "New Article"
    assert resp.json()["status"] == "idea"


async def test_list_plan_endpoint(client: AsyncClient, admin_token, db_session, site):
    p = Project(site_id=site.id, name="Plan List")
    db_session.add(p)
    await db_session.flush()
    item = ContentPlanItem(project_id=p.id, proposed_title="Item 1")
    db_session.add(item)
    await db_session.flush()

    resp = await client.get(
        f"/projects/{p.id}/plan",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_kanban_tasks_endpoint(client: AsyncClient, admin_token, db_session, site):
    from app.models.task import SeoTask, TaskType

    p = Project(site_id=site.id, name="Kanban Test")
    db_session.add(p)
    await db_session.flush()

    t = SeoTask(site_id=site.id, project_id=p.id, task_type=TaskType.page_404, url="/x", title="404 task")
    db_session.add(t)
    await db_session.flush()

    resp = await client.get(
        f"/projects/{p.id}/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "open" in data
    assert len(data["open"]) == 1


# ---- Brief (pure logic) ----

def test_brief_html_renders():
    from app.routers.projects import _render_brief_html
    brief = {
        "cluster_name": "SEO Tools",
        "target_url": "https://a.com/seo",
        "h1": "Best SEO Tools",
        "h2_suggestions": ["Free Tools", "Paid Tools"],
        "keywords": [{"phrase": "seo tools", "frequency": 5000, "target_url": None}],
        "total_volume": 5000,
    }
    html = _render_brief_html(brief)
    assert "Best SEO Tools" in html
    assert "Free Tools" in html
    assert "5000" in html
