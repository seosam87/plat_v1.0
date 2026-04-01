import uuid

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.services.user_service import create_user


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(
        db_session, "admindisable", "admindisable@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def site_id(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/sites",
        json={
            "name": "DisableSite",
            "url": "https://disable.example.com",
            "wp_username": "u",
            "app_password": "p",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["id"]


async def test_disable_site(client: AsyncClient, admin_token: str, site_id: str):
    resp = await client.patch(
        f"/sites/{site_id}/status?active=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_enable_site(client: AsyncClient, admin_token: str, site_id: str):
    await client.patch(
        f"/sites/{site_id}/status?active=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.patch(
        f"/sites/{site_id}/status?active=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


async def test_disable_unknown_site(client: AsyncClient, admin_token: str):
    resp = await client.patch(
        f"/sites/{uuid.uuid4()}/status?active=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
