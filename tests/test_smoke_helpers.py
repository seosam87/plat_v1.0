"""Unit tests for tests/_smoke_helpers.py — Phase 15.1 Plan 02."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from tests._smoke_helpers import (
    JINJA_ERROR_MARKERS,
    SMOKE_SKIP,
    UI_PREFIXES,
    UnknownParamError,
    assert_no_error_markers,
    assert_structural_html,
    build_param_map,
    discover_routes,
    is_partial,
    resolve_path,
)


# ---------------------------------------------------------------------------
# Fixture: stub FastAPI app with a mix of UI / API / non-GET / skipped routes.
# ---------------------------------------------------------------------------
@pytest.fixture()
def stub_app() -> FastAPI:
    app = FastAPI()

    # One route per UI prefix (11 total)
    @app.get("/ui/dashboard", response_class=HTMLResponse)
    async def ui_dashboard() -> str:  # pragma: no cover
        return "ok"

    @app.get("/analytics/{site_id}/opportunities", response_class=HTMLResponse)
    async def ui_analytics(site_id: str) -> str:  # pragma: no cover
        return "ok"

    @app.get("/audit/{site_id}", response_class=HTMLResponse)
    async def ui_audit(site_id: str) -> str:  # pragma: no cover
        return "ok"

    @app.get("/gap/{site_id}", response_class=HTMLResponse)
    async def ui_gap(site_id: str) -> str:  # pragma: no cover
        return "ok"

    @app.get("/intent/{site_id}", response_class=HTMLResponse)
    async def ui_intent(site_id: str) -> str:  # pragma: no cover
        return "ok"

    @app.get("/architecture/{site_id}", response_class=HTMLResponse)
    async def ui_arch(site_id: str) -> str:  # pragma: no cover
        return "ok"

    @app.get("/bulk/", response_class=HTMLResponse)
    async def ui_bulk() -> str:  # pragma: no cover
        return "ok"

    @app.get("/traffic-analysis/{site_id}", response_class=HTMLResponse)
    async def ui_ta(site_id: str) -> str:  # pragma: no cover
        return "ok"

    @app.get("/monitoring/", response_class=HTMLResponse)
    async def ui_mon() -> str:  # pragma: no cover
        return "ok"

    @app.get("/competitors/{site_id}", response_class=HTMLResponse)
    async def ui_comp(site_id: str) -> str:  # pragma: no cover
        return "ok"

    @app.get("/metrika/{site_id}", response_class=HTMLResponse)
    async def ui_metrika(site_id: str) -> str:  # pragma: no cover
        return "ok"

    # Routes that MUST be excluded
    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:  # pragma: no cover
        return "redirect"

    @app.get("/ui/login", response_class=HTMLResponse)
    async def ui_login() -> str:  # pragma: no cover
        return "login"

    @app.get("/ui/api/sites", response_class=JSONResponse)
    async def ui_api_sites() -> dict:  # pragma: no cover
        return {}

    @app.get("/api/keywords")
    async def api_keywords() -> dict:  # pragma: no cover
        return {}

    @app.post("/ui/keywords")
    async def post_kw() -> dict:  # pragma: no cover
        return {}

    @app.get("/healthz")
    async def healthz() -> dict:  # pragma: no cover
        return {}

    return app


# ---------------------------------------------------------------------------
# discover_routes
# ---------------------------------------------------------------------------
def test_discover_routes_returns_routespecs(stub_app: FastAPI) -> None:
    routes = discover_routes(stub_app)
    assert len(routes) >= 5
    assert all(hasattr(r, "path") and hasattr(r, "name") for r in routes)


def test_discover_routes_excludes_smoke_skip(stub_app: FastAPI) -> None:
    paths = {r.path for r in discover_routes(stub_app)}
    assert "/" not in paths
    assert "/ui/login" not in paths
    assert "/ui/api/sites" not in paths


def test_discover_routes_excludes_non_ui_and_non_get(stub_app: FastAPI) -> None:
    paths = {r.path for r in discover_routes(stub_app)}
    assert "/api/keywords" not in paths
    assert "/healthz" not in paths
    # POST-only path should not appear under GET discovery
    assert "/ui/keywords" not in paths


@pytest.mark.parametrize("prefix", UI_PREFIXES)
def test_discover_routes_covers_every_ui_prefix(
    stub_app: FastAPI, prefix: str
) -> None:
    paths = [r.path for r in discover_routes(stub_app)]
    assert any(p.startswith(prefix) for p in paths), (
        f"prefix {prefix} not represented in discovered routes"
    )


def test_discover_routes_sorted(stub_app: FastAPI) -> None:
    paths = [r.path for r in discover_routes(stub_app)]
    assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# build_param_map + resolve_path
# ---------------------------------------------------------------------------
def test_build_param_map_includes_module_string() -> None:
    pm = build_param_map({"site_id": "11111111-1111-1111-1111-111111111111"})
    assert pm["module"] == "general"
    assert pm["site_id"] == "11111111-1111-1111-1111-111111111111"


def test_resolve_path_substitutes_multiple_params() -> None:
    pm = build_param_map({"site_id": "s1", "keyword_id": "k1"})
    out = resolve_path("/sites/{site_id}/keywords/{keyword_id}", pm)
    assert out == "/sites/s1/keywords/k1"


def test_resolve_path_help_module_string() -> None:
    pm = build_param_map({})
    assert resolve_path("/ui/help/{module}", pm) == "/ui/help/general"


def test_resolve_path_unknown_param_raises_with_helpful_message() -> None:
    pm = build_param_map({"site_id": "s1"})
    with pytest.raises(UnknownParamError) as excinfo:
        resolve_path("/x/{unknown_thing}", pm)
    msg = str(excinfo.value)
    assert "unknown_thing" in msg
    assert "PARAM_MAP or SMOKE_SKIP" in msg


def test_resolve_path_supports_typed_converters() -> None:
    # FastAPI sometimes exposes paths like "{site_id:uuid}" via Starlette
    pm = build_param_map({"site_id": "s1"})
    assert resolve_path("/ui/sites/{site_id:uuid}", pm) == "/ui/sites/s1"


# ---------------------------------------------------------------------------
# assert_no_error_markers — today's bug regression
# ---------------------------------------------------------------------------
def test_assert_no_error_markers_catches_builtin_function_or_method() -> None:
    body = (
        "<html>...TypeError: 'builtin_function_or_method' object "
        "is not iterable...</html>"
    )
    with pytest.raises(AssertionError, match="builtin_function_or_method"):
        assert_no_error_markers(body, "/analytics/abc/opportunities")


def test_assert_no_error_markers_passes_clean_body() -> None:
    assert_no_error_markers("<html><title>ok</title></html>", "/x")


@pytest.mark.parametrize("marker", JINJA_ERROR_MARKERS)
def test_assert_no_error_markers_catches_every_marker(marker: str) -> None:
    with pytest.raises(AssertionError):
        assert_no_error_markers(f"prefix {marker} suffix", "/x")


# ---------------------------------------------------------------------------
# assert_structural_html
# ---------------------------------------------------------------------------
def test_assert_structural_html_full_page_passes() -> None:
    assert_structural_html(
        "<html><title>x</title><body>y</body></html>",
        "/x",
        is_partial=False,
    )


def test_assert_structural_html_full_page_missing_title_raises() -> None:
    with pytest.raises(AssertionError, match="missing <title>"):
        assert_structural_html("<div>x</div>", "/x", is_partial=False)


def test_assert_structural_html_full_page_missing_body_raises() -> None:
    with pytest.raises(AssertionError, match="missing <body>"):
        assert_structural_html(
            "<html><title>x</title></html>", "/x", is_partial=False
        )


def test_assert_structural_html_partial_empty_raises() -> None:
    with pytest.raises(AssertionError, match="empty body"):
        assert_structural_html("", "/x", is_partial=True)


def test_assert_structural_html_partial_passes() -> None:
    assert_structural_html("<div>x</div>", "/x", is_partial=True)


def test_assert_structural_html_main_tag_counts_as_body() -> None:
    assert_structural_html(
        "<html><title>x</title><main>y</main></html>",
        "/x",
        is_partial=False,
    )


# ---------------------------------------------------------------------------
# is_partial
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path,expected",
    [
        ("/ui/sites/{id}/tabs/keywords", True),
        ("/ui/sites/{id}/partials/header", True),
        ("/ui/keyword-suggest/detail/123", True),
        ("/metrika/abc/widget", True),
        ("/analytics/abc/fix-status/xyz", True),
        ("/analytics/abc/quick-wins/table", True),
        ("/ui/sites/{id}", False),
        ("/ui/dashboard", False),
        ("/analytics/abc/quick-wins", False),
    ],
)
def test_is_partial(path: str, expected: bool) -> None:
    assert is_partial(path) is expected


# ---------------------------------------------------------------------------
# SMOKE_SKIP contains the discovered wp_pipeline / content-publish entry.
# ---------------------------------------------------------------------------
def test_smoke_skip_contains_content_publish_preview() -> None:
    assert "/ui/content-publish/{site_id}/preview/{job_id}" in SMOKE_SKIP
    assert "job_id collision" in SMOKE_SKIP[
        "/ui/content-publish/{site_id}/preview/{job_id}"
    ]
