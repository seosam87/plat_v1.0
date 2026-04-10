"""Telegram authentication helpers.

Provides two validation flows:
1. WebApp initData (HMAC-SHA256 with key derived from "WebAppData")
2. Login Widget callback data (HMAC-SHA256 with key = SHA256(bot_token))

Both use stdlib only — no additional packages required.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse


def validate_telegram_webapp_initdata(
    init_data: str, bot_token: str, max_age: int = 3600
) -> dict | None:
    """Validate Telegram WebApp initData string.

    Returns parsed user dict or None if invalid/expired.
    Uses HMAC-SHA256(bot_token, key="WebAppData") per Telegram docs.

    Args:
        init_data: Raw initData string from Telegram.WebApp.initData
        bot_token: Telegram bot token from settings
        max_age: Maximum age in seconds (default 1 hour)

    Returns:
        Parsed user dict from initData["user"] field, or None on failure.
    """
    if not init_data or not bot_token:
        return None

    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = int(params.get("auth_date", 0))
    if time.time() - auth_date > max_age:
        return None

    user_json = params.get("user", "{}")
    try:
        return json.loads(user_json)
    except (json.JSONDecodeError, ValueError):
        return None


def validate_telegram_login_widget(data: dict, bot_token: str) -> bool:
    """Validate Telegram Login Widget callback data.

    Uses SHA256(bot_token) as HMAC key — different from WebApp flow.

    Args:
        data: Dict of query params from Telegram Login Widget redirect
        bot_token: Telegram bot token from settings

    Returns:
        True if signature is valid, False otherwise.
    """
    if not data or not bot_token:
        return False

    check_data = dict(data)
    received_hash = check_data.pop("hash", None)
    if not received_hash:
        return False

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(check_data.items())
    )
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_hash, received_hash)
