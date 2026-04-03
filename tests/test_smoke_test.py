"""
Unit tests for tests/smoke_test.py — covers pure (non-async, non-DB) functions.

These tests do NOT require a live database or running server.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# discover_routes_from_nav
# ---------------------------------------------------------------------------

def test_discover_routes_from_nav_includes_dashboard():
    from tests.smoke_test import discover_routes_from_nav
    routes = discover_routes_from_nav()
    urls = [r["url"] for r in routes]
    assert "/ui/dashboard" in urls


def test_discover_routes_from_nav_includes_site_scoped():
    from tests.smoke_test import discover_routes_from_nav
    routes = discover_routes_from_nav()
    urls = [r["url"] for r in routes]
    # At minimum keywords and positions should be discovered
    assert any("{site_id}" in u for u in urls)


def test_discover_routes_from_nav_no_none_urls():
    from tests.smoke_test import discover_routes_from_nav
    routes = discover_routes_from_nav()
    assert all(r["url"] is not None for r in routes)


def test_discover_routes_from_nav_includes_admin_routes():
    from tests.smoke_test import discover_routes_from_nav
    routes = discover_routes_from_nav()
    urls = [r["url"] for r in routes]
    assert "/ui/admin/users" in urls


def test_discover_routes_from_nav_has_source_field():
    from tests.smoke_test import discover_routes_from_nav
    routes = discover_routes_from_nav()
    assert all("source" in r for r in routes)
    assert all(r["source"] == "nav" for r in routes)


# ---------------------------------------------------------------------------
# discover_routes_from_main
# ---------------------------------------------------------------------------

def test_discover_routes_from_main_returns_list():
    from tests.smoke_test import discover_routes_from_main
    routes = discover_routes_from_main()
    assert isinstance(routes, list)
    assert len(routes) > 0


def test_discover_routes_from_main_excludes_login():
    from tests.smoke_test import discover_routes_from_main
    routes = discover_routes_from_main()
    urls = [r["url"] for r in routes]
    assert "/ui/login" not in urls


def test_discover_routes_from_main_excludes_api_fragments():
    from tests.smoke_test import discover_routes_from_main
    routes = discover_routes_from_main()
    urls = [r["url"] for r in routes]
    assert not any("/ui/api/" in u for u in urls)


# ---------------------------------------------------------------------------
# resolve_url
# ---------------------------------------------------------------------------

def test_resolve_url_replaces_site_id():
    from tests.smoke_test import resolve_url
    result = resolve_url("/ui/keywords/{site_id}", "abc-123", "proj-456")
    assert result == "/ui/keywords/abc-123"


def test_resolve_url_replaces_project_id():
    from tests.smoke_test import resolve_url
    result = resolve_url("/ui/projects/{project_id}/plan", "abc-123", "proj-456")
    assert result == "/ui/projects/proj-456/plan"


def test_resolve_url_no_placeholder():
    from tests.smoke_test import resolve_url
    result = resolve_url("/ui/dashboard", "abc-123", "proj-456")
    assert result == "/ui/dashboard"


def test_resolve_url_mixed_placeholders():
    from tests.smoke_test import resolve_url
    # If template has both, both should be replaced
    result = resolve_url("/ui/sites/{site_id}/detail", "site-uuid", "proj-uuid")
    assert result == "/ui/sites/site-uuid/detail"
    assert "{site_id}" not in result


# ---------------------------------------------------------------------------
# print_report
# ---------------------------------------------------------------------------

def test_print_report_exit_code_0_on_all_ok(capsys):
    from tests.smoke_test import print_report
    results = [
        {"url": "/ui/dashboard", "status": 200, "ok": True, "error": None, "skipped": False},
        {"url": "/ui/sites", "status": 200, "ok": True, "error": None, "skipped": False},
    ]
    code = print_report(results)
    assert code == 0


def test_print_report_exit_code_1_on_error(capsys):
    from tests.smoke_test import print_report
    results = [
        {"url": "/ui/dashboard", "status": 200, "ok": True, "error": None, "skipped": False},
        {"url": "/ui/broken", "status": 500, "ok": False, "error": "Internal Server Error", "skipped": False},
    ]
    code = print_report(results)
    assert code == 1


def test_print_report_3xx_is_not_error(capsys):
    from tests.smoke_test import print_report
    results = [{"url": "/ui/positions", "status": 302, "ok": True, "error": None, "skipped": False}]
    code = print_report(results)
    assert code == 0


def test_print_report_skipped_not_counted_as_error(capsys):
    from tests.smoke_test import print_report
    results = [
        {"url": "/ui/dashboard", "status": 200, "ok": True, "error": None, "skipped": False},
        {"url": "/ui/help/{module}", "status": None, "ok": True, "error": None, "skipped": True},
    ]
    code = print_report(results)
    assert code == 0


def test_print_report_prints_summary(capsys):
    from tests.smoke_test import print_report
    results = [
        {"url": "/ui/dashboard", "status": 200, "ok": True, "error": None, "skipped": False},
    ]
    print_report(results)
    captured = capsys.readouterr()
    assert "routes checked" in captured.out


# ---------------------------------------------------------------------------
# merge_routes
# ---------------------------------------------------------------------------

def test_merge_routes_deduplicates():
    from tests.smoke_test import merge_routes
    nav = [{"url": "/ui/dashboard", "source": "nav", "label": "Dashboard"}]
    main = [
        {"url": "/ui/dashboard", "source": "main", "label": "/ui/dashboard"},
        {"url": "/ui/sites", "source": "main", "label": "/ui/sites"},
    ]
    merged = merge_routes(nav, main)
    urls = [r["url"] for r in merged]
    assert urls.count("/ui/dashboard") == 1
    assert "/ui/sites" in urls


def test_merge_routes_nav_takes_priority():
    from tests.smoke_test import merge_routes
    nav = [{"url": "/ui/dashboard", "source": "nav", "label": "Обзор"}]
    main = [{"url": "/ui/dashboard", "source": "main", "label": "/ui/dashboard"}]
    merged = merge_routes(nav, main)
    dashboard = next(r for r in merged if r["url"] == "/ui/dashboard")
    assert dashboard["source"] == "nav"
    assert dashboard["label"] == "Обзор"


def test_merge_routes_marks_site_id_needed():
    from tests.smoke_test import merge_routes
    nav = [{"url": "/ui/keywords/{site_id}", "source": "nav", "label": "Keywords"}]
    merged = merge_routes(nav, [])
    keywords = next(r for r in merged if "{site_id}" in r["url"])
    assert keywords["needs_site_id"] is True
    assert keywords["needs_project_id"] is False


def test_merge_routes_marks_project_id_needed():
    from tests.smoke_test import merge_routes
    main = [{"url": "/ui/projects/{project_id}/kanban", "source": "main", "label": "/ui/projects/{project_id}/kanban"}]
    merged = merge_routes([], main)
    proj = next(r for r in merged if "{project_id}" in r["url"])
    assert proj["needs_project_id"] is True


def test_merge_routes_skips_unresolvable_patterns():
    from tests.smoke_test import merge_routes
    nav = [{"url": "/ui/crawls/{crawl_job_id}", "source": "nav", "label": "Crawl Detail"}]
    merged = merge_routes(nav, [])
    urls = [r["url"] for r in merged]
    assert "/ui/crawls/{crawl_job_id}" not in urls


def test_merge_routes_returns_sorted():
    from tests.smoke_test import merge_routes
    nav = [
        {"url": "/ui/sites", "source": "nav", "label": "Sites"},
        {"url": "/ui/dashboard", "source": "nav", "label": "Dashboard"},
    ]
    merged = merge_routes(nav, [])
    urls = [r["url"] for r in merged]
    assert urls == sorted(urls)
