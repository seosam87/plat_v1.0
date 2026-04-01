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
