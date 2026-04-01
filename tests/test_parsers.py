"""Unit tests for file parsers: Topvisor, Key Collector, Screaming Frog."""
import csv
import tempfile
from pathlib import Path

import openpyxl
import pytest

from app.parsers.base import find_column, safe_int, read_file
from app.parsers.topvisor_parser import parse_topvisor
from app.parsers.keycollector_parser import parse_keycollector
from app.parsers.screaming_frog_parser import parse_screaming_frog


# ---------------------------------------------------------------------------
# Helpers: create temp files
# ---------------------------------------------------------------------------


def _write_xlsx(rows: list[list], suffix=".xlsx") -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    path = tempfile.mktemp(suffix=suffix)
    wb.save(path)
    wb.close()
    return path


def _write_csv(rows: list[list], encoding="utf-8", delimiter=";") -> str:
    path = tempfile.mktemp(suffix=".csv")
    with open(path, "w", encoding=encoding, newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        for row in rows:
            writer.writerow(row)
    return path


# ---------------------------------------------------------------------------
# base.py
# ---------------------------------------------------------------------------


class TestFindColumn:
    def test_exact_match(self):
        assert find_column(["URL", "Title", "Status"], ["title"]) == 1

    def test_case_insensitive(self):
        assert find_column(["ADDRESS", "status code"], ["status code"]) == 1

    def test_partial_match_fallback(self):
        assert find_column(["Частота Яндекс", "URL"], ["частот"]) == 0

    def test_not_found(self):
        assert find_column(["A", "B"], ["xyz"]) is None

    def test_stripped(self):
        assert find_column(["  URL  ", "Title"], ["url"]) == 0


class TestSafeInt:
    def test_integer(self):
        assert safe_int("42") == 42

    def test_float_string(self):
        assert safe_int("3.0") == 3

    def test_dash(self):
        assert safe_int("-") is None

    def test_empty(self):
        assert safe_int("") is None

    def test_comma_decimal(self):
        assert safe_int("1,5") == 1

    def test_none_string(self):
        assert safe_int("None") is None


class TestReadFile:
    def test_read_xlsx(self):
        path = _write_xlsx([["A", "B"], ["1", "2"]])
        rows = read_file(path)
        assert len(rows) == 2
        assert rows[0] == ["A", "B"]

    def test_read_csv_utf8(self):
        path = _write_csv([["Запросы", "Частота"], ["seo", "100"]], encoding="utf-8")
        rows = read_file(path)
        assert len(rows) == 2
        assert rows[0][0] == "Запросы"

    def test_read_csv_cp1251(self):
        path = _write_csv([["Запросы", "Частота"], ["seo", "100"]], encoding="cp1251")
        rows = read_file(path)
        assert len(rows) == 2
        assert "Запросы" in rows[0][0]

    def test_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported"):
            read_file("/tmp/test.pdf")


# ---------------------------------------------------------------------------
# Topvisor parser
# ---------------------------------------------------------------------------


class TestTopvisorParser:
    def test_basic_keywords(self):
        path = _write_xlsx([
            ["Запросы", "URL", "Частота"],
            ["seo tools", "https://example.com/seo", "1500"],
            ["keyword research", "https://example.com/kw", "800"],
        ])
        result = parse_topvisor(path)
        assert result["row_count"] == 2
        assert result["keywords"][0]["phrase"] == "seo tools"
        assert result["keywords"][0]["frequency"] == 1500
        assert result["keywords"][0]["target_url"] == "https://example.com/seo"

    def test_date_columns_position_history(self):
        path = _write_xlsx([
            ["Запросы", "Частота", "01.03.2026", "15.03.2026"],
            ["seo tools", "1500", "5", "3"],
            ["keyword research", "800", "12", ""],
        ])
        result = parse_topvisor(path)
        assert result["date_columns"] == ["2026-03-01", "2026-03-15"]
        assert len(result["position_history"]) == 4  # 2 keywords × 2 dates
        # First keyword, first date
        ph = result["position_history"][0]
        assert ph["phrase"] == "seo tools"
        assert ph["date"] == "2026-03-01"
        assert ph["position"] == 5

    def test_empty_rows_skipped(self):
        path = _write_xlsx([
            ["Запросы", "Частота"],
            ["seo", "100"],
            ["", ""],
            ["tools", "200"],
        ])
        result = parse_topvisor(path)
        assert result["row_count"] == 2

    def test_csv_format(self):
        path = _write_csv([
            ["Запросы", "Частота", "01.03.2026"],
            ["seo", "100", "5"],
        ])
        result = parse_topvisor(path)
        assert result["row_count"] == 1
        assert result["keywords"][0]["frequency"] == 100

    def test_empty_file(self):
        path = _write_xlsx([])
        result = parse_topvisor(path)
        assert result["row_count"] == 0


# ---------------------------------------------------------------------------
# Key Collector parser
# ---------------------------------------------------------------------------


class TestKeyCollectorParser:
    def test_basic_with_groups(self):
        path = _write_xlsx([
            ["Фраза", "Родительская группа", "Частота [YW]", "Позиция [Yandex]", "URL позиции [Yandex]"],
            ["купить дом", "Коммерческие", "500", "3", "https://site.com/buy"],
            ["строительство", "Информационные", "1200", "15", "https://site.com/build"],
        ])
        result = parse_keycollector(path)
        assert result["row_count"] == 2
        assert result["groups"] == ["Информационные", "Коммерческие"]
        kw0 = result["keywords"][0]
        assert kw0["phrase"] == "купить дом"
        assert kw0["group_name"] == "Коммерческие"
        assert kw0["frequency"] == 500
        assert kw0["positions"][0]["engine"] == "yandex"
        assert kw0["positions"][0]["position"] == 3
        assert kw0["positions"][0]["url"] == "https://site.com/buy"

    def test_both_engines(self):
        path = _write_xlsx([
            ["Фраза", "Позиция [Yandex]", "URL позиции [Yandex]", "Позиция [Google]", "URL позиции [Google]"],
            ["seo", "5", "https://a.com", "3", "https://b.com"],
        ])
        result = parse_keycollector(path)
        kw = result["keywords"][0]
        assert len(kw["positions"]) == 2
        engines = {p["engine"] for p in kw["positions"]}
        assert engines == {"yandex", "google"}

    def test_no_group_column(self):
        path = _write_xlsx([
            ["Фраза", "Частота"],
            ["seo tools", "1000"],
        ])
        result = parse_keycollector(path)
        assert result["keywords"][0]["group_name"] is None
        assert result["groups"] == []

    def test_empty_rows_skipped(self):
        path = _write_xlsx([
            ["Фраза"],
            ["seo"],
            [""],
            ["tools"],
        ])
        result = parse_keycollector(path)
        assert result["row_count"] == 2


# ---------------------------------------------------------------------------
# Screaming Frog parser
# ---------------------------------------------------------------------------


class TestScreamingFrogParser:
    def test_basic_pages(self):
        path = _write_xlsx([
            ["Address", "Status Code", "Title 1", "H1-1", "Word Count", "Inlinks"],
            ["https://site.com/", "200", "Home", "Welcome", "500", "10"],
            ["https://site.com/about", "200", "About", "About Us", "300", "5"],
            ["https://site.com/old", "404", "", "", "0", "2"],
        ])
        result = parse_screaming_frog(path)
        assert result["row_count"] == 3
        assert result["summary"]["total"] == 3
        assert result["summary"]["status_distribution"]["200"] == 2
        assert result["summary"]["status_distribution"]["404"] == 1
        assert result["summary"]["with_title"] == 2
        assert result["summary"]["with_h1"] == 2
        assert result["summary"]["avg_word_count"] == 266.7  # (500+300+0)/3

    def test_page_fields(self):
        path = _write_xlsx([
            ["Address", "Status Code", "Title 1", "H1-1", "Word Count", "Inlinks"],
            ["https://site.com/page", "301", "Redirect", "", "0", "3"],
        ])
        result = parse_screaming_frog(path)
        page = result["pages"][0]
        assert page["url"] == "https://site.com/page"
        assert page["http_status"] == 301
        assert page["title"] == "Redirect"
        assert page["h1"] is None  # empty string → None
        assert page["inlinks"] == 3

    def test_non_url_rows_skipped(self):
        path = _write_xlsx([
            ["Address", "Status Code"],
            ["https://site.com/", "200"],
            ["not-a-url", "200"],
            ["javascript:void(0)", ""],
        ])
        result = parse_screaming_frog(path)
        assert result["row_count"] == 1

    def test_empty_file(self):
        path = _write_xlsx([])
        result = parse_screaming_frog(path)
        assert result["row_count"] == 0

    def test_csv_format(self):
        path = _write_csv([
            ["Address", "Status Code", "Title 1"],
            ["https://site.com/", "200", "Home"],
        ])
        result = parse_screaming_frog(path)
        assert result["row_count"] == 1
