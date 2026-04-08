"""Unit tests for resolve_locator auto-detect — no browser launch."""
from __future__ import annotations

from unittest.mock import MagicMock

from tests.fixtures.scenario_runner.locators import resolve_locator


def _mock_page() -> MagicMock:
    page = MagicMock(name="page")
    page.get_by_role = MagicMock(return_value="ROLE_LOCATOR")
    page.get_by_text = MagicMock(return_value="TEXT_LOCATOR")
    page.get_by_label = MagicMock(return_value="LABEL_LOCATOR")
    page.get_by_test_id = MagicMock(return_value="TESTID_LOCATOR")
    page.locator = MagicMock(return_value="CSS_LOCATOR")
    return page


def test_role_without_name() -> None:
    page = _mock_page()
    result = resolve_locator(page, "role=button")
    assert result == "ROLE_LOCATOR"
    page.get_by_role.assert_called_once_with("button")


def test_role_with_name_double_quotes() -> None:
    page = _mock_page()
    result = resolve_locator(page, 'role=button[name="Submit"]')
    assert result == "ROLE_LOCATOR"
    page.get_by_role.assert_called_once_with("button", name="Submit")


def test_role_with_name_single_quotes() -> None:
    page = _mock_page()
    result = resolve_locator(page, "role=link[name='Log in']")
    assert result == "ROLE_LOCATOR"
    page.get_by_role.assert_called_once_with("link", name="Log in")


def test_text_prefix() -> None:
    page = _mock_page()
    result = resolve_locator(page, "text=Hello world")
    assert result == "TEXT_LOCATOR"
    page.get_by_text.assert_called_once_with("Hello world")


def test_label_prefix() -> None:
    page = _mock_page()
    result = resolve_locator(page, "label=Username")
    assert result == "LABEL_LOCATOR"
    page.get_by_label.assert_called_once_with("Username")


def test_testid_prefix() -> None:
    page = _mock_page()
    result = resolve_locator(page, "testid=submit-btn")
    assert result == "TESTID_LOCATOR"
    page.get_by_test_id.assert_called_once_with("submit-btn")


def test_css_fallback() -> None:
    page = _mock_page()
    result = resolve_locator(page, "#results-table tr.result-row")
    assert result == "CSS_LOCATOR"
    page.locator.assert_called_once_with("#results-table tr.result-row")
    page.get_by_role.assert_not_called()
