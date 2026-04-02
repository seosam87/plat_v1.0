"""Tests for digest service: cron computation and formatters."""
from app.services.digest_service import compute_digest_cron
from app.services.telegram_service import format_weekly_digest


def test_cron_expression_monday_9am():
    assert compute_digest_cron(1, 9, 0) == "0 9 * * 1"


def test_cron_expression_friday_14_30():
    assert compute_digest_cron(5, 14, 30) == "30 14 * * 5"


def test_cron_expression_sunday():
    # Sunday = 7 in user input, 0 in cron
    assert compute_digest_cron(7, 10, 0) == "0 10 * * 0"


def test_cron_expression_wednesday():
    assert compute_digest_cron(3, 8, 15) == "15 8 * * 3"


def test_format_digest_with_changes():
    changes = [
        {"change_type": "page_404", "severity": "error", "page_url": "https://e.com/a/", "details": ""},
        {"change_type": "title_changed", "severity": "warning", "page_url": "https://e.com/b/", "details": ""},
    ]
    msg = format_weekly_digest("TestSite", changes, "2026-03-26 – 2026-04-02")
    assert "Еженедельный дайджест: TestSite" in msg
    assert "Критичные (1)" in msg
    assert "Предупреждения (1)" in msg
    assert "Всего изменений: 2" in msg


def test_format_digest_no_changes():
    msg = format_weekly_digest("TestSite", [], "2026-03-26 – 2026-04-02")
    assert "Нет изменений" in msg
