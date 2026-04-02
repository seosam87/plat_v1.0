"""Tests for gap service: scoring, parser, formula."""
from app.parsers.gap_parser import parse_gap_file
from app.services.gap_service import SCORE_FORMULA_DESCRIPTION, compute_potential_score


# ---- Scoring tests ----


def test_potential_score_top3():
    assert compute_potential_score(1000, 2) == 1000.0


def test_potential_score_top10():
    assert compute_potential_score(500, 7) == 350.0


def test_potential_score_top30():
    assert compute_potential_score(200, 25) == 60.0


def test_potential_score_beyond30():
    assert compute_potential_score(100, 50) == 10.0


def test_potential_score_no_data():
    assert compute_potential_score(None, 5) == 0.0
    assert compute_potential_score(100, None) == 0.0
    assert compute_potential_score(None, None) == 0.0


# ---- Parser tests ----


def test_parse_keysso_format():
    rows = [
        ["Запрос", "Частотность", "Позиция"],
        ["seo продвижение", "1000", "3"],
        ["аудит сайта", "500", "7"],
    ]
    result = parse_gap_file(rows)
    assert len(result) == 2
    assert result[0]["phrase"] == "seo продвижение"
    assert result[0]["frequency"] == 1000
    assert result[0]["position"] == 3


def test_parse_topvisor_format():
    rows = [
        ["Ключ", "Частота", "Позиция"],
        ["раскрутка", "200", "15"],
    ]
    result = parse_gap_file(rows)
    assert len(result) == 1
    assert result[0]["phrase"] == "раскрутка"


def test_parse_generic_english():
    rows = [
        ["keyword", "frequency", "position"],
        ["seo services", "800", "5"],
    ]
    result = parse_gap_file(rows)
    assert len(result) == 1
    assert result[0]["phrase"] == "seo services"
    assert result[0]["frequency"] == 800


def test_parse_empty_rows():
    assert parse_gap_file([]) == []
    assert parse_gap_file([["header"]]) == []


# ---- Formula description ----


def test_score_formula_description_exists():
    assert len(SCORE_FORMULA_DESCRIPTION) > 50
    assert "Потенциал" in SCORE_FORMULA_DESCRIPTION
    assert "TOP-3" in SCORE_FORMULA_DESCRIPTION
