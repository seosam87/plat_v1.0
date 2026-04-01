"""Unit tests for cluster service and router."""
import uuid

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.cluster import KeywordCluster
from app.models.keyword import Keyword
from app.models.user import UserRole
from app.services.user_service import create_user
from app.services.site_service import create_site


@pytest.fixture
async def admin_token(db_session):
    user = await create_user(
        db_session, "cl_admin", "cl@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    return create_access_token(str(user.id), user.role.value)


@pytest.fixture
async def site(db_session):
    user = await create_user(
        db_session, "cl_admin2", "cl2@test.com", hash_password("pass"), UserRole.admin
    )
    await db_session.flush()
    s = await create_site(
        db_session, name="Cluster Test", url="https://cl.example.com",
        wp_username="admin", app_password="secret", actor_id=user.id,
    )
    await db_session.flush()
    return s


# ---- Model ----

async def test_cluster_model(db_session, site):
    c = KeywordCluster(site_id=site.id, name="Commercial", target_url="https://cl.example.com/buy")
    db_session.add(c)
    await db_session.flush()
    assert c.id is not None
    assert c.name == "Commercial"


async def test_keyword_cluster_assignment(db_session, site):
    c = KeywordCluster(site_id=site.id, name="Info")
    db_session.add(c)
    await db_session.flush()

    kw = Keyword(site_id=site.id, phrase="how to seo", cluster_id=c.id)
    db_session.add(kw)
    await db_session.flush()

    from sqlalchemy import select
    saved = (await db_session.execute(
        select(Keyword).where(Keyword.cluster_id == c.id)
    )).scalar_one()
    assert saved.phrase == "how to seo"


# ---- Service ----

async def test_create_and_list_clusters(db_session, site):
    from app.services.cluster_service import create_cluster, list_clusters
    await create_cluster(db_session, site.id, "Cluster A")
    await create_cluster(db_session, site.id, "Cluster B")
    clusters = await list_clusters(db_session, site.id)
    assert len(clusters) == 2


async def test_assign_keywords(db_session, site):
    from app.services.cluster_service import create_cluster, assign_keywords_to_cluster
    c = await create_cluster(db_session, site.id, "Test Cluster")
    kw1 = Keyword(site_id=site.id, phrase="kw1")
    kw2 = Keyword(site_id=site.id, phrase="kw2")
    db_session.add_all([kw1, kw2])
    await db_session.flush()

    count = await assign_keywords_to_cluster(db_session, [kw1.id, kw2.id], c.id)
    assert count == 2

    from sqlalchemy import select
    assigned = (await db_session.execute(
        select(Keyword).where(Keyword.cluster_id == c.id)
    )).scalars().all()
    assert len(assigned) == 2


async def test_unassign_keywords(db_session, site):
    from app.services.cluster_service import create_cluster, assign_keywords_to_cluster
    c = await create_cluster(db_session, site.id, "Temp")
    kw = Keyword(site_id=site.id, phrase="temp kw", cluster_id=c.id)
    db_session.add(kw)
    await db_session.flush()

    count = await assign_keywords_to_cluster(db_session, [kw.id], None)
    assert count == 1

    from sqlalchemy import select
    saved = (await db_session.execute(select(Keyword).where(Keyword.id == kw.id))).scalar_one()
    assert saved.cluster_id is None


# ---- Router ----

async def test_create_cluster_endpoint(client: AsyncClient, admin_token, site):
    resp = await client.post(
        f"/clusters/sites/{site.id}",
        json={"name": "API Cluster", "target_url": "https://cl.example.com/page"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "API Cluster"


async def test_list_clusters_endpoint(client: AsyncClient, admin_token, site, db_session):
    c = KeywordCluster(site_id=site.id, name="Listed")
    db_session.add(c)
    await db_session.flush()

    resp = await client.get(
        f"/clusters/sites/{site.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_assign_endpoint(client: AsyncClient, admin_token, site, db_session):
    c = KeywordCluster(site_id=site.id, name="Assign Target")
    db_session.add(c)
    await db_session.flush()

    kw = Keyword(site_id=site.id, phrase="to assign")
    db_session.add(kw)
    await db_session.flush()

    resp = await client.post(
        "/clusters/assign",
        json={"keyword_ids": [str(kw.id)], "cluster_id": str(c.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["assigned"] == 1


async def test_delete_cluster_endpoint(client: AsyncClient, admin_token, site, db_session):
    c = KeywordCluster(site_id=site.id, name="To Delete")
    db_session.add(c)
    await db_session.flush()

    resp = await client.delete(
        f"/clusters/{c.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


async def test_export_csv_endpoint(client: AsyncClient, admin_token, site, db_session):
    kw = Keyword(site_id=site.id, phrase="csv export kw", frequency=100)
    db_session.add(kw)
    await db_session.flush()

    resp = await client.get(
        f"/clusters/sites/{site.id}/export.csv",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "csv export kw" in resp.text
