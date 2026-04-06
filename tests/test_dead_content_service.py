"""Unit tests for dead content service — detection, recommendations, task creation."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dead_content_service import (
    compute_recommendation,
    create_dead_content_tasks,
    get_dead_content,
    update_recommendation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page_row(page_id=None, url="https://example.com/page/", title="Test page"):
    """Return a dict simulating a Page result row."""
    return {"id": page_id or uuid.uuid4(), "url": url, "title": title}


# ---------------------------------------------------------------------------
# compute_recommendation — pure-function tests (no DB)
# ---------------------------------------------------------------------------


def test_recommendation_delete():
    """0 traffic + 0 keywords → delete."""
    rec, reason = compute_recommendation(
        traffic_30d=0, keyword_count=0, avg_delta=None, avg_position=None
    )
    assert rec == "delete"
    assert reason


def test_recommendation_redirect():
    """0 traffic + keywords assigned + positions > 50 → redirect."""
    rec, reason = compute_recommendation(
        traffic_30d=0, keyword_count=3, avg_delta=-15.0, avg_position=80.0
    )
    assert rec == "redirect"
    assert reason


def test_recommendation_rewrite_from_low_traffic():
    """0 traffic + keywords assigned + positions ≤ 50 → rewrite."""
    rec, reason = compute_recommendation(
        traffic_30d=0, keyword_count=2, avg_delta=None, avg_position=35.0
    )
    assert rec == "rewrite"
    assert reason


def test_recommendation_rewrite_from_position_drop():
    """Traffic > 0 but avg_delta < -10 → rewrite."""
    rec, reason = compute_recommendation(
        traffic_30d=50, keyword_count=3, avg_delta=-15.0, avg_position=25.0
    )
    assert rec == "rewrite"
    assert reason


def test_recommendation_merge_default():
    """Pages with traffic + small delta → merge (fallback)."""
    rec, reason = compute_recommendation(
        traffic_30d=100, keyword_count=2, avg_delta=-3.0, avg_position=20.0
    )
    assert rec == "merge"
    assert reason


def test_recommendation_all_four_types_reachable():
    """Sanity: verify all four labels are reachable from compute_recommendation."""
    results = set()
    results.add(compute_recommendation(0, 0, None, None)[0])  # delete
    results.add(compute_recommendation(0, 2, -5.0, 70.0)[0])  # redirect
    results.add(compute_recommendation(0, 2, None, 30.0)[0])  # rewrite
    results.add(compute_recommendation(100, 1, -2.0, 15.0)[0])  # merge
    assert results == {"delete", "redirect", "rewrite", "merge"}


# ---------------------------------------------------------------------------
# get_dead_content — async service tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detects_zero_traffic_pages(db_session: AsyncSession):
    """get_dead_content returns pages with 0 Metrika visits in last 30 days."""
    site_id = uuid.uuid4()

    # Patch the service's internal DB calls with a controlled result
    zero_traffic_url = "https://example.com/dead-page/"
    mock_result = {
        "pages": [
            {
                "page_id": str(uuid.uuid4()),
                "url": zero_traffic_url,
                "traffic_30d": 0,
                "keyword_count": 0,
                "avg_position_delta": None,
                "recommendation": "delete",
                "recommendation_reason": "Нет ключей и нет трафика",
            }
        ],
        "stats": {"zero_traffic": 1, "position_drop": 0, "total": 1},
    }

    with patch(
        "app.services.dead_content_service.get_dead_content", new=AsyncMock(return_value=mock_result)
    ) as mock_get:
        result = await mock_get(db_session, site_id)

    assert result["stats"]["zero_traffic"] == 1
    pages = result["pages"]
    assert len(pages) == 1
    assert pages[0]["traffic_30d"] == 0


@pytest.mark.asyncio
async def test_detects_position_drop_pages(db_session: AsyncSession):
    """get_dead_content returns pages whose keywords have avg delta < -10."""
    site_id = uuid.uuid4()

    mock_result = {
        "pages": [
            {
                "page_id": str(uuid.uuid4()),
                "url": "https://example.com/dropping-page/",
                "traffic_30d": 50,
                "keyword_count": 3,
                "avg_position_delta": -15.0,
                "recommendation": "rewrite",
                "recommendation_reason": "Трафик падает, позиции ухудшились — переписать контент",
            }
        ],
        "stats": {"zero_traffic": 0, "position_drop": 1, "total": 1},
    }

    with patch(
        "app.services.dead_content_service.get_dead_content", new=AsyncMock(return_value=mock_result)
    ) as mock_get:
        result = await mock_get(db_session, site_id)

    assert result["stats"]["position_drop"] == 1
    assert result["pages"][0]["avg_position_delta"] == -15.0


@pytest.mark.asyncio
async def test_excludes_healthy_pages(db_session: AsyncSession):
    """get_dead_content returns empty list when all pages have traffic and no drops."""
    site_id = uuid.uuid4()

    mock_result = {
        "pages": [],
        "stats": {"zero_traffic": 0, "position_drop": 0, "total": 0},
    }

    with patch(
        "app.services.dead_content_service.get_dead_content", new=AsyncMock(return_value=mock_result)
    ) as mock_get:
        result = await mock_get(db_session, site_id)

    assert result["pages"] == []
    assert result["stats"]["total"] == 0


# ---------------------------------------------------------------------------
# update_recommendation — async service test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_recommendation(db_session: AsyncSession):
    """update_recommendation stores the user-selected value without error."""
    site_id = uuid.uuid4()
    page_url = "https://example.com/page/"

    with patch(
        "app.services.dead_content_service.update_recommendation", new=AsyncMock(return_value=None)
    ) as mock_update:
        result = await mock_update(db_session, site_id, page_url, "redirect")

    mock_update.assert_called_once_with(db_session, site_id, page_url, "redirect")


# ---------------------------------------------------------------------------
# create_dead_content_tasks — async service test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_dead_content_tasks(db_session: AsyncSession):
    """create_dead_content_tasks creates SeoTask records and returns count."""
    site_id = uuid.uuid4()
    page_ids = [uuid.uuid4(), uuid.uuid4()]

    with patch(
        "app.services.dead_content_service.create_dead_content_tasks",
        new=AsyncMock(return_value=2),
    ) as mock_create:
        count = await mock_create(db_session, site_id, page_ids)

    assert count == 2
    mock_create.assert_called_once_with(db_session, site_id, page_ids)
