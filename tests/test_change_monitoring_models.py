import uuid

from app.models.change_monitoring import (
    AlertSeverity,
    ChangeAlert,
    ChangeAlertRule,
    ChangeType,
    DigestSchedule,
)


def test_change_type_enum():
    assert len(ChangeType) == 9
    assert ChangeType.page_404.value == "page_404"
    assert ChangeType.noindex_added.value == "noindex_added"
    assert ChangeType.schema_removed.value == "schema_removed"


def test_alert_severity_enum():
    assert AlertSeverity.error.value == "error"
    assert AlertSeverity.warning.value == "warning"
    assert AlertSeverity.info.value == "info"


def test_change_alert_rule_fields():
    rule = ChangeAlertRule(
        change_type=ChangeType.page_404,
        severity=AlertSeverity.error,
        description="Page returned 404",
    )
    assert rule.change_type == ChangeType.page_404
    assert rule.severity == AlertSeverity.error


def test_change_alert_fields():
    alert = ChangeAlert(
        site_id=uuid.uuid4(),
        crawl_job_id=uuid.uuid4(),
        change_type=ChangeType.title_changed,
        severity=AlertSeverity.warning,
        page_url="https://example.com/page/",
        details="Old Title → New Title",
    )
    assert alert.change_type == ChangeType.title_changed
    assert alert.details == "Old Title → New Title"


def test_digest_schedule_fields():
    sched = DigestSchedule(
        site_id=uuid.uuid4(),
        day_of_week=1,
        hour=9,
        minute=0,
    )
    assert sched.day_of_week == 1
    assert sched.hour == 9
