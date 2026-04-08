"""GEO Readiness check functions for AI/LLM engine optimisation.

9 rule-based DOM checks using BeautifulSoup + regex only.
No ML/NER — per D-05 in Phase 16 CONTEXT.

Each check function has signature:
    check_geo_*(html: str, page_data: dict) -> bool

The GEO_CHECK_RUNNERS dict maps check codes to check functions for use
by content_audit_service._CHECK_RUNNERS.
"""
from __future__ import annotations

import json
import re
from typing import Callable

from bs4 import BeautifulSoup


# ---- Constants ----

GEO_WEIGHTS: dict[str, int] = {
    "geo_faq_schema": 15,
    "geo_article_author": 15,
    "geo_breadcrumbs": 10,
    "geo_answer_first": 15,
    "geo_update_date": 10,
    "geo_h2_questions": 10,
    "geo_external_citations": 10,
    "geo_ai_robots": 10,
    "geo_summary_block": 5,
}
# sum = 100 (validated by tests)

AI_BOT_USER_AGENTS = [
    "GPTBot",
    "ClaudeBot",
    "PerplexityBot",
    "OAI-SearchBot",
    "Google-Extended",
]

AUTHORITATIVE_DOMAINS = frozenset({
    ".gov",
    ".edu",
    "wikipedia.org",
    "reuters.com",
    "bbc.com",
    "nytimes.com",
    "nature.com",
    "who.int",
})

QUESTION_PREFIXES = (
    "who", "what", "how", "why", "when", "where",
    "что", "как", "почему", "когда", "где", "кто", "зачем",
)

# Verb heuristic — Russian and English common verbs (from RESEARCH.md Pattern 1)
_VERB_RE = re.compile(
    r"\b(является|позволяет|помогает|обеспечивает|представляет|"
    r"is|are|was|were|can|will|has|have|provides|helps|allows)\b",
    re.IGNORECASE,
)

# Summary/TL;DR block id/class pattern
_SUMMARY_PATTERN_RE = re.compile(
    r"\b(summary|tldr|tl-dr|tl_dr|key[-_]takeaways|key_takeaways)\b",
    re.IGNORECASE,
)

# Robots.txt block detection: User-agent line followed by Disallow: /
_ROBOTS_BLOCK_RE = re.compile(
    r"User-agent:\s*({bots})\s*\n(?:[^\n]*\n)*?Disallow:\s*/(?:\s|$)".format(
        bots="|".join(re.escape(b) for b in AI_BOT_USER_AGENTS)
    ),
    re.IGNORECASE | re.MULTILINE,
)


