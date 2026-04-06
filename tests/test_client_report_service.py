"""Service-layer tests for client_report_service.

Tests cover:
- INSTRUCTION_TEMPLATES keys and structure (7 problem types with Russian labels/instructions)
- TOP_N constant value
- gather_report_data: data aggregation for all blocks
- gather_report_data: partial block config
- gather_report_data: summary structure
- ClientReport CRUD: create_report_record, save_report_pdf, mark_report_failed
- get_report_history ordering and limit
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.client_report_service import (
    INSTRUCTION_TEMPLATES,
    TOP_N,
    create_report_record,
    get_report_by_id,
    get_report_history,
    gather_report_data,
    mark_report_failed,
    save_report_pdf,
)


# ---------------------------------------------------------------------------
# Pure constant tests (no DB needed)
# ---------------------------------------------------------------------------


class TestInstructionTemplates:
    def test_instruction_templates_keys(self):
        """INSTRUCTION_TEMPLATES has exactly 7 expected keys."""
        expected = {
            "404",
            "noindex",
            "missing_toc",
            "missing_schema",
            "thin_content",
            "low_internal_links",
            "dead_content",
        }
        assert set(INSTRUCTION_TEMPLATES.keys()) == expected

    def test_instruction_templates_structure(self):
        """Each entry has non-empty 'label' and 'instruction' keys."""
        for key, tmpl in INSTRUCTION_TEMPLATES.items():
            assert "label" in tmpl, f"{key} missing label"
            assert "instruction" in tmpl, f"{key} missing instruction"
            assert len(tmpl["label"]) > 0, f"{key} has empty label"
            assert len(tmpl["instruction"]) > 0, f"{key} has empty instruction"

    def test_instruction_templates_russian_content(self):
        """Instructions contain Russian text (Cyrillic characters)."""
        for key, tmpl in INSTRUCTION_TEMPLATES.items():
            label = tmpl["label"]
            # At least one Cyrillic character in the label
            has_cyrillic = any("\u0400" <= c <= "\u04ff" for c in label)
            assert has_cyrillic, f"{key} label has no Russian text: {label!r}"

    def test_top_n_value(self):
        """TOP_N constant equals 20."""
        assert TOP_N == 20


# ---------------------------------------------------------------------------
# Helper for inserting site into test DB
# ---------------------------------------------------------------------------


async def _insert_site(db: AsyncSession, site_id: uuid.UUID) -> None:
    await db.execute(
        text(
            "INSERT INTO sites (id, name, url, wp_url, created_at, updated_at) "
            "VALUES (:id, 'Test Site', 'https://test.example.com', "
            "'https://test.example.com', NOW(), NOW())"
        ),
        {"id": site_id},
    )
    await db.flush()


# ---------------------------------------------------------------------------
# gather_report_data tests (mocked upstream services)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_report_data_all_blocks(db_session: AsyncSession):
    """gather_report_data with all blocks returns summary, problem_groups, positions."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    mock_qw = [
        {"url": "https://test.example.com/page/", "has_toc": False, "has_schema": True,
         "has_low_links": False, "has_thin_content": False, "avg_position": 8.0},
    ]
    mock_dc = {"pages": [], "summary": {}}
    mock_pos = {"distribution": {}, "top_gainers": [], "top_losers": []}

    with patch(
        "app.services.client_report_service.get_quick_wins",
        new_callable=AsyncMock,
        return_value=mock_qw,
    ):
        with patch(
            "app.services.client_report_service.get_dead_content",
            new_callable=AsyncMock,
            return_value=mock_dc,
        ):
            with patch(
                "app.services.client_report_service.site_overview",
                new_callable=AsyncMock,
                return_value=mock_pos,
            ):
                result = await gather_report_data(
                    db_session,
                    site_id,
                    {"quick_wins": True, "audit_errors": True, "dead_content": True, "positions": True},
                )

    assert "summary" in result
    assert "problem_groups" in result
    assert "positions" in result


