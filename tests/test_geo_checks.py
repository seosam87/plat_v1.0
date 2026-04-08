"""Unit tests for GEO readiness check functions.

Tests cover all 9 check functions, score computation, and weight validation.
These are pure functions -- no async, no DB.
"""
import pytest

from app.services.llm.geo_checks import (
    GEO_WEIGHTS,
    check_geo_faq_schema,
    check_geo_article_author,
    check_geo_breadcrumbs,
    check_geo_answer_first,
    check_geo_update_date,
    check_geo_h2_questions,
    check_geo_external_citations,
    check_geo_ai_robots,
    check_geo_summary_block,
    compute_geo_score,
)


# ---- GEO_WEIGHTS validation ----


def test_geo_weights_sum_to_100():
    assert sum(GEO_WEIGHTS.values()) == 100


def test_geo_weights_has_all_9_keys():
    expected = {
        "geo_faq_schema",
        "geo_article_author",
        "geo_breadcrumbs",
        "geo_answer_first",
        "geo_update_date",
        "geo_h2_questions",
        "geo_external_citations",
        "geo_ai_robots",
        "geo_summary_block",
    }
    assert set(GEO_WEIGHTS.keys()) == expected


# ---- geo_faq_schema ----

_FAQ_HTML_INLINE = """
<html><head>
<script type="application/ld+json">
{"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": "Q?", "acceptedAnswer": {"@type": "Answer", "text": "A."}}]}
</script>
</head><body><h1>Title</h1></body></html>
"""

_FAQ_HTML_GRAPH = """
<html><head>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [{"@type": "FAQPage", "mainEntity": []}]}
</script>
</head><body></body></html>
"""

_NO_FAQ_HTML = """
<html><head><script type="application/ld+json">{"@type": "Article"}</script></head>
<body><h1>No FAQ here</h1></body></html>
"""


def test_geo_faq_schema_present():
    assert check_geo_faq_schema(_FAQ_HTML_INLINE, {}) is True


def test_geo_faq_schema_in_graph():
    assert check_geo_faq_schema(_FAQ_HTML_GRAPH, {}) is True


def test_geo_faq_schema_absent():
    assert check_geo_faq_schema(_NO_FAQ_HTML, {}) is False


def test_geo_faq_schema_no_scripts():
    assert check_geo_faq_schema("<html><body><p>plain</p></body></html>", {}) is False


# ---- geo_article_author ----

_ARTICLE_AUTHOR_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "Article", "author": {"@type": "Person", "name": "Jane Doe"}}
</script>
</head><body></body></html>
"""

_ARTICLE_NO_AUTHOR_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "Article", "headline": "Title"}
</script>
</head><body></body></html>
"""

_ARTICLE_AUTHOR_LIST_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "Article", "author": [{"@type": "Person", "name": "A"}, {"@type": "Person", "name": "B"}]}
</script>
</head><body></body></html>
"""


def test_geo_article_author_present():
    assert check_geo_article_author(_ARTICLE_AUTHOR_HTML, {}) is True


def test_geo_article_author_list():
    assert check_geo_article_author(_ARTICLE_AUTHOR_LIST_HTML, {}) is True


def test_geo_article_author_no_author():
    assert check_geo_article_author(_ARTICLE_NO_AUTHOR_HTML, {}) is False


def test_geo_article_author_no_article():
    assert check_geo_article_author(_NO_FAQ_HTML, {}) is False


# ---- geo_breadcrumbs ----

_BREADCRUMB_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "BreadcrumbList", "itemListElement": []}
</script>
</head><body></body></html>
"""


def test_geo_breadcrumbs_present():
    assert check_geo_breadcrumbs(_BREADCRUMB_HTML, {}) is True


def test_geo_breadcrumbs_absent():
    assert check_geo_breadcrumbs(_NO_FAQ_HTML, {}) is False


# ---- geo_answer_first ----

_ANSWER_FIRST_HTML = """
<html><body>
<h1>What is Python?</h1>
<p>Python is a programming language that provides a simple syntax.</p>
</body></html>
"""

_ANSWER_FIRST_RU_HTML = """
<html><body>
<h1>Что такое Python?</h1>
<p>Python является языком программирования для задач автоматизации.</p>
</body></html>
"""

_ANSWER_FIRST_TOO_LONG_HTML = """
<html><body>
<h1>Long article</h1>
<p>This is a very long paragraph that goes on and on and contains way too many words
to pass the sixty word limit check and it just keeps going and going
without stopping because we need it to be over sixty words to fail the test
and this should definitely be over sixty words total right here.</p>
</body></html>
"""

