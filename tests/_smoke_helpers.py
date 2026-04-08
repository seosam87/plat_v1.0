"""Smoke crawler helpers — route discovery, param resolution, response assertions.

Per Phase 15.1 CONTEXT D-02 / D-03 / D-04 / D-05 and RESEARCH Pattern 1.

Pure, unit-testable helpers consumed by ``tests/test_ui_smoke.py`` (Plan 03).
No DB / network side effects at import time.
"""
from __future__ import annotations

import re
import typing
from dataclasses import dataclass
from typing import get_origin

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

try:
    from fastapi.datastructures import DefaultPlaceholder
except ImportError:  # pragma: no cover - defensive fallback for FastAPI variants
    class DefaultPlaceholder:  # type: ignore[no-redef]
        """Sentinel fallback when fastapi.datastructures.DefaultPlaceholder is unavailable."""

# Response classes that are NEVER HTML (tier-1 explicit negatives, for reference).
_NON_HTML_RESPONSE_HINTS = (
    "JSONResponse",
    "PlainTextResponse",
    "FileResponse",
    "StreamingResponse",
)

# ---------------------------------------------------------------------------
# Error markers — scanned inside response body to catch Jinja / 500s that
# still returned HTTP 200. "builtin_function_or_method" is today's bug
# (dict.items vs data.items collision on opportunities page).
# ---------------------------------------------------------------------------
JINJA_ERROR_MARKERS: tuple[str, ...] = (
    "TemplateSyntaxError",
    "UndefinedError",
    "jinja2.exceptions",
    "Traceback (most recent call last)",
    "builtin_function_or_method",
    "AttributeError:",
    "<title>500",
    "<title>Internal Server Error",
)

# ---------------------------------------------------------------------------
# Full UI prefix list — from RESEARCH Pattern 1. Any GET route whose path
# starts with one of these prefixes is automatically discovered for smoke.
# ---------------------------------------------------------------------------
UI_PREFIXES: tuple[str, ...] = (
    "/ui/",
    "/analytics/",
    "/audit/",
    "/gap/",
    "/intent/",
    "/architecture/",
    "/bulk/",
    "/traffic-analysis/",
    "/monitoring/",
    "/competitors/",
    "/metrika/",
    "/profile/",
)

# ---------------------------------------------------------------------------
# SMOKE_SKIP — allowlist of deliberately-skipped paths with reason comments.
# New routes default to being tested; opt-out requires an explicit entry here.
# ---------------------------------------------------------------------------
SMOKE_SKIP: dict[str, str] = {
    "/":             "root redirect to /ui/dashboard — not a render",
    "/ui/login":     "auth entry point — redirect loop in tests",
    "/ui/logout":    "session destruction / 302",
    "/ui/logs":      "live tail endpoint",
    "/ui/api/sites": "JSON-only API fragment, not a Jinja template",
    # wp_pipeline / content-publish routes use {job_id} which collides
    # between SuggestJob and WpContentJob — cannot resolve a single
    # PARAM_MAP entry. Defer to scenario runner (backlog 999.1).
    "/ui/content-publish/{site_id}/preview/{job_id}":
        "job_id collision (SuggestJob vs WpContentJob) — covered by backlog 999.1",
}


class UnknownParamError(RuntimeError):
    """Raised by ``resolve_path`` when a path segment has no PARAM_MAP entry."""


@dataclass(frozen=True)
class RouteSpec:
    path: str
    name: str
    methods: frozenset[str]


def _is_html_route(route: APIRoute) -> bool:
    """Three-tier HTML classification — see discover_routes docstring."""
    # Tier 1: explicit response_class (skip FastAPI's DefaultPlaceholder).
    rc = getattr(route, "response_class", None)
    if rc is not None and not isinstance(rc, DefaultPlaceholder):
        try:
            return issubclass(rc, HTMLResponse)
        except TypeError:
            # rc is an instance, not a class — treat as ambiguous, fall through.
            pass

    # Tier 2: return-type annotation.
    # Resolve via typing.get_type_hints so PEP 563 string annotations
    # (`from __future__ import annotations`) become live objects. If
    # resolution fails (forward refs, missing names), fall through to tier 3.
    endpoint = getattr(route, "endpoint", None)
    ann = None
    if endpoint is not None:
        try:
            ann = typing.get_type_hints(endpoint).get("return")
        except (NameError, AttributeError, TypeError):
            ann = None
    if ann is not None:
        # Parametrized generics: list[dict], dict[str, Any], etc.
        origin = get_origin(ann)
        if origin in (list, dict, tuple, set):
            return False
        if isinstance(ann, type):
            if issubclass(ann, HTMLResponse):
                return True
            if issubclass(ann, (list, dict, BaseModel)):
                return False
            # Generic Response / unknown class — fall through to tier 3.

    # Tier 3: conservative include.
    return True


