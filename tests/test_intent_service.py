"""Tests for intent detection from SERP results."""
from app.services.intent_service import detect_intent_from_serp


def test_detect_commercial_dominant():
    results = [
        {"domain": "shop1.ru", "url": "https://shop1.ru/product/", "position": i}
        for i in range(1, 9)
    ] + [
        {"domain": "habr.com", "url": "https://habr.com/blog/1", "position": 9},
        {"domain": "shop2.ru", "url": "https://shop2.ru/buy/", "position": 10},
    ]
    r = detect_intent_from_serp(results)
    assert r["intent"] == "commercial"
    assert r["commercial_count"] >= 7


def test_detect_informational_dominant():
    results = [
        {"domain": "habr.com", "url": "https://habr.com/blog/1", "position": 1},
        {"domain": "vc.ru", "url": "https://vc.ru/article/1", "position": 2},
        {"domain": "wiki.org", "url": "https://wikipedia.org/wiki/1", "position": 3},
        {"domain": "site.ru", "url": "https://site.ru/blog/post", "position": 4},
        {"domain": "site2.ru", "url": "https://site2.ru/article/1", "position": 5},
        {"domain": "site3.ru", "url": "https://site3.ru/blog/2", "position": 6},
        {"domain": "dzen.ru", "url": "https://dzen.ru/article/1", "position": 7},
        {"domain": "site4.ru", "url": "https://site4.ru/news/1", "position": 8},
        {"domain": "shop.ru", "url": "https://shop.ru/", "position": 9},
        {"domain": "shop2.ru", "url": "https://shop2.ru/", "position": 10},
    ]
    r = detect_intent_from_serp(results)
    assert r["intent"] == "informational"


def test_detect_mixed():
    results = [
        {"domain": "shop.ru", "url": "https://shop.ru/", "position": i}
        for i in range(1, 6)
    ] + [
        {"domain": f"blog{i}.ru", "url": f"https://blog{i}.ru/article/", "position": i + 5}
        for i in range(1, 6)
    ]
    r = detect_intent_from_serp(results)
    assert r["intent"] == "mixed"


def test_confidence_high():
    results = [
        {"domain": f"shop{i}.ru", "url": f"https://shop{i}.ru/", "position": i}
        for i in range(1, 11)
    ]
    r = detect_intent_from_serp(results)
    assert r["confidence"] >= 0.9


def test_confidence_low():
    results = [
        {"domain": "shop.ru", "url": "https://shop.ru/", "position": 1},
        {"domain": "blog.ru", "url": "https://blog.ru/article/", "position": 2},
    ]
    r = detect_intent_from_serp(results)
    assert r["confidence"] <= 0.6


def test_empty_results():
    r = detect_intent_from_serp([])
    assert r["intent"] == "unknown"
    assert r["confidence"] == 0.0
