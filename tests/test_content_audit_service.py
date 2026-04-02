"""Tests for content audit service: detection, classification, check engine."""
from app.services.content_audit_service import (
    classify_content_type,
    check_internal_links,
    detect_author_block,
    detect_cta_block,
    detect_related_posts,
    run_checks_for_page,
)


# ---- Author detection ----


def test_detect_author_block_present():
    html = '<div class="author-box"><span>John Doe</span></div>'
    assert detect_author_block(html) is True


def test_detect_author_block_absent():
    html = "<p>Just a normal paragraph.</p>"
    assert detect_author_block(html) is False


def test_detect_author_block_rel_author():
    html = '<a href="/about" rel="author">Author Name</a>'
    assert detect_author_block(html) is True


def test_detect_author_block_info_variant():
    html = '<div class="author-info"><img src="a.jpg">Bio text</div>'
    assert detect_author_block(html) is True


# ---- Related posts detection ----


def test_detect_related_posts_present():
    html = '<div class="related-posts"><ul><li>Post 1</li></ul></div>'
    assert detect_related_posts(html) is True


def test_detect_related_posts_russian_text():
    html = "<h3>Похожие статьи</h3><ul><li>Статья 1</li></ul>"
    assert detect_related_posts(html) is True


def test_detect_related_posts_yarpp():
    html = '<div class="yarpp-related"><p>Related content</p></div>'
    assert detect_related_posts(html) is True


def test_detect_related_posts_absent():
    html = "<article><p>Simple blog content here.</p></article>"
    assert detect_related_posts(html) is False


# ---- CTA detection ----


def test_detect_cta_present():
    html = '<div class="cta-block"><button>Call us</button></div>'
    assert detect_cta_block(html) is True


def test_detect_cta_button_text():
    html = "<section><button>Заказать</button></section>"
    assert detect_cta_block(html) is True


def test_detect_cta_absent():
    html = "<article><p>Simple content.</p></article>"
    assert detect_cta_block(html) is False


# ---- Classification ----


def test_classify_article_is_informational():
    assert classify_content_type("article", "https://e.com/blog/post") == "informational"


def test_classify_product_is_commercial():
    assert classify_content_type("product", "https://e.com/product/1") == "commercial"


def test_classify_category_is_commercial():
    assert classify_content_type("category", "https://e.com/category/seo") == "commercial"


def test_classify_landing_services_url():
    assert classify_content_type("landing", "https://e.com/uslugi/seo/") == "commercial"


def test_classify_landing_generic_url():
    assert classify_content_type("landing", "https://e.com/") == "informational"


def test_classify_unknown_stays_unknown():
    assert classify_content_type("unknown", "https://e.com/page") == "unknown"


# ---- Internal links check ----


def test_check_internal_links_pass():
    assert check_internal_links(3) is True


def test_check_internal_links_fail():
    assert check_internal_links(0) is False


# ---- Check engine ----


_CHECKS_ALL = [
    {"code": "toc_present", "applies_to": "informational", "is_active": True, "severity": "warning"},
    {"code": "schema_present", "applies_to": "unknown", "is_active": True, "severity": "warning"},
    {"code": "author_block", "applies_to": "informational", "is_active": True, "severity": "warning"},
    {"code": "related_posts", "applies_to": "informational", "is_active": True, "severity": "warning"},
    {"code": "cta_present", "applies_to": "commercial", "is_active": True, "severity": "error"},
    {"code": "internal_links", "applies_to": "unknown", "is_active": True, "severity": "warning"},
    {"code": "noindex_check", "applies_to": "unknown", "is_active": True, "severity": "error"},
]


def test_run_checks_all_pass():
    html = '<div class="author-box">A</div><div class="related-posts">R</div>'
    pd = {
        "has_toc": True, "has_schema": True, "has_noindex": False,
        "internal_link_count": 5, "content_type": "informational",
    }
    results = run_checks_for_page(html, pd, _CHECKS_ALL)
    statuses = {r["check_code"]: r["status"] for r in results}
    assert statuses["toc_present"] == "pass"
    assert statuses["schema_present"] == "pass"
    assert statuses["noindex_check"] == "pass"


def test_run_checks_toc_missing():
    html = "<p>Simple content</p>"
    pd = {
        "has_toc": False, "has_schema": True, "has_noindex": False,
        "internal_link_count": 2, "content_type": "informational",
    }
    results = run_checks_for_page(html, pd, _CHECKS_ALL)
    statuses = {r["check_code"]: r["status"] for r in results}
    assert statuses["toc_present"] == "warning"


def test_run_checks_skip_commercial_only():
    html = "<p>Blog post</p>"
    pd = {
        "has_toc": True, "has_schema": True, "has_noindex": False,
        "internal_link_count": 1, "content_type": "informational",
    }
    results = run_checks_for_page(html, pd, _CHECKS_ALL)
    codes = [r["check_code"] for r in results]
    assert "cta_present" not in codes


def test_run_checks_noindex_fails_as_error():
    html = "<p>Content</p>"
    pd = {
        "has_toc": True, "has_schema": True, "has_noindex": True,
        "internal_link_count": 1, "content_type": "informational",
    }
    results = run_checks_for_page(html, pd, _CHECKS_ALL)
    statuses = {r["check_code"]: r["status"] for r in results}
    assert statuses["noindex_check"] == "fail"


def test_run_checks_inactive_skipped():
    checks = [
        {"code": "toc_present", "applies_to": "unknown", "is_active": False, "severity": "warning"},
    ]
    html = "<p>Content</p>"
    pd = {"has_toc": False, "content_type": "informational"}
    results = run_checks_for_page(html, pd, checks)
    assert len(results) == 0
