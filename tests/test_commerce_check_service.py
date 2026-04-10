"""Tests for commerce_check_service.analyze_commercialization."""
import pytest
from app.services.commerce_check_service import analyze_commercialization


def test_all_commercial_results():
    results = [
        {"domain": "ozon.ru", "title": "Кроссовки", "url": "https://ozon.ru/shoes", "snippet": "", "position": i}
        for i in range(1, 11)
    ]
    r = analyze_commercialization("купить кроссовки", results)
    assert r["commercialization"] == 100
    assert r["intent"] == "commercial"
    assert r["phrase"] == "купить кроссовки"


def test_all_informational_results():
    results = [
        {"domain": "ru.wikipedia.org", "title": "Кроссовки", "url": "https://ru.wikipedia.org/wiki/Shoes", "snippet": "", "position": i}
        for i in range(1, 11)
    ]
    r = analyze_commercialization("кроссовки история", results)
    assert r["commercialization"] <= 20
    assert r["intent"] == "informational"


def test_mixed_results():
    results = [
        {"domain": "ozon.ru", "title": "Купить", "url": "https://ozon.ru", "snippet": "", "position": 1},
        {"domain": "ozon.ru", "title": "Магазин", "url": "https://ozon.ru", "snippet": "", "position": 2},
        {"domain": "ozon.ru", "title": "Цена", "url": "https://ozon.ru", "snippet": "", "position": 3},
        {"domain": "ozon.ru", "title": "Shop", "url": "https://ozon.ru", "snippet": "", "position": 4},
        {"domain": "forum.example.com", "title": "Обзор", "url": "https://forum.example.com", "snippet": "", "position": 5},
        {"domain": "blog.example.com", "title": "Отзыв", "url": "https://blog.example.com", "snippet": "", "position": 6},
        {"domain": "review.example.com", "title": "Тест", "url": "https://review.example.com", "snippet": "", "position": 7},
        {"domain": "info.example.com", "title": "Факты", "url": "https://info.example.com", "snippet": "", "position": 8},
        {"domain": "news.example.com", "title": "Новости", "url": "https://news.example.com", "snippet": "", "position": 9},
        {"domain": "edu.example.com", "title": "Учебник", "url": "https://edu.example.com", "snippet": "", "position": 10},
    ]
    r = analyze_commercialization("кроссовки", results)
    assert 20 <= r["commercialization"] <= 60
    assert r["intent"] == "mixed"


def test_empty_serp():
    r = analyze_commercialization("test", [])
    assert r["commercialization"] == 0
    assert r["intent"] == "informational"


def test_geo_dependency_detected():
    results = [
        {"domain": "maps.yandex.ru", "title": "Магазин рядом", "url": "https://maps.yandex.ru", "snippet": "ближайший магазин", "position": 1}
    ]
    r = analyze_commercialization("магазин рядом", results)
    assert r["geo_dependent"] is True
