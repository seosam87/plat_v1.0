"""Unit tests for suggest_service functions.

Tests use respx to mock httpx calls and test sync functions directly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx


# ---------------------------------------------------------------------------
# fetch_yandex_suggest_sync
# ---------------------------------------------------------------------------

class TestFetchYandexSuggestSync:
    def test_returns_list_of_strings_on_success(self):
        """fetch_yandex_suggest_sync returns list[str] from mocked JSON response."""
        from app.services.suggest_service import fetch_yandex_suggest_sync

        yandex_response = ["test query", ["подсказка 1", "подсказка 2", "подсказка 3"]]

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggest.yandex.ru/suggest-ya.cgi").mock(
                return_value=httpx.Response(200, json=yandex_response)
            )
            result = fetch_yandex_suggest_sync("test query", proxy_url=None)

        assert isinstance(result, list)
        assert len(result) == 3
        assert "подсказка 1" in result
        assert "подсказка 2" in result

    def test_returns_empty_list_on_http_error(self):
        """fetch_yandex_suggest_sync returns empty list on HTTP 429 status."""
        from app.services.suggest_service import fetch_yandex_suggest_sync

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggest.yandex.ru/suggest-ya.cgi").mock(
                return_value=httpx.Response(429)
            )
            result = fetch_yandex_suggest_sync("test query", proxy_url=None)

        assert result == []

    def test_returns_empty_list_on_network_error(self):
        """fetch_yandex_suggest_sync returns empty list on connection error."""
        from app.services.suggest_service import fetch_yandex_suggest_sync

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggest.yandex.ru/suggest-ya.cgi").mock(
                side_effect=httpx.ConnectError("Connection failed")
            )
            result = fetch_yandex_suggest_sync("test query", proxy_url=None)

        assert result == []

    def test_handles_dict_format_response(self):
        """fetch_yandex_suggest_sync handles alternative dict format with 'items' key."""
        from app.services.suggest_service import fetch_yandex_suggest_sync

        dict_response = {"items": [{"value": "подсказка а"}, {"value": "подсказка б"}]}

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggest.yandex.ru/suggest-ya.cgi").mock(
                return_value=httpx.Response(200, json=dict_response)
            )
            result = fetch_yandex_suggest_sync("test query", proxy_url=None)

        assert "подсказка а" in result
        assert "подсказка б" in result


# ---------------------------------------------------------------------------
# fetch_google_suggest_sync
# ---------------------------------------------------------------------------

class TestFetchGoogleSuggestSync:
    def test_returns_list_of_strings_on_success(self):
        """fetch_google_suggest_sync returns list[str] from mocked JSON response."""
        from app.services.suggest_service import fetch_google_suggest_sync

        google_response = ["query", ["suggestion one", "suggestion two"]]

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggestqueries.google.com/complete/search").mock(
                return_value=httpx.Response(200, json=google_response)
            )
            result = fetch_google_suggest_sync("test query")

        assert isinstance(result, list)
        assert "suggestion one" in result
        assert "suggestion two" in result

    def test_returns_empty_list_on_network_error(self):
        """fetch_google_suggest_sync returns empty list on network error."""
        from app.services.suggest_service import fetch_google_suggest_sync

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggestqueries.google.com/complete/search").mock(
                side_effect=httpx.ConnectError("Network error")
            )
            result = fetch_google_suggest_sync("test query")

        assert result == []

    def test_returns_empty_list_on_http_error(self):
        """fetch_google_suggest_sync returns empty list on HTTP error."""
        from app.services.suggest_service import fetch_google_suggest_sync

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggestqueries.google.com/complete/search").mock(
                return_value=httpx.Response(500)
            )
            result = fetch_google_suggest_sync("test query")

        assert result == []

    def test_returns_empty_list_when_response_has_no_suggestions(self):
        """fetch_google_suggest_sync returns empty list when response has only query."""
        from app.services.suggest_service import fetch_google_suggest_sync

        google_response = ["query"]  # len < 2

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://suggestqueries.google.com/complete/search").mock(
                return_value=httpx.Response(200, json=google_response)
            )
            result = fetch_google_suggest_sync("test query")

        assert result == []


# ---------------------------------------------------------------------------
# suggest_cache_key
# ---------------------------------------------------------------------------

class TestSuggestCacheKey:
    def test_yandex_and_google_key(self):
        """suggest_cache_key with include_google=True returns 'suggest:yg:тест'."""
        from app.services.suggest_service import suggest_cache_key

        result = suggest_cache_key("  Тест ", True)
        assert result == "suggest:yg:тест"

    def test_yandex_only_key(self):
        """suggest_cache_key with include_google=False returns 'suggest:y:тест'."""
        from app.services.suggest_service import suggest_cache_key

        result = suggest_cache_key("Тест", False)
        assert result == "suggest:y:тест"

    def test_normalizes_whitespace_and_case(self):
        """suggest_cache_key strips whitespace and lowercases the seed."""
        from app.services.suggest_service import suggest_cache_key

        result = suggest_cache_key("  ПРИВЕТ МИР  ", False)
        assert result == "suggest:y:привет мир"


# ---------------------------------------------------------------------------
# deduplicate_suggestions
# ---------------------------------------------------------------------------

class TestDeduplicateSuggestions:
    def test_merges_yandex_and_google_results(self):
        """deduplicate_suggestions merges both lists and preserves source tags."""
        from app.services.suggest_service import deduplicate_suggestions

        yandex = ["ключевое слово", "SEO продвижение"]
        google = ["google результат", "ещё один"]

        result = deduplicate_suggestions(yandex, google)

        assert len(result) == 4
        sources = {r["source"] for r in result}
        assert "yandex" in sources
        assert "google" in sources

    def test_deduplicates_overlapping_results(self):
        """deduplicate_suggestions removes duplicates across sources."""
        from app.services.suggest_service import deduplicate_suggestions

        yandex = ["общее слово", "только яндекс"]
        google = ["общее слово", "только гугл"]  # 'общее слово' is duplicate

        result = deduplicate_suggestions(yandex, google)

        keywords = [r["keyword"] for r in result]
        # 'общее слово' should appear only once (from yandex)
        assert keywords.count("общее слово") == 1
        assert len(result) == 3

    def test_yandex_results_have_source_yandex(self):
        """deduplicate_suggestions tags yandex-origin results correctly."""
        from app.services.suggest_service import deduplicate_suggestions

        result = deduplicate_suggestions(["яндекс слово"], [])

        assert result[0]["source"] == "yandex"
        assert result[0]["keyword"] == "яндекс слово"

    def test_google_results_have_source_google(self):
        """deduplicate_suggestions tags google-origin results correctly."""
        from app.services.suggest_service import deduplicate_suggestions

        result = deduplicate_suggestions([], ["google слово"])

        assert result[0]["source"] == "google"
        assert result[0]["keyword"] == "google слово"

    def test_strips_whitespace_from_keywords(self):
        """deduplicate_suggestions strips whitespace from keywords."""
        from app.services.suggest_service import deduplicate_suggestions

        result = deduplicate_suggestions(["  пробел  "], [])

        assert result[0]["keyword"] == "пробел"

    def test_empty_strings_are_filtered(self):
        """deduplicate_suggestions ignores empty or whitespace-only strings."""
        from app.services.suggest_service import deduplicate_suggestions

        result = deduplicate_suggestions(["", "   ", "нормальное"], [])

        assert len(result) == 1
        assert result[0]["keyword"] == "нормальное"

    def test_empty_inputs_return_empty_list(self):
        """deduplicate_suggestions with empty inputs returns empty list."""
        from app.services.suggest_service import deduplicate_suggestions

        result = deduplicate_suggestions([], [])

        assert result == []
