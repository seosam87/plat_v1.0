"""Phase 15.1 — UI smoke crawler.

Parametrized test over every discovered UI GET route in ``app.routes``.
Plus an explicit regression test for the ``data.items`` dict-collision bug
class (Jinja attribute/key collision that today hit the opportunities page).

Runs in the default ``pytest`` invocation — no special marker required.
"""
from __future__ import annotations

import pytest

from app.main import app
from tests._smoke_helpers import (
    JINJA_ERROR_MARKERS,  # noqa: F401  (re-exported for downstream inspection)
    SMOKE_SKIP,  # noqa: F401
    UnknownParamError,
    assert_no_error_markers,
    assert_structural_html,
    build_param_map,
    discover_routes,
    is_partial,
    resolve_path,
)
from tests.fixtures.smoke_seed import SMOKE_IDS

# Route discovery is a pure function — safe to run at collection time
# without a live DB.
ROUTES = discover_routes(app)
PARAM_MAP = build_param_map(SMOKE_IDS)

# Scope the fixture event loop to the session so the session-scoped
# smoke_seed / smoke_client fixtures share a single loop across the
# parametrized cases (pytest-asyncio 0.23 workaround per Plan 01 summary).
pytestmark = pytest.mark.asyncio(scope="session")

_ACCEPTABLE_STATUS = {200, 301, 302, 303, 307, 308}


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r.path)
async def test_ui_route_renders(route, smoke_client):
    """Every discovered UI GET route must render without Jinja errors.

    - Status must be 2xx or 3xx
    - HTML bodies must not contain any JINJA_ERROR_MARKERS
    - HTML bodies must pass a structural check (relaxed for partials)
    - Non-HTML responses (file downloads) skip body checks
    """
    try:
        url = resolve_path(route.path, PARAM_MAP)
    except UnknownParamError as e:
        pytest.fail(str(e))

    resp = await smoke_client.get(url, follow_redirects=False)
    assert resp.status_code in _ACCEPTABLE_STATUS, (
        f"{route.path} -> {resp.status_code}\n{resp.text[:500]}"
    )

    if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
        assert_no_error_markers(resp.text, route.path)
        assert_structural_html(resp.text, route.path, is_partial=is_partial(route.path))


async def test_data_items_dict_collision_regression(smoke_client):
    """Regression: today's production bug.

    ``{% for item in data.items %}`` resolved to ``dict.items`` method instead
    of a dict key, causing a 500 with ``builtin_function_or_method is not
    iterable``. The opportunities page must render without that marker
    appearing anywhere in the body.
    """
    url = f"/analytics/{SMOKE_IDS['site_id']}/opportunities"
    resp = await smoke_client.get(url, follow_redirects=True)
    assert resp.status_code == 200, (
        f"opportunities page returned {resp.status_code}\n{resp.text[:500]}"
    )
    assert "builtin_function_or_method" not in resp.text, (
        "data.items dict-collision regression: body contains "
        "'builtin_function_or_method' — a dict method was rendered as data"
    )
    assert "TemplateSyntaxError" not in resp.text
    assert "UndefinedError" not in resp.text
