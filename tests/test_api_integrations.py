"""Unit tests for GSC, DataForSEO, and Yandex Webmaster service clients."""
import base64
from unittest.mock import patch

import httpx
import pytest
import respx

from app.services.gsc_service import (
    build_authorize_url,
    exchange_code,
    fetch_search_analytics,
)
from app.services.dataforseo_service import (
    _auth_header,
    fetch_serp,
    fetch_search_volume,
    is_configured,
)
from app.services.yandex_webmaster_service import (
    get_user_id,
    list_hosts,
    fetch_search_queries,
)
from app.services.serp_parser_service import (
    _check_daily_limit,
    _get_ua,
    get_daily_usage,
    USER_AGENTS,
)


# ---------------------------------------------------------------------------
# GSC service
# ---------------------------------------------------------------------------


class TestGscService:
    def test_build_authorize_url(self):
        with patch("app.services.gsc_service.settings") as mock:
            mock.GSC_CLIENT_ID = "test-client-id"
            mock.GSC_REDIRECT_URI = "http://localhost:8000/auth/gsc/callback"
            url = build_authorize_url("site-123")
            assert "test-client-id" in url
            assert "state=site-123" in url
            assert "access_type=offline" in url

    @respx.mock
    @pytest.mark.asyncio
    async def test_exchange_code(self):
        with patch("app.services.gsc_service.settings") as mock:
            mock.GSC_CLIENT_ID = "cid"
            mock.GSC_CLIENT_SECRET = "csec"
            mock.GSC_REDIRECT_URI = "http://localhost/cb"

            respx.post("https://oauth2.googleapis.com/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "at-123",
                    "refresh_token": "rt-456",
                    "expires_in": 3600,
                })
            )
            result = await exchange_code("auth-code")
            assert result["access_token"] == "at-123"
            assert result["refresh_token"] == "rt-456"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_analytics(self):
        url_pattern = "https://searchconsole.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        respx.post(url_pattern).mock(
            return_value=httpx.Response(200, json={
                "rows": [
                    {
                        "keys": ["seo tools", "https://example.com/seo"],
                        "clicks": 50,
                        "impressions": 1000,
                        "ctr": 0.05,
                        "position": 3.2,
                    },
                ]
            })
        )
        # Use a simpler URL for the test
        rows = await fetch_search_analytics(
            "token-123",
            "https://example.com/",
            "2026-03-01",
            "2026-03-28",
        )
        assert len(rows) == 1
        assert rows[0]["query"] == "seo tools"
        assert rows[0]["clicks"] == 50
        assert rows[0]["position"] == 3.2

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_analytics_empty_response(self):
        url_pattern = "https://searchconsole.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        respx.post(url_pattern).mock(
            return_value=httpx.Response(200, json={"rows": []})
        )
        rows = await fetch_search_analytics("token", "https://example.com/", "2026-03-01", "2026-03-28")
        assert rows == []


# ---------------------------------------------------------------------------
# DataForSEO service
# ---------------------------------------------------------------------------


