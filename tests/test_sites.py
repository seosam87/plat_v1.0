import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.services.user_service import create_user


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(db_session, "admin2", "admin2@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def client_token(db_session):
    user = await create_user(db_session, "client1", "client1@test.com", hash_password("pass"), UserRole.client)
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


async def test_create_site_admin(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/sites",
        json={"name": "Test Site", "url": "https://example.com", "wp_username": "admin", "app_password": "secret"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Site"
    assert "app_password" not in data
    assert "encrypted_app_password" not in data


async def test_create_site_non_admin_forbidden(client: AsyncClient, client_token: str):
    resp = await client.post(
        "/sites",
        json={"name": "Bad", "url": "https://bad.com", "wp_username": "u", "app_password": "p"},
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert resp.status_code == 403


async def test_list_sites(client: AsyncClient, admin_token: str):
    resp = await client.get("/sites", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_delete_site(client: AsyncClient, admin_token: str):
    create_resp = await client.post(
        "/sites",
        json={"name": "Del", "url": "https://del.com", "wp_username": "u", "app_password": "p"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    site_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/sites/{site_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_resp.status_code == 204
