"""Tests for traffic analysis: bot detection, anomaly detection, log parsing."""
from app.services.traffic_analysis_service import (
    analyze_traffic_sources,
    classify_visit,
    detect_anomalies,
    detect_injection_patterns,
    parse_access_log,
)

_BOT_PATTERNS = [
    {"pattern_type": "ua", "pattern_value": "Googlebot", "is_active": True},
    {"pattern_type": "ua", "pattern_value": "YandexBot", "is_active": True},
]


def test_classify_bot_by_ua():
    r = classify_visit("Mozilla/5.0 (compatible; Googlebot/2.1)", "", "", _BOT_PATTERNS)
    assert r["is_bot"] is True
    assert "Googlebot" in r["bot_reason"]


def test_classify_human():
    r = classify_visit("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "1.2.3.4", "", _BOT_PATTERNS)
    assert r["is_bot"] is False


def test_classify_empty_ua():
    r = classify_visit("", "1.2.3.4", "", _BOT_PATTERNS)
    assert r["is_bot"] is True
    assert "Empty" in r["bot_reason"]


def test_classify_generic_bot_ua():
    r = classify_visit("python-requests/2.28.0", "", "", _BOT_PATTERNS)
    assert r["is_bot"] is True


def test_detect_anomalies_spike():
    data = [{"date": f"2026-03-{i:02d}", "visits": 100} for i in range(1, 28)]
    data[14]["visits"] = 1000  # spike on day 15
    r = detect_anomalies(data)
    assert r["anomaly_detected"] is True
    assert len(r["anomaly_days"]) >= 1


def test_detect_anomalies_normal():
    data = [{"date": f"2026-03-{i:02d}", "visits": 100 + i} for i in range(1, 28)]
    r = detect_anomalies(data)
    assert r["anomaly_detected"] is False


def test_analyze_traffic_sources():
    visits = [
        {"source": "organic", "page_url": "/a/", "referer": ""},
        {"source": "organic", "page_url": "/b/", "referer": ""},
        {"source": "bot_suspected", "page_url": "/a/", "referer": ""},
    ]
    r = analyze_traffic_sources(visits)
    assert r["organic"] == 2
    assert r["bot"] == 1


def test_parse_access_log():
    line = '192.168.1.1 - - [01/Apr/2026:10:00:00 +0000] "GET /page/ HTTP/1.1" 200 1234 "https://google.com/" "Mozilla/5.0"'
    results = parse_access_log(line)
    assert len(results) == 1
    assert results[0]["ip_address"] == "192.168.1.1"
    assert results[0]["page_url"] == "/page/"
    assert results[0]["user_agent"] == "Mozilla/5.0"


def test_parse_access_log_empty():
    assert parse_access_log("") == []


def test_detect_injection_mass_referer():
    visits = [
        {"referer": "https://spam.ru/", "ip_address": f"1.2.3.{i}", "page_url": "/"}
        for i in range(60)
    ]
    patterns = detect_injection_patterns(visits)
    assert len(patterns) >= 1
    assert "реферальный" in patterns[0]["pattern"].lower()
