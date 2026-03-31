from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import User, UserRole


async def make_user(db: AsyncSession, role: UserRole, email: str = None) -> User:
    email = email or f"{role.value}@example.com"
    user = User(
        username=email.split("@")[0],
        email=email,
        password_hash=hash_password("pass"),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


def auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id), user.role.value)
    return {"Authorization": f"Bearer {token}"}


# ── Admin can access admin endpoints ─────────────────────────────────────────

async def test_admin_list_users(client: AsyncClient, db_session: AsyncSession):
    admin = await make_user(db_session, UserRole.admin)
    resp = await client.get("/admin/users", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_admin_create_user(client: AsyncClient, db_session: AsyncSession):
    admin = await make_user(db_session, UserRole.admin)
    resp = await client.post(
        "/admin/users",
        json={"username": "new", "email": "new@example.com", "password": "pass123"},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@example.com"


async def test_admin_deactivate_user(client: AsyncClient, db_session: AsyncSession):
    admin = await make_user(db_session, UserRole.admin)
    target = await make_user(db_session, UserRole.client, "target@example.com")
    resp = await client.delete(f"/admin/users/{target.id}", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# ── Manager and client are forbidden ─────────────────────────────────────────

async def test_manager_cannot_list_users(client: AsyncClient, db_session: AsyncSession):
    manager = await make_user(db_session, UserRole.manager)
    resp = await client.get("/admin/users", headers=auth_headers(manager))
    assert resp.status_code == 403


async def test_client_cannot_list_users(client: AsyncClient, db_session: AsyncSession):
    client_user = await make_user(db_session, UserRole.client)
    resp = await client.get("/admin/users", headers=auth_headers(client_user))
    assert resp.status_code == 403


async def test_unauthenticated_cannot_list_users(client: AsyncClient):
    resp = await client.get("/admin/users")
    assert resp.status_code == 401


# ── Service-layer enforcement ─────────────────────────────────────────────────

async def test_service_layer_rejects_non_admin(db_session: AsyncSession):
    import pytest
    from fastapi import HTTPException

    from app.services.user_service import list_users

    manager = await make_user(db_session, UserRole.manager)
    with pytest.raises(HTTPException) as exc_info:
        await list_users(db_session, manager)
    assert exc_info.value.status_code == 403
