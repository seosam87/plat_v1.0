"""Locator auto-detection for scenario_runner.

Resolves a single YAML ``target:`` string into a Playwright Locator by
prefix dispatch. Supported prefixes:

- ``role=button[name="Submit"]`` / ``role=link``  → ``page.get_by_role``
- ``text=Some text``                              → ``page.get_by_text``
- ``label=Username``                              → ``page.get_by_label``
- ``testid=submit-btn``                           → ``page.get_by_test_id``
- Anything else                                   → ``page.locator`` (CSS)
"""
from __future__ import annotations

import re
from typing import Any

_ROLE_RE = re.compile(r'role=(\w+)(?:\[name=["\'](.+?)["\']\])?')


def resolve_locator(page: Any, target: str) -> Any:
    """Return a Playwright Locator for ``target`` against ``page``."""
    if target.startswith("role="):
        m = _ROLE_RE.match(target)
        if m is None:
            # Fall through to raw CSS if role= pattern malformed.
            return page.locator(target)
        kw = {"name": m.group(2)} if m.group(2) else {}
        return page.get_by_role(m.group(1), **kw)
    if target.startswith("text="):
        return page.get_by_text(target[len("text="):])
    if target.startswith("label="):
        return page.get_by_label(target[len("label="):])
    if target.startswith("testid="):
        return page.get_by_test_id(target[len("testid="):])
    return page.locator(target)
