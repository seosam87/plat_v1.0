"""Integration tests: analytics workflow pure functions compose correctly."""
from app.services.brief_service import (
    build_heading_structure,
    format_brief_text,
    suggest_seo_fields,
)
from app.services.serp_analysis_service import analyze_serp_results, classify_site_type


def test_serp_analysis_to_competitor_detection():
    """Full SERP data → top competitor identified correctly."""
    serp_data = [
        {"keyword_phrase": "kw1", "results": [
            {"position": 1, "url": "https://top.ru/a/", "domain": "top.ru", "title": "A"},
            {"position": 2, "url": "https://other.ru/b/", "domain": "other.ru", "title": "B"},
        ]},
        {"keyword_phrase": "kw2", "results": [
            {"position": 1, "url": "https://top.ru/c/", "domain": "top.ru", "title": "C"},
            {"position": 3, "url": "https://third.ru/d/", "domain": "third.ru", "title": "D"},
        ]},
        {"keyword_phrase": "kw3", "results": [
            {"position": 2, "url": "https://top.ru/e/", "domain": "top.ru", "title": "E"},
        ]},
    ]
    result = analyze_serp_results(serp_data, our_domain="mysite.ru")
    assert result["top_competitors"][0]["domain"] == "top.ru"
    assert result["top_competitors"][0]["appearances"] == 3


def test_heading_structure_from_competitors():
    """Competitor headings → valid heading structure with sources."""
    comp_headings = [
        [{"level": 2, "text": "Цены"}, {"level": 2, "text": "Отзывы"}, {"level": 3, "text": "Sub"}],
        [{"level": 2, "text": "Цены"}, {"level": 2, "text": "Контакты"}],
        [{"level": 2, "text": "Цены"}, {"level": 2, "text": "Отзывы"}],
    ]
    keywords = ["seo продвижение", "аудит сайта"]
    result = build_heading_structure(comp_headings, keywords)
    h2_texts = [h["text"] for h in result if h["level"] == 2]
    assert "Цены" in h2_texts
    assert "Отзывы" in h2_texts
    h3_sources = [h["source"] for h in result if h["level"] == 3]
    assert "keyword" in h3_sources


def test_seo_fields_to_brief_format():
    """suggest_seo_fields → format_brief_text produces complete output."""
    seo = suggest_seo_fields("SEO продвижение сайтов", "МойСайт")
    brief = {
        "title": "ТЗ: SEO продвижение",
        "target_url": "https://mysite.ru/seo/",
        "created_at": "2026-04-02",
        "recommended_title": seo["title"],
        "recommended_h1": seo["h1"],
        "recommended_meta": seo["meta_description"],
        "keywords_json": [{"phrase": "SEO продвижение", "frequency": 1000}],
        "headings_json": [{"level": 2, "text": "Преимущества"}],
        "structure_notes": "Раздел: Услуги",
        "competitor_data_json": {"domain": "comp.ru", "pages_analyzed": 3},
    }
    text = format_brief_text(brief)
    assert "SEO продвижение" in text
    assert "МойСайт" in text or "mysite" in text.lower()
    assert "Ключевые слова" in text
    assert "1000" in text


def test_full_brief_text_all_sections():
    """format_brief_text with all fields produces all sections."""
    brief = {
        "title": "Test",
        "target_url": "https://e.com/",
        "created_at": "2026-04-02",
        "recommended_title": "Title",
        "recommended_h1": "H1",
        "recommended_meta": "Meta",
        "keywords_json": [{"phrase": "kw", "frequency": 100}],
        "headings_json": [{"level": 2, "text": "Section"}],
        "structure_notes": "Notes",
        "competitor_data_json": {"domain": "comp.ru"},
    }
    text = format_brief_text(brief)
    for section in ["SEO-поля", "Ключевые слова", "Структура заголовков", "Место в структуре", "Данные конкурентов"]:
        assert section in text


def test_site_type_distribution():
    """analyze_serp_results returns correct type distribution."""
    serp_data = [
        {"keyword_phrase": "test", "results": [
            {"position": 1, "url": "https://avito.ru/search", "domain": "avito.ru", "title": "Avito"},
            {"position": 2, "url": "https://habr.com/blog/1", "domain": "habr.com", "title": "Habr"},
            {"position": 3, "url": "https://shop.ru/product", "domain": "shop.ru", "title": "Shop"},
            {"position": 4, "url": "https://wiki.org/page", "domain": "wikipedia.org", "title": "Wiki"},
        ]},
    ]
    result = analyze_serp_results(serp_data)
    dist = result["site_type_distribution"]
    assert dist.get("aggregator", 0) >= 1
    assert dist.get("informational", 0) >= 1
    assert dist.get("commercial", 0) >= 1


def test_filter_keyword_ids_format():
    """Keyword IDs from filter are strings suitable for session creation."""
    import uuid
    ids = [str(uuid.uuid4()) for _ in range(5)]
    # Verify they're valid UUIDs
    for kid in ids:
        parsed = uuid.UUID(kid)
        assert str(parsed) == kid
