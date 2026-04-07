"""Unit tests for Yandex Wordstat API service."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.services.wordstat_service import (
    WORDSTAT_API_BASE,
    fetch_wordstat_frequency_sync,
)
from app.services.service_credential_service import ENCRYPTED_FIELDS


def test_yandex_direct_in_encrypted_fields():
    """Yandex Direct token must be in encrypted fields registry."""
    assert "yandex_direct" in ENCRYPTED_FIELDS
    assert ENCRYPTED_FIELDS["yandex_direct"] == ["token"]


@respx.mock
def test_fetch_frequency_success():
    """Normal response returns phrase -> count map."""
    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(
        return_value=httpx.Response(200, json={"count": 12345})
    )
    result = fetch_wordstat_frequency_sync(["купить диван"], oauth_token="test")
    assert result == {"купить диван": 12345}


@respx.mock
def test_fetch_frequency_uses_bearer_token():
    """Request must include Bearer token header."""
    route = respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(
        return_value=httpx.Response(200, json={"count": 100})
    )
    fetch_wordstat_frequency_sync(["test"], oauth_token="my-token")
    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer my-token"


@respx.mock
def test_fetch_frequency_429_returns_partial():
    """429 quota exceeded returns what was collected so far."""
    responses = [
        httpx.Response(200, json={"count": 100}),
        httpx.Response(429, json={"error": "quota"}),
        httpx.Response(200, json={"count": 200}),
    ]
    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(side_effect=responses)
    result = fetch_wordstat_frequency_sync(
        ["phrase1", "phrase2", "phrase3"], oauth_token="test"
    )
    assert result == {"phrase1": 100}


@respx.mock
def test_fetch_frequency_partial_on_mid_batch_error():
    """Single phrase HTTP error is logged, others continue."""
    responses = [
        httpx.Response(200, json={"count": 50}),
        httpx.Response(500, json={"error": "boom"}),
        httpx.Response(200, json={"count": 75}),
    ]
    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(side_effect=responses)
    result = fetch_wordstat_frequency_sync(
        ["a", "b", "c"], oauth_token="test"
    )
    assert result == {"a": 50, "c": 75}


@respx.mock
def test_fetch_frequency_top_requests_fallback():
    """Handles topRequests list shape when count field absent."""
    respx.post(f"{WORDSTAT_API_BASE}/v1/topRequests").mock(
        return_value=httpx.Response(
            200, json={"topRequests": [{"count": 999}]}
        )
    )
    result = fetch_wordstat_frequency_sync(["x"], oauth_token="t")
    assert result == {"x": 999}


def test_fetch_frequency_empty_phrases():
    """Empty phrase list returns empty dict."""
    result = fetch_wordstat_frequency_sync([], oauth_token="test")
    assert result == {}
