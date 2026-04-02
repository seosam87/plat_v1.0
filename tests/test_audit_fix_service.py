"""Tests for audit fix service: fix generators and integrity checks."""
from app.services.audit_fix_service import (
    generate_cta_fix,
    generate_links_fix,
    generate_schema_fix,
    generate_toc_fix,
    verify_html_integrity,
)


# ---- TOC fix ----


def test_generate_toc_fix_with_headings():
    html = "<p>Intro text.</p><h2>Section One</h2><p>Content.</p><h3>Sub</h3><p>More.</p>"
    result = generate_toc_fix(html)
    assert result is not None
    assert "toc" in result["processed_html"].lower() or "Table of Contents" in result["processed_html"]
    assert result["diff"]["has_changes"] is True
    assert result["headings_count"] == 2


def test_generate_toc_fix_no_headings():
    html = "<p>Just a paragraph without headings.</p>"
    result = generate_toc_fix(html)
    assert result is None


def test_generate_toc_fix_diff_has_added_lines():
    html = "<p>Intro.</p><h2>Title</h2><p>Body.</p>"
    result = generate_toc_fix(html)
    assert result is not None
    assert result["diff"]["added_lines"] > 0


# ---- CTA fix ----


def test_generate_cta_fix_appends():
    html = "<p>Product description.</p>"
    cta = '<div class="cta-block"><button>Buy Now</button></div>'
    result = generate_cta_fix(html, cta)
    assert result is not None
    assert result["processed_html"].endswith(cta)
    assert result["diff"]["has_changes"] is True


def test_generate_cta_fix_already_present():
    html = '<p>Text</p><div class="cta-block"><button>Buy</button></div>'
    result = generate_cta_fix(html, "<div class='cta-block'>New CTA</div>")
    assert result is None


def test_generate_cta_fix_no_template():
    html = "<p>Text</p>"
    result = generate_cta_fix(html, "")
    assert result is None


# ---- Schema fix ----


def test_generate_schema_fix_injects():
    html = "<p>Content without schema.</p>"
    tag = '<script type="application/ld+json">{"@type":"Article"}</script>'
    result = generate_schema_fix(html, tag)
    assert result is not None
    assert "application/ld+json" in result["processed_html"]
    assert result["diff"]["has_changes"] is True


def test_generate_schema_fix_already_has():
    html = '<p>Content</p><script type="application/ld+json">{"@type":"Article"}</script>'
    tag = '<script type="application/ld+json">{"@type":"Service"}</script>'
    result = generate_schema_fix(html, tag)
    assert result is None


# ---- Links fix ----


def test_generate_links_fix_adds_links():
    html = "<p>We offer SEO services for small businesses.</p>"
    keywords = [{"phrase": "SEO services", "url": "https://e.com/seo/"}]
    result = generate_links_fix(html, keywords)
    assert result is not None
    assert 'href="https://e.com/seo/"' in result["processed_html"]
    assert result["links_added"] == 1


def test_generate_links_fix_no_opportunities():
    html = "<p>Nothing relevant here.</p>"
    keywords = [{"phrase": "blockchain consulting", "url": "https://e.com/bc/"}]
    result = generate_links_fix(html, keywords)
    assert result is None


# ---- Integrity ----


def test_verify_integrity_valid():
    original = "<h2>Title</h2><p>Content.</p>"
    processed = '<h2 id="title">Title</h2><div class="toc">TOC</div><p>Content.</p>'
    result = verify_html_integrity(original, processed)
    assert result["valid"] is True
    assert result["warnings"] == []


def test_verify_integrity_heading_count_mismatch():
    original = "<h2>A</h2><h2>B</h2><p>Text</p>"
    processed = "<h2>A</h2><p>Text</p>"
    result = verify_html_integrity(original, processed)
    assert len(result["warnings"]) > 0
    assert "заголовков" in result["warnings"][0].lower()


def test_verify_integrity_content_too_short():
    original = "<p>" + "A" * 1000 + "</p>"
    processed = "<p>" + "A" * 100 + "</p>"
    result = verify_html_integrity(original, processed)
    assert len(result["warnings"]) > 0
    assert "короче" in result["warnings"][0].lower()
