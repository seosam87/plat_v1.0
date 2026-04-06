"""URL normalization utility for analytical JOINs.

Normalizes URLs so that pages stored in different formats
(http vs https, with/without UTM params, with/without trailing slash)
can be correctly matched across tables:
  - pages (canonical URLs with https and trailing slash)
  - metrika_traffic_pages (may have http, UTM params)
  - keyword_positions (ranking URLs from SERP)

Design decisions (D-13, D-14):
  - http is upgraded to https (all production sites use HTTPS)
  - UTM parameters are stripped (not part of page identity)
  - Trailing slash added to bare paths without file extension
  - Fragment (#...) removed (server-side content is the same)
  - Scheme and host lowercased; path case preserved
  - Non-UTM query params sorted alphabetically for determinism
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_url(url: str | None) -> str | None:
    """Normalize a URL for consistent cross-table JOINs.

    Args:
        url: Raw URL string, or None.

    Returns:
        Normalized URL string, empty string if input is empty, or None if input is None.

    Examples:
        >>> normalize_url("http://example.com/page?utm_source=yandex")
        'https://example.com/page/'
        >>> normalize_url("https://example.com/page/")
        'https://example.com/page/'
        >>> normalize_url(None)  # returns None
        >>> normalize_url("")
        ''
    """
    if url is None:
        return None
    if url == "":
        return ""

    parsed = urlparse(url)

    # 1. Lowercase scheme and netloc (host); preserve path case
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # 2. Upgrade http to https
    if scheme == "http":
        scheme = "https"

    # 3. Strip UTM parameters; preserve and sort non-UTM params
    path = parsed.path
    raw_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {
        k: v for k, v in raw_params.items() if not k.lower().startswith("utm_")
    }
    # Sort alphabetically for deterministic output
    query = urlencode(sorted(filtered_params.items()), doseq=True) if filtered_params else ""

    # 4. Add trailing slash to path if:
    #    - path does not already end with "/"
    #    - last path segment has no "." (i.e. no file extension)
    if path and not path.endswith("/"):
        last_segment = path.split("/")[-1]
        if "." not in last_segment:
            path = path + "/"
    elif not path:
        # Empty path means root — ensure it becomes "/"
        path = "/"

    # 5. Strip fragment (set to empty string)
    fragment = ""

    return urlunparse((scheme, netloc, path, parsed.params, query, fragment))
