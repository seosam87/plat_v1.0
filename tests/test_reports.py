"""Unit tests for report service and ad traffic."""
import io
import pytest
import openpyxl

from app.services.report_service import generate_excel_report


class TestExcelReport:
    def test_generates_valid_xlsx(self):
        data = generate_excel_report(
            "Test Project",
            keywords=[{"phrase": "seo", "frequency": 100, "region": "RU", "engine": "google", "target_url": ""}],
            tasks=[{"title": "Fix 404", "task_type": "page_404", "status": "open", "url": "/x"}],
            positions=[{"query": "seo", "position": 5, "delta": 2, "url": "/seo", "engine": "google"}],
        )
        wb = openpyxl.load_workbook(io.BytesIO(data))
        assert "Positions" in wb.sheetnames
        assert "Keywords" in wb.sheetnames
        assert "Tasks" in wb.sheetnames
        # Check positions sheet has data
        ws = wb["Positions"]
        assert ws.cell(2, 1).value == "seo"
        assert ws.cell(2, 2).value == 5

    def test_empty_data(self):
        data = generate_excel_report("Empty", keywords=[], tasks=[], positions=[])
        wb = openpyxl.load_workbook(io.BytesIO(data))
        assert wb["Positions"].max_row == 1  # header only


class TestAdTrafficModel:
    def test_model_import(self):
        from app.models.ad_traffic import AdTraffic
        ad = AdTraffic(
            site_id="12345678-1234-1234-1234-123456789abc",
            source="google_ads",
            traffic_date="2026-03-01",
            sessions=100,
            conversions=5,
            cost=50.0,
        )
        assert ad.source == "google_ads"
        assert ad.sessions == 100
