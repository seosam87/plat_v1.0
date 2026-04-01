"""Unit tests for Phase 11 hardening: health, invite, rate limit."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.invite import InviteLink
from app.models.project import Project
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(db_session, "hard_admin", "hard@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def project(db_session):
    user = await create_user(db_session, "hard_admin2", "hard2@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    site = await create_site(db_session, name="Hard Site", url="https://hard.example.com", wp_username="admin", app_password="secret", actor_id=user.id)
    await db_session.flush()
    p = Project(site_id=site.id, name="Hard Project")
    db_session.add(p)
    await db_session.flush()
    return p


# ---- Invite system ----

async def test_create_invite(client: AsyncClient, admin_token, project):
    resp = await client.post(
        f"/invites/projects/{project.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "token" in resp.json()


async def test_accept_invite(client: AsyncClient, db_session, project):
    invite = InviteLink(
        project_id=project.id,
        token="test-invite-token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.flush()

    resp = await client.post(
        "/invites/accept",
        json={"token": "test-invite-token", "username": "newclient", "email": "client@test.com", "password": "pass123"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "client"


async def test_accept_expired_invite(client: AsyncClient, db_session, project):
    invite = InviteLink(
        project_id=project.id,
        token="expired-token",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(invite)
    await db_session.flush()

    resp = await client.post(
        "/invites/accept",
        json={"token": "expired-token", "username": "late", "email": "late@test.com", "password": "pass"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


async def test_accept_used_invite(client: AsyncClient, db_session, project):
    invite = InviteLink(
        project_id=project.id,
        token="used-token",
        used=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.flush()

    resp = await client.post(
        "/invites/accept",
        json={"token": "used-token", "username": "dup", "email": "dup@test.com", "password": "pass"},
    )
    assert resp.status_code == 400


async def test_invalid_invite_token(client: AsyncClient):
    resp = await client.post(
        "/invites/accept",
        json={"token": "nonexistent", "username": "x", "email": "x@test.com", "password": "pass"},
    )
    assert resp.status_code == 404


# ---- Health endpoint (model check) ----

def test_health_router_exists():
    from app.routers.health import router
    paths = [r.path for r in router.routes]
    assert "/health" in paths


# ---- Invite model ----

async def test_invite_model(db_session, project):
    inv = InviteLink(
        project_id=project.id,
        token="abc123",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(inv)
    await db_session.flush()
    assert inv.used is False
