"""Unit tests for quick wins service.

Tests verify:
- get_quick_wins returns pages with avg position 4-20
- Pages outside 4-20 range are excluded
- opportunity_score = (21 - avg_position) * weekly_traffic
- Results are sorted by opportunity_score descending
- issue_type filter works (missing_toc, missing_schema, low_links, thin_content)
- content_type filter works
- dispatch_batch_fix creates WpContentJob records
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.quick_wins_service import dispatch_batch_fix, get_quick_wins


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _insert_site(db: AsyncSession, site_id: uuid.UUID, name: str = "Test Site") -> None:
    await db.execute(
        text(
            "INSERT INTO sites (id, name, url, wp_url, created_at, updated_at) "
            "VALUES (:id, :name, :url, :url, NOW(), NOW())"
        ),
        {"id": site_id, "name": name, "url": f"https://{name.lower().replace(' ', '')}.com"},
    )


async def _insert_keyword(
    db: AsyncSession, keyword_id: uuid.UUID, site_id: uuid.UUID, phrase: str = "test phrase"
) -> None:
    await db.execute(
        text(
            "INSERT INTO keywords (id, site_id, phrase, created_at, updated_at) "
            "VALUES (:id, :site_id, :phrase, NOW(), NOW())"
        ),
        {"id": keyword_id, "site_id": site_id, "phrase": phrase},
    )


async def _insert_klp(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword_id: uuid.UUID,
    position: int,
    url: str,
    engine: str = "yandex",
) -> None:
    """Insert a KeywordLatestPosition row."""
    await db.execute(
        text(
            "INSERT INTO keyword_latest_positions "
            "(id, keyword_id, site_id, engine, position, url, checked_at, updated_at) "
            "VALUES (:id, :kwid, :sid, :engine, :pos, :url, NOW(), NOW()) "
            "ON CONFLICT (keyword_id, engine) DO UPDATE SET position=EXCLUDED.position, url=EXCLUDED.url"
        ),
        {
            "id": uuid.uuid4(),
            "kwid": keyword_id,
            "sid": site_id,
            "engine": engine,
            "pos": position,
            "url": url,
        },
    )


async def _insert_crawl_job(db: AsyncSession, site_id: uuid.UUID) -> uuid.UUID:
    crawl_job_id = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO crawl_jobs (id, site_id, status, pages_crawled) "
            "VALUES (:id, :site_id, 'done', 1)"
        ),
        {"id": crawl_job_id, "site_id": site_id},
    )
    return crawl_job_id


async def _insert_page(
    db: AsyncSession,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
    url: str,
    has_toc: bool = False,
    has_schema: bool = False,
    word_count: int = 500,
    inlinks_count: int = 5,
    content_type: str = "informational",
) -> uuid.UUID:
    page_id = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO pages (id, site_id, crawl_job_id, url, has_toc, has_schema, "
            "word_count, inlinks_count, content_type, page_type, architecture_role, "
            "http_status, depth, internal_link_count, source, crawled_at) "
            "VALUES (:id, :site_id, :crawl_job_id, :url, :has_toc, :has_schema, "
            ":word_count, :inlinks_count, :content_type, 'unknown', 'unknown', "
            "200, 1, 0, 'crawl', NOW())"
        ),
        {
            "id": page_id,
            "site_id": site_id,
            "crawl_job_id": crawl_job_id,
            "url": url,
            "has_toc": has_toc,
            "has_schema": has_schema,
            "word_count": word_count,
            "inlinks_count": inlinks_count,
            "content_type": content_type,
        },
    )
    return page_id


async def _insert_metrika_traffic(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_url: str,
    visits: int,
    days_ago: int = 3,
) -> None:
    period_end = date.today() - timedelta(days=days_ago)
    period_start = period_end - timedelta(days=6)
    await db.execute(
        text(
            "INSERT INTO metrika_traffic_pages "
            "(id, site_id, period_start, period_end, page_url, visits, created_at) "
            "VALUES (:id, :site_id, :period_start, :period_end, :page_url, :visits, NOW()) "
            "ON CONFLICT (site_id, period_start, period_end, page_url) DO UPDATE SET visits=EXCLUDED.visits"
        ),
        {
            "id": uuid.uuid4(),
            "site_id": site_id,
            "period_start": period_start,
            "period_end": period_end,
            "page_url": page_url,
            "visits": visits,
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_quick_wins_returns_pages_in_range(db_session: AsyncSession):
    """Pages with position 4-20 appear; pages outside the range do not."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    kw1 = uuid.uuid4()
    kw2 = uuid.uuid4()
    kw3 = uuid.uuid4()
    await _insert_keyword(db_session, kw1, site_id, "kw in range")
    await _insert_keyword(db_session, kw2, site_id, "kw too low")
    await _insert_keyword(db_session, kw3, site_id, "kw too high")

    in_range_url = "https://example.com/in-range/"
    too_low_url = "https://example.com/too-low/"
    too_high_url = "https://example.com/too-high/"

    await _insert_klp(db_session, site_id, kw1, 10, in_range_url)
    await _insert_klp(db_session, site_id, kw2, 25, too_low_url)   # outside range (>20)
    await _insert_klp(db_session, site_id, kw3, 1, too_high_url)   # outside range (<4)

    crawl_job_id = await _insert_crawl_job(db_session, site_id)
    await _insert_page(db_session, site_id, crawl_job_id, in_range_url, has_toc=False)
    await _insert_page(db_session, site_id, crawl_job_id, too_low_url, has_toc=False)
    await _insert_page(db_session, site_id, crawl_job_id, too_high_url, has_toc=False)

    await db_session.flush()

    results = await get_quick_wins(db_session, site_id)
    urls = [r["url"] for r in results]

    assert in_range_url in urls, "Page in range 4-20 should appear"
    assert too_low_url not in urls, "Page at position 25 should not appear"
    assert too_high_url not in urls, "Page at position 1 should not appear"


