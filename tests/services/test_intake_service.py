"""Tests for intake service layer: intake_service.py.

Uses real DB session from conftest.py (SAVEPOINT-isolated).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl import CrawlJob, CrawlJobStatus
from app.models.oauth_token import OAuthToken
from app.models.site import ConnectionStatus, Site
from app.models.site_intake import IntakeStatus, SiteIntake


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def site(db_session: AsyncSession) -> Site:
    """A basic connected site."""
    s = Site(
        name="Test Site",
        url="https://test-intake.com",
        connection_status=ConnectionStatus.connected,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest_asyncio.fixture
async def site_unknown(db_session: AsyncSession) -> Site:
    """A site with unknown connection status."""
    s = Site(
        name="Unknown Site",
        url="https://unknown-intake.com",
        connection_status=ConnectionStatus.unknown,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest_asyncio.fixture
async def site_with_gsc(db_session: AsyncSession, site: Site) -> Site:
    """Site that also has a GSC OAuth token."""
    token = OAuthToken(
        site_id=site.id,
        provider="gsc",
        access_token="fake_encrypted_token",
    )
    db_session.add(token)
    await db_session.flush()
    return site


@pytest_asyncio.fixture
async def site_with_crawl(db_session: AsyncSession, site: Site) -> Site:
    """Site that has a completed crawl job."""
    job = CrawlJob(
        site_id=site.id,
        status=CrawlJobStatus.done,
    )
    db_session.add(job)
    await db_session.flush()
    return site


@pytest_asyncio.fixture
async def site_with_metrika(db_session: AsyncSession) -> Site:
    """A site with a Metrika counter ID configured."""
    s = Site(
        name="Metrika Site",
        url="https://metrika-intake.com",
        connection_status=ConnectionStatus.connected,
        metrika_counter_id="12345678",
    )
    db_session.add(s)
    await db_session.flush()
    return s


# ---------------------------------------------------------------------------
# get_or_create_intake
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_intake_creates_new(
    db_session: AsyncSession, site: Site
):
    from app.services.intake_service import get_or_create_intake

    intake = await get_or_create_intake(db_session, site_id=site.id)
    assert intake.id is not None
    assert intake.site_id == site.id
    assert intake.status == IntakeStatus.draft
    assert intake.section_goals is False
    assert intake.section_access is False


@pytest.mark.asyncio
async def test_get_or_create_intake_returns_existing(
    db_session: AsyncSession, site: Site
):
    from app.services.intake_service import get_or_create_intake

    intake1 = await get_or_create_intake(db_session, site_id=site.id)
    intake2 = await get_or_create_intake(db_session, site_id=site.id)
    assert intake1.id == intake2.id


# ---------------------------------------------------------------------------
# save_goals_section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_goals_section(db_session: AsyncSession, site: Site):
    from app.services.intake_service import save_goals_section

    data = {
        "main_goal": "Increase organic traffic",
        "target_regions": "Moscow",
        "competitors": ["example.com"],
        "notes": "Focus on blog",
    }
    intake = await save_goals_section(db_session, site_id=site.id, data=data)
    assert intake.section_goals is True
    assert intake.goals_data == data
    assert intake.goals_data["main_goal"] == "Increase organic traffic"


# ---------------------------------------------------------------------------
# save_technical_section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_technical_section(db_session: AsyncSession, site: Site):
    from app.services.intake_service import save_technical_section

    data = {"robots_notes": "Block /wp-admin"}
    intake = await save_technical_section(db_session, site_id=site.id, data=data)
    assert intake.section_technical is True
    assert intake.technical_data == data
    assert intake.technical_data["robots_notes"] == "Block /wp-admin"


# ---------------------------------------------------------------------------
# save_access_section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_access_section(db_session: AsyncSession, site: Site):
    from app.services.intake_service import save_access_section

    intake = await save_access_section(db_session, site_id=site.id)
    assert intake.section_access is True


# ---------------------------------------------------------------------------
# save_analytics_section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_analytics_section(db_session: AsyncSession, site: Site):
    from app.services.intake_service import save_analytics_section

    intake = await save_analytics_section(db_session, site_id=site.id)
    assert intake.section_analytics is True


# ---------------------------------------------------------------------------
# save_checklist_section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_checklist_section(db_session: AsyncSession, site: Site):
    from app.services.intake_service import save_checklist_section

    intake = await save_checklist_section(db_session, site_id=site.id)
    assert intake.section_checklist is True


# ---------------------------------------------------------------------------
# get_verification_checklist — WP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checklist_wp_connected(db_session: AsyncSession, site: Site):
    """Site with connected status shows 'connected' for WP check."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(db_session, site_id=site.id)
    assert len(checklist) == 5
    wp_item = next(item for item in checklist if item["label"] == "WP подключен")
    assert wp_item["status"] == "connected"


