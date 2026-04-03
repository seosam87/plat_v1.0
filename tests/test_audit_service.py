"""Unit tests for audit_service detection functions and check engine.

All tests are pure (no DB) — detection functions and run_checks_for_page
are fully testable without any database connections.
"""
import pytest

from app.services.audit_service import (
    classify_content_type,
    detect_author_block,
    detect_cta_block,
    detect_related_posts,
    run_checks_for_page,
)


# ---------------------------------------------------------------------------
# detect_author_block
# ---------------------------------------------------------------------------


def test_detect_author_block_present():
    """HTML with author-box class returns True."""
    html = '<div class="author-box"><p>Jane Doe</p></div>'
    assert detect_author_block(html) is True


def test_detect_author_block_absent():
    """Plain HTML without any author indicators returns False."""
    html = "<div><p>Some article content here.</p></div>"
    assert detect_author_block(html) is False


def test_detect_author_block_rel_author():
    """HTML with rel="author" link returns True."""
    html = '<a href="/about/" rel="author">Jane Doe</a>'
    assert detect_author_block(html) is True


def test_detect_author_block_post_author_class():
    """HTML with post-author class returns True."""
    html = '<span class="post-author">Written by Jane</span>'
    assert detect_author_block(html) is True


def test_detect_author_block_author_info():
    """HTML with author-info class returns True."""
    html = '<section class="author-info"><p>Bio here</p></section>'
    assert detect_author_block(html) is True


# ---------------------------------------------------------------------------
# detect_related_posts
# ---------------------------------------------------------------------------


def test_detect_related_posts_present():
    """HTML with related-posts class returns True."""
    html = '<div class="related-posts"><ul><li>Article 1</li></ul></div>'
    assert detect_related_posts(html) is True


def test_detect_related_posts_russian_text():
    """HTML containing Russian 'Похожие статьи' returns True."""
    html = "<div><h3>Похожие статьи</h3><ul><li>Post</li></ul></div>"
    assert detect_related_posts(html) is True


def test_detect_related_posts_absent():
    """Plain HTML without related posts indicators returns False."""
    html = "<div><p>Some content without any related section.</p></div>"
    assert detect_related_posts(html) is False


def test_detect_related_posts_yarpp():
    """HTML with yarpp-related class (Yet Another Related Posts Plugin) returns True."""
    html = '<div class="yarpp-related"><ul><li>Related post</li></ul></div>'
    assert detect_related_posts(html) is True


def test_detect_related_posts_chitayte_takzhe():
    """HTML containing 'Читайте также' text returns True."""
    html = "<section><h4>Читайте также</h4></section>"
    assert detect_related_posts(html) is True


# ---------------------------------------------------------------------------
# detect_cta_block
# ---------------------------------------------------------------------------


def test_detect_cta_present():
    """HTML with cta-block class returns True."""
    html = '<div class="cta-block"><button>Click me</button></div>'
    assert detect_cta_block(html) is True


def test_detect_cta_button_text():
    """HTML containing 'Заказать' button text returns True."""
    html = '<button class="btn-primary">Заказать</button>'
    assert detect_cta_block(html) is True


def test_detect_cta_absent():
    """Plain HTML without CTA indicators returns False."""
    html = "<div><p>This is an informational article with no calls to action.</p></div>"
    assert detect_cta_block(html) is False


def test_detect_cta_ostavit_zayavku():
    """HTML with 'Оставить заявку' text returns True."""
    html = '<a href="/contact/" class="btn">Оставить заявку</a>'
    assert detect_cta_block(html) is True


def test_detect_cta_call_to_action_class():
    """HTML with call-to-action class returns True."""
    html = '<section class="call-to-action"><p>Contact us</p></section>'
    assert detect_cta_block(html) is True


# ---------------------------------------------------------------------------
# classify_content_type
# ---------------------------------------------------------------------------


def test_classify_article_is_informational():
    """page_type=article maps to informational."""
    result = classify_content_type("article", "/blog/how-to-do-seo/")
    assert result == "informational"


def test_classify_product_is_commercial():
    """page_type=product maps to commercial."""
    result = classify_content_type("product", "/shop/product-name/")
    assert result == "commercial"


def test_classify_category_is_commercial():
    """page_type=category maps to commercial."""
    result = classify_content_type("category", "/category/seo/")
    assert result == "commercial"


def test_classify_landing_services_url():
    """page_type=landing with /uslugi/ in URL maps to commercial."""
    result = classify_content_type("landing", "/uslugi/seo-prodvizhenie/")
    assert result == "commercial"


def test_classify_landing_price_url():
    """page_type=landing with /price/ in URL maps to commercial."""
    result = classify_content_type("landing", "/price/")
    assert result == "commercial"


def test_classify_landing_no_commercial_url():
    """page_type=landing without commercial URL patterns maps to informational."""
    result = classify_content_type("landing", "/o-kompanii/")
    assert result == "informational"