_ANSWER_FIRST_NO_H1_HTML = """
<html><body>
<h2>Subtitle</h2>
<p>Text without h1.</p>
</body></html>
"""

_ANSWER_FIRST_NO_VERB_HTML = """
<html><body>
<h1>Title</h1>
<p>Short text without typical verbs.</p>
</body></html>
"""


def test_geo_answer_first_en_verb():
    assert check_geo_answer_first(_ANSWER_FIRST_HTML, {}) is True


def test_geo_answer_first_ru_verb():
    assert check_geo_answer_first(_ANSWER_FIRST_RU_HTML, {}) is True


def test_geo_answer_first_too_long():
    assert check_geo_answer_first(_ANSWER_FIRST_TOO_LONG_HTML, {}) is False


def test_geo_answer_first_no_h1():
    assert check_geo_answer_first(_ANSWER_FIRST_NO_H1_HTML, {}) is False


def test_geo_answer_first_no_verb():
    assert check_geo_answer_first(_ANSWER_FIRST_NO_VERB_HTML, {}) is False


# ---- geo_update_date ----

_UPDATE_DATE_TIME_HTML = """
<html><body>
<time datetime="2025-01-15T10:00:00Z">January 15, 2025</time>
</body></html>
"""

_UPDATE_DATE_JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "Article", "dateModified": "2025-01-15"}
</script>
</head><body></body></html>
"""

_NO_UPDATE_DATE_HTML = """
<html><body><p>No date on this page.</p></body></html>
"""


def test_geo_update_date_time_tag():
    assert check_geo_update_date(_UPDATE_DATE_TIME_HTML, {}) is True


def test_geo_update_date_jsonld():
    assert check_geo_update_date(_UPDATE_DATE_JSONLD_HTML, {}) is True


def test_geo_update_date_absent():
    assert check_geo_update_date(_NO_UPDATE_DATE_HTML, {}) is False


# ---- geo_h2_questions ----

_H2_QUESTIONS_HTML = """
<html><body>
<h2>What is SEO?</h2>
<h2>How does it work?</h2>
<h2>Why is it important?</h2>
<h2>Regular heading</h2>
</body></html>
"""

_H2_QUESTIONS_RU_HTML = """
<html><body>
<h2>Что такое SEO?</h2>
<h2>Как это работает?</h2>
<h2>Обычный заголовок</h2>
<h2>Ещё один обычный</h2>
</body></html>
"""

_H2_NO_QUESTIONS_HTML = """
<html><body>
<h2>Introduction</h2>
<h2>Conclusion</h2>
<h2>Summary</h2>
</body></html>
"""

_H2_NO_H2S_HTML = """
<html><body>
<h1>Title</h1>
<p>Content without H2s.</p>
</body></html>
"""


def test_geo_h2_questions_majority():
    assert check_geo_h2_questions(_H2_QUESTIONS_HTML, {}) is True


def test_geo_h2_questions_ru():
    # 2 out of 4 = 50%, which is >= 30%
    assert check_geo_h2_questions(_H2_QUESTIONS_RU_HTML, {}) is True


def test_geo_h2_questions_none():
    assert check_geo_h2_questions(_H2_NO_QUESTIONS_HTML, {}) is False


def test_geo_h2_questions_no_h2s():
    assert check_geo_h2_questions(_H2_NO_H2S_HTML, {}) is False


# ---- geo_external_citations ----

_EXT_CITATIONS_HTML = """
<html><body>
<p>See <a href="https://en.wikipedia.org/wiki/Python">Wikipedia</a> and
<a href="https://www.bbc.com/news/tech">BBC</a> for more info.</p>
</body></html>
"""

_EXT_CITATIONS_GOV_EDU_HTML = """
<html><body>
<a href="https://data.gov/some-dataset">Gov data</a>
<a href="https://www.harvard.edu/research">Harvard</a>
</body></html>
"""

_EXT_CITATIONS_ONE_HTML = """
<html><body>
<a href="https://en.wikipedia.org/wiki/Python">Wikipedia only</a>
</body></html>
"""

_EXT_CITATIONS_INTERNAL_HTML = """
<html><body>
<a href="/page1">Internal 1</a>
<a href="/page2">Internal 2</a>
<a href="https://example.com/page">External non-whitelist</a>
</body></html>
"""


def test_geo_external_citations_two_whitelist():
    assert check_geo_external_citations(_EXT_CITATIONS_HTML, {}) is True


def test_geo_external_citations_gov_edu():
    assert check_geo_external_citations(_EXT_CITATIONS_GOV_EDU_HTML, {}) is True


def test_geo_external_citations_only_one():
    assert check_geo_external_citations(_EXT_CITATIONS_ONE_HTML, {}) is False


def test_geo_external_citations_no_whitelist():
    assert check_geo_external_citations(_EXT_CITATIONS_INTERNAL_HTML, {}) is False


# ---- geo_ai_robots ----

_ROBOTS_NOT_BLOCKING = "User-agent: *\nAllow: /"

_ROBOTS_BLOCKING_GPTBOT = "User-agent: GPTBot\nDisallow: /"

_ROBOTS_BLOCKING_CLAUDE = "User-agent: ClaudeBot\nDisallow: /"

_ROBOTS_PARTIAL_BLOCK = """User-agent: *
Allow: /