@pytest.mark.asyncio
async def test_checklist_wp_unknown(
    db_session: AsyncSession, site_unknown: Site
):
    """Site with unknown connection status shows 'unknown' for WP check."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(db_session, site_id=site_unknown.id)
    wp_item = next(item for item in checklist if item["label"] == "WP подключен")
    assert wp_item["status"] == "unknown"


# ---------------------------------------------------------------------------
# get_verification_checklist — GSC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checklist_gsc_connected(
    db_session: AsyncSession, site_with_gsc: Site
):
    """Site with GSC OAuthToken shows 'connected' for GSC check."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(
        db_session, site_id=site_with_gsc.id
    )
    gsc_item = next(item for item in checklist if item["label"] == "GSC подключен")
    assert gsc_item["status"] == "connected"


@pytest.mark.asyncio
async def test_checklist_no_gsc(db_session: AsyncSession, site: Site):
    """Site without GSC OAuthToken shows 'not_configured'."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(db_session, site_id=site.id)
    gsc_item = next(item for item in checklist if item["label"] == "GSC подключен")
    assert gsc_item["status"] == "not_configured"


# ---------------------------------------------------------------------------
# get_verification_checklist — Metrika
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checklist_metrika_connected(
    db_session: AsyncSession, site_with_metrika: Site
):
    """Site with metrika_counter_id shows 'connected' for Metrika check."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(
        db_session, site_id=site_with_metrika.id
    )
    metrika_item = next(
        item for item in checklist if item["label"] == "Метрика подключена"
    )
    assert metrika_item["status"] == "connected"


@pytest.mark.asyncio
async def test_checklist_no_metrika(db_session: AsyncSession, site: Site):
    """Site without metrika_counter_id shows 'not_configured'."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(db_session, site_id=site.id)
    metrika_item = next(
        item for item in checklist if item["label"] == "Метрика подключена"
    )
    assert metrika_item["status"] == "not_configured"


# ---------------------------------------------------------------------------
# get_verification_checklist — crawl
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checklist_crawl_done(
    db_session: AsyncSession, site_with_crawl: Site
):
    """Site with a completed crawl job shows 'connected' for crawl check."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(
        db_session, site_id=site_with_crawl.id
    )
    crawl_item = next(item for item in checklist if item["label"] == "Краул выполнен")
    assert crawl_item["status"] == "connected"


# ---------------------------------------------------------------------------
# complete_intake / reopen_intake
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_intake(db_session: AsyncSession, site: Site):
    from app.services.intake_service import complete_intake

    intake = await complete_intake(db_session, site_id=site.id)
    assert intake.status == IntakeStatus.complete


@pytest.mark.asyncio
async def test_reopen_intake_keeps_flags(db_session: AsyncSession, site: Site):
    """Reopening sets status to draft but preserves section flags."""
    from app.services.intake_service import (
        complete_intake,
        reopen_intake,
        save_access_section,
        save_goals_section,
    )

    await save_goals_section(
        db_session,
        site_id=site.id,
        data={"main_goal": "Traffic"},
    )
    await save_access_section(db_session, site_id=site.id)
    await complete_intake(db_session, site_id=site.id)

    intake = await reopen_intake(db_session, site_id=site.id)
    assert intake.status == IntakeStatus.draft
    # Flags must be preserved
    assert intake.section_goals is True
    assert intake.section_access is True


# ---------------------------------------------------------------------------
# get_intake_statuses_for_sites
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_intake_statuses_for_sites(db_session: AsyncSession, site: Site):
    """Batch query returns correct {site_id: status} dict."""
    from app.services.intake_service import (
        complete_intake,
        get_intake_statuses_for_sites,
        get_or_create_intake,
    )

    await get_or_create_intake(db_session, site_id=site.id)

    # Create a second site
    site2 = Site(name="Second Site", url="https://second-intake.com")
    db_session.add(site2)
    await db_session.flush()
    await complete_intake(db_session, site_id=site2.id)

    # Site with no intake record
    site3 = Site(name="No Intake Site", url="https://no-intake.com")
    db_session.add(site3)
    await db_session.flush()

    statuses = await get_intake_statuses_for_sites(
        db_session, site_ids=[site.id, site2.id, site3.id]
    )
    assert statuses[site.id] == "draft"
    assert statuses[site2.id] == "complete"
    assert site3.id not in statuses  # no intake record


@pytest.mark.asyncio
async def test_get_intake_statuses_for_sites_empty(db_session: AsyncSession):
    """Empty site_ids returns empty dict."""
    from app.services.intake_service import get_intake_statuses_for_sites

    result = await get_intake_statuses_for_sites(db_session, site_ids=[])
    assert result == {}


# ---------------------------------------------------------------------------
# Checklist structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checklist_returns_exactly_5_items(
    db_session: AsyncSession, site: Site
):
    """Checklist always returns exactly 5 items with expected labels."""
    from app.services.intake_service import get_verification_checklist

    checklist = await get_verification_checklist(db_session, site_id=site.id)
    assert len(checklist) == 5
    expected_labels = {
        "WP подключен",
        "GSC подключен",
        "Метрика подключена",
        "Sitemap найден",
        "Краул выполнен",
    }
    actual_labels = {item["label"] for item in checklist}
    assert actual_labels == expected_labels
    valid_statuses = {"connected", "not_configured", "unknown"}
    for item in checklist:
        assert item["status"] in valid_statuses, f"Invalid status: {item}"
