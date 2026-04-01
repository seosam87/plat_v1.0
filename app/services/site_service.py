import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import ConnectionStatus, Site
from app.services.audit_service import log_action
from app.services.crypto_service import decrypt, encrypt


async def get_sites(db: AsyncSession) -> list[Site]:
    result = await db.execute(select(Site).order_by(Site.created_at.desc()))
    return list(result.scalars().all())


async def get_site(db: AsyncSession, site_id: uuid.UUID) -> Site | None:
    result = await db.execute(select(Site).where(Site.id == site_id))
    return result.scalar_one_or_none()


async def create_site(
    db: AsyncSession,
    name: str,
    url: str,
    wp_username: str,
    app_password: str,
    actor_id: uuid.UUID | None = None,
) -> Site:
    site = Site(
        name=name,
        url=url.rstrip("/"),
        wp_username=wp_username,
        encrypted_app_password=encrypt(app_password),
    )
    db.add(site)
    await db.flush()
    await log_action(db, action="site.create", user_id=actor_id, entity_type="site", entity_id=str(site.id))
    return site


async def update_site(
    db: AsyncSession,
    site: Site,
    name: str | None = None,
    url: str | None = None,
    wp_username: str | None = None,
    app_password: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Site:
    if name is not None:
        site.name = name
    if url is not None:
        site.url = url.rstrip("/")
    if wp_username is not None:
        site.wp_username = wp_username
    if app_password is not None:
        site.encrypted_app_password = encrypt(app_password)
    await log_action(db, action="site.update", user_id=actor_id, entity_type="site", entity_id=str(site.id))
    return site


async def delete_site(db: AsyncSession, site: Site, actor_id: uuid.UUID | None = None) -> None:
    await log_action(db, action="site.delete", user_id=actor_id, entity_type="site", entity_id=str(site.id))
    await db.delete(site)


async def set_connection_status(db: AsyncSession, site: Site, status: ConnectionStatus) -> Site:
    site.connection_status = status
    return site


async def set_active_status(
    db: AsyncSession,
    site: Site,
    is_active: bool,
    actor_id: uuid.UUID | None = None,
) -> Site:
    site.is_active = is_active
    action = "site.enable" if is_active else "site.disable"
    await log_action(db, action=action, user_id=actor_id, entity_type="site", entity_id=str(site.id))
    return site


def get_decrypted_password(site: Site) -> str:
    """Decrypt WP Application Password for call-time use only. Never log or return to client."""
    return decrypt(site.encrypted_app_password)
