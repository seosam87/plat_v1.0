"""Tests for batch_wordstat_service.py.

Tests cover:
- Basic result parsing
- Error handling (continues on per-phrase failure)
- Exact vs broad match quoting (Pitfall 4)
- Monthly dynamics extraction
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.services.batch_wordstat_service import (
    _extract_count,
    _extract_monthly,
    check_wordstat_oauth_token,
    fetch_wordstat_batch_sync,
)

WORDSTAT_API_BASE = "https://api.wordstat.yandex.net"


# ---------------------------------------------------------------------------
# test_fetch_wordstat_batch_sync_returns_results
# ---------------------------------------------------------------------------


@respx.mock
def test_fetch_wordstat_batch_sync_returns_results():
    """Mock httpx responses for exact + broad calls; verify result parsing."""
    phrase = "купить телефон"
    exact_phrase = f'"{phrase}"'

    # Exact match route — quoted phrase
    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(
        side_effect=lambda request: (
            httpx.Response(200, json={"count": 500, "topRequests": []})
            if request.content and exact_phrase.encode() in request.content
            else httpx.Response(200, json={"count": 2000, "topRequests": []})
        )
    )

    results = fetch_wordstat_batch_sync(
        phrases=[phrase],
        oauth_token="test_token_123",
    )

    assert len(results) == 1
    result = results[0]
    assert result["phrase"] == phrase
    assert result["freq_exact"] is not None
    assert result["freq_broad"] is not None
    assert isinstance(result["monthly"], list)


# ---------------------------------------------------------------------------
# test_fetch_wordstat_batch_sync_handles_api_error
# ---------------------------------------------------------------------------


@respx.mock
def test_fetch_wordstat_batch_sync_handles_api_error():
    """Mock a 500 response for one phrase; verify None values and continued processing."""
    phrases = ["купить телефон", "ремонт квартиры"]

    call_count = {"n": 0}

    def mock_response(request):
        call_count["n"] += 1
        # First two calls (exact + broad for first phrase) return 500
        if call_count["n"] <= 2:
            return httpx.Response(500)
        # Subsequent calls succeed
        return httpx.Response(200, json={"count": 1500})

    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(side_effect=mock_response)

    results = fetch_wordstat_batch_sync(
        phrases=phrases,
        oauth_token="test_token",
    )

    # Both phrases should be present (error doesn't stop processing)
    assert len(results) == 2
    assert results[0]["phrase"] == phrases[0]
    # First phrase had HTTP errors — should have None values
    assert results[0]["freq_exact"] is None
    assert results[0]["freq_broad"] is None
    # Second phrase should succeed
    assert results[1]["phrase"] == phrases[1]


# ---------------------------------------------------------------------------
# test_exact_vs_broad_different_quotes
# ---------------------------------------------------------------------------


@respx.mock
def test_exact_vs_broad_different_quotes():
    """Verify exact call sends quoted phrase; broad call sends unquoted phrase (Pitfall 4)."""
    phrase = "смартфон купить"
    captured_bodies: list[bytes] = []

    def capture_and_respond(request):
        captured_bodies.append(request.content)
        return httpx.Response(200, json={"count": 100})

    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(side_effect=capture_and_respond)

    fetch_wordstat_batch_sync(phrases=[phrase], oauth_token="token_xyz")

    # Should have made exactly 2 calls (exact + broad)
    assert len(captured_bodies) == 2

    import json

    # First call: exact match — phrase must be wrapped in double-quotes
    body_exact = json.loads(captured_bodies[0])
    assert body_exact["phrase"] == f'"{phrase}"', (
        f"Exact call should send '\"phrase\"' but got: {body_exact['phrase']!r}"
    )

    # Second call: broad match — phrase must NOT have extra quotes
    body_broad = json.loads(captured_bodies[1])
    assert body_broad["phrase"] == phrase, (
        f"Broad call should send plain phrase but got: {body_broad['phrase']!r}"
    )


# ---------------------------------------------------------------------------
# test_monthly_data_parsed
# ---------------------------------------------------------------------------


@respx.mock
def test_monthly_data_parsed():
    """Verify monthly dynamics list is returned correctly from broad response."""
    phrase = "ноутбук"
    monthly_payload = [
        {"year_month": "2026-01", "frequency": 1200},
        {"year_month": "2026-02", "frequency": 1340},
        {"year_month": "2026-03", "frequency": 1450},
    ]

    call_count = {"n": 0}

    def respond(request):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Exact match
            return httpx.Response(200, json={"count": 900})
        else:
            # Broad match with monthly data
            return httpx.Response(200, json={"count": 1450, "monthlyData": monthly_payload})

    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(side_effect=respond)

    results = fetch_wordstat_batch_sync(phrases=[phrase], oauth_token="token_abc")

    assert len(results) == 1
    result = results[0]
    assert result["monthly"] == monthly_payload
    assert result["freq_broad"] == 1450


# ---------------------------------------------------------------------------
# test_check_wordstat_oauth_token_returns_none_when_not_configured
# ---------------------------------------------------------------------------


def test_check_wordstat_oauth_token_returns_none_when_not_configured():
    """Returns None when yandex_direct credential is not in DB."""
    import app.services.service_credential_service as scs_module

    mock_db = MagicMock()
    with patch.object(scs_module, "get_credential_sync", return_value=None):
        token = check_wordstat_oauth_token(mock_db)

    assert token is None


# ---------------------------------------------------------------------------
# test_check_wordstat_oauth_token_returns_token
# ---------------------------------------------------------------------------


def test_check_wordstat_oauth_token_returns_token():
    """Returns token string when yandex_direct credential is configured."""
    import app.services.service_credential_service as scs_module

    mock_db = MagicMock()
    with patch.object(scs_module, "get_credential_sync", return_value={"token": "my_oauth_token_123"}):
        token = check_wordstat_oauth_token(mock_db)

    assert token == "my_oauth_token_123"


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


def test_extract_count_from_count_field():
    """_extract_count reads from top-level count field."""
    assert _extract_count({"count": 500}) == 500


def test_extract_count_from_top_requests():
    """_extract_count falls back to topRequests[0].count."""
    data = {"topRequests": [{"phrase": "test", "count": 250}]}
    assert _extract_count(data) == 250


def test_extract_count_returns_zero_on_empty():
    """_extract_count returns 0 on empty response."""
    assert _extract_count({}) == 0


def test_extract_monthly_from_monthly_data_key():
    """_extract_monthly parses monthlyData list."""
    data = {
        "monthlyData": [
            {"year_month": "2026-01", "frequency": 100},
            {"year_month": "2026-02", "frequency": 200},
        ]
    }
    result = _extract_monthly(data)
    assert len(result) == 2
    assert result[0] == {"year_month": "2026-01", "frequency": 100}


def test_extract_monthly_empty_on_no_key():
    """_extract_monthly returns empty list when no monthly data present."""
    assert _extract_monthly({"count": 500}) == []
