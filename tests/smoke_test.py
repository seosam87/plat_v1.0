"""Thin CLI wrapper around tests._smoke_helpers (Phase 15.1 D-08: evolve, don't rewrite).

Route discovery, param resolution and error-marker scanning live in
``tests/_smoke_helpers.py`` and are shared with ``tests/test_ui_smoke.py``.
This module is the standalone CLI entry point for ad-hoc runs.

Usage:
    python -m tests.smoke_test                              # in-process ASGI
    python -m tests.smoke_test --url http://localhost:8000  # live server
    python -m tests.smoke_test --email admin@x --password secret

Exit 0 = all routes OK; exit 1 = any HTTP >=400, exception, or error marker.
"""
from __future__ import annotations

import os
import sys

import httpx
from httpx import ASGITransport

from tests._smoke_helpers import (
    JINJA_ERROR_MARKERS,
    build_param_map,
    discover_routes,
    resolve_path,
)

GREEN, YELLOW, RED, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[0m"
FALLBACK_SITE_ID = "00000000-0000-0000-0000-000000000001"


async def get_first_site_id(db_url: str) -> str | None:
    """Best-effort: fetch first site UUID from DB. Returns None on any failure."""
    try:
        import asyncpg
        conn = await asyncpg.connect(db_url.replace("+asyncpg", ""))
        try:
            row = await conn.fetchrow("SELECT id FROM sites LIMIT 1")
            return str(row["id"]) if row else None
        finally:
            await conn.close()
    except Exception:
        return None


async def authenticate(client: httpx.AsyncClient, email: str, password: str) -> str:
    """POST to /ui/login, return the access_token cookie value."""
    resp = await client.post("/ui/login", data={"email": email, "password": password}, follow_redirects=False)
    if resp.status_code in (200, 302, 303):
        token = resp.cookies.get("access_token") or client.cookies.get("access_token")
        if token:
            return token
    raise RuntimeError(f"Login failed: status={resp.status_code}. Check SMOKE_ADMIN_EMAIL/PASSWORD.")


async def run_smoke_test(
    base_url: str | None = None,
    admin_email: str | None = None,
    admin_password: str | None = None,
) -> list[dict]:
    """Visit every discovered UI route. Returns dicts: url/status/ok/error/skipped."""
    from app.config import settings
    from app.main import app as fastapi_app

    email = admin_email or os.environ.get("SMOKE_ADMIN_EMAIL", "admin@example.com")
    password = admin_password or os.environ.get("SMOKE_ADMIN_PASSWORD", "admin123")

    routes = discover_routes(fastapi_app)
    site_id = await get_first_site_id(settings.DATABASE_URL) or FALLBACK_SITE_ID
    _keys = ("site_id", "project_id", "keyword_id", "gap_keyword_id",
             "suggest_job_id", "crawl_job_id", "job_id", "report_id", "audit_id", "user_id")
    param_map = build_param_map({k: site_id for k in _keys})

    client_kwargs: dict = (
        {"transport": ASGITransport(app=fastapi_app), "base_url": "http://test"}
        if base_url is None else {"base_url": base_url}
    )
    results: list[dict] = []

    async with httpx.AsyncClient(**client_kwargs, follow_redirects=True, timeout=30.0) as client:
        try:
            client.cookies.set("access_token", await authenticate(client, email, password))
        except RuntimeError as exc:
            return [{"url": "/ui/login (auth)", "status": None, "ok": False, "error": str(exc), "skipped": False}]

        for route in routes:
            try:
                resolved = resolve_path(route.path, param_map)
            except Exception as exc:
                results.append({"url": route.path, "status": None, "ok": True, "error": f"skip: {exc}", "skipped": True})
                continue
            try:
                resp = await client.get(resolved)
                status, ok, error = resp.status_code, resp.status_code < 400, None
                if not ok:
                    error = f"HTTP {status}"
                else:
                    for marker in JINJA_ERROR_MARKERS:
                        if marker in resp.text:
                            ok, error = False, f"body marker: {marker}"
                            break
                results.append({"url": resolved, "status": status, "ok": ok, "error": error, "skipped": False})
            except Exception as exc:
                results.append({"url": resolved, "status": None, "ok": False, "error": str(exc), "skipped": False})

    return results


def print_report(results: list[dict]) -> int:
    """Print colored results table. Returns exit code: 0=all OK, 1=any errors."""
    header = f"{'URL':<60} {'Status':<8} {'Result':<12}"
    print(header); print("-" * len(header))
    errors = skipped = 0
    for r in results:
        if r.get("skipped"):
            skipped += 1
            print(f"{r['url']:<60} {'SKIP':<8} {YELLOW}SKIPPED{RESET}")
            continue
        status = r["status"]
        status_str = str(status) if status is not None else "ERR"
        if r["ok"] and status and status < 300:
            label = f"{GREEN}OK{RESET}"
        elif r["ok"] and status and status < 400:
            label = f"{YELLOW}REDIRECT{RESET}"
        else:
            label = f"{RED}ERROR{RESET}"; errors += 1
        suffix = f"  [{r['error']}]" if r.get("error") else ""
        print(f"{r['url']:<60} {status_str:<8} {label}{suffix}")
    print("-" * len(header))
    print(f"{len(results) - skipped} checked. {skipped} skipped. {errors} error(s).")
    return 1 if errors > 0 else 0


async def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="UI smoke test — visits every discovered route")
    p.add_argument("--url", default=None, help="Base URL for live server (default: in-process ASGI)")
    p.add_argument("--email", default=None, help="Admin email (default: $SMOKE_ADMIN_EMAIL)")
    p.add_argument("--password", default=None, help="Admin password (default: $SMOKE_ADMIN_PASSWORD)")
    a = p.parse_args()
    sys.exit(print_report(await run_smoke_test(base_url=a.url, admin_email=a.email, admin_password=a.password)))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
