"""Proxy health checker supporting HTTP and SOCKS5 proxies.

Uses httpx with optional socksio for SOCKS5 support.
"""
from __future__ import annotations

import time

import httpx
from loguru import logger

HEALTH_CHECK_URL = "https://ya.ru/robots.txt"


def check_proxy_sync(proxy_url: str) -> tuple[str, int | None]:
    """Check whether a proxy is alive.

    Args:
        proxy_url: Full proxy URL, e.g. ``http://host:port`` or
            ``socks5://host:port``.

    Returns:
        Tuple of ``(status, response_time_ms)`` where status is
        ``"active"`` or ``"dead"``.  ``response_time_ms`` is None when dead.
    """
    start = time.monotonic()
    try:
        with httpx.Client(proxy=proxy_url, timeout=10) as client:
            resp = client.get(HEALTH_CHECK_URL)
            resp.raise_for_status()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ("active", elapsed_ms)
    except ImportError:
        logger.warning(
            "SOCKS5 proxy health check failed: install httpx[socks]"
        )
        return ("dead", None)
    except Exception as exc:
        logger.warning("Proxy health check failed for {}: {}", proxy_url, exc)
        return ("dead", None)
