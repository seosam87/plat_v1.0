"""Session-scoped Playwright fixtures for scenario_runner.

Raw ``playwright.async_api`` usage — NOT pytest-playwright (which conflicts
with custom pytest collectors; see RESEARCH.md Pitfall 1).

Pattern 2 from 19.1-RESEARCH.md:
- One Chromium per pytest session (amortize launch cost)
- Per-scenario ``BrowserContext`` constructed from cached ``storage_state.json``
- Programmatic login once against the seeded ``smoke_admin`` user
- Tracing started per-scenario (snapshots + screenshots + sources) so failures
  capture a full replayable trace.zip
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

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


@pytest_asyncio.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest_asyncio.fixture(scope="session")
async def scenario_playwright():
    _require_playwright()
    async with async_playwright() as pw:
        yield pw


@pytest_asyncio.fixture(scope="session")
async def scenario_browser(scenario_playwright):
    browser = await scenario_playwright.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        await browser.close()


@pytest_asyncio.fixture(scope="session")
async def storage_state(scenario_browser, base_url) -> str:
    """Programmatic login → cached storage_state.json.

    The file is written under ``artifacts/.auth/`` (gitignored). If it already
    exists from a previous run in the same workspace, it is reused; CI wipes
    ``artifacts/`` between runs so staleness is not an issue.
    """
    if STORAGE_STATE.exists():
        return str(STORAGE_STATE)

    ctx = await scenario_browser.new_context()
    page = await ctx.new_page()
    await page.goto(f"{base_url}/ui/login")
    await page.get_by_label("Username").fill("smoke_admin")
    await page.get_by_label("Password").fill("smoke-password")
    await page.get_by_role("button", name="Log in").click()
    await page.wait_for_url(f"{base_url}/ui/dashboard")
    STORAGE_STATE.parent.mkdir(parents=True, exist_ok=True)
    await ctx.storage_state(path=str(STORAGE_STATE))
    await ctx.close()
    return str(STORAGE_STATE)


@pytest_asyncio.fixture
async def scenario_page(scenario_browser, storage_state):
    """Per-scenario fresh BrowserContext with auth + tracing armed.

    Tracing is STARTED here but STOPPED by the caller (see collector.py) so
    the failure hook can write trace.zip on the same page/context/loop that
    ran the scenario.
    """
    ctx = await scenario_browser.new_context(storage_state=storage_state)
    await ctx.tracing.start(snapshots=True, screenshots=True, sources=True)
    page = await ctx.new_page()
    try:
        yield page
    finally:
        await ctx.close()