@pytest.mark.asyncio
async def test_opportunity_score_formula(db_session: AsyncSession):
    """Score = (21 - avg_position) * weekly_traffic; position=5, traffic=100 -> score=1600."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    kw = uuid.uuid4()
    await _insert_keyword(db_session, kw, site_id, "score test")

    page_url = "https://example.com/score-page/"
    await _insert_klp(db_session, site_id, kw, 5, page_url)

    crawl_job_id = await _insert_crawl_job(db_session, site_id)
    await _insert_page(db_session, site_id, crawl_job_id, page_url, has_toc=False)

    await _insert_metrika_traffic(db_session, site_id, page_url, 100)
    await db_session.flush()

    results = await get_quick_wins(db_session, site_id)
    assert len(results) >= 1

    page = next((r for r in results if r["url"] == page_url), None)
    assert page is not None
    # (21 - 5) * 100 = 1600
    assert page["opportunity_score"] == pytest.approx(1600, rel=0.1)


@pytest.mark.asyncio
async def test_sorted_by_score_desc(db_session: AsyncSession):
    """Results are sorted by opportunity_score descending by default."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    crawl_job_id = await _insert_crawl_job(db_session, site_id)

    urls_and_positions = [
        ("https://example.com/low-score/", 18, 10),   # score = 3 * 10 = 30
        ("https://example.com/high-score/", 5, 200),  # score = 16 * 200 = 3200
        ("https://example.com/mid-score/", 10, 100),  # score = 11 * 100 = 1100
    ]

    for url, pos, traffic in urls_and_positions:
        kw = uuid.uuid4()
        await _insert_keyword(db_session, kw, site_id, f"kw for {url}")
        await _insert_klp(db_session, site_id, kw, pos, url)
        await _insert_page(db_session, site_id, crawl_job_id, url, has_toc=False)
        await _insert_metrika_traffic(db_session, site_id, url, traffic)

    await db_session.flush()

    results = await get_quick_wins(db_session, site_id)
    scores = [r["opportunity_score"] for r in results if r["url"] in [u for u, _, _ in urls_and_positions]]
    # Must be descending
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], f"Not sorted descending: {scores}"


