"""Unit tests for crawl task helpers and crawler_service.extract_seo_data."""
import pytest
from unittest.mock import MagicMock

from app.tasks.crawl_tasks import _is_internal_link, _normalise_url
from app.services.crawler_service import extract_seo_data


# ---------------------------------------------------------------------------
# _is_internal_link
# ---------------------------------------------------------------------------


class TestIsInternalLink:
    def test_same_domain(self):
        assert _is_internal_link("https://example.com", "https://example.com/page") is True

    def test_different_domain(self):
        assert _is_internal_link("https://example.com", "https://other.com/page") is False

    def test_relative_url_no_host(self):
        assert _is_internal_link("https://example.com", "/about") is True

    def test_subdomain_is_external(self):
        assert _is_internal_link("https://example.com", "https://blog.example.com/post") is False

    def test_empty_href(self):
        assert _is_internal_link("https://example.com", "") is True


# ---------------------------------------------------------------------------
# _normalise_url
# ---------------------------------------------------------------------------


class TestNormaliseUrl:
    def test_absolute_url(self):
        result = _normalise_url("https://example.com", "https://example.com/page")
        assert result == "https://example.com/page"

    def test_relative_url(self):
        result = _normalise_url("https://example.com/blog/", "/about")
        assert result == "https://example.com/about"

    def test_strips_fragment(self):
        result = _normalise_url("https://example.com", "https://example.com/page#section")
        assert result == "https://example.com/page"

    def test_non_http_returns_none(self):
        assert _normalise_url("https://example.com", "mailto:a@b.com") is None

    def test_javascript_returns_none(self):
        assert _normalise_url("https://example.com", "javascript:void(0)") is None

    def test_relative_path(self):
        result = _normalise_url("https://example.com/blog/post", "other-post")
        assert result == "https://example.com/blog/other-post"


# ---------------------------------------------------------------------------
# extract_seo_data (mocked Playwright page)
# ---------------------------------------------------------------------------


def _make_mock_page(
    title="Test Title",
    h1_text="Main Heading",
    meta_desc="A description",
    robots_content=None,
    has_schema=False,
    has_toc=False,
):
    """Build a mock Playwright page with configurable SEO elements."""
    page = MagicMock()
    page.title.return_value = title

    # h1
    if h1_text:
        h1_el = MagicMock()
        h1_el.inner_text.return_value = h1_text
        page.query_selector.side_effect = lambda sel: {
            "h1": h1_el,
            "meta[name='description']": _mock_meta(meta_desc) if meta_desc else None,
            "meta[name='robots']": _mock_meta(robots_content) if robots_content else None,
        }.get(sel.split(",")[0].strip() if "," not in sel else sel, None)
    else:
        page.query_selector.return_value = None

    # More precise mock: query_selector is called with different selectors
    def query_selector_side_effect(selector):
        if selector == "h1":
            if h1_text:
                el = MagicMock()
                el.inner_text.return_value = h1_text
                return el
            return None
        elif selector == "meta[name='description']":
            return _mock_meta(meta_desc) if meta_desc else None
        elif selector == "meta[name='robots']":
            return _mock_meta(robots_content) if robots_content else None
        elif "toc" in selector or "table-of-contents" in selector:
            return MagicMock() if has_toc else None
        return None

    page.query_selector.side_effect = query_selector_side_effect

    # query_selector_all for schema detection
    if has_schema:
        page.query_selector_all.return_value = [MagicMock()]
    else:
        page.query_selector_all.return_value = []

    return page


def _mock_meta(content):
    if content is None:
        return None
    el = MagicMock()
    el.get_attribute.return_value = content
    return el


class TestExtractSeoData:
    def test_extracts_basic_fields(self):
        page = _make_mock_page(title="My Title", h1_text="Hello", meta_desc="Desc")
        result = extract_seo_data(page)
        assert result["title"] == "My Title"
        assert result["h1"] == "Hello"
        assert result["meta_description"] == "Desc"

    def test_noindex_detected(self):
        page = _make_mock_page(robots_content="noindex, nofollow")
        result = extract_seo_data(page)
        assert result["has_noindex"] is True

    def test_no_noindex_when_robots_absent(self):
        page = _make_mock_page(robots_content=None)
        result = extract_seo_data(page)
        assert result["has_noindex"] is False

    def test_index_follow_not_noindex(self):
        page = _make_mock_page(robots_content="index, follow")
        result = extract_seo_data(page)
        assert result["has_noindex"] is False

    def test_schema_detected(self):
        page = _make_mock_page(has_schema=True)
        result = extract_seo_data(page)
        assert result["has_schema"] is True

    def test_no_schema(self):
        page = _make_mock_page(has_schema=False)
        result = extract_seo_data(page)
        assert result["has_schema"] is False

    def test_toc_detected(self):
        page = _make_mock_page(has_toc=True)
        result = extract_seo_data(page)
        assert result["has_toc"] is True

    def test_no_toc(self):
        page = _make_mock_page(has_toc=False)
        result = extract_seo_data(page)
        assert result["has_toc"] is False

    def test_missing_h1(self):
        page = _make_mock_page(h1_text=None)
        result = extract_seo_data(page)
        assert result["h1"] == ""

    def test_missing_meta_description(self):
        page = _make_mock_page(meta_desc=None)
        result = extract_seo_data(page)
        assert result["meta_description"] == ""
