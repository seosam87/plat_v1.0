"""Tests for diff_service: compute_diff and build_snapshot."""
import types

import pytest

from app.services.diff_service import build_snapshot, compute_diff


# ---------------------------------------------------------------------------
# compute_diff
# ---------------------------------------------------------------------------

def test_compute_diff_detects_title_change():
    old = {"title": "Old Title", "h1": "Heading", "meta_description": "desc", "http_status": 200, "content_preview": ""}
    new = {"title": "New Title", "h1": "Heading", "meta_description": "desc", "http_status": 200, "content_preview": ""}
    diff = compute_diff(old, new)
    assert "title" in diff
    assert diff["title"] == {"old": "Old Title", "new": "New Title"}
    # Unchanged fields should NOT appear in diff
    assert "h1" not in diff
    assert "meta_description" not in diff


def test_compute_diff_empty_when_no_changes():
    snap = {"title": "Same", "h1": "Same H1", "meta_description": "Same desc", "http_status": 200, "content_preview": ""}
    diff = compute_diff(snap, snap.copy())
    assert diff == {}


def test_compute_diff_detects_multiple_changes():
    old = {"title": "T1", "h1": "H1", "meta_description": "D1", "http_status": 200, "content_preview": "old"}
    new = {"title": "T2", "h1": "H1", "meta_description": "D2", "http_status": 404, "content_preview": "new"}
    diff = compute_diff(old, new)
    assert set(diff.keys()) == {"title", "meta_description", "http_status", "content_preview"}


def test_compute_diff_handles_missing_keys():
    """Keys present in only one snapshot are still detected as changes."""
    old = {"title": "T1"}
    new = {"title": "T1", "h1": "New H1"}
    diff = compute_diff(old, new)
    assert "h1" in diff
    assert diff["h1"] == {"old": None, "new": "New H1"}


# ---------------------------------------------------------------------------
# build_snapshot
# ---------------------------------------------------------------------------

def _make_page(**kwargs):
    """Create a simple namespace object mimicking a Page ORM row."""
    defaults = {
        "title": "Test Title",
        "h1": "Test H1",
        "meta_description": "Test description",
        "http_status": 200,
        "canonical_url": "",
        "has_schema": False,
        "has_toc": False,
        "has_noindex": False,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def test_build_snapshot_fields():
    page = _make_page()
    snap = build_snapshot(page)
    assert snap["title"] == "Test Title"
    assert snap["h1"] == "Test H1"
    assert snap["meta_description"] == "Test description"
    assert snap["http_status"] == 200
    assert snap["content_preview"] == ""


def test_build_snapshot_with_content_preview():
    page = _make_page(title="Article", h1="Big Heading", meta_description="", http_status=200)
    snap = build_snapshot(page, content_preview="First paragraph text...")
    assert snap["content_preview"] == "First paragraph text..."


def test_build_snapshot_none_fields_become_empty_string():
    page = _make_page(title=None, h1=None, meta_description=None, http_status=None)
    snap = build_snapshot(page)
    assert snap["title"] == ""
    assert snap["h1"] == ""
    assert snap["meta_description"] == ""
    assert snap["http_status"] is None
