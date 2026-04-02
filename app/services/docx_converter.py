"""Convert DOCX files to clean HTML using mammoth."""
from __future__ import annotations

import io
import re

import mammoth


def docx_to_html(file_bytes: bytes) -> str:
    """Convert DOCX bytes to clean HTML string."""
    result = mammoth.convert_to_html(io.BytesIO(file_bytes))
    html = result.value
    # Clean up mammoth output
    html = _clean_html(html)
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
