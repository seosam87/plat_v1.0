"""PAA (People Also Ask) extraction service.

Extracts "Частые вопросы" and "Похожие запросы" blocks from Yandex SERP HTML
fetched via XMLProxy. Uses BeautifulSoup4 with lxml parser.

Per D-07: lxml parser.
Per D-08: first level only, no recursive expansion.
Per D-10: extract BOTH block types.
Per Research Pitfall 3: text-content matching, not class selectors.
"""
from __future__ import annotations

from bs4 import BeautifulSoup, Tag
from loguru import logger

# Block label constants (canonical lowercase form)
BLOCK_FREQUENT = "частые вопросы"
BLOCK_RELATED = "похожие запросы"

_BLOCK_KEYWORDS: dict[str, str] = {
    BLOCK_FREQUENT: BLOCK_FREQUENT,
    BLOCK_RELATED: BLOCK_RELATED,
}

# Minimum text length to consider a candidate question (chars)
_MIN_QUESTION_LEN = 10

# Heading-level tags that can mark the start of a PAA block
_HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5"]

# Container tags used to group PAA items
_ITEM_TAGS = ["li", "a", "span"]


def _extract_items_from_next_siblings(heading_tag: Tag, source_block: str, seen: set[str]) -> list[dict]:
    """Walk the heading's next siblings to find PAA items.

    This avoids picking up items from unrelated sibling headings by stopping
    at the next heading-level element or the end of the parent.
    """
    results: list[dict] = []
    for sibling in heading_tag.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        # Stop at next heading
        if sibling.name in _HEADING_TAGS:
            break
        # Recurse into the sibling to find li/a items
        for item in sibling.find_all(_ITEM_TAGS):
            text = item.get_text(separator=" ", strip=True)
            if len(text) < _MIN_QUESTION_LEN:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append({"question": text, "source_block": source_block})
    return results


def extract_paa_blocks(html: str) -> list[dict]:
    """Extract PAA questions from a Yandex SERP HTML page.

    Searches for heading-level tags whose own text content (not descendants)
    contains "частые вопросы" or "похожие запросы" (case-insensitive) and
    then extracts li/a items from the heading's immediate next siblings.

    Also tries data-fast-name attribute selectors as a fallback.

    Args:
        html: Full Yandex SERP HTML returned by XMLProxy.

    Returns:
        List of dicts: ``{"question": str, "source_block": str}``.
        Duplicates (same question text, case-insensitive) are removed.
    """
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []
    seen: set[str] = set()

    # -----------------------------------------------------------------------
    # Strategy 1: heading-only text matching + next-sibling traversal
    #
    # We use `tag.string` (direct text only) or the tag's own text stripped of
    # whitespace for heading tags to avoid matching parent containers that
    # aggregate text from multiple blocks.
    # -----------------------------------------------------------------------
    all_tags = soup.find_all(True)  # all elements
    for tag in all_tags:
        if not isinstance(tag, Tag):
            continue

        # Use own direct text for headings to avoid aggregated parent text
        if tag.name in _HEADING_TAGS:
            tag_own_text = (tag.string or tag.get_text(separator="", strip=True)).lower()
        else:
            # For non-headings, use get_text but require an exact match rather
            # than substring to avoid false positives on large containers
            tag_own_text = (tag.string or "").lower()

        matched_block: str | None = None
        for keyword, block_label in _BLOCK_KEYWORDS.items():
            if keyword in tag_own_text:
                matched_block = block_label
                break

        if matched_block is None:
            continue

        # For headings: walk next siblings scoped to heading's parent
        if tag.name in _HEADING_TAGS:
            items = _extract_items_from_next_siblings(tag, matched_block, seen)
            results.extend(items)
        else:
            # For non-heading elements with exact text match (e.g. <div>Похожие запросы</div>)
            items = _extract_items_from_next_siblings(tag, matched_block, seen)
            results.extend(items)

    # -----------------------------------------------------------------------
    # Strategy 2: data-fast-name attribute fallback
    # -----------------------------------------------------------------------
    for el in soup.find_all(attrs={"data-fast-name": True}):
        fast_name = (el.get("data-fast-name") or "").lower()
        if "question" in fast_name or "frequent" in fast_name or "paa" in fast_name:
            for candidate in el.find_all(_ITEM_TAGS):
                text = candidate.get_text(separator=" ", strip=True)
                if len(text) >= _MIN_QUESTION_LEN:
                    key = text.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append({"question": text, "source_block": BLOCK_FREQUENT})
        elif "related" in fast_name or "similar" in fast_name:
            for candidate in el.find_all(_ITEM_TAGS):
                text = candidate.get_text(separator=" ", strip=True)
                if len(text) >= _MIN_QUESTION_LEN:
                    key = text.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append({"question": text, "source_block": BLOCK_RELATED})

    if not results:
        logger.warning(
            "PAA extraction returned 0 results — Yandex HTML structure may have changed "
            "(no headings matching 'частые вопросы' / 'похожие запросы' found)"
        )

    return results


def extract_paa_for_phrase(phrase: str, xmlproxy_html: str) -> list[dict]:
    """Extract PAA questions for a single input phrase.

    Wraps ``extract_paa_blocks`` and prepends the phrase to every result.

    Args:
        phrase: The search phrase submitted by the user.
        xmlproxy_html: Yandex SERP HTML returned by XMLProxy for this phrase.

    Returns:
        List of dicts: ``{"phrase": str, "question": str, "source_block": str}``.
    """
    blocks = extract_paa_blocks(xmlproxy_html)
    return [{"phrase": phrase, **item} for item in blocks]
