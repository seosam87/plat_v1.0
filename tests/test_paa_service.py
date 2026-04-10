"""Unit tests for PAA extraction service.

Tests cover extraction of "Частые вопросы" and "Похожие запросы" blocks
from Yandex SERP HTML using BeautifulSoup4.  All tests use mock HTML
snippets — no network calls required.
"""
from __future__ import annotations

import pytest

from app.services.paa_service import BLOCK_FREQUENT, BLOCK_RELATED, extract_paa_blocks, extract_paa_for_phrase


# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

_HTML_FREQUENT_ONLY = """
<html><body>
  <div class="serp-list">
    <div>
      <h3>Частые вопросы</h3>
      <ul>
        <li><a href="#">Как выбрать телефон для работы?</a></li>
        <li><a href="#">Какой телефон лучше для фотографий?</a></li>
        <li><a href="#">Сколько стоит хороший смартфон?</a></li>
      </ul>
    </div>
  </div>
</body></html>
"""

_HTML_RELATED_ONLY = """
<html><body>
  <div class="serp-list">
    <div>
      <div>Похожие запросы</div>
      <ul>
        <li><a href="#">смартфон до 30000 рублей</a></li>
        <li><a href="#">лучший телефон 2024 года</a></li>
        <li><a href="#">рейтинг смартфонов по соотношению цена-качество</a></li>
      </ul>
    </div>
  </div>
</body></html>
"""

_HTML_BOTH_BLOCKS = """
<html><body>
  <div class="serp-list">
    <section>
      <h2>Частые вопросы</h2>
      <ul>
        <li>Как настроить WiFi на смартфоне?</li>
        <li>Почему телефон греется при зарядке?</li>
      </ul>
    </section>
    <section>
      <h3>Похожие запросы</h3>
      <ul>
        <li>как заряжать смартфон правильно</li>
        <li>почему телефон быстро разряжается</li>
      </ul>
    </section>
  </div>
</body></html>
"""

_HTML_BOTH_CASE_INSENSITIVE = """
<html><body>
  <div>
    <h2>ЧАСТЫЕ ВОПРОСЫ</h2>
    <ul>
      <li>Что такое операционная система Android?</li>
    </ul>
    <h2>ПОХОЖИЕ ЗАПРОСЫ</h2>
    <ul>
      <li>особенности операционных систем для смартфонов</li>
    </ul>
  </div>
</body></html>
"""

_HTML_DUPLICATE_QUESTIONS = """
<html><body>
  <div>
    <h3>Частые вопросы</h3>
    <ul>
      <li>Как выбрать телефон для работы?</li>
      <li>Как выбрать телефон для работы?</li>
      <li>Сколько стоит хороший смартфон?</li>
    </ul>
  </div>
</body></html>
"""

_HTML_EMPTY = ""
_HTML_NO_PAA = "<html><body><p>Обычная страница без блоков PAA.</p></body></html>"


# ---------------------------------------------------------------------------
# Tests: extract_paa_blocks
# ---------------------------------------------------------------------------


def test_extract_paa_blocks_finds_frequent_questions():
    """Should extract questions from 'Частые вопросы' heading with list items."""
    results = extract_paa_blocks(_HTML_FREQUENT_ONLY)

    assert len(results) > 0, "Expected at least one PAA result"
    source_blocks = {r["source_block"] for r in results}
    assert BLOCK_FREQUENT in source_blocks, f"Expected '{BLOCK_FREQUENT}' in source_blocks"

    questions = [r["question"] for r in results]
    # At least one question should mention relevant content
    assert any("телефон" in q.lower() for q in questions), "Expected question about телефон"


def test_extract_paa_blocks_finds_related_queries():
    """Should extract questions from 'Похожие запросы' heading."""
    results = extract_paa_blocks(_HTML_RELATED_ONLY)

    assert len(results) > 0, "Expected at least one PAA result"
    source_blocks = {r["source_block"] for r in results}
    assert BLOCK_RELATED in source_blocks, f"Expected '{BLOCK_RELATED}' in source_blocks"


def test_extract_paa_blocks_both_blocks():
    """Should extract from BOTH 'Частые вопросы' and 'Похожие запросы' blocks."""
    results = extract_paa_blocks(_HTML_BOTH_BLOCKS)

    assert len(results) >= 2, "Expected results from at least 2 blocks"
    source_blocks = {r["source_block"] for r in results}
    assert BLOCK_FREQUENT in source_blocks, f"Expected '{BLOCK_FREQUENT}'"
    assert BLOCK_RELATED in source_blocks, f"Expected '{BLOCK_RELATED}'"


def test_extract_paa_blocks_case_insensitive():
    """Should match headings regardless of case (ЧАСТЫЕ ВОПРОСЫ vs частые вопросы)."""
    results = extract_paa_blocks(_HTML_BOTH_CASE_INSENSITIVE)

    source_blocks = {r["source_block"] for r in results}
    assert BLOCK_FREQUENT in source_blocks, "Case-insensitive match for 'ЧАСТЫЕ ВОПРОСЫ' failed"
    assert BLOCK_RELATED in source_blocks, "Case-insensitive match for 'ПОХОЖИЕ ЗАПРОСЫ' failed"


def test_extract_paa_blocks_empty_html():
    """Should return empty list for empty HTML string."""
    results = extract_paa_blocks(_HTML_EMPTY)
    assert results == [], f"Expected empty list for empty HTML, got: {results}"


def test_extract_paa_blocks_no_paa_html():
    """Should return empty list if no PAA blocks are present."""
    results = extract_paa_blocks(_HTML_NO_PAA)
    assert results == [], f"Expected empty list for HTML without PAA blocks, got: {results}"


def test_extract_paa_blocks_deduplication():
    """Duplicate question texts should appear only once in output."""
    results = extract_paa_blocks(_HTML_DUPLICATE_QUESTIONS)

    questions = [r["question"] for r in results]
    unique_questions = list(dict.fromkeys(q.lower() for q in questions))
    assert len(questions) == len(unique_questions), (
        f"Expected deduplicated results, got duplicates: {questions}"
    )


def test_extract_paa_blocks_result_structure():
    """Each result dict should have 'question' and 'source_block' keys."""
    results = extract_paa_blocks(_HTML_BOTH_BLOCKS)

    for r in results:
        assert "question" in r, f"Missing 'question' key in result: {r}"
        assert "source_block" in r, f"Missing 'source_block' key in result: {r}"
        assert r["source_block"] in (BLOCK_FREQUENT, BLOCK_RELATED), (
            f"Unexpected source_block value: {r['source_block']}"
        )
        assert len(r["question"]) >= 10, f"Question too short: '{r['question']}'"


# ---------------------------------------------------------------------------
# Tests: extract_paa_for_phrase
# ---------------------------------------------------------------------------


def test_extract_paa_for_phrase_prepends_phrase():
    """Each result should have 'phrase', 'question', and 'source_block' keys."""
    results = extract_paa_for_phrase("купить телефон", _HTML_FREQUENT_ONLY)

    for r in results:
        assert "phrase" in r, f"Missing 'phrase' key in result: {r}"
        assert r["phrase"] == "купить телефон"
        assert "question" in r
        assert "source_block" in r


def test_extract_paa_for_phrase_empty_html():
    """Should return empty list when HTML is empty."""
    results = extract_paa_for_phrase("купить телефон", "")
    assert results == []
