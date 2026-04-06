"""Unit tests for impact_score_service pure functions.

Tests cover:
- SEVERITY_WEIGHTS dict values
- compute_single_impact_score correctness and edge cases
- build_impact_rows URL normalization and traffic lookup
"""
from __future__ import annotations

import pytest

from app.services.impact_score_service import (
    SEVERITY_WEIGHTS,
    build_impact_rows,
    compute_single_impact_score,
)


class TestSeverityWeights:
    def test_warning_weight(self):
        assert SEVERITY_WEIGHTS["warning"] == 1

    def test_error_weight(self):
        assert SEVERITY_WEIGHTS["error"] == 3

    def test_critical_weight(self):
        assert SEVERITY_WEIGHTS["critical"] == 5

    def test_all_keys_present(self):
        assert set(SEVERITY_WEIGHTS.keys()) == {"warning", "error", "critical"}


class TestComputeSingleImpactScore:
    def test_critical_with_traffic(self):
        result = compute_single_impact_score(severity="critical", monthly_traffic=500)
        assert result == 2500

    def test_warning_with_zero_traffic(self):
        result = compute_single_impact_score(severity="warning", monthly_traffic=0)
        assert result == 0

    def test_error_with_traffic(self):
        result = compute_single_impact_score(severity="error", monthly_traffic=100)
        assert result == 300

    def test_warning_with_traffic(self):
        result = compute_single_impact_score(severity="warning", monthly_traffic=1000)
        assert result == 1000

    def test_unknown_severity_raises_value_error(self):
        with pytest.raises(ValueError):
            compute_single_impact_score(severity="unknown", monthly_traffic=100)

    def test_another_unknown_severity_raises_value_error(self):
        with pytest.raises(ValueError):
            compute_single_impact_score(severity="info", monthly_traffic=50)


class TestBuildImpactRows:
    def test_basic_row_with_traffic(self):
        audit_rows = [
            {
                "page_url": "https://example.com/page/",
                "check_code": "missing_toc",
                "severity": "warning",
            }
        ]
        traffic = {"https://example.com/page/": 200}
        rows = build_impact_rows(audit_rows, traffic)
        assert len(rows) == 1
        assert rows[0]["impact_score"] == 200  # 1 * 200
        assert rows[0]["monthly_traffic"] == 200
        assert rows[0]["severity_weight"] == 1

    def test_url_normalization_http_to_https(self):
        audit_rows = [
            {
                "page_url": "http://example.com/page/",
                "check_code": "missing_schema",
                "severity": "error",
            }
        ]
        # traffic stored under normalized https URL
        traffic = {"https://example.com/page/": 150}
        rows = build_impact_rows(audit_rows, traffic)
        assert len(rows) == 1
        assert rows[0]["impact_score"] == 450  # 3 * 150

    def test_zero_traffic_when_no_metrika_data(self):
        audit_rows = [
            {
                "page_url": "https://example.com/no-traffic/",
                "check_code": "missing_toc",
                "severity": "critical",
            }
        ]
        rows = build_impact_rows(audit_rows, {})
        assert len(rows) == 1
        assert rows[0]["impact_score"] == 0
        assert rows[0]["monthly_traffic"] == 0

    def test_utm_stripped_for_matching(self):
        audit_rows = [
            {
                "page_url": "https://example.com/page/?utm_source=yandex",
                "check_code": "missing_toc",
                "severity": "warning",
            }
        ]
        # traffic stored under clean URL
        traffic = {"https://example.com/page/": 300}
        rows = build_impact_rows(audit_rows, traffic)
        assert len(rows) == 1
        assert rows[0]["impact_score"] == 300

    def test_multiple_rows(self):
        audit_rows = [
            {"page_url": "https://example.com/a/", "check_code": "missing_toc", "severity": "warning"},
            {"page_url": "https://example.com/b/", "check_code": "missing_schema", "severity": "critical"},
        ]
        traffic = {
            "https://example.com/a/": 100,
            "https://example.com/b/": 200,
        }
        rows = build_impact_rows(audit_rows, traffic)
        assert len(rows) == 2
        scores = {r["page_url"]: r["impact_score"] for r in rows}
        assert scores["https://example.com/a/"] == 100   # 1 * 100
        assert scores["https://example.com/b/"] == 1000  # 5 * 200

    def test_row_contains_required_fields(self):
        audit_rows = [
            {"page_url": "https://example.com/p/", "check_code": "missing_toc", "severity": "error"}
        ]
        rows = build_impact_rows(audit_rows, {"https://example.com/p/": 50})
        row = rows[0]
        assert "page_url" in row
        assert "check_code" in row
        assert "severity" in row
        assert "severity_weight" in row
        assert "monthly_traffic" in row
        assert "impact_score" in row
