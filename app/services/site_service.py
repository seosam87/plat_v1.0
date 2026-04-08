import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.crawl import CrawlJob
from app.models.keyword import Keyword
from app.models.position import KeywordPosition
from app.models.schedule import CrawlSchedule, PositionSchedule, ScheduleType
from app.models.site import ConnectionStatus, Site
from app.services.audit_service import log_action
from app.services.crypto_service import decrypt, encrypt


# ─── Project Health Widget (Phase 18-01) ────────────────────────────────────


@dataclass
class HealthStep:
    key: str
    title: str
    description: str
    done: bool
    status: str  # "done" | "current" | "pending"
    next_url: str | None
    is_current: bool = False


@dataclass
class SiteHealth:
    steps: list[HealthStep] = field(default_factory=list)
    completed_count: int = 0
    current_step_index: int | None = None
    is_fully_set_up: bool = False
    analytics_connected: bool = False
    keyword_count: int = 0
    crawl_count: int = 0
    competitor_count: int = 0


# Ordered step definitions — (key, title RU, description RU, next_url template)
_STEP_DEFS: list[tuple[str, str, str, str | None]] = [
    (
        "site_created",
        "Сайт создан",
        "Запись о сайте существует в системе",
        None,
    ),
    (
        "wp_creds",
        "Доступ к WordPress настроен",
        "Указаны URL, логин и Application Password",
        "/ui/sites/{site_id}/edit",
    ),
    (
        "keywords",
        "Ключевые слова добавлены",
        "Импортированы или заведены вручную ключи",
        "/ui/keywords/{site_id}",
    ),
    (
        "competitors",
        "Конкуренты добавлены",
        "Указан хотя бы один конкурент для отслеживания",
        "/ui/competitors/{site_id}",
    ),
    (
        "crawl",
        "Первый краул выполнен",
        "Сайт хотя бы раз был просканирован",
        "/ui/sites/{site_id}/crawls",
    ),
    (
        "positions",
        "Позиции проверены",
        "Хотя бы одна проверка позиций выполнена",
        "/ui/positions/{site_id}",
    ),
    (
        "schedule",
        "Расписание настроено",
        "Включён автоматический краул или проверка позиций",
        "/ui/sites/{site_id}/schedule",
    ),
]


async def compute_site_health(
    db: AsyncSession, site_id: uuid.UUID
) -> SiteHealth:
    """Compute a 7-step project setup health snapshot for the given site.

    Synchronous (single request) — ≤ 8 indexed queries total. Exposes raw
    counts so callers can reuse them without duplicating COUNTs.
    """
    site = await db.get(Site, site_id)
    if site is None:
        return SiteHealth()

    async def _count(model, *filters) -> int:
        stmt = select(func.count()).select_from(model).where(*filters)
        return (await db.execute(stmt)).scalar() or 0

    kw_count = await _count(Keyword, Keyword.site_id == site_id)
    comp_count = await _count(Competitor, Competitor.site_id == site_id)
    crawl_count_val = await _count(CrawlJob, CrawlJob.site_id == site_id)
    pos_count = await _count(
        KeywordPosition, KeywordPosition.site_id == site_id
    )
    cs_count = await _count(
        CrawlSchedule,
        CrawlSchedule.site_id == site_id,
        CrawlSchedule.is_active.is_(True),
        CrawlSchedule.schedule_type != ScheduleType.manual,
    )
    ps_count = await _count(
        PositionSchedule,
        PositionSchedule.site_id == site_id,
        PositionSchedule.is_active.is_(True),
        PositionSchedule.schedule_type != ScheduleType.manual,
    )
    sched_count = cs_count + ps_count

    done_flags = [
        True,  # site_created (site is not None)
        bool(site.wp_username and site.encrypted_app_password and site.url),
        kw_count > 0,
        comp_count > 0,
        crawl_count_val > 0,
        pos_count > 0,
        sched_count > 0,
    ]

    steps: list[HealthStep] = []
    current_idx: int | None = None
    for i, (key, title, desc, url_tpl) in enumerate(_STEP_DEFS):
        done = done_flags[i]
        next_url = (
            None
            if done or url_tpl is None
            else url_tpl.format(site_id=site_id)
        )
        if done:
            status = "done"
        elif current_idx is None:
            status = "current"
            current_idx = i
        else:
            status = "pending"
        steps.append(
            HealthStep(
                key=key,
                title=title,
                description=desc,
                done=done,
                status=status,
                next_url=next_url,
                is_current=(status == "current"),
            )
        )

    completed_count = sum(1 for d in done_flags if d)
    is_fully_set_up = completed_count == 7
    analytics_connected = bool(site.metrika_token)

    return SiteHealth(
        steps=steps,
        completed_count=completed_count,
        current_step_index=current_idx,
        is_fully_set_up=is_fully_set_up,
        analytics_connected=analytics_connected,
        keyword_count=kw_count,
        crawl_count=crawl_count_val,
        competitor_count=comp_count,
    )


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
    wp_username: str | None = None,
    app_password: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Site:
    site = Site(
        name=name,
        url=url.rstrip("/"),
        wp_username=wp_username or None,
        encrypted_app_password=encrypt(app_password) if app_password else None,
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
    # Clean up redbeat entries for both crawl and position schedules
    from app.services.schedule_service import remove_redbeat_entry, remove_position_redbeat_entry
    remove_redbeat_entry(site.id)
    remove_position_redbeat_entry(site.id)
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
