"""Tests for relevant_url_service.find_relevant_url and _normalize_domain."""
import pytest
from app.services.relevant_url_service import find_relevant_url, _normalize_domain


def test_target_domain_found():
    results = [
        {"domain": "competitor1.ru", "url": "https://competitor1.ru/page", "position": 1, "title": "", "snippet": ""},
        {"domain": "competitor2.ru", "url": "https://competitor2.ru/page", "position": 2, "title": "", "snippet": ""},
        {"domain": "example.ru", "url": "https://example.ru/target-page", "position": 3, "title": "", "snippet": ""},
        {"domain": "competitor3.ru", "url": "https://competitor3.ru/page", "position": 4, "title": "", "snippet": ""},
    ]
    r = find_relevant_url("test query", results, "example.ru")
    assert r["url"] == "https://example.ru/target-page"
    assert r["position"] == 3
    assert r["top_competitors"] == ["competitor1.ru", "competitor2.ru", "competitor3.ru"]


def test_target_domain_not_found():
    results = [
        {"domain": "other1.ru", "url": "https://other1.ru/page", "position": 1, "title": "", "snippet": ""},
        {"domain": "other2.ru", "url": "https://other2.ru/page", "position": 2, "title": "", "snippet": ""},
    ]
    r = find_relevant_url("test query", results, "example.ru")
    assert r["url"] is None
    assert r["position"] is None
    assert len(r["top_competitors"]) == 2


def test_www_normalization():
    results = [
        {"domain": "www.example.ru", "url": "https://www.example.ru/page", "position": 1, "title": "", "snippet": ""},
    ]
    r = find_relevant_url("test", results, "example.ru")
    assert r["url"] == "https://www.example.ru/page"
    assert r["position"] == 1


def test_subdomain_match():
    results = [
        {"domain": "blog.example.ru", "url": "https://blog.example.ru/post", "position": 5, "title": "", "snippet": ""},
    ]
    r = find_relevant_url("test", results, "example.ru")
    assert r["url"] == "https://blog.example.ru/post"
    assert r["position"] == 5


def test_empty_serp():
    r = find_relevant_url("test", [], "example.ru")
    assert r["url"] is None
    assert r["position"] is None
    assert r["top_competitors"] == []


def test_top_3_competitors_limit():
    results = [{"domain": f"comp{i}.ru", "url": f"https://comp{i}.ru", "position": i, "title": "", "snippet": ""} for i in range(1, 11)]
    r = find_relevant_url("test", results, "example.ru")
    assert len(r["top_competitors"]) == 3


def test_normalize_domain():
    assert _normalize_domain("www.Example.RU") == "example.ru"
    assert _normalize_domain("https://www.example.ru/path") == "example.ru"
    assert _normalize_domain("EXAMPLE.RU") == "example.ru"


def test_first_match_wins():
    """When target domain appears multiple times, first (highest) position wins."""
    results = [
        {"domain": "example.ru", "url": "https://example.ru/page1", "position": 2, "title": "", "snippet": ""},
        {"domain": "example.ru", "url": "https://example.ru/page2", "position": 7, "title": "", "snippet": ""},
    ]
    r = find_relevant_url("test", results, "example.ru")
    assert r["url"] == "https://example.ru/page1"
    assert r["position"] == 2


def test_returns_phrase_in_result():
    r = find_relevant_url("my phrase", [], "example.ru")
    assert r["phrase"] == "my phrase"
