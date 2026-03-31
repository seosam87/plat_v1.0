import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, decode_access_token
from app.auth.password import hash_password, verify_password
from app.models.user import User, UserRole


# ── Helper ──────────────────────────────────────────────────────────────────

async def make_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "secret123",
    role: UserRole = UserRole.client,
) -> User:
    user = User(
        username=email.split("@")[0],
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


# ── Password unit tests ──────────────────────────────────────────────────────

def test_hash_and_verify_password():
    hashed = hash_password("correct")
    assert verify_password("correct", hashed) is True
    assert verify_password("wrong", hashed) is False


# ── JWT unit tests ───────────────────────────────────────────────────────────

def test_create_and_decode_token():
    token = create_access_token("user-123", "admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"


# ── Auth endpoint tests ──────────────────────────────────────────────────────

async def test_login_success(client: AsyncClient, db_session: AsyncSession):
    await make_user(db_session, email="login@example.com", password="pass123")
    resp = await client.post(
        "/auth/token",
        data={"username": "login@example.com", "password": "pass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    await make_user(db_session, email="wrong@example.com", password="correct")
    resp = await client.post(
        "/auth/token",
        data={"username": "wrong@example.com", "password": "incorrect"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(
        "/auth/token",
        data={"username": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


async def test_get_me_authenticated(client: AsyncClient, db_session: AsyncSession):
    user = await make_user(db_session, email="me@example.com", role=UserRole.admin)
    token = create_access_token(str(user.id), user.role.value)
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@example.com"
    assert data["role"] == "admin"


async def test_get_me_no_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_get_me_invalid_token(client: AsyncClient):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert resp.status_code == 401


async def test_inactive_user_cannot_login(client: AsyncClient, db_session: AsyncSession):
    user = User(
        username="inactive",
        email="inactive@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.client,
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()
    resp = await client.post(
        "/auth/token",
        data={"username": "inactive@example.com", "password": "pass"},
    )
    assert resp.status_code == 400
