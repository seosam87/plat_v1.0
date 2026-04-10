"""XMLProxy API client for Yandex SERP position checking.

Provides synchronous wrappers for use inside Celery tasks.
Parses Yandex XML responses returned by xmlproxy.ru.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from loguru import logger

XMLPROXY_SEARCH = "https://xmlproxy.ru/search/xml"
XMLPROXY_BALANCE = "https://xmlproxy.ru/balance.php"


class XMLProxyError(Exception):
    """Raised when XMLProxy returns an error code in the XML response."""

    def __init__(self, code: int, message: str = "") -> None:
        self.code = code
        self.message = message
        super().__init__(f"XMLProxy error {code}: {message}")


def search_yandex_sync(
    user: str,
    key: str,
    query: str,
    lr: int = 213,
    max_position: int = 200,
) -> dict:
    """Perform a Yandex search via XMLProxy and return parsed results.

    Fetches up to ``max_position`` results (multiple pages of 100).

    Args:
        user: XMLProxy account login.
        key: XMLProxy API key.
        query: Search query string.
        lr: Yandex region code (default 213 = Moscow).
        max_position: Search depth (default 200).

    Returns:
        dict with keys ``results`` (list of dicts) and ``error_code`` (None).

    Raises:
        XMLProxyError: If the XML response contains an error element.
        httpx.HTTPError: On network/HTTP failures.
    """
    per_page = 100
    pages_needed = (max_position + per_page - 1) // per_page
    all_results: list[dict] = []

    with httpx.Client(timeout=30) as client:
        for page in range(pages_needed):
            params = {
                "user": user,
                "key": key,
                "query": query,
                "lr": str(lr),
                "groupby": f"attr=d.mode=deep.groups-on-page={per_page}",
                "page": str(page),
                "ydomain": "ru",
            }
            resp = client.get(XMLPROXY_SEARCH, params=params)
            resp.raise_for_status()
            parsed = _parse_yandex_xml(resp.text)

            if not parsed["results"]:
                break

            # Offset positions by page
            for item in parsed["results"]:
                item["position"] = item["position"] + page * per_page
            all_results.extend(parsed["results"])

    return {"results": all_results, "error_code": None}


def fetch_yandex_html_sync(
    user: str,
    key: str,
    query: str,
    lr: int = 213,
) -> str:
    """Fetch Yandex SERP page HTML via XMLProxy for PAA block extraction.

    Uses XMLProxy's passthrough parameter ``&html=1`` to get the raw Yandex
    SERP HTML body instead of the structured XML position feed.  The returned
    HTML can be parsed with BeautifulSoup to extract PAA ("Частые вопросы"
    and "Похожие запросы") blocks.

    Args:
        user: XMLProxy account login.
        key: XMLProxy API key.
        query: Search query string.
        lr: Yandex region code (default 213 = Moscow).

    Returns:
        Raw HTML string of the Yandex SERP page (may be an empty string if
        XMLProxy does not support ``&html=1`` for this account tier — caller
        should log a warning in that case).

    Raises:
        XMLProxyError: If the response contains an XML error element.
        httpx.HTTPError: On network/HTTP failures.
    """
    params = {
        "user": user,
        "key": key,
        "query": query,
        "lr": str(lr),
        "groupby": "attr=d.mode=deep.groups-on-page=10",
        "page": "0",
        "ydomain": "ru",
        "html": "1",  # request raw Yandex SERP HTML instead of XML positions
    }
    with httpx.Client(timeout=30) as client:
        resp = client.get(XMLPROXY_SEARCH, params=params)
        resp.raise_for_status()

    # If the response looks like XML (starts with <), check for error element
    text = resp.text
    if text.lstrip().startswith("<"):
        try:
            root = ET.fromstring(text)
            error_el = root.find(".//error")
            if error_el is not None:
                code_attr = error_el.get("code", "0")
                raise XMLProxyError(int(code_attr), error_el.text or "")
            # Response is XML without error — extract any HTML passage content
            passages = []
            for passage in root.findall(".//passage"):
                passages.append(passage.text or "")
            if passages:
                return " ".join(passages)
        except (ET.ParseError, ValueError):
            pass  # Not valid XML — treat as raw HTML

    return text


def fetch_balance_sync(user: str, key: str) -> dict | None:
    """Fetch XMLProxy account balance.

    Args:
        user: XMLProxy account login.
        key: XMLProxy API key.

    Returns:
        dict with ``data``, ``cur_cost``, ``max_cost`` keys, or None on failure.
    """
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(XMLPROXY_BALANCE, params={"user": user, "key": key})
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("XMLProxy balance fetch failed: {}", exc)
        return None


def _parse_yandex_xml(xml_text: str) -> dict:
    """Parse Yandex XML response returned by XMLProxy.

    Raises:
        XMLProxyError: When the XML contains an ``<error code="N">`` element.
    """
    root = ET.fromstring(xml_text)

    error_el = root.find(".//error")
    if error_el is not None:
        code_attr = error_el.get("code", "0")
        raise XMLProxyError(int(code_attr), error_el.text or "")

    results: list[dict] = []
    for position, group in enumerate(root.findall(".//group"), start=1):
        doc = group.find("doc")
        if doc is None:
            continue
        url_el = doc.find("url")
        title_el = doc.find("title")
        domain_el = doc.find("domain")

        url = url_el.text if url_el is not None and url_el.text else ""
        title = title_el.text if title_el is not None and title_el.text else ""
        domain = domain_el.text if domain_el is not None and domain_el.text else ""

        # Fall back to extracting domain from URL if the element is missing/empty
        if not domain and url:
            parts = url.split("/")
            domain = parts[2] if len(parts) > 2 else url

        results.append(
            {
                "position": position,
                "url": url,
                "title": title,
                "domain": domain,
            }
        )

    return {"results": results, "error_code": None}
