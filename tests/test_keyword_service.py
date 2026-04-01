"""Tests for keyword models, service, and API endpoints."""
import uuid

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.keyword import Keyword, KeywordGroup, SearchEngine
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(
        db_session, "kw_admin", "kw@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def site(db_session):
    from app.models.user import User
    from sqlalchemy import select

    user = await create_user(
        db_session, "kw_admin2", "kw2@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    s = await create_site(
        db_session,
        name="KW Test",
        url="https://kw.example.com",
        wp_username="admin",
        app_password="secret",
        actor_id=user.id,
    )
    await db_session.flush()
    return s


# ---- Model-level tests ----


async def test_keyword_model(db_session, site):
    kw = Keyword(
        site_id=site.id,
        phrase="seo tools",
        frequency=1500,
        engine=SearchEngine.google,
    )
    db_session.add(kw)
    await db_session.flush()

    from sqlalchemy import select
    result = await db_session.execute(select(Keyword).where(Keyword.site_id == site.id))
    saved = result.scalar_one()
    assert saved.phrase == "seo tools"
    assert saved.frequency == 1500
    assert saved.engine == SearchEngine.google


async def test_keyword_group_model(db_session, site):
    group = KeywordGroup(site_id=site.id, name="Commercial")
    db_session.add(group)
    await db_session.flush()

    kw = Keyword(site_id=site.id, phrase="buy seo tools", group_id=group.id)
    db_session.add(kw)
    await db_session.flush()

    from sqlalchemy import select
    saved = (await db_session.execute(
        select(Keyword).where(Keyword.group_id == group.id)
    )).scalar_one()
    assert saved.phrase == "buy seo tools"


async def test_nested_group(db_session, site):
    parent = KeywordGroup(site_id=site.id, name="Parent")
    db_session.add(parent)
    await db_session.flush()

    child = KeywordGroup(site_id=site.id, name="Child", parent_id=parent.id)
    db_session.add(child)
    await db_session.flush()

    from sqlalchemy import select
    saved = (await db_session.execute(
        select(KeywordGroup).where(KeywordGroup.parent_id == parent.id)
    )).scalar_one()
    assert saved.name == "Child"


# ---- Service-level tests ----


async def test_add_keyword_normalizes_phrase(db_session, site):
    from app.services.keyword_service import add_keyword
    kw = await add_keyword(db_session, site.id, phrase="  SEO Tools  ")
    assert kw.phrase == "seo tools"


async def test_bulk_add_keywords(db_session, site):
    from app.services.keyword_service import bulk_add_keywords, count_keywords
    rows = [
        {"phrase": "keyword one", "frequency": 100},
        {"phrase": "keyword two", "frequency": 200},
        {"phrase": "", "frequency": 0},  # empty phrase — should be skipped
    ]
    count = await bulk_add_keywords(db_session, site.id, rows)
    assert count == 2
    total = await count_keywords(db_session, site.id)
    assert total == 2


async def test_get_or_create_group(db_session, site):
    from app.services.keyword_service import get_or_create_group
    g1 = await get_or_create_group(db_session, site.id, "Commercial")
    g2 = await get_or_create_group(db_session, site.id, "Commercial")
    assert g1.id == g2.id  # same group returned


# ---- API endpoint tests ----


async def test_add_keyword_endpoint(client: AsyncClient, admin_token, site):
    resp = await client.post(
        f"/keywords/sites/{site.id}",
        json={"phrase": "buy seo tools", "frequency": 500, "engine": "google"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["phrase"] == "buy seo tools"
    assert data["frequency"] == 500


async def test_list_keywords_endpoint(client: AsyncClient, admin_token, site, db_session):
    kw = Keyword(site_id=site.id, phrase="test kw")
    db_session.add(kw)
    await db_session.flush()

    resp = await client.get(
        f"/keywords/sites/{site.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_count_keywords_endpoint(client: AsyncClient, admin_token, site):
    resp = await client.get(
        f"/keywords/sites/{site.id}/count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "count" in resp.json()


async def test_delete_keyword_endpoint(client: AsyncClient, admin_token, site, db_session):
    kw = Keyword(site_id=site.id, phrase="to delete")
    db_session.add(kw)
    await db_session.flush()

    resp = await client.delete(
        f"/keywords/{kw.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


async def test_list_groups_endpoint(client: AsyncClient, admin_token, site, db_session):
    g = KeywordGroup(site_id=site.id, name="Test Group")
    db_session.add(g)
    await db_session.flush()

    resp = await client.get(
        f"/keywords/sites/{site.id}/groups",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Test Group"
