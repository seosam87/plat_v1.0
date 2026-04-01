"""Diff service: compute field-level changes between page snapshots."""
from __future__ import annotations

SNAPSHOT_FIELDS = ("title", "h1", "meta_description", "http_status", "content_preview")


def compute_diff(old_snap: dict, new_snap: dict) -> dict:
    """Compare two snapshot dicts field-by-field.

    Returns a dict of changed fields: ``{field: {"old": ..., "new": ...}}``.
    Returns an empty dict if no fields differ.
    """
    diff: dict = {}
    all_keys = set(old_snap.keys()) | set(new_snap.keys())
    for key in all_keys:
        old_val = old_snap.get(key)
        new_val = new_snap.get(key)
        if old_val != new_val:
            diff[key] = {"old": old_val, "new": new_val}
    return diff


def build_snapshot(page, content_preview: str = "") -> dict:
    """Build a snapshot dict from a Page ORM instance.

    Parameters
    ----------
    page:
        A ``Page`` ORM object (typed loosely to avoid circular import).
    content_preview:
        Optional short text extracted from page body (first N chars).

    Returns
    -------
    dict with SNAPSHOT_FIELDS keys.
    """
    return {
        "title": page.title or "",
        "h1": page.h1 or "",
        "meta_description": page.meta_description or "",
        "http_status": page.http_status,
        "content_preview": content_preview,
    }
