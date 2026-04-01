"""Unit tests for Telegram alert service."""
from unittest.mock import patch

import httpx
import pytest
import respx

from app.services.telegram_service import (
    format_position_drop_alert,
    is_configured,
    send_message,
)


class TestTelegramService:
    def test_is_configured_true(self):
        with patch("app.services.telegram_service.settings") as mock:
            mock.TELEGRAM_BOT_TOKEN = "bot123"
            mock.TELEGRAM_CHAT_ID = "456"
            assert is_configured() is True

    def test_is_configured_false(self):
        with patch("app.services.telegram_service.settings") as mock:
            mock.TELEGRAM_BOT_TOKEN = ""
            mock.TELEGRAM_CHAT_ID = ""
            assert is_configured() is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        with patch("app.services.telegram_service.settings") as mock:
            mock.TELEGRAM_BOT_TOKEN = "bot123"
            mock.TELEGRAM_CHAT_ID = "456"
            respx.post("https://api.telegram.org/botbot123/sendMessage").mock(
                return_value=httpx.Response(200, json={"ok": True})
            )
            result = await send_message("Test alert")
            assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        with patch("app.services.telegram_service.settings") as mock:
            mock.TELEGRAM_BOT_TOKEN = "bot123"
            mock.TELEGRAM_CHAT_ID = "456"
            respx.post("https://api.telegram.org/botbot123/sendMessage").mock(
                return_value=httpx.Response(403)
            )
            result = await send_message("Fail")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_not_configured(self):
        with patch("app.services.telegram_service.settings") as mock:
            mock.TELEGRAM_BOT_TOKEN = ""
            mock.TELEGRAM_CHAT_ID = ""
            result = await send_message("Skip")
            assert result is False

    def test_format_alert(self):
        msg = format_position_drop_alert("MySite", "seo tools", 3, 10, "https://a.com")
        assert "seo tools" in msg
        assert "3" in msg
        assert "10" in msg
        assert "+7" in msg
        assert "MySite" in msg