User-agent: GPTBot
Disallow: /
"""

_ROBOTS_EMPTY = ""


def test_geo_ai_robots_not_blocking():
    assert check_geo_ai_robots("", {"robots_txt": _ROBOTS_NOT_BLOCKING}) is True


def test_geo_ai_robots_empty_robots():
    assert check_geo_ai_robots("", {"robots_txt": _ROBOTS_EMPTY}) is True


def test_geo_ai_robots_blocking_gptbot():
    assert check_geo_ai_robots("", {"robots_txt": _ROBOTS_BLOCKING_GPTBOT}) is False


def test_geo_ai_robots_blocking_claudebot():
    assert check_geo_ai_robots("", {"robots_txt": _ROBOTS_BLOCKING_CLAUDE}) is False


def test_geo_ai_robots_partial_block():
    assert check_geo_ai_robots("", {"robots_txt": _ROBOTS_PARTIAL_BLOCK}) is False


def test_geo_ai_robots_no_robots_txt_key():
    # Missing robots_txt key in page_data -> treat as empty -> not blocked -> True
    assert check_geo_ai_robots("", {}) is True


# ---- geo_summary_block ----

_SUMMARY_CLASS_HTML = """
<html><body>
<h1>Title</h1>
<div class="summary">TL;DR: This article explains X.</div>
<h2>Introduction</h2>
</body></html>
"""

_TLDR_ID_HTML = """
<html><body>
<h1>Title</h1>
<div id="tldr"><p>Quick summary here.</p></div>
<h2>Section</h2>
</body></html>
"""

_KEY_TAKEAWAYS_HTML = """
<html><body>
<h1>Title</h1>
<section class="key-takeaways"><ul><li>Point 1</li></ul></section>
<h2>Details</h2>
</body></html>
"""

_SUMMARY_AFTER_H2_HTML = """
<html><body>
<h1>Title</h1>
<h2>Introduction</h2>
<div class="summary">Too late: after H2.</div>
</body></html>
"""

_NO_SUMMARY_HTML = """
<html><body>
<h1>Title</h1>
<p>Regular paragraph.</p>
<h2>Section</h2>
</body></html>
"""


def test_geo_summary_block_class():
    assert check_geo_summary_block(_SUMMARY_CLASS_HTML, {}) is True


def test_geo_summary_block_tldr_id():
    assert check_geo_summary_block(_TLDR_ID_HTML, {}) is True


def test_geo_summary_block_key_takeaways():
    assert check_geo_summary_block(_KEY_TAKEAWAYS_HTML, {}) is True


def test_geo_summary_block_after_h2():
    assert check_geo_summary_block(_SUMMARY_AFTER_H2_HTML, {}) is False


def test_geo_summary_block_absent():
    assert check_geo_summary_block(_NO_SUMMARY_HTML, {}) is False


# ---- compute_geo_score ----


def test_compute_geo_score_all_pass():
    results = [
        {"check_code": code, "status": "pass"} for code in GEO_WEIGHTS.keys()
    ]
    assert compute_geo_score(results) == 100


def test_compute_geo_score_none_pass():
    results = [
        {"check_code": code, "status": "fail"} for code in GEO_WEIGHTS.keys()
    ]
    assert compute_geo_score(results) == 0


def test_compute_geo_score_single_faq():
    results = [{"check_code": "geo_faq_schema", "status": "pass"}]
    assert compute_geo_score(results) == 15


def test_compute_geo_score_faq_and_author():
    results = [
        {"check_code": "geo_faq_schema", "status": "pass"},
        {"check_code": "geo_article_author", "status": "pass"},
    ]
    assert compute_geo_score(results) == 30


def test_compute_geo_score_ignores_non_geo():
    results = [
        {"check_code": "toc_present", "status": "pass"},
        {"check_code": "geo_faq_schema", "status": "pass"},
    ]
    assert compute_geo_score(results) == 15


def test_compute_geo_score_warning_not_counted():
    results = [
        {"check_code": "geo_faq_schema", "status": "warning"},
    ]
    assert compute_geo_score(results) == 0
