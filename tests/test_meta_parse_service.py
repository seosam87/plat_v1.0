"""Tests for meta_parse_service.fetch_and_parse_urls."""
import inspect
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.meta_parse_service import _fetch_url, fetch_and_parse_urls


@pytest.mark.asyncio
async def test_fetch_url_success():
    """Test successful URL fetch with proper meta extraction."""
    html = """<html><head>
        <title>Test Page</title>
        <meta name="description" content="Test description">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="https://example.com/page">
    </head><body>
        <h1>Main Heading</h1>
        <h2>Sub 1</h2><h2>Sub 2</h2>
    </body></html>"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_response.url = "https://example.com/page"

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    result = await _fetch_url(mock_client, "https://example.com/page")
    assert result["status_code"] == 200
    assert result["title"] == "Test Page"
    assert result["h1"] == "Main Heading"
    assert result["meta_description"] == "Test description"
    assert result["canonical"] == "https://example.com/page"
    assert result["robots"] == "index, follow"
    assert result["h2_list"] == ["Sub 1", "Sub 2"]
    assert result["error"] is None
    assert result["input_url"] == "https://example.com/page"
    assert result["final_url"] == "https://example.com/page"


@pytest.mark.asyncio
async def test_fetch_url_error():
    """Test URL fetch failure returns error dict."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    result = await _fetch_url(mock_client, "https://broken.example.com")
    assert result["status_code"] is None
    assert result["error"] is not None
    assert "Connection refused" in result["error"]
    assert result["title"] is None
    assert result["h1"] is None
    assert result["h2_list"] == []


@pytest.mark.asyncio
async def test_fetch_url_no_meta_tags():
    """Test page with no meta tags returns None for optional fields."""
    html = "<html><head><title>Bare Page</title></head><body></body></html>"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_response.url = "https://bare.example.com/"

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    result = await _fetch_url(mock_client, "https://bare.example.com/")
    assert result["status_code"] == 200
    assert result["title"] == "Bare Page"
    assert result["h1"] is None
    assert result["meta_description"] is None
    assert result["canonical"] is None
    assert result["robots"] is None
    assert result["h2_list"] == []
    assert result["error"] is None


@pytest.mark.asyncio
async def test_fetch_and_parse_urls_concurrency():
    """Test that concurrency is limited by semaphore (function signature check)."""
    sig = inspect.signature(fetch_and_parse_urls)
    assert "concurrency" in sig.parameters
    assert sig.parameters["concurrency"].default == 5


@pytest.mark.asyncio
async def test_fetch_url_h2_limit():
    """Test that h2_list is limited to 10 items."""
    h2_tags = "".join(f"<h2>Heading {i}</h2>" for i in range(15))
    html = f"<html><head><title>T</title></head><body>{h2_tags}</body></html>"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_response.url = "https://example.com/"

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    result = await _fetch_url(mock_client, "https://example.com/")
    assert len(result["h2_list"]) == 10
