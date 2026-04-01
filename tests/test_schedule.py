import pytest
from unittest.mock import patch
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(
        db_session, "sched_admin", "sched@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def site_id(db_session, admin_token):
    from app.models.user import User
    from sqlalchemy import select

    user = (await db_session.execute(select(User))).scalar_one()
    site = await create_site(
        db_session,
        name="Schedule Test",
        url="https://sched.example.com",
        wp_username="admin",
        app_password="secret",
        actor_id=user.id,
    )
    await db_session.flush()
    return site.id


@patch("app.services.schedule_service.sync_schedule_to_redbeat")
async def test_get_schedule_default(mock_sync, client: AsyncClient, admin_token: str, site_id):
    resp = await client.get(
        f"/sites/{site_id}/schedule",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule_type"] == "manual"


@patch("app.services.schedule_service.sync_schedule_to_redbeat")
async def test_set_schedule_daily(mock_sync, client: AsyncClient, admin_token: str, site_id):
    resp = await client.put(
        f"/sites/{site_id}/schedule",
        json={"schedule_type": "daily"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule_type"] == "daily"
    assert data["cron_expression"] == "0 3 * * *"
    mock_sync.assert_called_once()


@patch("app.services.schedule_service.sync_schedule_to_redbeat")
async def test_set_schedule_weekly(mock_sync, client: AsyncClient, admin_token: str, site_id):
    resp = await client.put(
        f"/sites/{site_id}/schedule",
        json={"schedule_type": "weekly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule_type"] == "weekly"
    assert data["cron_expression"] == "0 3 * * 1"


@patch("app.services.schedule_service.sync_schedule_to_redbeat")
async def test_set_schedule_back_to_manual(mock_sync, client: AsyncClient, admin_token: str, site_id):
    # First set to daily
    await client.put(
        f"/sites/{site_id}/schedule",
        json={"schedule_type": "daily"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Then back to manual
    resp = await client.put(
        f"/sites/{site_id}/schedule",
        json={"schedule_type": "manual"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule_type"] == "manual"
    assert data["cron_expression"] is None


@patch("app.services.schedule_service.sync_schedule_to_redbeat")
async def test_schedule_not_found_site(mock_sync, client: AsyncClient, admin_token: str):
    import uuid

    resp = await client.put(
        f"/sites/{uuid.uuid4()}/schedule",
        json={"schedule_type": "daily"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
