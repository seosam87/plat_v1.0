"""Tests for SERP analysis service: classification, competitor detection."""
from app.services.serp_analysis_service import (
    analyze_serp_results,
    classify_site_type,
    extract_domain,
)


def test_classify_site_type_aggregator():
    assert classify_site_type("avito.ru") == "aggregator"
    assert classify_site_type("ozon.ru") == "aggregator"


def test_classify_site_type_aggregator_subdomain():
    assert classify_site_type("m.avito.ru") == "aggregator"


def test_classify_site_type_informational():
    assert classify_site_type("habr.com") == "informational"
    assert classify_site_type("wikipedia.org") == "informational"


def test_classify_site_type_informational_url():
    assert classify_site_type("example.com", "https://example.com/blog/post") == "informational"


def test_classify_site_type_commercial_default():
    assert classify_site_type("mysite.ru") == "commercial"


def test_extract_domain():
    assert extract_domain("https://www.example.com/page/") == "example.com"
    assert extract_domain("https://sub.example.com/") == "sub.example.com"


def test_analyze_serp_results_basic():
    serp_data = [
        {
            "keyword_phrase": "seo продвижение",
            "results": [
                {"position": 1, "url": "https://competitor.ru/seo/", "domain": "competitor.ru", "title": "SEO"},
                {"position": 2, "url": "https://avito.ru/seo/", "domain": "avito.ru", "title": "Avito"},
                {"position": 3, "url": "https://competitor.ru/about/", "domain": "competitor.ru", "title": "About"},
            ],
        },
        {
            "keyword_phrase": "раскрутка сайта",
            "results": [
                {"position": 1, "url": "https://competitor.ru/promo/", "domain": "competitor.ru", "title": "Promo"},
                {"position": 2, "url": "https://other.ru/", "domain": "other.ru", "title": "Other"},
            ],
        },
    ]
    result = analyze_serp_results(serp_data)
    assert result["total_keywords"] == 2
    assert result["top_competitors"][0]["domain"] == "competitor.ru"
    assert result["top_competitors"][0]["appearances"] == 2


def test_analyze_serp_results_excludes_our_domain():
    serp_data = [
        {
            "keyword_phrase": "test",
            "results": [
                {"position": 1, "url": "https://mysite.ru/page/", "domain": "mysite.ru", "title": "Our"},
                {"position": 2, "url": "https://comp.ru/page/", "domain": "comp.ru", "title": "Comp"},
            ],
        },
    ]
    result = analyze_serp_results(serp_data, our_domain="mysite.ru")
    domains = [c["domain"] for c in result["top_competitors"]]
    assert "mysite.ru" not in domains
    assert "comp.ru" in domains


def test_analyze_serp_results_empty():
    result = analyze_serp_results([])
    assert result["total_keywords"] == 0
    assert result["top_competitors"] == []


def test_analyze_serp_site_type_distribution():
    serp_data = [
        {
            "keyword_phrase": "test",
            "results": [
                {"position": 1, "url": "https://avito.ru/", "domain": "avito.ru", "title": "A"},
                {"position": 2, "url": "https://habr.com/blog/", "domain": "habr.com", "title": "H"},
                {"position": 3, "url": "https://shop.ru/", "domain": "shop.ru", "title": "S"},
            ],
        },
    ]
    result = analyze_serp_results(serp_data)
    dist = result["site_type_distribution"]
    assert dist.get("aggregator", 0) >= 1
    assert dist.get("informational", 0) >= 1
    assert dist.get("commercial", 0) >= 1
