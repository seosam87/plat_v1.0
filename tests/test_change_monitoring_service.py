"""Tests for change detection and Telegram formatters."""
from app.services.change_monitoring_service import detect_changes
from app.services.telegram_service import (
    format_change_alert,
    format_weekly_digest,
)


def _snap(**overrides):
    base = {
        "title": "Page Title",
        "h1": "Heading",
        "meta_description": "Description",
        "http_status": 200,
        "content_preview": "Some content here",
        "canonical_url": "https://e.com/page/",
        "has_schema": True,
        "has_toc": True,
        "has_noindex": False,
    }
    base.update(overrides)
    return base


# ---- Detection tests ----


def test_detect_new_page():
    result = detect_changes("https://e.com/new/", None, _snap(), 200)
    assert len(result) == 1
    assert result[0]["change_type"] == "new_page"


def test_detect_404():
    old = _snap(http_status=200)
    new = _snap(http_status=404)
    result = detect_changes("url", old, new, 404)
    types = [r["change_type"] for r in result]
    assert "page_404" in types


def test_detect_noindex_added():
    old = _snap(has_noindex=False)
    new = _snap(has_noindex=True)
    result = detect_changes("url", old, new, 200)
    types = [r["change_type"] for r in result]
    assert "noindex_added" in types


def test_detect_schema_removed():
    old = _snap(has_schema=True)
    new = _snap(has_schema=False)
    result = detect_changes("url", old, new, 200)
    types = [r["change_type"] for r in result]
    assert "schema_removed" in types


def test_detect_title_changed():
    old = _snap(title="Old Title")
    new = _snap(title="New Title")
    result = detect_changes("url", old, new, 200)
    types = [r["change_type"] for r in result]
    assert "title_changed" in types
    detail = next(r for r in result if r["change_type"] == "title_changed")
    assert "Old Title" in detail["details"]
    assert "New Title" in detail["details"]


def test_detect_canonical_changed():
    old = _snap(canonical_url="https://e.com/old/")
    new = _snap(canonical_url="https://e.com/new/")
    result = detect_changes("url", old, new, 200)
    types = [r["change_type"] for r in result]
    assert "canonical_changed" in types


def test_detect_no_changes():
    snap = _snap()
    result = detect_changes("url", snap, snap, 200)
    assert result == []


def test_detect_multiple_changes():
    old = _snap(title="A", h1="B")
    new = _snap(title="X", h1="Y")
    result = detect_changes("url", old, new, 200)
    types = [r["change_type"] for r in result]
    assert "title_changed" in types
    assert "h1_changed" in types
    assert len(result) == 2


# ---- Formatter tests ----


def test_format_change_alert():
    msg = format_change_alert("MySite", "page_404", "https://e.com/page/", "HTTP 200 → 404")
    assert "MySite" in msg
    assert "https://e.com/page/" in msg
    assert "404" in msg


def test_format_weekly_digest_structure():
    changes = [
        {"change_type": "page_404", "severity": "error", "page_url": "https://e.com/a/", "details": ""},
        {"change_type": "title_changed", "severity": "warning", "page_url": "https://e.com/b/", "details": ""},
        {"change_type": "new_page", "severity": "info", "page_url": "https://e.com/c/", "details": ""},
    ]
    msg = format_weekly_digest("MySite", changes, "2026-03-26 – 2026-04-02")
    assert "Еженедельный дайджест" in msg
    assert "MySite" in msg
    assert "Критичные (1)" in msg
    assert "Предупреждения (1)" in msg
    assert "Всего изменений: 3" in msg


def test_format_weekly_digest_empty():
    msg = format_weekly_digest("MySite", [], "2026-03-26 – 2026-04-02")
    assert "Нет изменений" in msg
