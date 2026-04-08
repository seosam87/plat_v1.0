"""Unit tests for app.services.site_service.compute_site_health (Phase 18-01).

Covers each of the 7 health signals plus aggregate behaviour. Uses the real
async DB session fixture from tests/conftest.py — no SQLAlchemy mocking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.models.site import Site, ConnectionStatus
from app.models.keyword import Keyword
from app.models.competitor import Competitor
from app.models.crawl import CrawlJob, CrawlJobStatus
from app.models.position import KeywordPosition
from app.models.schedule import CrawlSchedule, PositionSchedule, ScheduleType


pytestmark = pytest.mark.asyncio


async def _make_site(db, **overrides) -> Site:
    site = Site(
        name=overrides.pop("name", "Test Site"),
        url=overrides.pop("url", f"https://ex-{uuid.uuid4().hex[:8]}.test"),
        connection_status=ConnectionStatus.unknown,
        **overrides,
    )
    db.add(site)
    await db.flush()
    return site


async def _ensure_kp_partition(db) -> None:
    """Ensure there's a DEFAULT partition for keyword_positions so we can insert."""
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS keyword_positions_default "
            "PARTITION OF keyword_positions DEFAULT"
        )
    )


# ─── Individual signal tests ────────────────────────────────────────────────


async def test_step1_site_created_always_done(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session)
    health = await compute_site_health(db_session, site.id)
    assert health.steps[0].done is True
    assert health.steps[0].key == "site_created"


async def test_step2_wp_creds_done(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(
        db_session, wp_username="admin", encrypted_app_password="enc"
    )
    h = await compute_site_health(db_session, site.id)
    assert h.steps[1].key == "wp_creds"
    assert h.steps[1].done is True

    site2 = await _make_site(db_session, wp_username="admin")
    h2 = await compute_site_health(db_session, site2.id)
    assert h2.steps[1].done is False


async def test_step3_keywords_done(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session)
    h0 = await compute_site_health(db_session, site.id)
    assert h0.steps[2].done is False
    assert h0.keyword_count == 0

    db_session.add(Keyword(site_id=site.id, phrase="test kw"))
    await db_session.flush()
    h = await compute_site_health(db_session, site.id)
    assert h.steps[2].key == "keywords"
    assert h.steps[2].done is True
    assert h.keyword_count == 1


async def test_step4_competitors_done(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session)
    h0 = await compute_site_health(db_session, site.id)
    assert h0.steps[3].done is False
    assert h0.competitor_count == 0

    db_session.add(Competitor(site_id=site.id, domain="rival.com"))
    await db_session.flush()
    h = await compute_site_health(db_session, site.id)
    assert h.steps[3].key == "competitors"
    assert h.steps[3].done is True
    assert h.competitor_count == 1


async def test_step5_crawl_done(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session)
    h0 = await compute_site_health(db_session, site.id)
    assert h0.steps[4].done is False
    assert h0.crawl_count == 0

    db_session.add(CrawlJob(site_id=site.id, status=CrawlJobStatus.done))
    await db_session.flush()
    h = await compute_site_health(db_session, site.id)
    assert h.steps[4].key == "crawl"
    assert h.steps[4].done is True
    assert h.crawl_count == 1


async def test_step6_position_done(db_session):
    from app.services.site_service import compute_site_health

    await _ensure_kp_partition(db_session)
    site = await _make_site(db_session)
    kw = Keyword(site_id=site.id, phrase="p")
    db_session.add(kw)
    await db_session.flush()

    h0 = await compute_site_health(db_session, site.id)
    assert h0.steps[5].done is False

    db_session.add(
        KeywordPosition(
            keyword_id=kw.id,
            site_id=site.id,
            engine="yandex",
            position=5,
            checked_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()
    h = await compute_site_health(db_session, site.id)
    assert h.steps[5].key == "positions"
    assert h.steps[5].done is True


async def test_step7_schedule_done(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session)
    # manual → not done
    db_session.add(
        CrawlSchedule(
            site_id=site.id, schedule_type=ScheduleType.manual, is_active=True
        )
    )
    await db_session.flush()
    h = await compute_site_health(db_session, site.id)
    assert h.steps[6].done is False

    site2 = await _make_site(db_session)
    db_session.add(
        CrawlSchedule(
            site_id=site2.id, schedule_type=ScheduleType.daily, is_active=False
        )
    )
    await db_session.flush()
    h2 = await compute_site_health(db_session, site2.id)
    assert h2.steps[6].done is False

    site3 = await _make_site(db_session)
    db_session.add(
        CrawlSchedule(
            site_id=site3.id, schedule_type=ScheduleType.daily, is_active=True
        )
    )
    await db_session.flush()
    h3 = await compute_site_health(db_session, site3.id)
    assert h3.steps[6].key == "schedule"
    assert h3.steps[6].done is True


async def test_progress_counts_partial(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(
        db_session, wp_username="u", encrypted_app_password="e"
    )
    db_session.add(Keyword(site_id=site.id, phrase="p"))
    await db_session.flush()
    h = await compute_site_health(db_session, site.id)
    # steps 1,2,3 done (indexes 0,1,2)
    assert h.completed_count == 3
    assert h.current_step_index == 3
    assert h.is_fully_set_up is False


async def test_fully_set_up(db_session):
    from app.services.site_service import compute_site_health

    await _ensure_kp_partition(db_session)
    site = await _make_site(
        db_session, wp_username="u", encrypted_app_password="e"
    )
    kw = Keyword(site_id=site.id, phrase="p")
    db_session.add_all(
        [
            kw,
            Competitor(site_id=site.id, domain="r.com"),
            CrawlJob(site_id=site.id, status=CrawlJobStatus.done),
            CrawlSchedule(
                site_id=site.id,
                schedule_type=ScheduleType.daily,
                is_active=True,
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        KeywordPosition(
            keyword_id=kw.id,
            site_id=site.id,
            engine="yandex",
            position=1,
            checked_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()

    h = await compute_site_health(db_session, site.id)
    assert h.completed_count == 7
    assert h.is_fully_set_up is True
    assert h.current_step_index is None


async def test_analytics_secondary(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session, metrika_token="tok")
    h = await compute_site_health(db_session, site.id)
    assert h.analytics_connected is True
    # does not make site fully set up
    assert h.is_fully_set_up is False


async def test_next_step_url_present_for_pending(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session)
    h = await compute_site_health(db_session, site.id)
    for step in h.steps:
        if not step.done:
            assert step.next_url, f"pending step {step.key} missing next_url"


async def test_competitors_next_url_format(db_session):
    from app.services.site_service import compute_site_health

    site = await _make_site(db_session)
    h = await compute_site_health(db_session, site.id)
    comp = next(s for s in h.steps if s.key == "competitors")
    assert comp.next_url == f"/ui/competitors/{site.id}"
