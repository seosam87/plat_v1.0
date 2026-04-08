"""Tests for GEO filter params on the audit page router (Plan 16-02, Task 1).

Uses the session-scoped smoke_client + smoke_seed fixtures from Phase 15.1.
All tests assert HTTP 200 and no Jinja errors — the data is smoke-seeded.

pytestmark sets asyncio scope to "session" so the session-scoped smoke_client
fixture shares the same event loop across all tests (pytest-asyncio 0.23 pattern).
"""
from __future__ import annotations

import pytest

from tests.fixtures.smoke_seed import SMOKE_IDS

SITE_ID = SMOKE_IDS["site_id"]

# Session scope required — smoke_client is session-scoped (pytest-asyncio 0.23)
pytestmark = pytest.mark.asyncio(scope="session")


async def test_audit_page_renders_with_geo_column(smoke_client):
    """GET /audit/{site_id} returns 200 and body references GEO column."""
    resp = await smoke_client.get(f"/audit/{SITE_ID}")
    assert resp.status_code == 200
    body = resp.text.lower()
    assert "geo" in body


async def test_audit_page_geo_score_min_filter(smoke_client):
    """GET /audit/{site_id}?geo_score_min=50 returns 200 (filter accepted)."""
    resp = await smoke_client.get(f"/audit/{SITE_ID}?geo_score_min=50")
    assert resp.status_code == 200


async def test_audit_page_geo_score_full_range(smoke_client):
    """GET /audit/{site_id}?geo_score_min=0&geo_score_max=100 returns 200."""
    resp = await smoke_client.get(f"/audit/{SITE_ID}?geo_score_min=0&geo_score_max=100")
    assert resp.status_code == 200


async def test_audit_page_geo_check_valid(smoke_client):
    """GET /audit/{site_id}?geo_check=geo_faq_schema returns 200 (valid check code)."""
    resp = await smoke_client.get(f"/audit/{SITE_ID}?geo_check=geo_faq_schema")
    assert resp.status_code == 200


async def test_audit_page_geo_check_invalid_silent(smoke_client):
    """GET /audit/{site_id}?geo_check=invalid_code returns 200 (silently ignored)."""
    resp = await smoke_client.get(f"/audit/{SITE_ID}?geo_check=invalid_code")
    assert resp.status_code == 200
