"""Tests for CRM service layer: client_service.py.

Uses real DB session from conftest.py (SAVEPOINT-isolated).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientContact, ClientInteraction
from app.models.site import Site
from app.models.task import SeoTask, TaskStatus, TaskType
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def manager(db_session: AsyncSession) -> User:
    user = User(
        username="manager1",
        email="manager1@test.com",
        password_hash="fakehash",
        role=UserRole.manager,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def manager2(db_session: AsyncSession) -> User:
    user = User(
        username="manager2",
        email="manager2@test.com",
        password_hash="fakehash",
        role=UserRole.manager,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def sample_client(db_session: AsyncSession, manager: User) -> Client:
    from app.services.client_service import create_client

    return await create_client(
        db_session,
        company_name="Acme Corp",
        legal_name="Acme LLC",
        inn="1234567890",
        email="acme@test.com",
        manager_id=manager.id,
    )


# ---------------------------------------------------------------------------
# Client CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_client(db_session: AsyncSession, manager: User):
    from app.services.client_service import create_client

    c = await create_client(
        db_session,
        company_name="Test Company",
        manager_id=manager.id,
    )
    assert c.id is not None
    assert c.company_name == "Test Company"
    assert c.manager_id == manager.id
    assert c.is_deleted is False


@pytest.mark.asyncio
async def test_get_client(db_session: AsyncSession, sample_client: Client):
    from app.services.client_service import get_client

    c = await get_client(db_session, sample_client.id)
    assert c is not None
    assert c.company_name == "Acme Corp"


@pytest.mark.asyncio
async def test_get_client_returns_none_for_deleted(
    db_session: AsyncSession, sample_client: Client
):
    from app.services.client_service import delete_client, get_client

    await delete_client(db_session, sample_client.id)
    c = await get_client(db_session, sample_client.id)
    assert c is None


@pytest.mark.asyncio
async def test_update_client(db_session: AsyncSession, sample_client: Client):
    from app.services.client_service import update_client

    updated = await update_client(
        db_session, sample_client.id, company_name="Acme Updated"
    )
    assert updated is not None
    assert updated.company_name == "Acme Updated"


@pytest.mark.asyncio
async def test_delete_client_soft_deletes(
    db_session: AsyncSession, sample_client: Client
):
    from app.services.client_service import delete_client

    result = await delete_client(db_session, sample_client.id)
    assert result is True
    # Verify is_deleted flag is set
    await db_session.refresh(sample_client)
    assert sample_client.is_deleted is True


# ---------------------------------------------------------------------------
# list_clients: pagination, search, manager filter, date filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_clients_pagination(
    db_session: AsyncSession, manager: User
):
    from app.services.client_service import create_client, list_clients

    for i in range(5):
        await create_client(db_session, company_name=f"Company {i:02d}")

    clients, total = await list_clients(db_session, page=1, page_size=3)
    assert total == 5
    assert len(clients) == 3

    clients2, total2 = await list_clients(db_session, page=2, page_size=3)
    assert total2 == 5
    assert len(clients2) == 2


@pytest.mark.asyncio
async def test_list_clients_search(
    db_session: AsyncSession, sample_client: Client
):
    from app.services.client_service import create_client, list_clients

    await create_client(db_session, company_name="Other Company")

    # Search by company name
    clients, total = await list_clients(db_session, search="acme")
    assert total == 1
    assert clients[0].company_name == "Acme Corp"

    # Search by INN
    clients, total = await list_clients(db_session, search="1234567890")
    assert total == 1

    # Search by email
    clients, total = await list_clients(db_session, search="acme@test")
    assert total == 1


@pytest.mark.asyncio
async def test_list_clients_manager_filter(
    db_session: AsyncSession, manager: User, manager2: User
):
    from app.services.client_service import create_client, list_clients

    await create_client(db_session, company_name="A", manager_id=manager.id)
    await create_client(db_session, company_name="B", manager_id=manager2.id)

    clients, total = await list_clients(db_session, manager_id=manager.id)
    assert total == 1
    assert clients[0].company_name == "A"


@pytest.mark.asyncio
async def test_list_clients_date_range_filter(
    db_session: AsyncSession, manager: User
):
    from app.services.client_service import create_client, list_clients
    from datetime import date

    c1 = await create_client(db_session, company_name="Old Client")
    c2 = await create_client(db_session, company_name="New Client")

    # Both are created "now", so filtering from today should include both
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    clients, total = await list_clients(
        db_session, created_from=yesterday, created_to=tomorrow
    )
    assert total == 2

    # Filter to a past date range should return 0
    old = date(2020, 1, 1)
    old_end = date(2020, 1, 2)
    clients, total = await list_clients(
        db_session, created_from=old, created_to=old_end
    )
    assert total == 0


@pytest.mark.asyncio
async def test_list_clients_ordered_by_company_name(
    db_session: AsyncSession, manager: User
):
    from app.services.client_service import create_client, list_clients

    await create_client(db_session, company_name="Zulu Corp")
    await create_client(db_session, company_name="Alpha Inc")

    clients, total = await list_clients(db_session)
    assert clients[0].company_name == "Alpha Inc"
    assert clients[1].company_name == "Zulu Corp"


@pytest.mark.asyncio
async def test_list_clients_excludes_deleted(
    db_session: AsyncSession, sample_client: Client
):
    from app.services.client_service import delete_client, list_clients

    await delete_client(db_session, sample_client.id)
    clients, total = await list_clients(db_session)
    assert total == 0


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_contact(
    db_session: AsyncSession, sample_client: Client
):
    from app.services.client_service import create_contact

    contact = await create_contact(
        db_session,
        client_id=sample_client.id,
        name="John Doe",
        phone="+7999123",
        email="john@acme.com",
        role="CTO",
        telegram_username="@johndoe",
    )
    assert contact.id is not None
    assert contact.name == "John Doe"
    assert contact.client_id == sample_client.id


@pytest.mark.asyncio
async def test_update_contact(
    db_session: AsyncSession, sample_client: Client
):
    from app.services.client_service import create_contact, update_contact

    contact = await create_contact(
        db_session, client_id=sample_client.id, name="Jane"
    )
    updated = await update_contact(
        db_session,
        contact_id=contact.id,
        client_id=sample_client.id,
        name="Jane Updated",
    )
    assert updated is not None
    assert updated.name == "Jane Updated"


@pytest.mark.asyncio
async def test_delete_contact(
    db_session: AsyncSession, sample_client: Client
):
    from app.services.client_service import create_contact, delete_contact

    contact = await create_contact(
        db_session, client_id=sample_client.id, name="Temp"
    )
    result = await delete_contact(db_session, contact.id)
    assert result is True


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_interaction(
    db_session: AsyncSession, sample_client: Client, manager: User
):
    from app.services.client_service import create_interaction

    interaction = await create_interaction(
        db_session,
        client_id=sample_client.id,
        author_id=manager.id,
        note="Initial meeting",
    )
    assert interaction.id is not None
    assert interaction.note == "Initial meeting"
    assert interaction.client_id == sample_client.id


@pytest.mark.asyncio
async def test_list_interactions_ordered_desc(
    db_session: AsyncSession, sample_client: Client, manager: User
):
    from app.services.client_service import create_interaction, list_interactions

    i1 = await create_interaction(
        db_session,
        client_id=sample_client.id,
        author_id=manager.id,
        note="First",
        interaction_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    i2 = await create_interaction(
        db_session,
        client_id=sample_client.id,
        author_id=manager.id,
        note="Second",
        interaction_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    interactions, total = await list_interactions(
        db_session, client_id=sample_client.id
    )
    assert total == 2
    assert interactions[0].note == "Second"  # newer first
    assert interactions[1].note == "First"


@pytest.mark.asyncio
async def test_update_interaction(
    db_session: AsyncSession, sample_client: Client, manager: User
):
    from app.services.client_service import create_interaction, update_interaction

    interaction = await create_interaction(
        db_session,
        client_id=sample_client.id,
        author_id=manager.id,
        note="Old note",
    )
    updated = await update_interaction(
        db_session, interaction.id, note="New note"
    )
    assert updated is not None
    assert updated.note == "New note"


@pytest.mark.asyncio
async def test_delete_interaction(
    db_session: AsyncSession, sample_client: Client, manager: User
):
    from app.services.client_service import create_interaction, delete_interaction

    interaction = await create_interaction(
        db_session,
        client_id=sample_client.id,
        author_id=manager.id,
        note="To remove",
    )
    result = await delete_interaction(db_session, interaction.id)
    assert result is True


# ---------------------------------------------------------------------------
# Site attachment
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sample_site(db_session: AsyncSession) -> Site:
    site = Site(
        name="Test Site",
        url="https://test-site.com",
    )
    db_session.add(site)
    await db_session.flush()
    return site


@pytest.mark.asyncio
async def test_attach_site(
    db_session: AsyncSession, sample_client: Client, sample_site: Site
):
    from app.services.client_service import attach_site

    await attach_site(db_session, sample_site.id, sample_client.id)
    await db_session.refresh(sample_site)
    assert sample_site.client_id == sample_client.id


@pytest.mark.asyncio
async def test_attach_site_already_attached_error(
    db_session: AsyncSession, sample_client: Client, sample_site: Site, manager: User
):
    from app.services.client_service import attach_site, create_client

    other = await create_client(db_session, company_name="Other")
    await attach_site(db_session, sample_site.id, sample_client.id)

    with pytest.raises(ValueError, match="already attached"):
        await attach_site(db_session, sample_site.id, other.id)


@pytest.mark.asyncio
async def test_detach_site(
    db_session: AsyncSession, sample_client: Client, sample_site: Site
):
    from app.services.client_service import attach_site, detach_site

    await attach_site(db_session, sample_site.id, sample_client.id)
    await detach_site(db_session, sample_site.id)
    await db_session.refresh(sample_site)
    assert sample_site.client_id is None


@pytest.mark.asyncio
async def test_list_unattached_sites(
    db_session: AsyncSession, sample_client: Client, sample_site: Site
):
    from app.services.client_service import attach_site, list_unattached_sites

    # Before attaching, site should be in unattached list
    sites = await list_unattached_sites(db_session)
    assert any(s.id == sample_site.id for s in sites)

    # After attaching, should not be in general unattached list
    await attach_site(db_session, sample_site.id, sample_client.id)
    sites = await list_unattached_sites(db_session)
    assert not any(s.id == sample_site.id for s in sites)

    # But should appear when current_client_id is provided
    sites = await list_unattached_sites(
        db_session, current_client_id=sample_client.id
    )
    assert any(s.id == sample_site.id for s in sites)


# ---------------------------------------------------------------------------
# Open task count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_open_task_count_for_client(
    db_session: AsyncSession, sample_client: Client, sample_site: Site, manager: User
):
    from app.services.client_service import attach_site, get_open_task_count_for_client

    await attach_site(db_session, sample_site.id, sample_client.id)

    # Add some tasks
    task1 = SeoTask(
        site_id=sample_site.id,
        task_type=TaskType.manual,
        title="Open task",
        status=TaskStatus.open,
    )
    task2 = SeoTask(
        site_id=sample_site.id,
        task_type=TaskType.manual,
        title="Resolved task",
        status=TaskStatus.resolved,
    )
    db_session.add_all([task1, task2])
    await db_session.flush()

    count = await get_open_task_count_for_client(db_session, sample_client.id)
    assert count == 1  # Only non-resolved tasks
