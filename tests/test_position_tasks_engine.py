"""Unit tests for engine propagation in position_tasks.py.

Tests verify that _check_via_dataforseo and _check_via_serp_parser
use kw.engine instead of hardcoded "google".
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from app.models.keyword import SearchEngine


def _make_keyword(phrase: str, engine_val) -> MagicMock:
    """Create a mock Keyword object."""
    kw = MagicMock()
    kw.id = uuid.uuid4()
    kw.phrase = phrase
    kw.engine = engine_val
    return kw


SITE_ID = str(uuid.uuid4())
SITE_DOMAIN = "example.com"


def _make_db_ctx(site_url: str):
    """Return a context-manager mock that exposes a mock DB session."""
    mock_site = MagicMock()
    mock_site.url = site_url

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_site
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    # get_sync_db() returns a context manager
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# _check_via_dataforseo tests
# ---------------------------------------------------------------------------


class TestCheckViaDataforseo:
    """Tests for engine propagation in _check_via_dataforseo."""

    def _run(self, keywords, serp_results):
        """Patch local imports and run _check_via_dataforseo; return write calls."""
        from app.tasks.position_tasks import _check_via_dataforseo

        ctx = _make_db_ctx(f"https://{SITE_DOMAIN}/")
        write_calls = []

        def fake_write(db, kw_id, site_uuid, engine, position, url=None):
            write_calls.append({"engine": engine, "position": position, "url": url})

        async def fake_fetch(batch):
            return serp_results

        with (
            patch("app.database.get_sync_db", return_value=ctx),
            patch("app.services.dataforseo_service.fetch_serp_batch", side_effect=fake_fetch),
            patch("app.services.position_service.write_position_sync", side_effect=fake_write),
        ):
            _check_via_dataforseo(SITE_ID, keywords)

        return write_calls

    def test_yandex_keyword_writes_yandex_engine(self):
        """_check_via_dataforseo passes engine='yandex' for Yandex keywords."""
        kw = _make_keyword("купить диван", SearchEngine.yandex)
        serp_results = [
            {
                "keyword": "купить диван",
                "results": [{"url": f"https://{SITE_DOMAIN}/page", "position": 3}],
            }
        ]
        writes = self._run([kw], serp_results)
        assert writes, "write_position_sync should have been called"
        assert writes[0]["engine"] == "yandex", (
            f"Expected engine='yandex', got {writes[0]['engine']!r}"
        )

    def test_none_engine_defaults_to_google(self):
        """_check_via_dataforseo defaults to engine='google' when kw.engine is None."""
        kw = _make_keyword("buy sofa", None)
        kw.engine = None
        serp_results = [
            {
                "keyword": "buy sofa",
                "results": [{"url": f"https://{SITE_DOMAIN}/page", "position": 5}],
            }
        ]
        writes = self._run([kw], serp_results)
        assert writes, "write_position_sync should have been called"
        assert writes[0]["engine"] == "google", (
            f"Expected engine='google', got {writes[0]['engine']!r}"
        )


# ---------------------------------------------------------------------------
# _check_via_serp_parser tests
# ---------------------------------------------------------------------------


class TestCheckViaSerpParser:
    """Tests for engine propagation in _check_via_serp_parser."""

    def _run(self, keywords, parse_result=None):
        """Patch local imports and run _check_via_serp_parser; return (parse_calls, write_calls)."""
        from app.tasks.position_tasks import _check_via_serp_parser

        if parse_result is None:
            parse_result = {"results": [{"url": f"https://{SITE_DOMAIN}/page", "position": 2}]}

        ctx = _make_db_ctx(f"https://{SITE_DOMAIN}/")
        parse_calls = []
        write_calls = []

        def fake_parse(phrase, engine="google"):
            parse_calls.append({"phrase": phrase, "engine": engine})
            return parse_result

        def fake_write(db, kw_id, site_uuid, engine, position, url=None):
            write_calls.append({"engine": engine, "position": position, "url": url})

        with (
            patch("app.database.get_sync_db", return_value=ctx),
            patch("app.services.serp_parser_service.parse_serp_sync", side_effect=fake_parse),
            patch("app.services.serp_parser_service._check_daily_limit", return_value=True),
            patch("app.services.position_service.write_position_sync", side_effect=fake_write),
        ):
            _check_via_serp_parser(SITE_ID, keywords)

        return parse_calls, write_calls

    def test_yandex_keyword_calls_parse_with_yandex_engine(self):
        """_check_via_serp_parser passes engine='yandex' to parse_serp_sync."""
        kw = _make_keyword("купить диван", SearchEngine.yandex)
        parse_calls, _ = self._run([kw])

        assert parse_calls, "parse_serp_sync should have been called"
        assert parse_calls[0]["engine"] == "yandex", (
            f"Expected parse engine='yandex', got {parse_calls[0]['engine']!r}"
        )

    def test_yandex_keyword_writes_yandex_engine(self):
        """_check_via_serp_parser passes engine='yandex' to write_position_sync."""
        kw = _make_keyword("купить диван", SearchEngine.yandex)
        _, write_calls = self._run([kw])

        assert write_calls, "write_position_sync should have been called"
        assert write_calls[0]["engine"] == "yandex", (
            f"Expected write engine='yandex', got {write_calls[0]['engine']!r}"
        )

    def test_none_engine_parse_defaults_to_google(self):
        """_check_via_serp_parser defaults to engine='google' for kw.engine=None."""
        kw = _make_keyword("buy sofa", None)
        kw.engine = None
        parse_calls, _ = self._run([kw])

        assert parse_calls, "parse_serp_sync should have been called"
        assert parse_calls[0]["engine"] == "google", (
            f"Expected parse engine='google', got {parse_calls[0]['engine']!r}"
        )

    def test_none_engine_write_defaults_to_google(self):
        """_check_via_serp_parser defaults write engine='google' for kw.engine=None."""
        kw = _make_keyword("buy sofa", None)
        kw.engine = None
        _, write_calls = self._run([kw])

        assert write_calls, "write_position_sync should have been called"
        assert write_calls[0]["engine"] == "google", (
            f"Expected write engine='google', got {write_calls[0]['engine']!r}"
        )
