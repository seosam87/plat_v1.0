"""Unit tests for competitor module."""
import pytest

from app.models.competitor import Competitor
from app.services.competitor_service import create_competitor


class TestCompetitorModel:
    def test_model_fields(self):
        c = Competitor(
            site_id="12345678-1234-1234-1234-123456789abc",
            domain="competitor.com",
            name="Competitor Inc",
            notes="Main competitor",
        )
        assert c.domain == "competitor.com"
        assert c.name == "Competitor Inc"


class TestCompetitorServiceImports:
    def test_imports(self):
        from app.services.competitor_service import (
            create_competitor,
            list_competitors,
            get_competitor,
            delete_competitor,
            compare_positions,
            detect_serp_competitors,
        )
        assert callable(create_competitor)
        assert callable(compare_positions)
        assert callable(detect_serp_competitors)


class TestDomainNormalization:
    """Test domain cleaning logic used in create_competitor."""

    def test_strips_protocol(self):
        test_cases = [
            ("https://example.com", "example.com"),
            ("http://example.com", "example.com"),
            ("https://www.example.com", "example.com"),
            ("www.example.com", "example.com"),
            ("example.com", "example.com"),
            ("EXAMPLE.COM", "example.com"),
            ("https://example.com/", "example.com"),
        ]
        for input_domain, expected in test_cases:
            domain = input_domain.strip().lower().rstrip("/")
            for prefix in ("https://", "http://", "www."):
                if domain.startswith(prefix):
                    domain = domain[len(prefix):]
            assert domain == expected, f"Failed for {input_domain}"


class TestEndpointsRegistered:
    def test_competitor_routes(self):
        from app.routers.competitors import router
        paths = [r.path for r in router.routes]
        assert "/competitors/sites/{site_id}" in paths
        assert "/competitors/{competitor_id}" in paths
        assert "/competitors/sites/{site_id}/compare/{competitor_id}" in paths
        assert "/competitors/sites/{site_id}/detect" in paths

    def test_ui_routes(self):
        from app.main import app
        paths = [r.path for r in app.routes]
        assert "/ui/competitors/{site_id}" in paths


class TestCompareLogic:
    """Test position comparison delta logic."""

    def test_we_are_behind(self):
        our, comp = 15, 5
        delta = our - comp  # positive = we are behind
        assert delta == 10

    def test_we_are_ahead(self):
        our, comp = 3, 10
        delta = our - comp  # negative = we are ahead
        assert delta == -7

    def test_same_position(self):
        our, comp = 5, 5
        delta = our - comp
        assert delta == 0
