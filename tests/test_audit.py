from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole


async def make_admin(db: AsyncSession) -> User:
    user = User(
        username="auditadmin",
        email="auditadmin@example.com",
        password_hash=hash_password("pass"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def test_login_writes_audit_row(client: AsyncClient, db_session: AsyncSession):
    admin = await make_admin(db_session)
    resp = await client.post(
        "/auth/token",
        data={"username": "auditadmin@example.com", "password": "pass"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.login")
    )
    rows = result.scalars().all()
    assert len(rows) >= 1
    assert rows[0].user_id == admin.id


async def test_failed_login_writes_audit_row(client: AsyncClient, db_session: AsyncSession):
    await client.post(
        "/auth/token",
        data={"username": "nobody@example.com", "password": "wrong"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.login_failed")
    )
    rows = result.scalars().all()
    assert len(rows) >= 1


async def test_create_user_writes_audit_row(client: AsyncClient, db_session: AsyncSession):
    admin = await make_admin(db_session)
    token = create_access_token(str(admin.id), "admin")
    resp = await client.post(
        "/admin/users",
        json={"username": "newuser", "email": "new@example.com", "password": "pw"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.created")
    )
    assert result.scalars().first() is not None


async def test_deactivate_writes_audit_row(client: AsyncClient, db_session: AsyncSession):
    admin = await make_admin(db_session)
    target = User(
        username="victim",
        email="victim@example.com",
        password_hash=hash_password("pw"),
        role=UserRole.client,
        is_active=True,
    )
    db_session.add(target)
    await db_session.flush()

    token = create_access_token(str(admin.id), "admin")
    resp = await client.delete(
        f"/admin/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.deactivated")
    )
    assert result.scalars().first() is not None
