"""Unit tests for wp_service sync functions and schedule_service internals."""
import base64
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.services.wp_service import (
    _basic_auth_header,
    get_posts_sync,
    get_pages_sync,
    create_post_sync,
)
from app.services.schedule_service import (
    _cron_expression,
    _redbeat_key,
    _schedule_to_crontab,
)
from app.models.schedule import ScheduleType


# ---------------------------------------------------------------------------
# _basic_auth_header
# ---------------------------------------------------------------------------


class TestBasicAuthHeader:
    def test_produces_valid_base64(self):
        header = _basic_auth_header("admin", "secret")
        assert header.startswith("Basic ")
        decoded = base64.b64decode(header.split(" ")[1]).decode()
        assert decoded == "admin:secret"

    def test_special_characters(self):
        header = _basic_auth_header("user@site", "p@ss:word")
        decoded = base64.b64decode(header.split(" ")[1]).decode()
        assert decoded == "user@site:p@ss:word"


# ---------------------------------------------------------------------------
# wp_service sync functions (mocked httpx + site object)
# ---------------------------------------------------------------------------


def _fake_site(url="https://example.com", wp_username="admin"):
    site = MagicMock()
    site.id = uuid.uuid4()
    site.url = url
    site.wp_username = wp_username
    site.encrypted_app_password = "encrypted"
    return site


@pytest.fixture(autouse=True)
def mock_decrypt():
    with patch("app.services.wp_service.get_decrypted_password", return_value="secret"):
        yield


class TestGetPostsSync:
    @respx.mock
    def test_returns_posts(self):
        site = _fake_site()
        posts = [{"id": 1, "title": {"rendered": "Hello"}}]
        respx.get("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(200, json=posts)
        )
        result = get_posts_sync(site)
        assert result == posts

    @respx.mock
    def test_returns_empty_on_error(self):
        site = _fake_site()
        respx.get("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(500)
        )
        result = get_posts_sync(site)
        assert result == []

    @respx.mock
    def test_returns_empty_on_network_error(self):
        site = _fake_site()
        respx.get("https://example.com/wp-json/wp/v2/posts").mock(
            side_effect=httpx.ConnectError("refused")
        )
        result = get_posts_sync(site)
        assert result == []


class TestGetPagesSync:
    @respx.mock
    def test_returns_pages(self):
        site = _fake_site()
        pages_data = [{"id": 10, "title": {"rendered": "About"}}]
        respx.get("https://example.com/wp-json/wp/v2/pages").mock(
            return_value=httpx.Response(200, json=pages_data)
        )
        result = get_pages_sync(site)
        assert result == pages_data

    @respx.mock
    def test_returns_empty_on_error(self):
        site = _fake_site()
        respx.get("https://example.com/wp-json/wp/v2/pages").mock(
            return_value=httpx.Response(403)
        )
        result = get_pages_sync(site)
        assert result == []


class TestCreatePostSync:
    @respx.mock
    def test_creates_post(self):
        site = _fake_site()
        created = {"id": 42, "title": {"rendered": "New Post"}}
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = create_post_sync(site, title="New Post", content="Body")
        assert result == created

    @respx.mock
    def test_returns_none_on_error(self):
        site = _fake_site()
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(500)
        )
        result = create_post_sync(site, title="Fail", content="Body")
        assert result is None


# ---------------------------------------------------------------------------
# schedule_service internal helpers
# ---------------------------------------------------------------------------


class TestScheduleHelpers:
    def test_redbeat_key(self):
        sid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        assert _redbeat_key(sid) == "crawl-schedule:12345678-1234-1234-1234-123456789abc"

    def test_cron_expression_daily(self):
        assert _cron_expression(ScheduleType.daily) == "0 3 * * *"

    def test_cron_expression_weekly(self):
        assert _cron_expression(ScheduleType.weekly) == "0 3 * * 1"

    def test_cron_expression_manual(self):
        assert _cron_expression(ScheduleType.manual) is None

    def test_schedule_to_crontab_daily(self):
        ct = _schedule_to_crontab(ScheduleType.daily)
        assert ct is not None

    def test_schedule_to_crontab_manual_returns_none(self):
        assert _schedule_to_crontab(ScheduleType.manual) is None


class TestRestoreSchedulesFromDb:
    @patch("app.services.schedule_service.sync_schedule_to_redbeat")
    @patch("app.database.get_sync_db")
    def test_restore_calls_sync_for_active_schedules(self, mock_db_ctx, mock_sync):
        from app.services.schedule_service import restore_schedules_from_db

        # Mock a DB session returning one active schedule
        mock_schedule = SimpleNamespace(
            site_id=uuid.uuid4(),
            schedule_type=ScheduleType.daily,
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_schedule]
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        restore_schedules_from_db()

        mock_sync.assert_called_once_with(
            mock_schedule.site_id, ScheduleType.daily, True
        )

    @patch("app.services.schedule_service.sync_schedule_to_redbeat")
    @patch("app.database.get_sync_db")
    def test_restore_handles_empty_db(self, mock_db_ctx, mock_sync):
        from app.services.schedule_service import restore_schedules_from_db

        mock_session = MagicMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        restore_schedules_from_db()

        mock_sync.assert_not_called()