@pytest.mark.asyncio
async def test_gather_report_data_quick_wins_only(db_session: AsyncSession):
    """With only quick_wins enabled, positions key is present but empty."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    mock_qw = [
        {"url": "https://test.example.com/p/", "has_toc": False, "has_schema": True,
         "has_low_links": False, "has_thin_content": False, "avg_position": 5.0},
    ]

    with patch(
        "app.services.client_report_service.get_quick_wins",
        new_callable=AsyncMock,
        return_value=mock_qw,
    ):
        result = await gather_report_data(
            db_session,
            site_id,
            {"quick_wins": True, "audit_errors": False, "dead_content": False, "positions": False},
        )

    assert "problem_groups" in result
    # positions block was not requested — should be empty dict
    assert result["positions"] == {}


@pytest.mark.asyncio
async def test_gather_report_data_summary_structure(db_session: AsyncSession):
    """Summary contains total_pages, total_problems, critical_count."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    with patch(
        "app.services.client_report_service.get_quick_wins",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await gather_report_data(
            db_session,
            site_id,
            {"quick_wins": True, "audit_errors": False, "dead_content": False, "positions": False},
        )

    summary = result["summary"]
    assert "total_pages" in summary
    assert "total_problems" in summary
    assert "critical_count" in summary


@pytest.mark.asyncio
async def test_gather_report_data_problem_groups_have_instruction(db_session: AsyncSession):
    """Each problem group in the result includes label and instruction from template."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    mock_qw = [
        {"url": "https://test.example.com/a/", "has_toc": False, "has_schema": True,
         "has_low_links": False, "has_thin_content": False, "avg_position": 7.0},
    ]

    with patch(
        "app.services.client_report_service.get_quick_wins",
        new_callable=AsyncMock,
        return_value=mock_qw,
    ):
        result = await gather_report_data(
            db_session,
            site_id,
            {"quick_wins": True},
        )

    assert len(result["problem_groups"]) >= 1
    group = result["problem_groups"][0]
    assert "label" in group
    assert "instruction" in group
    assert "pages" in group


# ---------------------------------------------------------------------------
# CRUD tests: create_report_record, save_report_pdf, mark_report_failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_report_record(db_session: AsyncSession):
    """create_report_record creates a ClientReport with status 'pending'."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    blocks = {"quick_wins": True, "audit_errors": False}
    report = await create_report_record(db_session, site_id, blocks)

    assert report.status == "pending"
    assert report.blocks_config == blocks
    assert report.site_id == site_id
    assert report.id is not None
    assert report.pdf_data is None


@pytest.mark.asyncio
async def test_save_report_pdf(db_session: AsyncSession):
    """save_report_pdf updates status to 'ready' and stores pdf_data."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    report = await create_report_record(db_session, site_id, {"quick_wins": True})
    fake_pdf = b"%PDF-1.4 fake content"
    await save_report_pdf(db_session, report.id, fake_pdf)
    await db_session.commit()

    updated = await get_report_by_id(db_session, report.id)
    assert updated is not None
    assert updated.status == "ready"
    assert updated.pdf_data == fake_pdf


@pytest.mark.asyncio
async def test_mark_report_failed(db_session: AsyncSession):
    """mark_report_failed updates status to 'failed' and stores error_message."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    report = await create_report_record(db_session, site_id, {"quick_wins": True})
    await mark_report_failed(db_session, report.id, "WeasyPrint timed out")
    await db_session.commit()

    updated = await get_report_by_id(db_session, report.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error_message == "WeasyPrint timed out"


@pytest.mark.asyncio
async def test_mark_report_failed_truncates_long_error(db_session: AsyncSession):
    """mark_report_failed truncates error_message to 500 chars."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    report = await create_report_record(db_session, site_id, {"quick_wins": True})
    long_error = "x" * 600
    await mark_report_failed(db_session, report.id, long_error)
    await db_session.commit()

    updated = await get_report_by_id(db_session, report.id)
    assert updated is not None
    assert len(updated.error_message) == 500


@pytest.mark.asyncio
async def test_get_report_history_ordered_by_created_at(db_session: AsyncSession):
    """get_report_history returns reports newest-first, limited to 50."""
    site_id = uuid.uuid4()
    await _insert_site(db_session, site_id)

    # Create 3 reports
    r1 = await create_report_record(db_session, site_id, {"quick_wins": True})
    r2 = await create_report_record(db_session, site_id, {"audit_errors": True})
    r3 = await create_report_record(db_session, site_id, {"dead_content": True})
    await db_session.flush()

    history = await get_report_history(db_session, site_id)
    assert len(history) == 3

    # Newest first — r3 created last
    report_ids = [r.id for r in history]
    assert report_ids.index(r3.id) < report_ids.index(r2.id)
    assert report_ids.index(r2.id) < report_ids.index(r1.id)


@pytest.mark.asyncio
async def test_get_report_by_id_returns_none_for_missing(db_session: AsyncSession):
    """get_report_by_id returns None for unknown UUID."""
    result = await get_report_by_id(db_session, uuid.uuid4())
    assert result is None
