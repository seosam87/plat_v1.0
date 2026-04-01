"""Tests for project comments, task workflow, and project access control."""
import uuid

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.project import Project
from app.models.project_comment import ProjectComment
from app.models.task import SeoTask, TaskStatus, TaskType
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


@pytest.fixture
async def admin(db_session):
    user = await create_user(db_session, "pf_admin", "pf@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    return user


@pytest.fixture
async def admin_token(admin):
    return create_access_token(str(admin.id), admin.role.value)


@pytest.fixture
async def manager(db_session):
    user = await create_user(db_session, "pf_mgr", "pfm@test.com", hash_password("pass"), UserRole.manager)
    await db_session.flush()
    return user


@pytest.fixture
async def manager_token(manager):
    return create_access_token(str(manager.id), manager.role.value)


@pytest.fixture
async def project(db_session, admin):
    site = await create_site(db_session, name="PF Site", url="https://pf.example.com",
                              wp_username="admin", app_password="secret", actor_id=admin.id)
    await db_session.flush()
    p = Project(site_id=site.id, name="Feature Project")
    db_session.add(p)
    await db_session.flush()
    return p


# ---- Task status workflow ----

def test_task_status_values():
    assert list(TaskStatus) == [
        TaskStatus.open,
        TaskStatus.assigned,
        TaskStatus.in_progress,
        TaskStatus.review,
        TaskStatus.resolved,
    ]


def test_task_type_includes_manual():
    assert TaskType.manual.value == "manual"
    assert TaskType.missing_page.value == "missing_page"
    assert TaskType.cannibalization.value == "cannibalization"


# ---- Comments ----

async def test_add_comment(db_session, admin, project):
    from app.services.project_service import add_comment, list_comments
    c = await add_comment(db_session, project.id, admin.id, "First comment")
    assert c.text == "First comment"
    comments = await list_comments(db_session, project.id)
    assert len(comments) == 1


async def test_comment_api(client: AsyncClient, admin_token, project):
    resp = await client.post(
        f"/projects/{project.id}/comments",
        json={"text": "API comment"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["text"] == "API comment"


async def test_list_comments_api(client: AsyncClient, admin_token, project, db_session, admin):
    c = ProjectComment(project_id=project.id, user_id=admin.id, text="Existing")
    db_session.add(c)
    await db_session.flush()

    resp = await client.get(
        f"/projects/{project.id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert resp.json()[0]["username"] == "pf_admin"


# ---- Project access ----

async def test_admin_sees_all_projects(db_session, admin, project):
    from app.services.project_service import get_accessible_projects
    projects = await get_accessible_projects(db_session, admin)
    assert len(projects) >= 1


async def test_manager_no_access_sees_nothing(db_session, manager, project):
    from app.services.project_service import get_accessible_projects
    projects = await get_accessible_projects(db_session, manager)
    assert projects == []


async def test_manager_with_access_sees_project(db_session, manager, project):
    from app.services.project_service import grant_access, get_accessible_projects
    await grant_access(db_session, project.id, manager.id)
    projects = await get_accessible_projects(db_session, manager)
    assert len(projects) == 1
    assert projects[0].id == project.id


async def test_revoke_access(db_session, manager, project):
    from app.services.project_service import grant_access, revoke_access, get_accessible_projects
    await grant_access(db_session, project.id, manager.id)
    await revoke_access(db_session, project.id, manager.id)
    projects = await get_accessible_projects(db_session, manager)
    assert projects == []


async def test_grant_access_api(client: AsyncClient, admin_token, project, manager):
    resp = await client.post(
        f"/projects/{project.id}/access",
        json={"user_id": str(manager.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "granted"


async def test_manager_cannot_comment_without_access(client: AsyncClient, manager_token, project):
    resp = await client.post(
        f"/projects/{project.id}/comments",
        json={"text": "Should fail"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 403


# ---- Manual task creation ----

async def test_create_manual_task(client: AsyncClient, admin_token, project):
    resp = await client.post(
        f"/projects/{project.id}/tasks/create",
        json={"title": "Manual task", "description": "Do something"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Manual task"
    assert data["task_type"] == "manual"
    assert data["status"] == "open"


async def test_create_assigned_task(client: AsyncClient, admin_token, project, manager):
    resp = await client.post(
        f"/projects/{project.id}/tasks/create",
        json={"title": "Assigned task", "assignee_id": str(manager.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "assigned"
    assert resp.json()["assignee_id"] == str(manager.id)
