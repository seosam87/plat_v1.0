"""Tests for brief service: heading structure, SEO fields, text formatting.
Also covers Phase 25 brief TOP-10 service (crawl + aggregation).
"""
from app.services.brief_service import (
    build_heading_structure,
    format_brief_text,
    suggest_seo_fields,
)


def test_suggest_seo_fields_length():
    seo = suggest_seo_fields("SEO продвижение сайтов в поисковых системах", "МойСайт")
    assert len(seo["title"]) <= 60
    assert len(seo["meta_description"]) <= 160


def test_suggest_seo_fields_contains_keyword():
    seo = suggest_seo_fields("продвижение сайтов", "МойСайт")
    assert "продвижение сайтов" in seo["title"].lower()
    assert "продвижение сайтов" in seo["h1"].lower()
    assert "продвижение сайтов" in seo["meta_description"].lower()


def test_suggest_seo_fields_short_keyword():
    seo = suggest_seo_fields("SEO", "Site")
    assert seo["h1"] == "SEO"


def test_build_heading_structure_common_h2():
    comp_headings = [
        [{"level": 2, "text": "Преимущества"}, {"level": 2, "text": "Цены"}],
        [{"level": 2, "text": "Преимущества"}, {"level": 2, "text": "Контакты"}],
    ]
    result = build_heading_structure(comp_headings, [])
    h2_texts = [h["text"] for h in result if h["level"] == 2]
    assert "Преимущества" in h2_texts  # appears on both competitors


def test_build_heading_structure_keyword_h3():
    comp_headings = [[{"level": 2, "text": "Услуги"}]]
    keywords = ["seo продвижение", "аудит сайта"]
    result = build_heading_structure(comp_headings, keywords)
    h3_texts = [h["text"] for h in result if h["level"] == 3]
    assert len(h3_texts) == 2
    assert result[-1]["source"] == "keyword"


def test_build_heading_structure_empty_competitors():
    result = build_heading_structure([], ["keyword"])
    # Should still produce keyword-based H3s
    assert len(result) >= 1


def test_format_brief_text_structure():
    brief = {
        "title": "ТЗ: SEO",
        "target_url": "https://e.com/seo/",
        "created_at": "2026-04-02",
        "recommended_title": "SEO — Site",
        "recommended_h1": "SEO",
        "recommended_meta": "Description",
        "keywords_json": [{"phrase": "seo", "frequency": 1000}],
        "headings_json": [{"level": 2, "text": "Intro"}],
        "structure_notes": "Main section",
        "competitor_data_json": {"domain": "comp.ru"},
    }
    text = format_brief_text(brief)
    assert "ТЗ: SEO" in text
    assert "SEO-поля" in text
    assert "Ключевые слова" in text
    assert "Структура заголовков" in text
    assert "Место в структуре" in text
    assert "Данные конкурентов" in text


def test_format_brief_text_keywords():
    brief = {
        "title": "Test",
        "keywords_json": [
            {"phrase": "seo продвижение", "frequency": 1000},
            {"phrase": "аудит сайта", "frequency": 500},
        ],
    }
    text = format_brief_text(brief)
    assert "seo продвижение" in text
    assert "1000" in text
    assert "аудит сайта" in text


# ---------------------------------------------------------------------------
# Phase 25: brief_top10_service tests
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

from app.services.brief_top10_service import aggregate_brief_data, crawl_top10_page


def test_aggregate_brief_data_h2_cloud_sorted():
    """H2 cloud should be sorted by count descending."""
    pages = [
        {"h2s": ["SEO оптимизация", "Контент"], "text": "купить стоимость цена", "title": "Page 1", "url": "http://a.com"},
        {"h2s": ["SEO оптимизация", "Аналитика"], "text": "привет мир python программирование", "title": "Page 2", "url": "http://b.com"},
        {"h2s": ["SEO оптимизация"], "text": "сайт контент текст", "title": "Page 3", "url": "http://c.com"},
    ]
    result = aggregate_brief_data(pages, ["seo"])

    h2_cloud = result["h2_cloud"]
    assert len(h2_cloud) > 0
    assert h2_cloud[0]["text"] == "SEO оптимизация"
    assert h2_cloud[0]["count"] == 3
    counts = [item["count"] for item in h2_cloud]
    assert counts == sorted(counts, reverse=True)


def test_aggregate_brief_data_thematic_words_excludes_stopwords():
    """Thematic words should not contain Russian stopwords."""
    pages = [
        {
            "h2s": [],
            "text": "что как для это при или его все они она мы вы python программирование разработка",
            "title": "Test",
            "url": "http://test.com",
        }
    ]
    result = aggregate_brief_data(pages, ["test"])

    thematic_words = result["thematic_words"]
    word_set = {item["word"] for item in thematic_words}
    stopwords = {"что", "как", "для", "это", "при", "или", "его", "все", "они", "она", "мы", "вы"}
    assert not stopwords.intersection(word_set), f"Found stopwords in result: {stopwords.intersection(word_set)}"


