"""Tests for brief service: heading structure, SEO fields, text formatting."""
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
