"""Tests for morning_digest_service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.morning_digest_service import (
    MAX_CHARS,
    build_morning_digest,
)


def _make_mock_db(projects=None):
    """Build a mock synchronous SQLAlchemy session."""
    db = MagicMock()

    if projects is None:
        projects = []

    # Mock the execute call chain
    # First call returns projects, subsequent calls return counts
    call_count = [0]

    def execute_side_effect(stmt):
        result = MagicMock()
        call_idx = call_count[0]
        call_count[0] += 1

        if call_idx == 0:
            # projects query
            result.all.return_value = projects
        else:
            # scalar queries (top10, open_tasks, in_progress_tasks)
            scalar_result = MagicMock()
            scalar_result.scalar.return_value = 0
            return scalar_result

        return result

    db.execute.side_effect = execute_side_effect
    return db


def _make_project(name="Test Project", site_name="test.com"):
    """Create mock project and site objects."""
    project = MagicMock()
    project.id = "test-project-id"
    project.name = name
    project.archived = False

    site = MagicMock()
    site.id = "test-site-id"
    site.name = site_name

    return project, site


class TestBuildMorningDigest:
    def test_returns_string_with_expected_header(self):
        """build_morning_digest returns a string containing the expected header."""
        db = _make_mock_db()
        result = build_morning_digest(db)
        assert isinstance(result, str)
        assert "<b>SEO Morning Digest" in result

    def test_zero_projects_returns_message_not_crash(self):
        """With 0 projects, returns a valid message rather than crashing."""
        db = _make_mock_db(projects=[])
        result = build_morning_digest(db)
        assert isinstance(result, str)
        assert "<b>SEO Morning Digest" in result
        assert "Open Dashboard" in result

    def test_message_truncated_to_max_chars(self):
        """Message is truncated to <= MAX_CHARS characters."""
        # Build a db that returns many projects to force truncation
        db = MagicMock()

        many_projects = [
            _make_project(name=f"Project {'X' * 200} {i}", site_name=f"site{i}.com")
            for i in range(20)
        ]

        call_count = [0]

        def execute_side_effect(stmt):
            result = MagicMock()
            call_idx = call_count[0]
            call_count[0] += 1

            if call_idx == 0:
                result.all.return_value = many_projects
            else:
                scalar_result = MagicMock()
                scalar_result.scalar.return_value = 5
                return scalar_result

            return result

        db.execute.side_effect = execute_side_effect

        result = build_morning_digest(db)
        assert len(result) <= MAX_CHARS

    def test_project_info_in_message(self):
        """Project name and site name appear in the digest."""
        project, site = _make_project(name="My SEO Project", site_name="mysite.com")
        db = MagicMock()

        call_count = [0]

        def execute_side_effect(stmt):
            result = MagicMock()
            call_idx = call_count[0]
            call_count[0] += 1

            if call_idx == 0:
                result.all.return_value = [(project, site)]
            else:
                scalar_result = MagicMock()
                scalar_result.scalar.return_value = 3
                return scalar_result

            return result

        db.execute.side_effect = execute_side_effect

        with patch(
            "app.services.morning_digest_service._count_top10",
            return_value=5,
        ):
            result = build_morning_digest(db)

        assert "My SEO Project" in result
        assert "mysite.com" in result
        assert "TOP-10: 5" in result

    def test_dashboard_link_in_message(self):
        """Digest includes a link to the dashboard."""
        db = _make_mock_db(projects=[])
        result = build_morning_digest(db)
        assert "Open Dashboard" in result
        assert "/ui/dashboard" in result
