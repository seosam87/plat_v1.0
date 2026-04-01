import uuid
from datetime import date

from app.models.metrika import MetrikaTrafficDaily, MetrikaTrafficPage, MetrikaEvent
from app.models.site import Site


def test_metrika_traffic_daily_fields():
    row = MetrikaTrafficDaily(
        site_id=uuid.uuid4(),
        traffic_date=date(2026, 3, 1),
        visits=100,
        users=80,
    )
    assert row.visits == 100
    assert row.users == 80
    assert row.traffic_date == date(2026, 3, 1)


def test_metrika_traffic_page_fields():
    row = MetrikaTrafficPage(
        site_id=uuid.uuid4(),
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        page_url="https://example.com/page-1/",
        visits=50,
    )
    assert row.page_url == "https://example.com/page-1/"
    assert row.visits == 50


def test_metrika_event_fields():
    ev = MetrikaEvent(
        site_id=uuid.uuid4(),
        event_date=date(2026, 2, 15),
        label="Schema.org added",
    )
    assert ev.label == "Schema.org added"


def test_site_has_metrika_attrs():
    assert hasattr(Site, "metrika_counter_id")
    assert hasattr(Site, "metrika_token")
