"""Unit tests for keyword_latest_positions flat table and refresh logic.

Tests verify:
- KeywordLatestPosition model has the correct columns
- refresh_latest_positions() correctly picks the most recent position per (keyword_id, engine)
- Multiple keywords with multiple engines produce one row each
- Repeated refresh updates existing rows rather than duplicating
- write_positions_batch() triggers refresh automatically
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword_latest_position import KeywordLatestPosition
from app.models.position import KeywordPosition
from app.services.position_service import refresh_latest_positions, write_positions_batch


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_kp(
    keyword_id: uuid.UUID,
    site_id: uuid.UUID,
    engine: str,
    position: int | None,
    checked_at: datetime,
) -> KeywordPosition:
    return KeywordPosition(
        keyword_id=keyword_id,
        site_id=site_id,
        engine=engine,
        position=position,
        checked_at=checked_at,
    )


# ---------------------------------------------------------------------------
# Structural tests — no DB needed
# ---------------------------------------------------------------------------


def test_model_columns():
    """KeywordLatestPosition has all required columns."""
    mapper = inspect(KeywordLatestPosition)
    col_names = {c.key for c in mapper.mapper.column_attrs}
    required = {
        "id",
        "keyword_id",
        "site_id",
        "engine",
        "position",
        "previous_position",
        "delta",
        "url",
        "checked_at",
        "updated_at",
    }
    for col in required:
        assert col in col_names, f"Missing column: {col}"


def test_model_tablename():
    """KeywordLatestPosition uses the correct table name."""
    assert KeywordLatestPosition.__tablename__ == "keyword_latest_positions"


def test_model_unique_constraint():
    """KeywordLatestPosition has uq_klp_keyword_engine constraint."""
    constraint_names = {
        c.name
        for c in KeywordLatestPosition.__table__.constraints
        if hasattr(c, "name") and c.name
    }
    assert "uq_klp_keyword_engine" in constraint_names


# ---------------------------------------------------------------------------
# Integration tests — require db_session fixture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_latest_positions_inserts(db_session: AsyncSession):
    """After 3 position rows for same keyword, refresh picks the most recent."""
    site_id = uuid.uuid4()
    keyword_id = uuid.uuid4()

    # Insert site and keyword so FK constraints pass
    await db_session.execute(
        text(
            "INSERT INTO sites (id, name, url, wp_url, created_at, updated_at) "
            "VALUES (:id, 'Test', 'https://test.com', 'https://test.com', NOW(), NOW())"
        ),
        {"id": site_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO keywords (id, site_id, phrase, created_at, updated_at) "
            "VALUES (:id, :site_id, 'test kw', NOW(), NOW())"
        ),
        {"id": keyword_id, "site_id": site_id},
    )

    now = _now()
    # Ensure monthly partition exists
    await db_session.execute(
        text("SELECT create_kp_partition(:d)"), {"d": now.date()}
    )

    for i, pos in enumerate([10, 8, 5]):
        await db_session.execute(
            text(
                "INSERT INTO keyword_positions "
                "(id, keyword_id, site_id, engine, position, checked_at) "
                "VALUES (:id, :kwid, :sid, 'yandex', :pos, :cat)"
            ),
            {
                "id": uuid.uuid4(),
                "kwid": keyword_id,
                "sid": site_id,
                "pos": pos,
                "cat": now - timedelta(days=2 - i),
            },
        )
    await db_session.flush()

    count = await refresh_latest_positions(db_session, site_id)
    assert count >= 1

    result = await db_session.execute(
        text(
            "SELECT position FROM keyword_latest_positions "
            "WHERE keyword_id = :kwid AND engine = 'yandex'"
        ),
        {"kwid": keyword_id},
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 5  # most recent position


@pytest.mark.asyncio
async def test_refresh_latest_positions_multiple_keywords(db_session: AsyncSession):
    """2 keywords × 2 engines = 4 rows in keyword_latest_positions after refresh."""
    site_id = uuid.uuid4()

    await db_session.execute(
        text(
            "INSERT INTO sites (id, name, url, wp_url, created_at, updated_at) "
            "VALUES (:id, 'Test2', 'https://test2.com', 'https://test2.com', NOW(), NOW())"
        ),
        {"id": site_id},
    )

    kw_ids = [uuid.uuid4(), uuid.uuid4()]
    for kw_id in kw_ids:
        await db_session.execute(
            text(
                "INSERT INTO keywords (id, site_id, phrase, created_at, updated_at) "
                "VALUES (:id, :site_id, 'phrase', NOW(), NOW())"
            ),
            {"id": kw_id, "site_id": site_id},
        )

    now = _now()
    await db_session.execute(
        text("SELECT create_kp_partition(:d)"), {"d": now.date()}
    )

    for kw_id in kw_ids:
        for engine in ("yandex", "google"):
            await db_session.execute(
                text(
                    "INSERT INTO keyword_positions "
                    "(id, keyword_id, site_id, engine, position, checked_at) "
                    "VALUES (:id, :kwid, :sid, :eng, 15, :cat)"
                ),
                {
                    "id": uuid.uuid4(),
                    "kwid": kw_id,
                    "sid": site_id,
                    "eng": engine,
                    "cat": now,
                },
            )
    await db_session.flush()

    count = await refresh_latest_positions(db_session, site_id)
    assert count == 4


@pytest.mark.asyncio
async def test_refresh_updates_existing(db_session: AsyncSession):
    """Second refresh with a newer position updates the row (no duplicate)."""
    site_id = uuid.uuid4()
    keyword_id = uuid.uuid4()

    await db_session.execute(
        text(
            "INSERT INTO sites (id, name, url, wp_url, created_at, updated_at) "
            "VALUES (:id, 'Test3', 'https://test3.com', 'https://test3.com', NOW(), NOW())"
        ),
        {"id": site_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO keywords (id, site_id, phrase, created_at, updated_at) "
            "VALUES (:id, :site_id, 'kw3', NOW(), NOW())"
        ),
        {"id": keyword_id, "site_id": site_id},
    )

    now = _now()
    await db_session.execute(
        text("SELECT create_kp_partition(:d)"), {"d": now.date()}
    )

    # First position check
    await db_session.execute(
        text(
            "INSERT INTO keyword_positions "
            "(id, keyword_id, site_id, engine, position, checked_at) "
            "VALUES (:id, :kwid, :sid, 'yandex', 12, :cat)"
        ),
        {"id": uuid.uuid4(), "kwid": keyword_id, "sid": site_id, "cat": now - timedelta(hours=2)},
    )
    await db_session.flush()
    await refresh_latest_positions(db_session, site_id)

    # Second position check (newer)
    await db_session.execute(
        text(
            "INSERT INTO keyword_positions "
            "(id, keyword_id, site_id, engine, position, checked_at) "
            "VALUES (:id, :kwid, :sid, 'yandex', 7, :cat)"
        ),
        {"id": uuid.uuid4(), "kwid": keyword_id, "sid": site_id, "cat": now},
    )
    await db_session.flush()
    await refresh_latest_positions(db_session, site_id)

    result = await db_session.execute(
        text(
            "SELECT COUNT(*), MIN(position) FROM keyword_latest_positions "
            "WHERE keyword_id = :kwid AND engine = 'yandex'"
        ),
        {"kwid": keyword_id},
    )
    row = result.fetchone()
    assert row[0] == 1  # only one row (no duplicate)
    assert row[1] == 7  # updated to latest


@pytest.mark.asyncio
async def test_write_positions_batch_triggers_refresh(db_session: AsyncSession):
    """write_positions_batch() populates keyword_latest_positions automatically."""
    site_id = uuid.uuid4()
    keyword_id = uuid.uuid4()

    await db_session.execute(
        text(
            "INSERT INTO sites (id, name, url, wp_url, created_at, updated_at) "
            "VALUES (:id, 'Test4', 'https://test4.com', 'https://test4.com', NOW(), NOW())"
        ),
        {"id": site_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO keywords (id, site_id, phrase, created_at, updated_at) "
            "VALUES (:id, :site_id, 'kw4', NOW(), NOW())"
        ),
        {"id": keyword_id, "site_id": site_id},
    )
    await db_session.flush()

    rows = [
        {
            "keyword_id": keyword_id,
            "engine": "yandex",
            "position": 9,
        }
    ]
    await write_positions_batch(db_session, site_id, rows)

    result = await db_session.execute(
        text(
            "SELECT position FROM keyword_latest_positions "
            "WHERE keyword_id = :kwid AND engine = 'yandex'"
        ),
        {"kwid": keyword_id},
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 9
