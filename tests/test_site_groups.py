"""Unit tests for site group access control."""
import uuid

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.site import Site
from app.models.site_group import SiteGroup
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(db_session, "sg_admin", "sg@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def manager_and_token(db_session):
    user = await create_user(db_session, "sg_manager", "sgm@test.com", hash_password("pass"), UserRole.manager)
    await db_session.flush()
    token = create_access_token(str(user.id), user.role.value)
    return user, token


# ---- Model tests ----

async def test_site_group_model(db_session):
    g = SiteGroup(name="Direction A", description="Sites for direction A")
    db_session.add(g)
    await db_session.flush()
    assert g.id is not None


async def test_site_with_group(db_session):
    g = SiteGroup(name="Group B")
    db_session.add(g)
    await db_session.flush()

    user = await create_user(db_session, "sg_admin3", "sg3@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    site = await create_site(db_session, name="Grouped Site", url="https://sg.example.com",
                              wp_username="admin", app_password="secret", actor_id=user.id)
    site.site_group_id = g.id
    await db_session.flush()

    from sqlalchemy import select
    saved = (await db_session.execute(select(Site).where(Site.id == site.id))).scalar_one()
    assert saved.site_group_id == g.id


# ---- Service tests ----

async def test_admin_sees_all_sites(db_session):
    from app.services.site_group_service import get_accessible_sites
    admin = await create_user(db_session, "sg_admin4", "sg4@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()

    user2 = await create_user(db_session, "sg_admin5", "sg5@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()
    await create_site(db_session, name="S1", url="https://s1.example.com", wp_username="a", app_password="s", actor_id=user2.id)
    await create_site(db_session, name="S2", url="https://s2.example.com", wp_username="a", app_password="s", actor_id=user2.id)
    await db_session.flush()

    sites = await get_accessible_sites(db_session, admin)
    assert len(sites) >= 2


async def test_manager_sees_only_assigned_group(db_session):
    from app.services.site_group_service import get_accessible_sites, assign_user_to_group, assign_site_to_group, create_group

    manager = await create_user(db_session, "sg_mgr", "sgmgr@test.com", hash_password("pass"), UserRole.manager)
    admin = await create_user(db_session, "sg_admin6", "sg6@test.com", hash_password("pass"), UserRole.admin)
    await db_session.flush()

    g1 = await create_group(db_session, "Direction 1")
    g2 = await create_group(db_session, "Direction 2")

    s1 = await create_site(db_session, name="Site Dir1", url="https://dir1.example.com", wp_username="a", app_password="s", actor_id=admin.id)
    s2 = await create_site(db_session, name="Site Dir2", url="https://dir2.example.com", wp_username="a", app_password="s", actor_id=admin.id)
    await db_session.flush()

    await assign_site_to_group(db_session, s1.id, g1.id)
    await assign_site_to_group(db_session, s2.id, g2.id)
    await assign_user_to_group(db_session, manager.id, g1.id)  # manager only in group 1

    sites = await get_accessible_sites(db_session, manager)
    assert len(sites) == 1
    assert sites[0].name == "Site Dir1"


async def test_manager_with_no_groups_sees_nothing(db_session):
    from app.services.site_group_service import get_accessible_sites

    manager = await create_user(db_session, "sg_mgr2", "sgmgr2@test.com", hash_password("pass"), UserRole.manager)
    await db_session.flush()

    sites = await get_accessible_sites(db_session, manager)
    assert sites == []


async def test_can_access_site(db_session):
    from app.services.site_group_service import can_access_site, create_group, assign_user_to_group, assign_site_to_group

    admin = await create_user(db_session, "sg_admin7", "sg7@test.com", hash_password("pass"), UserRole.admin)
    manager = await create_user(db_session, "sg_mgr3", "sgmgr3@test.com", hash_password("pass"), UserRole.manager)
    await db_session.flush()

    g = await create_group(db_session, "Access Test Group")
    s = await create_site(db_session, name="Access Site", url="https://access.example.com", wp_username="a", app_password="s", actor_id=admin.id)
    await db_session.flush()

    await assign_site_to_group(db_session, s.id, g.id)
    await assign_user_to_group(db_session, manager.id, g.id)

    assert await can_access_site(db_session, admin, s.id) is True
    assert await can_access_site(db_session, manager, s.id) is True


# ---- API tests ----

async def test_create_group_endpoint(client: AsyncClient, admin_token):
    resp = await client.post(
        "/site-groups",
        json={"name": "API Group", "description": "Test group"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "API Group"


async def test_list_groups_endpoint(client: AsyncClient, admin_token, db_session):
    g = SiteGroup(name="Listed Group")
    db_session.add(g)
    await db_session.flush()

    resp = await client.get(
        "/site-groups",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
