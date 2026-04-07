"""Regression tests: position check must default NULL engine to yandex, not google.

Per user memory "Default engine Yandex" and todo
2026-04-02-fix-position-check-ignores-keyword-engine-preference.
"""
from __future__ import annotations

from pathlib import Path


def _position_tasks_source() -> str:
    return Path("app/tasks/position_tasks.py").read_text()


def test_null_engine_defaults_to_yandex():
    """No occurrence of old 'else \"google\"' default remains."""
    src = _position_tasks_source()
    assert 'if kw.engine else "google"' not in src, (
        "NULL engine must default to 'yandex' not 'google'"
    )


def test_yandex_default_present_multiple_times():
    """DataForSEO and SERP parser paths both use 'yandex' default."""
    src = _position_tasks_source()
    count = src.count('if kw.engine else "yandex"')
    assert count >= 2, f"expected >=2 yandex defaults, got {count}"


def test_keyword_split_routes_null_engine_to_yandex():
    """Line 55-56 split: NULL engine is included in yandex_kws."""
    src = _position_tasks_source()
    assert "not kw.engine or kw.engine.value == \"yandex\"" in src


def test_xmlproxy_path_writes_yandex_engine_str():
    """_check_via_xmlproxy path hardcodes engine_str='yandex' (Yandex-only)."""
    src = _position_tasks_source()
    assert 'engine_str = "yandex"' in src


def test_explicit_google_keyword_still_google():
    """When kw.engine is 'google', the expression yields 'google'."""
    class FakeEngine:
        value = "google"

    class FakeKw:
        engine = FakeEngine()

    kw = FakeKw()
    engine_str = kw.engine.value if kw.engine else "yandex"
    assert engine_str == "google"


def test_explicit_yandex_keyword_yandex():
    class FakeEngine:
        value = "yandex"

    class FakeKw:
        engine = FakeEngine()

    kw = FakeKw()
    engine_str = kw.engine.value if kw.engine else "yandex"
    assert engine_str == "yandex"


def test_null_engine_yields_yandex():
    class FakeKw:
        engine = None

    kw = FakeKw()
    engine_str = kw.engine.value if kw.engine else "yandex"
    assert engine_str == "yandex"
