"""Playwright fixtures for scenario_runner.

Raw ``playwright.async_api`` usage — NOT pytest-playwright (which conflicts
with custom pytest collectors; see RESEARCH.md Pitfall 1).

Event-loop discipline
---------------------
pytest-asyncio creates a fresh event loop per fixture scope and the
scenario_runner's custom ``ScenarioItem.runtest`` runs its own
``asyncio.run`` — those two loops do NOT match and every Playwright
object bound to one loop explodes when touched from the other (``The
future belongs to a different loop``).

To avoid that, we manage ONE dedicated event loop ourselves inside the
``scenario_page`` fixture and stash it on the ``page`` object as
``page._scenario_loop``. The collector reuses that same loop when
running scenario steps and failure-artifact capture — guaranteeing
everything runs on a single loop.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover - skip path when playwright missing
    async_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_AVAILABLE = False

STORAGE_STATE = Path("artifacts/.auth/storage_state.json")


def _require_playwright() -> None:
    if not _PLAYWRIGHT_AVAILABLE:
        pytest.skip(
            "playwright not installed — scenario_runner browser fixtures "
            "require `pip install playwright && playwright install chromium`"
        )


@pytest.fixture
def base_url() -> str:
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture
def scenario_page(base_url: str):
    """Per-scenario BrowserContext with auth + tracing armed.

    Sync fixture that owns its event loop. Yields a Playwright ``page``
    with:
      - ``page._scenario_loop``: the dedicated asyncio loop
      - ``page._scenario_base_url``: base URL for relative navigation
    """
    _require_playwright()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    pw_cm: Any = None
    pw_obj: Any = None
    browser: Any = None
    ctx: Any = None

    async def _setup():
        nonlocal pw_cm, pw_obj, browser, ctx
        pw_cm = async_playwright()
        pw_obj = await pw_cm.__aenter__()
        browser = await pw_obj.chromium.launch(headless=True)

        # Login once per scenario (scenarios are few; the login overhead is
        # acceptable and avoids cross-loop storage_state caching headaches).
        login_ctx = await browser.new_context()
        login_page = await login_ctx.new_page()
        await login_page.goto(f"{base_url}/ui/login")
        await login_page.get_by_label("Email").fill("smoke@example.com")
        await login_page.get_by_label("Password").fill("smoke-password")
        await login_page.get_by_role("button", name="Sign In").click()
        await login_page.wait_for_url(f"{base_url}/ui/dashboard")
        STORAGE_STATE.parent.mkdir(parents=True, exist_ok=True)
        state_path = str(STORAGE_STATE)
        await login_ctx.storage_state(path=state_path)
        await login_ctx.close()

        ctx = await browser.new_context(storage_state=state_path)
        await ctx.tracing.start(snapshots=True, screenshots=True, sources=True)
        page = await ctx.new_page()
        page._scenario_loop = loop  # type: ignore[attr-defined]
        page._scenario_base_url = base_url  # type: ignore[attr-defined]
        return page

    page = loop.run_until_complete(_setup())

    try:
        yield page
    finally:
        async def _teardown():
            try:
                if ctx is not None:
                    await ctx.close()
            finally:
                if browser is not None:
                    await browser.close()
                if pw_cm is not None:
                    await pw_cm.__aexit__(None, None, None)

        try:
            loop.run_until_complete(_teardown())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
