"""Unit tests for normalize_url utility.

Tests cover:
- UTM parameter stripping
- http to https upgrade
- Trailing slash addition
- Fragment removal
- Mixed case normalization
- Edge cases (None, empty string)
- Non-UTM query parameter preservation
"""
import pytest

from app.utils.url_normalize import normalize_url


def test_strips_utm_params():
    """Single UTM parameter is removed; other parts preserved."""
    result = normalize_url("https://example.com/page/?utm_source=yandex&utm_medium=cpc")
    assert result == "https://example.com/page/"


def test_strips_multiple_utm():
    """All five UTM parameters are removed, leaving only the base URL."""
    result = normalize_url(
        "https://example.com/?utm_source=a&utm_medium=b&utm_campaign=c&utm_content=d&utm_term=e"
    )
    assert result == "https://example.com/"


def test_preserves_non_utm_params():
    """Non-UTM query parameters are preserved and sorted alphabetically."""
    result = normalize_url("https://example.com/page/?id=123&lang=ru")
    assert result == "https://example.com/page/?id=123&lang=ru"


def test_http_to_https():
    """http scheme is upgraded to https."""
    result = normalize_url("http://example.com/page/")
    assert result == "https://example.com/page/"


def test_trailing_slash_added():
    """Path without trailing slash and without file extension gets slash added."""
    result = normalize_url("https://example.com/page")
    assert result == "https://example.com/page/"


def test_root_url():
    """Root URL without trailing slash gets slash added."""
    result = normalize_url("https://example.com")
    assert result == "https://example.com/"


def test_already_normalized():
    """Already normalized URL is returned unchanged."""
    result = normalize_url("https://example.com/page/")
    assert result == "https://example.com/page/"


def test_mixed_case_scheme():
    """Scheme and host are lowercased; path case is preserved."""
    result = normalize_url("HTTP://Example.COM/Page/")
    assert result == "https://example.com/Page/"


def test_empty_string():
    """Empty string returns empty string."""
    result = normalize_url("")
    assert result == ""


def test_none_input():
    """None input returns None."""
    result = normalize_url(None)
    assert result is None


def test_strips_fragment():
    """URL fragment (#...) is removed."""
    result = normalize_url("https://example.com/page/#section")
    assert result == "https://example.com/page/"


def test_http_utm_combined():
    """Both http->https upgrade and UTM stripping happen together."""
    result = normalize_url("http://example.com/page?utm_source=yandex")
    assert result == "https://example.com/page/"


def test_file_extension_no_trailing_slash():
    """Paths with a file extension do not get a trailing slash added."""
    result = normalize_url("https://example.com/image.png")
    assert result == "https://example.com/image.png"


def test_non_utm_mixed_with_utm():
    """UTM params removed; non-UTM params kept alphabetically sorted."""
    result = normalize_url(
        "https://example.com/page/?id=5&utm_source=yandex&lang=ru&utm_medium=cpc"
    )
    assert result == "https://example.com/page/?id=5&lang=ru"
