"""Convert DOCX files to clean HTML using mammoth.

Handles documents that use built-in Word heading styles as well as
documents that use custom styles or bold/enlarged font as headings.
"""
from __future__ import annotations

import io
import re

import mammoth

# Map common custom style names to heading tags.
# Mammoth ignores styles it doesn't recognise; these mappings catch
# frequently used Russian and English custom style names.
_CUSTOM_STYLE_MAP = "\n".join([
    "p[style-name='Heading 1'] => h1:fresh",
    "p[style-name='Heading 2'] => h2:fresh",
    "p[style-name='Heading 3'] => h3:fresh",
    "p[style-name='Заголовок 1'] => h1:fresh",
    "p[style-name='Заголовок 2'] => h2:fresh",
    "p[style-name='Заголовок 3'] => h3:fresh",
    "p[style-name='Title'] => h1:fresh",
    "p[style-name='Subtitle'] => h2:fresh",
    "p[style-name='Название'] => h1:fresh",
    "p[style-name='Подзаголовок'] => h2:fresh",
])


def docx_to_html(file_bytes: bytes) -> str:
    """Convert DOCX bytes to clean HTML string.

    Uses mammoth with custom style mappings, then post-processes
    the output to promote bold-only paragraphs to headings.
    """
    result = mammoth.convert_to_html(
        io.BytesIO(file_bytes),
        style_map=_CUSTOM_STYLE_MAP,
    )
    html = result.value
    html = _clean_html(html)
    html = _promote_bold_paragraphs(html)
    return html


def extract_title(html: str) -> str:
    """Extract title from first H1/H2 or first strong/bold text."""
    for pattern in [
        r"<h[12][^>]*>(.*?)</h[12]>",
        r"<strong>(.*?)</strong>",
        r"<b>(.*?)</b>",
    ]:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return "Untitled"


def _promote_bold_paragraphs(html: str) -> str:
    """Detect paragraphs that are entirely bold/strong and promote to headings.

    Heuristic: a <p> whose only content is <strong>…</strong> (optionally
    wrapped in other inline tags) and whose plain text is ≤ 150 chars is
    very likely a heading.  The first such paragraph becomes h1 (title);
    subsequent ones become h2.

    This handles DOCX files where the author used bold + larger font
    instead of Word's built-in Heading styles.
    """
    # Pattern: <p> containing only <strong>text</strong> (possibly nested inline tags)
    bold_p = re.compile(
        r"<p>(\s*<strong>(.*?)</strong>\s*)</p>",
        re.IGNORECASE | re.DOTALL,
    )

    has_h1 = bool(re.search(r"<h1[\s>]", html, re.IGNORECASE))
    has_any_heading = bool(re.search(r"<h[1-6][\s>]", html, re.IGNORECASE))
    promoted_first = False

    def _replace(match: re.Match) -> str:
        nonlocal promoted_first, has_h1
        inner_html = match.group(1)
        plain = re.sub(r"<[^>]+>", "", inner_html).strip()
        # Skip if too long to be a heading or too short (likely just bold emphasis)
        if len(plain) > 150 or len(plain) < 3:
            return match.group(0)
        # Skip if bold paragraph is embedded in a longer text context
        # (contains sentence-ending punctuation at end — likely not a heading)
        if plain.endswith((".","!","…")) and len(plain) > 80:
            return match.group(0)
        # First bold paragraph and no existing h1 → h1; otherwise h2
        if not promoted_first and not has_h1:
            promoted_first = True
            has_h1 = True
            return f"<h1>{plain}</h1>"
        return f"<h2>{plain}</h2>"

    # Only apply promotion if the document has no headings at all.
    # If mammoth already detected some headings, don't interfere.
    if has_any_heading:
        return html

    return bold_p.sub(_replace, html)


def _clean_html(html: str) -> str:
    """Clean up mammoth HTML output."""
    # Remove empty paragraphs
    html = re.sub(r"<p>\s*</p>", "", html)
    # Remove excessive whitespace
    html = re.sub(r"\n{3,}", "\n\n", html)
    # Ensure headings are properly spaced
    html = re.sub(r"</p>\s*<h", "</p>\n\n<h", html)
    html = re.sub(r"</h(\d)>\s*<p", r"</h\1>\n<p", html)
    return html.strip()
