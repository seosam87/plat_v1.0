"""Unit tests for XMLProxy service — XML parsing and API client."""
import pytest
import respx
import httpx

from app.services.xmlproxy_service import (
    _parse_yandex_xml,
    search_yandex_sync,
    fetch_balance_sync,
    XMLProxyError,
)

# ---------------------------------------------------------------------------
# Sample XML fixtures
# ---------------------------------------------------------------------------

ORGANIC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<yandexsearch version="1.0">
  <response>
    <results>
      <grouping>
        <group>
          <doc>
            <url>https://example.com/page1</url>
            <title>Example Page 1</title>
            <domain>example.com</domain>
          </doc>
        </group>
        <group>
          <doc>
            <url>https://foo.org/article</url>
            <title>Foo Article</title>
            <domain>foo.org</domain>
          </doc>
        </group>
        <group>
          <doc>
            <url>https://bar.net/</url>
            <title>Bar Site</title>
            <domain>bar.net</domain>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>"""

ERROR_55_XML = """<?xml version="1.0" encoding="UTF-8"?>
<yandexsearch version="1.0">
  <response>
    <error code="-55">async</error>
  </response>
</yandexsearch>"""

ERROR_32_XML = """<?xml version="1.0" encoding="UTF-8"?>
<yandexsearch version="1.0">
  <response>
    <error code="-32">no funds</error>
  </response>
</yandexsearch>"""

NODOMAIN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<yandexsearch version="1.0">
  <response>
    <results>
      <grouping>
        <group>
          <doc>
            <url>https://nodomain.example.com/path</url>
            <title>No Domain Field</title>
            <domain></domain>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>"""


# ---------------------------------------------------------------------------
# _parse_yandex_xml tests
# ---------------------------------------------------------------------------


def test_parse_organic_results():
    result = _parse_yandex_xml(ORGANIC_XML)
    assert result["error_code"] is None
    assert len(result["results"]) == 3
    assert result["results"][0] == {
        "position": 1,
        "url": "https://example.com/page1",
        "title": "Example Page 1",
        "domain": "example.com",
    }
    assert result["results"][1]["position"] == 2
    assert result["results"][2]["position"] == 3


def test_parse_error_55():
    with pytest.raises(XMLProxyError) as exc_info:
        _parse_yandex_xml(ERROR_55_XML)
    assert exc_info.value.code == -55


def test_parse_error_32():
    with pytest.raises(XMLProxyError) as exc_info:
        _parse_yandex_xml(ERROR_32_XML)
    assert exc_info.value.code == -32


def test_parse_domain_fallback_from_url():
    """When <domain> is empty, domain is extracted from URL."""
    result = _parse_yandex_xml(NODOMAIN_XML)
    assert result["results"][0]["domain"] == "nodomain.example.com"


# ---------------------------------------------------------------------------
# search_yandex_sync (respx mock)
# ---------------------------------------------------------------------------


@respx.mock
def test_search_yandex_sync_returns_results():
    respx.get("https://xmlproxy.ru/search.php").mock(
        return_value=httpx.Response(200, text=ORGANIC_XML)
    )
    result = search_yandex_sync("user", "key", "test query", lr=213)
    assert len(result["results"]) == 3
    assert result["results"][0]["url"] == "https://example.com/page1"


# ---------------------------------------------------------------------------
# fetch_balance_sync (respx mock)
# ---------------------------------------------------------------------------


@respx.mock
def test_fetch_balance_sync_returns_balance():
    balance_data = {"data": 100.0, "cur_cost": 0.018, "max_cost": 0.05}
    respx.get("https://xmlproxy.ru/balance.php").mock(
        return_value=httpx.Response(200, json=balance_data)
    )
    result = fetch_balance_sync("user", "key")
    assert result is not None
    assert result["data"] == 100.0
    assert result["cur_cost"] == 0.018


@respx.mock
def test_fetch_balance_sync_returns_none_on_error():
    respx.get("https://xmlproxy.ru/balance.php").mock(
        side_effect=httpx.ConnectError("refused")
    )
    result = fetch_balance_sync("user", "key")
    assert result is None