def test_classify_unknown_stays_unknown():
    """page_type=unknown maps to unknown."""
    result = classify_content_type("unknown", "/some-page/")
    assert result == "unknown"


# ---------------------------------------------------------------------------
# run_checks_for_page
# ---------------------------------------------------------------------------

# Reusable check definitions
_CHK_TOC = {
    "code": "toc_present",
    "is_active": True,
    "applies_to": "informational",
    "severity": "warning",
}
_CHK_SCHEMA = {
    "code": "schema_present",
    "is_active": True,
    "applies_to": "unknown",
    "severity": "warning",
}
_CHK_NOINDEX = {
    "code": "noindex_check",
    "is_active": True,
    "applies_to": "unknown",
    "severity": "error",
}
_CHK_CTA = {
    "code": "cta_present",
    "is_active": True,
    "applies_to": "commercial",
    "severity": "warning",
}
_CHK_AUTHOR = {
    "code": "author_block",
    "is_active": True,
    "applies_to": "informational",
    "severity": "warning",
}
_CHK_INTERNAL = {
    "code": "internal_links",
    "is_active": True,
    "applies_to": "unknown",
    "severity": "warning",
}


def test_run_checks_all_pass():
    """Page with TOC, schema, no noindex, and internal links passes all checks."""
    html = ""
    page_data = {
        "has_toc": True,
        "has_schema": True,
        "has_noindex": False,
        "internal_link_count": 5,
        "content_type": "informational",
        "page_type": "article",
        "url": "/blog/test/",
    }
    check_defs = [_CHK_TOC, _CHK_SCHEMA, _CHK_NOINDEX, _CHK_INTERNAL]
    results = run_checks_for_page(html, page_data, check_defs)
    by_code = {r["check_code"]: r for r in results}
    assert by_code["toc_present"]["status"] == "pass"
    assert by_code["schema_present"]["status"] == "pass"
    assert by_code["noindex_check"]["status"] == "pass"
    assert by_code["internal_links"]["status"] == "pass"


def test_run_checks_toc_missing():
    """Informational page without TOC produces toc_present=warning."""
    html = ""
    page_data = {
        "has_toc": False,
        "has_schema": True,
        "has_noindex": False,
        "internal_link_count": 3,
        "content_type": "informational",
        "page_type": "article",
        "url": "/blog/test/",
    }
    results = run_checks_for_page(html, page_data, [_CHK_TOC])
    assert results[0]["check_code"] == "toc_present"
    assert results[0]["status"] == "warning"


def test_run_checks_skip_commercial_only():
    """Informational page skips the cta_present check (applies_to=commercial)."""
    html = ""
    page_data = {
        "has_toc": True,
        "has_schema": True,
        "has_noindex": False,
        "internal_link_count": 1,
        "content_type": "informational",
        "page_type": "article",
        "url": "/blog/test/",
    }
    results = run_checks_for_page(html, page_data, [_CHK_CTA, _CHK_TOC])
    codes = {r["check_code"] for r in results}
    assert "cta_present" not in codes, "cta_present should be skipped for informational"
    assert "toc_present" in codes


def test_run_checks_noindex_fails_as_error():
    """Page with noindex=True produces noindex_check=fail (severity=error)."""
    html = ""
    page_data = {
        "has_toc": False,
        "has_schema": False,
        "has_noindex": True,
        "internal_link_count": 0,
        "content_type": "unknown",
        "page_type": "unknown",
        "url": "/some-page/",
    }
    results = run_checks_for_page(html, page_data, [_CHK_NOINDEX])
    assert results[0]["check_code"] == "noindex_check"
    assert results[0]["status"] == "fail"


def test_run_checks_inactive_skipped():
    """Check with is_active=False is not included in results."""
    inactive_toc = {**_CHK_TOC, "is_active": False}
    html = ""
    page_data = {
        "has_toc": False,
        "has_schema": False,
        "has_noindex": False,
        "internal_link_count": 0,
        "content_type": "informational",
        "page_type": "article",
        "url": "/blog/",
    }
    results = run_checks_for_page(html, page_data, [inactive_toc])
    codes = [r["check_code"] for r in results]
    assert "toc_present" not in codes


def test_run_checks_unknown_applies_to_matches_all():
    """Check with applies_to=unknown runs against any content_type."""
    html = ""
    page_data = {
        "has_toc": False,
        "has_schema": True,
        "has_noindex": False,
        "internal_link_count": 0,
        "content_type": "commercial",
        "page_type": "product",
        "url": "/shop/",
    }
    # schema_present has applies_to=unknown — should run on commercial pages too
    results = run_checks_for_page(html, page_data, [_CHK_SCHEMA])
    assert len(results) == 1
    assert results[0]["check_code"] == "schema_present"
    assert results[0]["status"] == "pass"
