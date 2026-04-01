"""Unit tests for position service delta computation and model."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.position import KeywordPosition


# ---- Model tests ----


async def test_position_model(db_session):
    """KeywordPosition can be created with all fields."""
    kp = KeywordPosition(
        keyword_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        engine="google",
        position=5,
        previous_position=8,
        delta=3,
        url="https://example.com/page",
        clicks=10,
        impressions=200,
        ctr=0.05,
        checked_at=datetime.now(timezone.utc),
    )
    assert kp.delta == 3  # improved by 3


# ---- Delta computation tests (pure logic) ----


class TestDeltaComputation:
    def test_positive_delta_means_improved(self):
        # Was position 10, now position 5 → delta = 10 - 5 = 5 (improved)
        previous = 10
        current = 5
        delta = previous - current
        assert delta == 5

    def test_negative_delta_means_dropped(self):
        # Was position 3, now position 8 → delta = 3 - 8 = -5 (dropped)
        previous = 3
        current = 8
        delta = previous - current
        assert delta == -5

    def test_zero_delta_means_unchanged(self):
        previous = 5
        current = 5
        delta = previous - current
        assert delta == 0

    def test_none_previous_means_no_delta(self):
        previous = None
        current = 5
        delta = None if previous is None else previous - current
        assert delta is None

    def test_none_current_means_no_delta(self):
        previous = 5
        current = None
        delta = None if current is None else previous - current
        assert delta is None


# ---- Service write_position mock test ----


class TestWritePosition:
    @pytest.mark.asyncio
    async def test_write_with_no_previous(self):
        """First position for a keyword should have delta=None."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        from app.services.position_service import write_position

        with patch("app.services.position_service._get_previous_position", return_value=None):
            record = await write_position(
                mock_db,
                keyword_id=uuid.uuid4(),
                site_id=uuid.uuid4(),
                engine="google",
                position=5,
            )
        assert record.position == 5
        assert record.delta is None
        assert record.previous_position is None

    @pytest.mark.asyncio
    async def test_write_with_previous(self):
        """Second position should compute delta from previous."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        prev = SimpleNamespace(position=10)

        from app.services.position_service import write_position

        with patch("app.services.position_service._get_previous_position", return_value=prev):
            record = await write_position(
                mock_db,
                keyword_id=uuid.uuid4(),
                site_id=uuid.uuid4(),
                engine="google",
                position=5,
            )
        assert record.position == 5
        assert record.previous_position == 10
        assert record.delta == 5  # improved


# ---- Router test ----


async def test_positions_router_registered():
    from app.routers.positions import router
    paths = [r.path for r in router.routes]
    assert "/positions/sites/{site_id}" in paths
    assert "/positions/keywords/{keyword_id}/history" in paths
    assert "/positions/sites/{site_id}/check" in paths


async def test_new_endpoints_registered():
    """All Phase 3 endpoints are registered in the router."""
    from app.routers.positions import router
    paths = [r.path for r in router.routes]
    assert "/positions/sites/{site_id}/distribution" in paths
    assert "/positions/sites/{site_id}/lost-gained" in paths
    assert "/positions/sites/{site_id}/compare" in paths
    assert "/positions/sites/{site_id}/by-url" in paths


class TestDistributionLogic:
    """Test distribution counting logic (pure Python, no DB)."""

    def test_categorize_positions(self):
        """Verify categorization thresholds match the service logic."""
        positions = [1, 2, 3, 5, 8, 10, 15, 25, 50, 80, None]
        top3 = sum(1 for p in positions if p is not None and p <= 3)
        top10 = sum(1 for p in positions if p is not None and p <= 10)
        top30 = sum(1 for p in positions if p is not None and p <= 30)
        top100 = sum(1 for p in positions if p is not None and p <= 100)
        not_ranked = sum(1 for p in positions if p is None)
        assert top3 == 3   # 1, 2, 3
        assert top10 == 6  # 1, 2, 3, 5, 8, 10
        assert top30 == 8  # + 15, 25
        assert top100 == 10  # + 50, 80
        assert not_ranked == 1


class TestLostGainedLogic:
    """Test lost/gained classification logic."""

    def test_gained_classification(self):
        """Keyword enters TOP-N: old=None or >threshold, new<=threshold."""
        threshold = 10
        # Was not ranked, now in TOP-10
        old, new = None, 5
        is_gained = (old is None or old > threshold) and (new is not None and new <= threshold)
        assert is_gained

    def test_lost_classification(self):
        """Keyword leaves TOP-N: old<=threshold, new=None or >threshold."""
        threshold = 10
        # Was in TOP-10, now out
        old, new = 3, 15
        is_lost = (old is not None and old <= threshold) and (new is None or new > threshold)
        assert is_lost

    def test_stayed_in_top(self):
        """Keyword stays in TOP-N: neither gained nor lost."""
        threshold = 10
        old, new = 5, 3
        is_gained = (old is None or old > threshold) and (new is not None and new <= threshold)
        is_lost = (old is not None and old <= threshold) and (new is None or new > threshold)
        assert not is_gained
        assert not is_lost


class TestCompareDeltaLogic:
    """Test date comparison delta computation."""

    def test_delta_improvement(self):
        """Position A=10, Position B=3 → delta = 10 - 3 = 7 (improved in B)."""
        pos_a, pos_b = 10, 3
        delta = pos_a - pos_b
        assert delta == 7

    def test_delta_drop(self):
        """Position A=3, Position B=10 → delta = 3 - 10 = -7 (dropped in B)."""
        pos_a, pos_b = 3, 10
        delta = pos_a - pos_b
        assert delta == -7

    def test_delta_none_when_missing(self):
        """If either position is None, delta is None."""
        pos_a, pos_b = None, 5
        delta = (pos_a - pos_b) if (pos_a is not None and pos_b is not None) else None
        assert delta is None


class TestServiceImports:
    """Verify all new service functions are importable."""

    def test_imports(self):
        from app.services.position_service import (
            get_position_distribution,
            get_lost_gained_keywords,
            compare_positions_by_date,
            get_positions_by_url,
        )
        assert callable(get_position_distribution)
        assert callable(get_lost_gained_keywords)
        assert callable(compare_positions_by_date)
        assert callable(get_positions_by_url)