def _parse_ld_json(html: str) -> list[dict]:
    """Extract all JSON-LD objects from HTML as a flat list of dicts."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(data, list):
            results.extend(data)
        elif isinstance(data, dict):
            # Expand @graph if present
            graph = data.get("@graph")
            if graph and isinstance(graph, list):
                results.extend(graph)
                # Also keep the wrapper object itself in case it has a top-level @type
            results.append(data)
    return results


# ---- Check 1: FAQPage JSON-LD ----

def check_geo_faq_schema(html: str, page_data: dict) -> bool:
    """True if FAQPage JSON-LD schema is present (incl. inside @graph)."""
    for obj in _parse_ld_json(html):
        if obj.get("@type") == "FAQPage":
            return True
    return False


# ---- Check 2: Article + Author/Person schema ----

def check_geo_article_author(html: str, page_data: dict) -> bool:
    """True if Article schema AND author with @type Person/Author is present."""
    objects = _parse_ld_json(html)
    has_article = False
    has_author = False
    for obj in objects:
        if obj.get("@type") == "Article":
            has_article = True
            # Check author field on this article object
            author = obj.get("author")
            if author:
                if isinstance(author, list):
                    for a in author:
                        if isinstance(a, dict) and a.get("@type") in ("Person", "Author"):
                            has_author = True
                elif isinstance(author, dict) and author.get("@type") in ("Person", "Author"):
                    has_author = True
    return has_article and has_author


# ---- Check 3: BreadcrumbList schema ----

def check_geo_breadcrumbs(html: str, page_data: dict) -> bool:
    """True if BreadcrumbList JSON-LD schema is present."""
    for obj in _parse_ld_json(html):
        if obj.get("@type") == "BreadcrumbList":
            return True
    return False


# ---- Check 4: Answer-first paragraph ----

def check_geo_answer_first(html: str, page_data: dict) -> bool:
    """True if first <p> after <h1> has ≤60 words and contains a verb.

    Implements the direct-answer heuristic for GEO readiness (D-05 #4).
    Uses verb regex from RESEARCH.md Pattern 1 verbatim.
    """
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if not h1:
        return False

    # Walk siblings to find first <p> before any h2/h3
    el = h1.find_next_sibling()
    while el and el.name not in ("p", "h2", "h3"):
        el = el.find_next_sibling()

    if not el or el.name != "p":
        return False

    text = el.get_text(strip=True)
    words = text.split()
    if len(words) > 60:
        return False

    return bool(_VERB_RE.search(text))


# ---- Check 5: Update date ----

def check_geo_update_date(html: str, page_data: dict) -> bool:
    """True if <time datetime> tag or dateModified in JSON-LD is present."""
    soup = BeautifulSoup(html, "lxml")
    # Check for <time datetime="..."> tag
    if soup.find("time", attrs={"datetime": True}):
        return True
    # Check JSON-LD for dateModified
    for obj in _parse_ld_json(html):
        if obj.get("dateModified"):
            return True
    return False


# ---- Check 6: H2 questions ----

def check_geo_h2_questions(html: str, page_data: dict) -> bool:
    """True if ≥30% of H2 headings start with a question word (EN/RU)."""
    soup = BeautifulSoup(html, "lxml")
    h2s = soup.find_all("h2")
    if not h2s:
        return False

    question_count = 0
    for h2 in h2s:
        text = h2.get_text(strip=True).lower()
        if any(text.startswith(prefix) for prefix in QUESTION_PREFIXES):
            question_count += 1

    return (question_count / len(h2s)) >= 0.3


# ---- Check 7: External citations ----

def check_geo_external_citations(html: str, page_data: dict) -> bool:
    """True if ≥2 outbound links point to whitelist authoritative domains."""
    soup = BeautifulSoup(html, "lxml")
    count = 0
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith(("http://", "https://")):
            continue
        for domain in AUTHORITATIVE_DOMAINS:
            if domain.startswith("."):
                # TLD-based match: domain ends with .gov or .edu
                # Extract hostname from href
                try:
                    from urllib.parse import urlparse
                    hostname = urlparse(href).hostname or ""
                    if hostname.endswith(domain):
                        count += 1
                        break
                except Exception:
                    continue
            else:
                if domain in href:
                    count += 1
                    break

    return count >= 2


# ---- Check 8: AI robots ----

def check_geo_ai_robots(html: str, page_data: dict) -> bool:
    """True if robots.txt does NOT block known AI bot user agents.

    Returns True (not blocked) when:
    - robots_txt is missing or empty (safe default)
    - robots_txt has no Disallow: / directive for any AI bot

    Per D-05 #8: checks GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot, Google-Extended.

    NOTE: This check uses page_data["robots_txt"] — a pre-fetched string.
    Actual robots.txt fetching is deferred to Phase 16 backlog (robots fetch at crawl time).
    """
    robots_txt = page_data.get("robots_txt", "") or ""
    if not robots_txt.strip():
        return True  # No robots.txt = not blocked

    return not bool(_ROBOTS_BLOCK_RE.search(robots_txt))


# ---- Check 9: Summary/TL;DR block ----

def check_geo_summary_block(html: str, page_data: dict) -> bool:
    """True if a summary/tldr/key-takeaways element exists before the first H2.

    Checks class and id attributes for matching patterns.
    """
    soup = BeautifulSoup(html, "lxml")
    first_h2 = soup.find("h2")

    def _has_summary_attrs(tag) -> bool:
        """Check if tag has class or id matching summary/tldr/key-takeaways pattern."""
        classes = " ".join(tag.get("class", []))
        tag_id = tag.get("id", "")
        return bool(
            _SUMMARY_PATTERN_RE.search(classes) or _SUMMARY_PATTERN_RE.search(tag_id)
        )

    if first_h2 is None:
        # No H2 — search entire body
        body = soup.find("body") or soup
        for tag in body.find_all(True):
            if _has_summary_attrs(tag):
                return True
        return False

    # Check all elements that appear before first_h2 in document order
    for tag in soup.find_all(True):
        if tag == first_h2:
            break
        if _has_summary_attrs(tag):
            return True
    return False


# ---- Score computation ----

def compute_geo_score(results: list[dict]) -> int:
    """Sum weights of passed geo_* checks. Returns 0–100.

    Args:
        results: List of dicts with keys check_code and status.
                 Status must be "pass" for the weight to be counted.
    """
    return sum(
        GEO_WEIGHTS.get(r["check_code"], 0)
        for r in results
        if r["check_code"].startswith("geo_") and r["status"] == "pass"
    )


# ---- Runner registry ----

GEO_CHECK_RUNNERS: dict[str, Callable] = {
    "geo_faq_schema": check_geo_faq_schema,
    "geo_article_author": check_geo_article_author,
    "geo_breadcrumbs": check_geo_breadcrumbs,
    "geo_answer_first": check_geo_answer_first,
    "geo_update_date": check_geo_update_date,
    "geo_h2_questions": check_geo_h2_questions,
    "geo_external_citations": check_geo_external_citations,
    "geo_ai_robots": check_geo_ai_robots,
    "geo_summary_block": check_geo_summary_block,
}
