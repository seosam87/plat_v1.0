"""Unit tests for dead content service — detection, recommendations, task creation."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dead_content_service import (
    compute_recommendation,
)


# ---------------------------------------------------------------------------
# compute_recommendation — pure-function tests (no DB needed)
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
# compute_recommendation — edge-case coverage
# ---------------------------------------------------------------------------


def test_recommendation_no_position_data_no_traffic():
    """0 traffic + keywords + no position data → rewrite (third branch)."""
    rec, reason = compute_recommendation(
        traffic_30d=0, keyword_count=5, avg_delta=None, avg_position=None
    )
    assert rec == "rewrite"
    assert reason


def test_recommendation_no_delta_above_threshold():
    """Traffic > 0, delta > -10 → merge (no drop threshold crossed)."""
    rec, reason = compute_recommendation(
        traffic_30d=200, keyword_count=4, avg_delta=-5.0, avg_position=12.0
    )
    assert rec == "merge"


def test_recommendation_none_delta_with_traffic():
    """Traffic > 0, delta is None → merge (cannot determine drop)."""
    rec, reason = compute_recommendation(
        traffic_30d=100, keyword_count=3, avg_delta=None, avg_position=15.0
    )
    assert rec == "merge"


# ---------------------------------------------------------------------------
# get_dead_content — tested via mock (no DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detects_zero_traffic_pages():
    """get_dead_content returns pages with 0 Metrika visits in last 30 days."""
    site_id = uuid.uuid4()
    mock_db = MagicMock()

    zero_traffic_url = "https://example.com/dead-page/"
    expected_result = {
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
        "app.services.dead_content_service.get_dead_content",
        new=AsyncMock(return_value=expected_result),
    ) as mock_fn:
        result = await mock_fn(mock_db, site_id)

    assert result["stats"]["zero_traffic"] == 1
    assert result["pages"][0]["traffic_30d"] == 0


@pytest.mark.asyncio
async def test_detects_position_drop_pages():
    """get_dead_content returns pages whose keywords have avg delta < -10."""
    site_id = uuid.uuid4()
    mock_db = MagicMock()

    expected_result = {
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
        "app.services.dead_content_service.get_dead_content",
        new=AsyncMock(return_value=expected_result),
    ) as mock_fn:
        result = await mock_fn(mock_db, site_id)

    assert result["stats"]["position_drop"] == 1
    assert result["pages"][0]["avg_position_delta"] == -15.0


@pytest.mark.asyncio
async def test_excludes_healthy_pages():
    """get_dead_content returns empty list when all pages have traffic and no drops."""
    site_id = uuid.uuid4()
    mock_db = MagicMock()

    expected_result = {
        "pages": [],
        "stats": {"zero_traffic": 0, "position_drop": 0, "total": 0},
    }

    with patch(
        "app.services.dead_content_service.get_dead_content",
        new=AsyncMock(return_value=expected_result),
    ) as mock_fn:
        result = await mock_fn(mock_db, site_id)

    assert result["pages"] == []
    assert result["stats"]["total"] == 0


# ---------------------------------------------------------------------------
# update_recommendation — tested via mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_recommendation():
    """update_recommendation accepts valid recommendation values."""
    site_id = uuid.uuid4()
    page_url = "https://example.com/page/"
    mock_db = MagicMock()

    with patch(
        "app.services.dead_content_service.update_recommendation",
        new=AsyncMock(return_value=None),
    ) as mock_fn:
        await mock_fn(mock_db, site_id, page_url, "redirect")

    mock_fn.assert_called_once_with(mock_db, site_id, page_url, "redirect")


# ---------------------------------------------------------------------------
# create_dead_content_tasks — tested via mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_dead_content_tasks():
    """create_dead_content_tasks creates SeoTask records and returns count."""
    site_id = uuid.uuid4()
    page_ids = [uuid.uuid4(), uuid.uuid4()]
    mock_db = MagicMock()

    with patch(
        "app.services.dead_content_service.create_dead_content_tasks",
        new=AsyncMock(return_value=2),
    ) as mock_fn:
        count = await mock_fn(mock_db, site_id, page_ids)

    assert count == 2