@pytest.mark.asyncio
async def test_filter_by_issue_type_missing_toc(db_session: AsyncSession):
    """Filter issue_type='missing_toc' returns only pages where has_toc=False."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)
    crawl_job_id = await _insert_crawl_job(db_session, site_id)

    kw1, kw2 = uuid.uuid4(), uuid.uuid4()
    await _insert_keyword(db_session, kw1, site_id, "no toc page")
    await _insert_keyword(db_session, kw2, site_id, "has toc page")

    url_no_toc = "https://example.com/no-toc/"
    url_has_toc = "https://example.com/has-toc/"

    await _insert_klp(db_session, site_id, kw1, 10, url_no_toc)
    await _insert_klp(db_session, site_id, kw2, 10, url_has_toc)
    await _insert_page(db_session, site_id, crawl_job_id, url_no_toc, has_toc=False)
    await _insert_page(db_session, site_id, crawl_job_id, url_has_toc, has_toc=True)

    await db_session.flush()

    results = await get_quick_wins(db_session, site_id, issue_type="missing_toc")
    urls = [r["url"] for r in results]

    assert url_no_toc in urls, "Page without TOC should appear in missing_toc filter"
    assert url_has_toc not in urls, "Page with TOC should not appear in missing_toc filter"


@pytest.mark.asyncio
async def test_filter_by_content_type(db_session: AsyncSession):
    """Filter content_type='informational' returns only informational pages."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)
    crawl_job_id = await _insert_crawl_job(db_session, site_id)

    kw1, kw2 = uuid.uuid4(), uuid.uuid4()
    await _insert_keyword(db_session, kw1, site_id, "info page kw")
    await _insert_keyword(db_session, kw2, site_id, "commercial page kw")

    url_info = "https://example.com/info-page/"
    url_commercial = "https://example.com/commercial-page/"

    await _insert_klp(db_session, site_id, kw1, 10, url_info)
    await _insert_klp(db_session, site_id, kw2, 10, url_commercial)
    await _insert_page(db_session, site_id, crawl_job_id, url_info, has_toc=False, content_type="informational")
    await _insert_page(db_session, site_id, crawl_job_id, url_commercial, has_toc=False, content_type="commercial")

    await db_session.flush()

    results = await get_quick_wins(db_session, site_id, content_type="informational")
    urls = [r["url"] for r in results]

    assert url_info in urls, "Informational page should appear in informational filter"
    assert url_commercial not in urls, "Commercial page should not appear in informational filter"


@pytest.mark.asyncio
async def test_dispatch_batch_fix_creates_jobs(db_session: AsyncSession):
    """dispatch_batch_fix() creates WpContentJob records for selected pages."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)
    crawl_job_id = await _insert_crawl_job(db_session, site_id)

    url1 = "https://example.com/fix-page-1/"
    url2 = "https://example.com/fix-page-2/"

    page_id1 = await _insert_page(db_session, site_id, crawl_job_id, url1, has_toc=False)
    page_id2 = await _insert_page(db_session, site_id, crawl_job_id, url2, has_toc=False)
    await db_session.flush()

    result = await dispatch_batch_fix(
        db_session,
        site_id=site_id,
        page_ids=[page_id1, page_id2],
        fix_types=["toc"],
    )

    assert "dispatched" in result
    assert result["dispatched"] >= 2

    # Verify WpContentJob records were created
    rows = await db_session.execute(
        text(
            "SELECT COUNT(*) FROM wp_content_jobs "
            "WHERE site_id = :site_id AND page_url IN (:url1, :url2)"
        ),
        {"site_id": site_id, "url1": url1, "url2": url2},
    )
    count = rows.scalar()
    assert count >= 2, f"Expected at least 2 WpContentJob rows, got {count}"