def test_aggregate_brief_data_volume_stats():
    """Volume stats should be correct averages."""
    pages = [
        {"h2s": ["H2 1", "H2 2"], "text": "a" * 100, "title": "T1", "url": "http://a.com"},
        {"h2s": ["H2 A"], "text": "b" * 200, "title": "T2", "url": "http://b.com"},
    ]
    result = aggregate_brief_data(pages, ["test"])

    assert result["avg_text_length"] == 150
    assert result["avg_h2_count"] == 1.5
    assert result["pages_crawled"] == 2
    assert result["pages_attempted"] == 2


def test_aggregate_brief_data_commercialization_pct():
    """Commercialization % should reflect pages with purchase indicators."""
    pages = [
        {"h2s": [], "text": "купить товар стоимость цена", "title": "Shop", "url": "http://shop.com"},
        {"h2s": [], "text": "информационная статья без покупок", "title": "Info", "url": "http://info.com"},
    ]
    result = aggregate_brief_data(pages, ["test"])
    assert result["commercialization_pct"] == 50


def test_aggregate_brief_data_empty_pages():
    """Empty input should return zero stats without raising."""
    result = aggregate_brief_data([], ["test"])

    assert result["pages_crawled"] == 0
    assert result["pages_attempted"] == 0
    assert result["h2_cloud"] == []
    assert result["thematic_words"] == []
    assert result["title_suggestions"] == []


def test_aggregate_brief_data_with_none_pages():
    """None entries in crawled_pages should be filtered out gracefully."""
    pages = [
        None,
        {"h2s": ["H2 Title"], "text": "контент сайта оптимизация", "title": "Real Page", "url": "http://real.com"},
        None,
    ]
    result = aggregate_brief_data(pages, ["test"])

    assert result["pages_crawled"] == 1
    assert result["pages_attempted"] == 3


def test_aggregate_brief_data_title_suggestions_deduplicated():
    """Title suggestions should be deduplicated."""
    pages = [
        {"h2s": [], "text": "text1", "title": "Same Title", "url": "http://a.com"},
        {"h2s": [], "text": "text2", "title": "Same Title", "url": "http://b.com"},
        {"h2s": [], "text": "text3", "title": "Unique Title", "url": "http://c.com"},
    ]
    result = aggregate_brief_data(pages, ["test"])
    assert len(result["title_suggestions"]) == 2


def test_aggregate_brief_data_highlights_from_snippets():
    """Highlights should be populated from SERP snippets."""
    pages = [{"h2s": [], "text": "some text", "title": "T", "url": "http://a.com"}]
    snippets = ["First highlight text", "Second highlight text", "First highlight text"]

    result = aggregate_brief_data(pages, ["test"], serp_snippets=snippets)
    assert len(result["highlights"]) == 2


def test_crawl_top10_page_returns_none_on_http_error():
    """Should return None when server returns HTTP 4xx status."""
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 404

    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    mock_page.goto.return_value = mock_response

    import app.celery_app as ca_module
    from app.services import brief_top10_service as svc
    original_get_browser = ca_module.get_browser
    ca_module.get_browser = lambda: mock_browser
    try:
        result = svc.crawl_top10_page("http://example.com/not-found")
    finally:
        ca_module.get_browser = original_get_browser

    assert result is None


def test_crawl_top10_page_returns_none_on_exception():
    """Should return None on any exception (e.g., timeout)."""
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    mock_page.goto.side_effect = Exception("Timeout exceeded")

    import app.celery_app as ca_module
    from app.services import brief_top10_service as svc
    original_get_browser = ca_module.get_browser
    ca_module.get_browser = lambda: mock_browser
    try:
        result = svc.crawl_top10_page("http://example.com")
    finally:
        ca_module.get_browser = original_get_browser

    assert result is None


def test_brief_tasks_importable():
    """All 4 Celery tasks should be importable and have correct names."""
    from app.tasks.brief_tasks import (
        run_brief_step1_serp,
        run_brief_step2_crawl,
        run_brief_step3_aggregate,
        run_brief_step4_finalize,
    )

    assert run_brief_step1_serp.name == "app.tasks.brief_tasks.run_brief_step1_serp"
    assert run_brief_step2_crawl.name == "app.tasks.brief_tasks.run_brief_step2_crawl"
    assert run_brief_step3_aggregate.name == "app.tasks.brief_tasks.run_brief_step3_aggregate"
    assert run_brief_step4_finalize.name == "app.tasks.brief_tasks.run_brief_step4_finalize"


def test_brief_step2_has_correct_soft_time_limit():
    """Step 2 (Playwright crawl) must have soft_time_limit=900 for long page loads."""
    from app.tasks.brief_tasks import run_brief_step2_crawl
    assert run_brief_step2_crawl.soft_time_limit == 900
