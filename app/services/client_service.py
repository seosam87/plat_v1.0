"""Client CRM service: CRUD for clients, contacts, interactions, site linking."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientContact, ClientInteraction
from app.models.site import Site
from app.models.task import SeoTask, TaskStatus


# ---- Clients ----


async def list_clients(
    db: AsyncSession,
    *,
    search: str | None = None,
    manager_id: uuid.UUID | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Client], int]:
    query = select(Client).where(Client.is_deleted == False)  # noqa: E712

    if search:
        term = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Client.company_name).like(term),
                func.lower(Client.inn).like(term),
                func.lower(Client.email).like(term),
            )
        )

    if manager_id is not None:
        query = query.where(Client.manager_id == manager_id)

    if created_from is not None:
        query = query.where(Client.created_at >= datetime.combine(created_from, datetime.min.time(), tzinfo=timezone.utc))

    if created_to is not None:
        query = query.where(Client.created_at <= datetime.combine(created_to, datetime.max.time(), tzinfo=timezone.utc))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Client.company_name.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_client(db: AsyncSession, client_id: uuid.UUID) -> Client | None:
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.is_deleted == False)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def create_client(
    db: AsyncSession,
    *,
    company_name: str,
    legal_name: str | None = None,
    inn: str | None = None,
    kpp: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    notes: str | None = None,
    manager_id: uuid.UUID | None = None,
) -> Client:
    client = Client(
        company_name=company_name,
        legal_name=legal_name,
        inn=inn,
        kpp=kpp,
        phone=phone,
        email=email,
        notes=notes,
        manager_id=manager_id,
    )
    db.add(client)
    await db.flush()
    logger.info("Created client {} ({})", client.id, company_name)
    return client


async def update_client(
    db: AsyncSession,
    client_id: uuid.UUID,
    **kwargs: str | uuid.UUID | None,
) -> Client | None:
    client = await get_client(db, client_id)
    if client is None:
        return None
    for key, value in kwargs.items():
        if hasattr(client, key):
            setattr(client, key, value)
    await db.flush()
    logger.info("Updated client {}", client_id)
    return client


async def delete_client(db: AsyncSession, client_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.is_deleted == False)  # noqa: E712
    )
    client = result.scalar_one_or_none()
    if client is None:
        return False
    client.is_deleted = True
    await db.flush()
    logger.info("Soft-deleted client {}", client_id)
    return True


# ---- Contacts ----


async def create_contact(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    role: str | None = None,
    telegram_username: str | None = None,
    notes: str | None = None,
) -> ClientContact:
    contact = ClientContact(
        client_id=client_id,
        name=name,
        phone=phone,
        email=email,
        role=role,
        telegram_username=telegram_username,
        notes=notes,
    )
    db.add(contact)
    await db.flush()
    logger.info("Created contact {} for client {}", contact.id, client_id)
    return contact


async def update_contact(
    db: AsyncSession,
    contact_id: uuid.UUID,
    client_id: uuid.UUID,
    **kwargs: str | None,
) -> ClientContact | None:
    result = await db.execute(
        select(ClientContact).where(
            ClientContact.id == contact_id,
            ClientContact.client_id == client_id,
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        return None
    for key, value in kwargs.items():
        if hasattr(contact, key):
            setattr(contact, key, value)
    await db.flush()
    logger.info("Updated contact {}", contact_id)
    return contact


async def delete_contact(db: AsyncSession, contact_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(ClientContact).where(ClientContact.id == contact_id)
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        return False
    await db.delete(contact)
    await db.flush()
    logger.info("Deleted contact {}", contact_id)
    return True


# ---- Interactions ----


async def list_interactions(
    db: AsyncSession,
    client_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[ClientInteraction], int]:
    base = select(ClientInteraction).where(ClientInteraction.client_id == client_id)

    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = base.order_by(ClientInteraction.interaction_date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def create_interaction(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    author_id: uuid.UUID | None = None,
    note: str,
    interaction_date: datetime | None = None,
) -> ClientInteraction:
    interaction = ClientInteraction(
        client_id=client_id,
        author_id=author_id,
        note=note,
        interaction_date=interaction_date or datetime.now(timezone.utc),
    )
    db.add(interaction)
    await db.flush()
    logger.info("Created interaction {} for client {}", interaction.id, client_id)
    return interaction


async def update_interaction(
    db: AsyncSession,
    interaction_id: uuid.UUID,
    *,
    note: str,
) -> ClientInteraction | None:
    result = await db.execute(
        select(ClientInteraction).where(ClientInteraction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if interaction is None:
        return None
    interaction.note = note
    await db.flush()
    logger.info("Updated interaction {}", interaction_id)
    return interaction


async def delete_interaction(db: AsyncSession, interaction_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(ClientInteraction).where(ClientInteraction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if interaction is None:
        return False
    await db.delete(interaction)
    await db.flush()
    logger.info("Deleted interaction {}", interaction_id)
    return True


# ---- Site linking ----


async def attach_site(
    db: AsyncSession, site_id: uuid.UUID, client_id: uuid.UUID
) -> None:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if site is None:
        raise ValueError(f"Site {site_id} not found")
    if site.client_id is not None and site.client_id != client_id:
        raise ValueError("Site already attached to another client")
    site.client_id = client_id
    await db.flush()
    logger.info("Attached site {} to client {}", site_id, client_id)


async def detach_site(db: AsyncSession, site_id: uuid.UUID) -> None:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if site is None:
        raise ValueError(f"Site {site_id} not found")
    site.client_id = None
    await db.flush()
    logger.info("Detached site {}", site_id)


async def list_unattached_sites(
    db: AsyncSession,
    *,
    search: str | None = None,
    current_client_id: uuid.UUID | None = None,
) -> list[Site]:
    if current_client_id is not None:
        query = select(Site).where(
            or_(Site.client_id.is_(None), Site.client_id == current_client_id)
        )
    else:
        query = select(Site).where(Site.client_id.is_(None))

    if search:
        term = f"%{search.lower()}%"
        query = query.where(func.lower(Site.url).like(term))

    query = query.order_by(Site.url.asc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_open_task_count_for_client(
    db: AsyncSession, client_id: uuid.UUID
) -> int:
    query = (
        select(func.count())
        .select_from(SeoTask)
        .join(Site, SeoTask.site_id == Site.id)
        .where(Site.client_id == client_id, SeoTask.status != TaskStatus.resolved)
    )
    return (await db.execute(query)).scalar_one()
