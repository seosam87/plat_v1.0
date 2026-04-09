"""Intake service: CRUD + verification checklist for site audit intake feature."""
from __future__ import annotations

import uuid
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.architecture import SitemapEntry
from app.models.crawl import CrawlJob, CrawlJobStatus
from app.models.oauth_token import OAuthToken
from app.models.site import ConnectionStatus, Site
from app.models.site_intake import IntakeStatus, SiteIntake


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_intake(db: AsyncSession, site_id: uuid.UUID) -> SiteIntake | None:
    result = await db.execute(
        select(SiteIntake).where(SiteIntake.site_id == site_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def get_or_create_intake(
    db: AsyncSession, *, site_id: uuid.UUID
) -> SiteIntake:
    """Return existing intake for site_id, or create a new draft one.

    Handles IntegrityError gracefully on race conditions by retrying SELECT.
    """
    intake = await _get_intake(db, site_id)
    if intake is not None:
        return intake

    try:
        intake = SiteIntake(site_id=site_id, status=IntakeStatus.draft)
        db.add(intake)
        await db.flush()
        logger.info("Created intake {} for site {}", intake.id, site_id)
        return intake
    except IntegrityError:
        # Race condition: another process created one; retry SELECT
        await db.rollback()
        intake = await _get_intake(db, site_id)
        if intake is None:
            raise
        return intake


async def save_goals_section(
    db: AsyncSession, *, site_id: uuid.UUID, data: dict[str, Any]
) -> SiteIntake:
    """Store goals_data dict and mark section_goals=True."""
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.goals_data = data
    intake.section_goals = True
    await db.flush()
    logger.debug("Saved goals section for site {}", site_id)
    return intake


async def save_technical_section(
    db: AsyncSession, *, site_id: uuid.UUID, data: dict[str, Any]
) -> SiteIntake:
    """Store technical_data dict and mark section_technical=True."""
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.technical_data = data
    intake.section_technical = True
    await db.flush()
    logger.debug("Saved technical section for site {}", site_id)
    return intake


async def save_access_section(
    db: AsyncSession, *, site_id: uuid.UUID
) -> SiteIntake:
    """Mark section_access=True (read-only tab — no data to store)."""
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.section_access = True
    await db.flush()
    logger.debug("Saved access section for site {}", site_id)
    return intake


async def save_analytics_section(
    db: AsyncSession, *, site_id: uuid.UUID
) -> SiteIntake:
    """Mark section_analytics=True (read-only tab — no data to store)."""
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.section_analytics = True
    await db.flush()
    logger.debug("Saved analytics section for site {}", site_id)
    return intake


async def save_checklist_section(
    db: AsyncSession, *, site_id: uuid.UUID
) -> SiteIntake:
    """Mark section_checklist=True (derived tab — no data to store)."""
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.section_checklist = True
    await db.flush()
    logger.debug("Saved checklist section for site {}", site_id)
    return intake


async def get_verification_checklist(
    db: AsyncSession, *, site_id: uuid.UUID
) -> list[dict[str, str]]:
    """Return a list of 5 checklist items querying Site, OAuthToken, SitemapEntry, CrawlJob.

    Each item has keys: "label" (str) and "status" ("connected" | "not_configured" | "unknown").
    """
    # 1. WP connection status from Site model
    site_result = await db.execute(
        select(Site.connection_status, Site.metrika_counter_id).where(Site.id == site_id)
    )
    site_row = site_result.one_or_none()

    if site_row is None:
        wp_status = "not_configured"
        metrika_status = "not_configured"
    else:
        connection_status, metrika_counter_id = site_row
        if connection_status == ConnectionStatus.connected:
            wp_status = "connected"
        elif connection_status == ConnectionStatus.failed:
            wp_status = "not_configured"
        else:
            wp_status = "unknown"

        # 3. Metrika: counter_id present and non-empty
        if metrika_counter_id and metrika_counter_id.strip():
            metrika_status = "connected"
        else:
            metrika_status = "not_configured"

    # 2. GSC: count oauth_tokens for this site with provider='gsc'
    gsc_count_result = await db.execute(
        select(func.count()).select_from(OAuthToken).where(
            OAuthToken.site_id == site_id,
            OAuthToken.provider == "gsc",
        )
    )
    gsc_count = gsc_count_result.scalar_one()
    gsc_status = "connected" if gsc_count > 0 else "not_configured"

    # 4. Sitemap: count sitemap_entries for this site
    sitemap_count_result = await db.execute(
        select(func.count()).select_from(SitemapEntry).where(
            SitemapEntry.site_id == site_id
        )
    )
    sitemap_count = sitemap_count_result.scalar_one()
    sitemap_status = "connected" if sitemap_count > 0 else "not_configured"

    # 5. Crawl: count crawl_jobs with status='done' for this site
    crawl_count_result = await db.execute(
        select(func.count()).select_from(CrawlJob).where(
            CrawlJob.site_id == site_id,
            CrawlJob.status == CrawlJobStatus.done,
        )
    )
    crawl_count = crawl_count_result.scalar_one()
    crawl_status = "connected" if crawl_count > 0 else "not_configured"

    return [
        {"label": "WP подключен", "status": wp_status},
        {"label": "GSC подключен", "status": gsc_status},
        {"label": "Метрика подключена", "status": metrika_status},
        {"label": "Sitemap найден", "status": sitemap_status},
        {"label": "Краул выполнен", "status": crawl_status},
    ]


async def complete_intake(
    db: AsyncSession, *, site_id: uuid.UUID
) -> SiteIntake:
    """Set intake status to complete."""
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.status = IntakeStatus.complete
    await db.flush()
    logger.info("Completed intake for site {}", site_id)
    return intake


async def reopen_intake(
    db: AsyncSession, *, site_id: uuid.UUID
) -> SiteIntake:
    """Set intake status back to draft; section flags remain intact."""
    intake = await get_or_create_intake(db, site_id=site_id)
    intake.status = IntakeStatus.draft
    await db.flush()
    logger.info("Reopened intake for site {}", site_id)
    return intake


async def get_intake_statuses_for_sites(
    db: AsyncSession, *, site_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Batch query returning {site_id: status_value} for the given site IDs.

    Avoids N+1 when rendering site lists. Returns only sites that have an intake record.
    """
    if not site_ids:
        return {}

    result = await db.execute(
        select(SiteIntake.site_id, SiteIntake.status).where(
            SiteIntake.site_id.in_(site_ids)
        )
    )
    return {row.site_id: row.status.value for row in result.all()}
