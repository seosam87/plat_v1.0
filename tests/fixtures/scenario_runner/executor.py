"""Async executor for scenario_runner.

Dispatches parsed ``Scenario.steps`` to Playwright page operations. Reserved
19.2 tour step types (say/highlight/wait_for_click) are skipped with a
WARNING so a single YAML file runs under both 19.1 (tests) and 19.2 (tours).

P0 step types wired here (plan 19.1-03):
    open | click | fill | wait_for | expect_text | expect_status
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from .locators import resolve_locator

if TYPE_CHECKING:
    from .schema import Scenario


RESERVED_OPS: set[str] = {"say", "highlight", "wait_for_click"}


def _install_response_tracker(page: Any) -> dict[str, Any]:
    """Subscribe to ``page.on("response", ...)`` and return a mutable holder.

    Only main-frame responses are tracked; the latest one is stored under
    the ``last`` key. Used by ``expect_status`` to assert the most recent
    top-level navigation response.
    """
    holder: dict[str, Any] = {"last": None}

    def _on_response(response: Any) -> None:
        try:
            if response.frame == page.main_frame:
                holder["last"] = response
        except Exception:  # pragma: no cover - defensive
            holder["last"] = response

    page.on("response", _on_response)
    return holder


async def run_scenario(page: Any, scenario: "Scenario") -> None:
    """Execute a parsed Scenario against a Playwright ``page``.

    ``page`` may be ``None`` for scenarios consisting solely of reserved
    step types (useful for collector unit tests that do not launch a browser).
    """
    response_holder: dict[str, Any] | None = None
    if page is not None:
        response_holder = _install_response_tracker(page)

    for idx, step in enumerate(scenario.steps):
        op = step.op
        if op in RESERVED_OPS:
            logger.warning(
                f"scenario={scenario.name} step[{idx}] op='{op}' "
                f"reserved for 19.2 tour player — skipping"
            )
            continue

        if page is None:
            raise RuntimeError(
                f"scenario={scenario.name} step[{idx}] op='{op}' requires a "
                f"Playwright page but none was provided"
            )

        if op == "open":
            # Prepend base_url for relative paths so scenarios can use
            # "/ui/..." without hard-coding the host (base_url stashed on
            # page by the scenario_page fixture).
            url = step.url
            if url.startswith("/"):
                base = getattr(page, "_scenario_base_url", "")
                url = f"{base}{url}"
            await page.goto(url)
        elif op == "click":
            await resolve_locator(page, step.target).click()
        elif op == "fill":
            await resolve_locator(page, step.target).fill(step.value)
        elif op == "wait_for":
            # Lazy import — only scenarios that actually run P0 Playwright
            # steps need playwright installed (test_executor uses only the
            # reserved path and must work without a browser).
            from playwright.async_api import expect  # type: ignore

            locator = resolve_locator(page, step.target)
            state = step.state
            if state == "visible":
                await expect(locator).to_be_visible(timeout=step.timeout)
            elif state == "hidden":
                await expect(locator).to_be_hidden(timeout=step.timeout)
            elif state == "attached":
                await expect(locator).to_be_attached(timeout=step.timeout)
            else:  # pragma: no cover - schema restricts values
                raise ValueError(f"unknown wait_for state: {state}")
        elif op == "expect_text":
            from playwright.async_api import expect  # type: ignore

            await expect(resolve_locator(page, step.target)).to_contain_text(
                step.contains
            )
        elif op == "expect_status":
            assert response_holder is not None
            last = response_holder["last"]
            if last is None:
                raise AssertionError(
                    f"expect_status: no main-frame response seen yet "
                    f"(scenario={scenario.name} step[{idx}])"
                )
            if last.status != step.code:
                raise AssertionError(
                    f"expect_status: expected {step.code}, got {last.status} "
                    f"(scenario={scenario.name} step[{idx}])"
                )
        else:  # pragma: no cover - schema discriminated union covers this
            raise NotImplementedError(f"unhandled step op='{op}'")
