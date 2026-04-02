"""Tests for architecture service: URL tree, sitemap parsing, inlinks diff."""
from app.services.architecture_service import (
    build_url_tree,
    compute_inlinks_diff,
    parse_sitemap_xml,
)


# ---- URL Tree ----


def test_build_url_tree_basic():
    urls = ["https://e.com/", "https://e.com/about/", "https://e.com/blog/"]
    tree = build_url_tree(urls)
    assert tree["name"] == "/"
    assert len(tree["children"]) == 2
    names = {c["name"] for c in tree["children"]}
    assert "about" in names
    assert "blog" in names


def test_build_url_tree_deep():
    urls = ["https://e.com/uslugi/seo/audit/", "https://e.com/uslugi/seo/"]
    tree = build_url_tree(urls)
    uslugi = tree["children"][0]
    assert uslugi["name"] == "uslugi"
    seo = uslugi["children"][0]
    assert seo["name"] == "seo"
    assert len(seo["children"]) == 1
    assert seo["children"][0]["name"] == "audit"


def test_build_url_tree_empty():
    tree = build_url_tree([])
    assert tree["name"] == "/"
    assert tree["children"] == []
    assert tree["page_count"] == 0


def test_build_url_tree_page_count():
    urls = ["https://e.com/a/", "https://e.com/a/b/", "https://e.com/a/c/"]
    tree = build_url_tree(urls)
    assert tree["page_count"] == 3


# ---- Sitemap parsing ----


def test_parse_sitemap_xml():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://e.com/page1/</loc><lastmod>2026-01-01</lastmod></url>
        <url><loc>https://e.com/page2/</loc></url>
    </urlset>"""
    entries = parse_sitemap_xml(xml)
    assert len(entries) == 2
    assert entries[0]["url"] == "https://e.com/page1/"
    assert entries[0]["lastmod"] == "2026-01-01"


def test_parse_sitemap_xml_index():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>https://e.com/sitemap-posts.xml</loc></sitemap>
        <sitemap><loc>https://e.com/sitemap-pages.xml</loc></sitemap>
    </sitemapindex>"""
    entries = parse_sitemap_xml(xml)
    assert len(entries) == 2
    assert entries[0]["is_index"] is True


def test_parse_sitemap_xml_empty():
    assert parse_sitemap_xml("") == []
    assert parse_sitemap_xml("not xml") == []


# ---- Inlinks diff ----


def test_compute_inlinks_diff_added():
    old = [{"source_url": "/a/", "target_url": "/b/", "anchor_text": "link"}]
    new = [
        {"source_url": "/a/", "target_url": "/b/", "anchor_text": "link"},
        {"source_url": "/a/", "target_url": "/c/", "anchor_text": "new"},
    ]
    diff = compute_inlinks_diff(old, new)
    assert diff["added_count"] == 1
    assert diff["removed_count"] == 0
    assert diff["added"][0]["target_url"] == "/c/"


def test_compute_inlinks_diff_removed():
    old = [{"source_url": "/a/", "target_url": "/b/"}]
    new = []
    diff = compute_inlinks_diff(old, new)
    assert diff["removed_count"] == 1
    assert diff["added_count"] == 0


def test_compute_inlinks_diff_no_changes():
    links = [{"source_url": "/a/", "target_url": "/b/"}]
    diff = compute_inlinks_diff(links, links)
    assert diff["added_count"] == 0
    assert diff["removed_count"] == 0