def discover_routes(app: FastAPI) -> list[RouteSpec]:
    """Enumerate smoke-testable HTML GET routes from app.routes.

    A route is included iff ALL of:
      - it's a fastapi APIRoute
      - GET is among its methods
      - path does not start with /api/
      - path starts with one of UI_PREFIXES
      - it passes the HTML classification filter (_is_html_route):
          1. response_class explicitly set and is HTMLResponse subclass -> include
             (DefaultPlaceholder sentinel is treated as "not declared")
          2. return annotation is HTMLResponse subclass -> include
             return annotation is list/dict/BaseModel/parametrized list[..] -> exclude
          3. neither signal present -> include (conservative fallback)
      - path is not in SMOKE_SKIP

      Edge case: if a route declares response_class=HTMLResponse AND has a
      -> list[dict] annotation, tier 1 wins and the route is included.
    """
    out: list[RouteSpec] = []
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        if "GET" not in r.methods:
            continue
        if r.path.startswith("/api/"):
            continue
        if not any(r.path.startswith(p) for p in UI_PREFIXES):
            continue
        if not _is_html_route(r):
            continue
        if r.path in SMOKE_SKIP:
            continue
        out.append(
            RouteSpec(
                path=r.path,
                name=r.name or r.path,
                methods=frozenset(r.methods),
            )
        )
    return sorted(out, key=lambda s: s.path)


def build_param_map(smoke_ids: dict[str, str]) -> dict[str, str]:
    """Return a path-param substitution map seeded from ``smoke_ids``.

    Adds the string-typed ``module`` param (``/ui/help/{module}``) which is
    not a UUID — per RESEARCH correction.
    """
    pm: dict[str, str] = {k: str(v) for k, v in smoke_ids.items()}
    # "module": "general" — /ui/help/{module} is a string path param, not a UUID.
    pm.setdefault("module", "general")
    return pm


_PARAM_RE = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")


def resolve_path(path_template: str, param_map: dict[str, str]) -> str:
    """Substitute ``{name}`` segments in ``path_template`` using ``param_map``.

    Raises ``UnknownParamError`` with a helpful message on miss so the
    developer knows exactly which path / param pair to fix.
    """

    def repl(m: "re.Match[str]") -> str:
        name = m.group(1)
        if name not in param_map:
            raise UnknownParamError(
                f"Unknown path param '{name}' in {path_template} — "
                f"add to PARAM_MAP or SMOKE_SKIP"
            )
        return param_map[name]

    return _PARAM_RE.sub(repl, path_template)


def assert_no_error_markers(body: str, path: str) -> None:
    """Fail if response body contains any known Jinja / traceback marker."""
    for marker in JINJA_ERROR_MARKERS:
        if marker in body:
            raise AssertionError(
                f"{path}: response body contains error marker '{marker}'"
            )


def assert_structural_html(body: str, path: str, *, is_partial: bool) -> None:
    """Assert the response body looks like a real rendered template.

    Partials: just non-empty body.
    Full pages: require ``<title>`` and a ``<body>`` or ``<main>`` tag.
    """
    if is_partial:
        if not body or not body.strip():
            raise AssertionError(f"{path}: partial returned empty body")
        return
    if "<title>" not in body:
        raise AssertionError(f"{path}: full page missing <title>")
    if "<body" not in body and "<main" not in body:
        raise AssertionError(f"{path}: full page missing <body>/<main>")


def is_partial(path: str) -> bool:
    """Heuristic: does this path render an HTMX partial rather than a page?

    Recognised partial markers:
      - "/tabs/"        — tabbed-panel partial
      - "/partials/"    — explicit partial directory
      - "/detail/"      — inline detail panel
      - "/widget"       — dashboard widget partial (e.g. /metrika/{id}/widget)
      - "/fix-status/"  — fix-status row swap
      - "/quick-wins/table" — table-only swap inside quick-wins page

    Only relaxes the structural HTML check for these paths. The body
    error-marker scan and the non-empty body check still apply.
    """
    return (
        "/tabs/" in path
        or "/partials/" in path
        or "/detail/" in path
        or "/widget" in path
        or "/fix-status/" in path
        or "/quick-wins/table" in path
    )
