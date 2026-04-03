"""
UI Smoke Test — discovers every UI route, authenticates as admin, and visits each URL.

Usage:
    python -m tests.smoke_test                          # in-process (no live server needed)
    python -m tests.smoke_test --url http://localhost:8000  # against live server
    python -m tests.smoke_test --email admin@example.com --password secret

Exit codes:
    0 — all routes returned 2xx/3xx
    1 — at least one route returned 4xx/5xx
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import httpx
from httpx import ASGITransport

from app.navigation import NAV_SECTIONS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_SITE_ID = "00000000-0000-0000-0000-000000000001"
FAKE_PROJECT_ID = "00000000-0000-0000-0000-000000000002"

# Routes to skip unconditionally
SKIP_ROUTES = {
    "/ui/login",
    "/ui/logout",
    "/",
    "/ui/logs",
}

# Route patterns to skip (contain placeholders we can't easily resolve)
SKIP_PATTERNS = ["{crawl_job_id}", "{job_id}", "{module}", "/ui/api/"]

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Route discovery
# ---------------------------------------------------------------------------

def discover_routes_from_nav() -> list[dict]:
    """Extract URL templates from NAV_SECTIONS children and top-level urls."""
    routes = []
    for section in NAV_SECTIONS:
        # Top-level section url (e.g. /ui/dashboard)
        if section.get("url") is not None:
            routes.append({"url": section["url"], "source": "nav", "label": section["label"]})
        # Children
        for child in section.get("children", []):
            url = child.get("url")
            if url is not None:
                routes.append({"url": url, "source": "nav", "label": child.get("label", url)})
    return routes


def discover_routes_from_main() -> list[dict]:
    """Parse app/main.py source to extract @app.get paths."""
    main_py = Path(__file__).parent.parent / "app" / "main.py"
    source_text = main_py.read_text(encoding="utf-8")

    # Match @app.get("...") or @app.get('...')
    pattern = re.compile(r'@app\.get\(["\']([^"\']+)["\']')
    found = pattern.findall(source_text)

    routes = []
    for url in found:
        # Skip explicitly excluded paths
        if url in SKIP_ROUTES:
            continue
        # Skip API fragments and paths with unwanted placeholders
        skip = False
        for pat in SKIP_PATTERNS:
            if pat in url:
                skip = True
                break
        if skip:
            continue
        routes.append({"url": url, "source": "main", "label": url})

    return routes


def _normalize_template(url: str) -> str:
    """Normalize URL template for deduplication: replace all {placeholders} with {param}."""
    return re.sub(r"\{[^}]+\}", "{param}", url)


def merge_routes(nav_routes: list[dict], main_routes: list[dict]) -> list[dict]:
    """Merge and deduplicate routes. nav_routes take priority for labeling."""
    seen_normalized: dict[str, dict] = {}

    # Nav routes first (higher priority for labels)
    for route in nav_routes:
        url = route["url"]
        norm = _normalize_template(url)
        # Skip routes with unresolvable placeholders
        skip = False
        for pat in SKIP_PATTERNS:
            if pat in url:
                skip = True
                break
        if skip:
            continue
        if norm not in seen_normalized:
            seen_normalized[norm] = {
                "url": url,
                "source": route.get("source", "nav"),
                "label": route.get("label", url),
                "needs_site_id": "{site_id}" in url,
                "needs_project_id": "{project_id}" in url,
            }

    # Main routes (only add if template not already seen)
    for route in main_routes:
        url = route["url"]
        norm = _normalize_template(url)
        if norm not in seen_normalized:
            seen_normalized[norm] = {
                "url": url,
                "source": route.get("source", "main"),
                "label": route.get("label", url),
                "needs_site_id": "{site_id}" in url,
                "needs_project_id": "{project_id}" in url,
            }

    result = sorted(seen_normalized.values(), key=lambda r: r["url"])
    return result


# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------

def resolve_url(template: str, site_id: str, project_id: str) -> str:
    """Replace {site_id} and {project_id} placeholders with real values."""
    url = template.replace("{site_id}", site_id)
    url = url.replace("{project_id}", project_id)
    return url


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def authenticate(client: httpx.AsyncClient, admin_email: str, admin_password: str) -> str:
    """POST to /ui/login, return the access_token value from the response cookie."""
    response = await client.post(
        "/ui/login",
        data={"email": admin_email, "password": admin_password},
        follow_redirects=False,
    )

    # Success: 302 redirect with cookie set
    if response.status_code in (200, 302, 303):
        token = response.cookies.get("access_token")
        if token:
            return token
        # Also check the client cookie jar (populated by follow_redirects)
        token = client.cookies.get("access_token")
        if token:
            return token

    raise RuntimeError(
        f"Login failed: status={response.status_code}. "
        f"Make sure SMOKE_ADMIN_EMAIL/SMOKE_ADMIN_PASSWORD are set correctly."
    )


# ---------------------------------------------------------------------------
# Site ID resolution
# ---------------------------------------------------------------------------

async def get_first_site_id(db_url: str) -> str | None:
    """Query DB for first site UUID. Used for {site_id} substitution."""
    try:
        import asyncpg

        # asyncpg doesn't want the +asyncpg driver suffix
        clean_url = db_url.replace("+asyncpg", "")
        conn = await asyncpg.connect(clean_url)
        try:
            row = await conn.fetchrow("SELECT id FROM sites LIMIT 1")
            if row:
                return str(row["id"])
            return None
        finally:
            await conn.close()
    except Exception:
        # DB not available or no sites — fall back to fake UUID
        return None


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_smoke_test(
    base_url: str | None = None,
    admin_email: str | None = None,
    admin_password: str | None = None,
) -> list[dict]:
    """
    Run smoke test against all discovered UI routes.

    Returns list of result dicts:
        {"url": str, "status": int | None, "ok": bool, "error": str | None, "skipped": bool}

    If base_url is None: use in-process httpx.AsyncClient(transport=ASGITransport(app=app)).
    If base_url is provided: use httpx.AsyncClient(base_url=base_url).
    """
    from app.config import settings

    # Resolve credentials
    email = admin_email or os.environ.get("SMOKE_ADMIN_EMAIL", "admin@example.com")
    password = admin_password or os.environ.get("SMOKE_ADMIN_PASSWORD", "admin123")

    # Discover routes
    nav_routes = discover_routes_from_nav()
    main_routes = discover_routes_from_main()
    routes = merge_routes(nav_routes, main_routes)

    # Get site_id from DB (best-effort)
    site_id = await get_first_site_id(settings.DATABASE_URL)
    if site_id is None:
        site_id = FAKE_SITE_ID
    project_id = site_id  # use same UUID as fallback

    # Build HTTP client
    if base_url is None:
        from app.main import app as fastapi_app
        transport = ASGITransport(app=fastapi_app)
        client_kwargs = {"transport": transport, "base_url": "http://test"}
    else:
        client_kwargs = {"base_url": base_url}

    results: list[dict] = []

    async with httpx.AsyncClient(
        **client_kwargs,
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        # Authenticate: get cookie
        try:
            token = await authenticate(client, email, password)
            client.cookies.set("access_token", token)
        except RuntimeError as e:
            results.append({
                "url": "/ui/login (auth)",
                "status": None,
                "ok": False,
                "error": str(e),
                "skipped": False,
            })
            return results

        # Visit each route
        for route in routes:
            url_template = route["url"]

            # Skip explicitly excluded routes
            if url_template in SKIP_ROUTES:
                continue

            # Skip routes with unresolvable placeholders
            should_skip = False
            for pat in SKIP_PATTERNS:
                if pat in url_template:
                    should_skip = True
                    break
            if should_skip:
                results.append({
                    "url": url_template,
                    "status": None,
                    "ok": True,
                    "error": None,
                    "skipped": True,
                })
                continue

            # Resolve URL
            resolved = resolve_url(url_template, site_id, project_id)

            try:
                response = await client.get(resolved)
                status = response.status_code
                ok = status < 400
                results.append({
                    "url": resolved,
                    "status": status,
                    "ok": ok,
                    "error": None if ok else f"HTTP {status}",
                    "skipped": False,
                })
            except Exception as exc:
                results.append({
                    "url": resolved,
                    "status": None,
                    "ok": False,
                    "error": str(exc),
                    "skipped": False,
                })

    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results: list[dict]) -> int:
    """Print colored table of results. Returns exit code: 0=all OK, 1=any errors."""
    col_url = 60
    col_status = 8
    col_result = 12

    header = f"{'URL':<{col_url}} {'Status':<{col_status}} {'Result':<{col_result}}"
    print(header)
    print("-" * len(header))

    errors = 0
    skipped = 0

    for r in results:
        if r.get("skipped"):
            skipped += 1
            line = f"{r['url']:<{col_url}} {'SKIP':<{col_status}} {YELLOW}SKIPPED{RESET}"
            print(line)
            continue

        status = r["status"]
        ok = r["ok"]
        status_str = str(status) if status is not None else "ERR"

        if ok and status is not None and status < 300:
            result_label = f"{GREEN}OK{RESET}"
        elif ok and status is not None and status < 400:
            result_label = f"{YELLOW}REDIRECT{RESET}"
        else:
            result_label = f"{RED}ERROR{RESET}"
            errors += 1

        error_suffix = f"  [{r['error']}]" if r.get("error") else ""
        line = f"{r['url']:<{col_url}} {status_str:<{col_status}} {result_label}{error_suffix}"
        print(line)

    print("-" * len(header))
    total_checked = len(results) - skipped
    print(f"{total_checked} routes checked. {skipped} skipped. {errors} error(s).")

    return 1 if errors > 0 else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="UI smoke test — visits every discovered route")
    parser.add_argument(
        "--url",
        default=None,
        help="Base URL for live server (default: in-process via ASGITransport)",
    )
    parser.add_argument("--email", default=None, help="Admin email (default: SMOKE_ADMIN_EMAIL env or admin@example.com)")
    parser.add_argument("--password", default=None, help="Admin password (default: SMOKE_ADMIN_PASSWORD env or admin123)")
    args = parser.parse_args()

    results = await run_smoke_test(
        base_url=args.url,
        admin_email=args.email,
        admin_password=args.password,
    )
    exit_code = print_report(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
