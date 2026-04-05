"""Unit tests for PDF report generation in report_service."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGeneratePdfReportBrief:
    """Test generate_pdf_report with brief type returns bytes."""

    @pytest.mark.asyncio
    async def test_brief_returns_bytes(self):
        from app.services.report_service import generate_pdf_report

        project_id = uuid.uuid4()
        site_id = uuid.uuid4()

        # Mock project
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.name = "Test Project"
        mock_project.site_id = site_id

        # Mock site
        mock_site = MagicMock()
        mock_site.domain = "example.com"

        # Build fake DB that returns mocked objects
        mock_db = AsyncMock()

        # We need execute to return different things based on call order
        # 1st call: project lookup
        # 2nd call: site lookup
        # 3rd call: site_overview (multiple internal calls)
        # tasks call
        execute_results = []

        def _scalar_one_or_none_project():
            m = MagicMock()
            m.scalar_one_or_none.return_value = mock_project
            return m

        def _scalar_one_or_none_site():
            m = MagicMock()
            m.scalar_one_or_none.return_value = mock_site
            return m

        def _scalar_one(val):
            m = MagicMock()
            m.scalar_one.return_value = val
            return m

        def _scalars_all_tasks():
            m = MagicMock()
            m.scalars.return_value.all.return_value = []
            return m

        def _mappings_one_or_none():
            m = MagicMock()
            dist = {"top3": 5, "top10": 20, "top30": 40, "top100": 60, "not_ranked": 10, "total": 70}
            m.mappings.return_value.one_or_none.return_value = dist
            return m

        def _mappings_all():
            m = MagicMock()
            m.mappings.return_value.all.return_value = []
            return m

        # Track call count to return different results
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return _scalar_one_or_none_project()
            elif n == 2:
                return _scalar_one_or_none_site()
            elif n == 3:
                # keyword_count
                return _scalar_one(50)
            elif n == 4:
                # open_tasks
                return _scalar_one(3)
            elif n == 5:
                # crawl_count
                return _scalar_one(10)
            elif n == 6:
                # distribution
                return _mappings_one_or_none()
            elif n == 7:
                # top movers
                return _mappings_all()
            elif n == 8:
                # project tasks
                return _scalars_all_tasks()
            elif n == 9:
                # recent crawl changes
                return _mappings_all()
            else:
                return _scalars_all_tasks()

        mock_db.execute = mock_execute

        fake_pdf = b"%PDF-1.4 brief"

        # Patch weasyprint at the import point used by the service
        mock_weasyprint = MagicMock()
        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = fake_pdf
        mock_weasyprint.HTML.return_value = mock_html_instance

        import sys
        sys.modules["weasyprint"] = mock_weasyprint

        try:
            result = await generate_pdf_report(mock_db, project_id, "brief")
        finally:
            del sys.modules["weasyprint"]

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestGeneratePdfReportDetailed:
    """Test generate_pdf_report with detailed type returns bytes."""

    @pytest.mark.asyncio
    async def test_detailed_returns_bytes(self):
        from app.services.report_service import generate_pdf_report

        project_id = uuid.uuid4()
        site_id = uuid.uuid4()

        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.name = "Detailed Test"
        mock_project.site_id = site_id

        mock_site = MagicMock()
        mock_site.domain = "detailed.com"

        call_count = [0]

        def _scalar_one_or_none_val(val):
            m = MagicMock()
            m.scalar_one_or_none.return_value = val
            return m

        def _scalar_one(val):
            m = MagicMock()
            m.scalar_one.return_value = val
            return m

        def _scalars_all(items):
            m = MagicMock()
            m.scalars.return_value.all.return_value = items
            return m

        def _mappings_one_or_none(val):
            m = MagicMock()
            m.mappings.return_value.one_or_none.return_value = val
            return m

        def _mappings_all(items):
            m = MagicMock()
            m.mappings.return_value.all.return_value = items
            return m

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return _scalar_one_or_none_val(mock_project)
            elif n == 2:
                return _scalar_one_or_none_val(mock_site)
            elif n == 3:
                return _scalar_one(10)
            elif n == 4:
                return _scalar_one(1)
            elif n == 5:
                return _scalar_one(5)
            elif n == 6:
                dist = {"top3": 2, "top10": 8, "top30": 15, "top100": 20, "not_ranked": 5, "total": 25}
                return _mappings_one_or_none(dist)
            elif n == 7:
                return _mappings_all([])
            elif n == 8:
                return _scalars_all([])
            elif n == 9:
                return _mappings_all([])
            else:
                return _scalars_all([])

        mock_db = AsyncMock()
        mock_db.execute = mock_execute

        fake_pdf = b"%PDF-1.4 detailed"

        mock_weasyprint = MagicMock()
        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = fake_pdf
        mock_weasyprint.HTML.return_value = mock_html_instance

        import sys
        sys.modules["weasyprint"] = mock_weasyprint

        try:
            result = await generate_pdf_report(mock_db, project_id, "detailed")
        finally:
            del sys.modules["weasyprint"]

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestGeneratePdfReportInvalidProject:
    """Test that invalid project_id raises HTTPException."""

    @pytest.mark.asyncio
    async def test_invalid_project_raises_404(self):
        from fastapi import HTTPException
        from app.services.report_service import generate_pdf_report

        project_id = uuid.uuid4()

        mock_db = AsyncMock()

        def _scalar_none():
            m = MagicMock()
            m.scalar_one_or_none.return_value = None
            return m

        async def mock_execute(query, *args, **kwargs):
            return _scalar_none()

        mock_db.execute = mock_execute

        with pytest.raises(HTTPException) as exc_info:
            await generate_pdf_report(mock_db, project_id, "brief")

        assert exc_info.value.status_code == 404


class TestGeneratePdfReportFunctionExists:
    """Verify generate_pdf_report is exported from report_service."""

    def test_function_exported(self):
        from app.services.report_service import generate_pdf_report
        assert callable(generate_pdf_report)
