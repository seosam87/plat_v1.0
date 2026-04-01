"""Content enrichment pipeline: TOC generation, schema.org, internal linking, diff.

All functions are pure (input HTML → output HTML) for easy unit testing.
The Celery task orchestrates them in sequence.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from difflib import unified_diff


# ---- TOC generation ----

def extract_headings(html: str) -> list[dict]:
    """Extract H2 and H3 headings from HTML content.

    Returns list of {level: 2|3, text: str, id: str}.
    """
    pattern = re.compile(r"<h([23])([^>]*)>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
    headings = []
    for match in pattern.finditer(html):
        level = int(match.group(1))
        attrs = match.group(2)
        text = re.sub(r"<[^>]+>", "", match.group(3)).strip()
        # Extract existing id from attributes
        id_match = re.search(r'id=["\']([^"\']*)["\']', attrs)
        existing_id = id_match.group(1) if id_match else None
        slug = existing_id or _slugify(text)
        headings.append({"level": level, "text": text, "id": slug})
    return headings


def generate_toc_html(headings: list[dict]) -> str:
    """Generate a Table of Contents HTML block from headings."""
    if not headings:
        return ""
    lines = ['<div class="toc"><h4>Table of Contents</h4><ul>']
    for h in headings:
        indent = "  " if h["level"] == 3 else ""
        tag = "ul" if h["level"] == 3 else "li"
        lines.append(f'{indent}<li><a href="#{h["id"]}">{h["text"]}</a></li>')
    lines.append("</ul></div>")
    return "\n".join(lines)


def inject_toc(html: str, toc_html: str) -> str:
    """Insert TOC block after the first paragraph or at the start of content."""
    if not toc_html:
        return html
    # Try to insert after first </p>
    first_p_end = html.find("</p>")
    if first_p_end != -1:
        pos = first_p_end + 4
        return html[:pos] + "\n" + toc_html + "\n" + html[pos:]
    return toc_html + "\n" + html


def add_heading_ids(html: str, headings: list[dict]) -> str:
    """Add id attributes to headings that lack them."""
    for h in headings:
        # Find the heading tag and add id if missing
        pattern = re.compile(
            rf"(<h{h['level']})([^>]*>)(.*?)(</h{h['level']}>)",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            text = re.sub(r"<[^>]+>", "", match.group(3)).strip()
            if text == h["text"] and f'id="{h["id"]}"' not in match.group(0):
                new_tag = f'{match.group(1)} id="{h["id"]}"{match.group(2)}{match.group(3)}{match.group(4)}'
                html = html.replace(match.group(0), new_tag, 1)
                break
    return html


# ---- Schema.org JSON-LD injection ----

def generate_schema_article(
    title: str,
    url: str,
    date_published: str | None = None,
    author: str = "Author",
) -> str:
    """Generate a JSON-LD schema.org Article script tag."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],
        "url": url,
        "author": {"@type": "Person", "name": author},
    }
    if date_published:
        schema["datePublished"] = date_published
    return f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'


def has_schema_ld(html: str) -> bool:
    """Check if HTML already contains a JSON-LD schema.org block."""
    return 'application/ld+json' in html


def inject_schema(html: str, schema_tag: str) -> str:
    """Append schema.org JSON-LD to the end of HTML content."""
    if has_schema_ld(html):
        return html
    return html + "\n" + schema_tag


# ---- Internal linking ----

def find_link_opportunities(
    content: str,
    keywords_with_urls: list[dict],
    max_links: int = 5,
) -> list[dict]:
    """Find places in content where we can insert internal links.

    keywords_with_urls: [{phrase: str, url: str}]
    Returns: [{phrase, url, position}] — matches found in content.
    """
    opportunities = []
    content_lower = content.lower()
    for kw in keywords_with_urls:
        phrase = kw["phrase"].lower()
        url = kw["url"]
        # Skip if URL is already linked
        if f'href="{url}"' in content.lower() or f"href='{url}'" in content.lower():
            continue
        pos = content_lower.find(phrase)
        if pos != -1:
            # Check not already inside a tag
            before = content[:pos]
            if before.rfind("<a") > before.rfind("</a>") and before.rfind("<a") > before.rfind(">"):
                continue  # inside an <a> tag
            opportunities.append({"phrase": kw["phrase"], "url": url, "position": pos})
            if len(opportunities) >= max_links:
                break
    return opportunities


def insert_links(content: str, opportunities: list[dict]) -> str:
    """Insert <a> tags for found link opportunities. Process in reverse order to maintain positions."""
    for opp in sorted(opportunities, key=lambda x: x["position"], reverse=True):
        pos = opp["position"]
        phrase_len = len(opp["phrase"])
        original = content[pos:pos + phrase_len]
        link = f'<a href="{opp["url"]}">{original}</a>'
        content = content[:pos] + link + content[pos + phrase_len:]
    return content


# ---- Diff computation ----

def compute_content_diff(original: str, processed: str) -> dict:
    """Compute a structured diff between original and processed content.

    Returns {changed_blocks: [{type: "added"|"removed"|"changed", content: str}], has_changes: bool}.
    """
    orig_lines = original.splitlines(keepends=True)
    proc_lines = processed.splitlines(keepends=True)

    diff_lines = list(unified_diff(orig_lines, proc_lines, fromfile="original", tofile="processed", lineterm=""))

    added = [l[1:] for l in diff_lines if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in diff_lines if l.startswith("-") and not l.startswith("---")]

    return {
        "has_changes": bool(added or removed),
        "added_lines": len(added),
        "removed_lines": len(removed),
        "diff_text": "".join(diff_lines),
    }


# ---- Helpers ----

def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:80]
