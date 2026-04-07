"""Unit tests for SMOKE_IDS constants (Phase 15.1, Plan 01 Task 1)."""
from __future__ import annotations

from uuid import UUID

from tests.fixtures.smoke_seed import SMOKE_IDS, SeedHandle


REQUIRED_KEYS = {
    "site_id",
    "user_id",
    "keyword_id",
    "gap_keyword_id",
    "suggest_job_id",
    "crawl_job_id",
    "job_id",
    "report_id",
    "audit_id",
    "audit_check_id",
    "project_id",
    "task_id",
    "session_id",
    "cluster_id",
    "brief_id",
    "competitor_id",
    "group_id",
}


def test_site_id_deterministic():
    assert SMOKE_IDS["site_id"] == "11111111-1111-1111-1111-111111111111"


def test_all_required_keys_present():
    assert set(SMOKE_IDS.keys()) == REQUIRED_KEYS
    assert len(SMOKE_IDS) == 17


def test_all_values_are_valid_uuids():
    for key, value in SMOKE_IDS.items():
        # Must parse without raising.
        UUID(value)


def test_job_id_alias_matches_suggest_job_id():
    assert SMOKE_IDS["job_id"] == SMOKE_IDS["suggest_job_id"]


def test_seed_handle_dataclass_exists():
    assert SeedHandle.__dataclass_fields__.keys() >= {"ids", "session", "connection"}