class TestDataForSeoService:
    def test_auth_header(self):
        with patch("app.services.dataforseo_service.settings") as mock:
            mock.DATAFORSEO_LOGIN = "user"
            mock.DATAFORSEO_PASSWORD = "pass"
            header = _auth_header()
            decoded = base64.b64decode(header.split(" ")[1]).decode()
            assert decoded == "user:pass"

    def test_is_configured_false(self):
        with patch("app.services.dataforseo_service.settings") as mock:
            mock.DATAFORSEO_LOGIN = ""
            mock.DATAFORSEO_PASSWORD = ""
            assert is_configured() is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_serp(self):
        with patch("app.services.dataforseo_service.settings") as mock:
            mock.DATAFORSEO_LOGIN = "user"
            mock.DATAFORSEO_PASSWORD = "pass"

            respx.post("https://api.dataforseo.com/v3/serp/google/organic/live/advanced").mock(
                return_value=httpx.Response(200, json={
                    "tasks": [{
                        "result": [{
                            "items": [
                                {"type": "organic", "rank_group": 1, "url": "https://a.com", "title": "A", "description": "Desc A"},
                                {"type": "organic", "rank_group": 2, "url": "https://b.com", "title": "B", "description": "Desc B"},
                                {"type": "paid", "rank_group": 0, "url": "https://ad.com", "title": "Ad"},
                            ]
                        }]
                    }]
                })
            )
            results = await fetch_serp("seo tools")
            assert len(results) == 2  # paid filtered out
            assert results[0]["position"] == 1
            assert results[0]["url"] == "https://a.com"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_volume(self):
        with patch("app.services.dataforseo_service.settings") as mock:
            mock.DATAFORSEO_LOGIN = "user"
            mock.DATAFORSEO_PASSWORD = "pass"

            respx.post("https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live").mock(
                return_value=httpx.Response(200, json={
                    "tasks": [{
                        "result": [
                            {"keyword": "seo tools", "search_volume": 5000, "competition": 0.3, "cpc": 1.5},
                        ]
                    }]
                })
            )
            results = await fetch_search_volume(["seo tools"])
            assert len(results) == 1
            assert results[0]["search_volume"] == 5000

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_serp_not_configured(self):
        with patch("app.services.dataforseo_service.settings") as mock:
            mock.DATAFORSEO_LOGIN = ""
            mock.DATAFORSEO_PASSWORD = ""
            results = await fetch_serp("test")
            assert results == []


# ---------------------------------------------------------------------------
# Yandex Webmaster service
# ---------------------------------------------------------------------------


class TestYandexWebmasterService:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_user_id(self):
        with patch("app.services.yandex_webmaster_service.settings") as mock:
            mock.YANDEX_WEBMASTER_TOKEN = "test-token"
            respx.get("https://api.webmaster.yandex.net/v4/user/").mock(
                return_value=httpx.Response(200, json={"user_id": 12345})
            )
            uid = await get_user_id()
            assert uid == "12345"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_hosts(self):
        with patch("app.services.yandex_webmaster_service.settings") as mock:
            mock.YANDEX_WEBMASTER_TOKEN = "test-token"
            respx.get("https://api.webmaster.yandex.net/v4/user/123/hosts/").mock(
                return_value=httpx.Response(200, json={
                    "hosts": [
                        {"host_id": "h1", "ascii_host_url": "https://example.com", "verified": True},
                    ]
                })
            )
            hosts = await list_hosts("123")
            assert len(hosts) == 1
            assert hosts[0]["verified"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_queries(self):
        with patch("app.services.yandex_webmaster_service.settings") as mock:
            mock.YANDEX_WEBMASTER_TOKEN = "test-token"
            respx.get(
                "https://api.webmaster.yandex.net/v4/user/123/hosts/h1/search-queries/popular"
            ).mock(
                return_value=httpx.Response(200, json={
                    "queries": [
                        {
                            "query_text": "seo tools",
                            "indicators": {
                                "TOTAL_CLICKS": 30,
                                "TOTAL_SHOWS": 500,
                                "AVG_SHOW_POSITION": 4.5,
                            },
                        },
                    ]
                })
            )
            rows = await fetch_search_queries("123", "h1", "2026-03-01", "2026-03-28")
            assert len(rows) == 1
            assert rows[0]["query"] == "seo tools"
            assert rows[0]["clicks"] == 30
            assert rows[0]["position"] == 4.5


# ---------------------------------------------------------------------------
# SERP parser service (unit — no Playwright)
# ---------------------------------------------------------------------------


class TestSerpParserService:
    def test_user_agent_rotation(self):
        ua1 = _get_ua()
        assert ua1 in USER_AGENTS

    def test_daily_limit_check(self):
        # Should be True when counter is fresh
        assert _check_daily_limit() is True

    def test_get_daily_usage(self):
        usage = get_daily_usage()
        assert "used" in usage
        assert "limit" in usage
        assert usage["limit"] == 50  # default SERP_MAX_DAILY_REQUESTS
