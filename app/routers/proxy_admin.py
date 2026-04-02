"""Admin router for proxy pool management and service credentials.

Provides CRUD endpoints for proxies, credential save/load for XMLProxy,
rucaptcha, and anticaptcha, plus health check and balance fetch endpoints.
All endpoints are synchronous (sync DB via get_sync_db context manager) since
the underlying services are synchronous.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from sqlalchemy import select

from app.database import get_sync_db
from app.models.proxy import Proxy, ProxyStatus, ProxyType
from app.services.proxy_health_service import check_proxy_sync
from app.services.service_credential_service import (
    get_credential_sync,
    save_credential_sync,
)
from app.services.xmlproxy_service import fetch_balance_sync

router = APIRouter(prefix="/admin/proxies", tags=["proxy-admin"])

_jinja_templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Proxy CRUD
# ---------------------------------------------------------------------------


@router.post("", response_class=HTMLResponse)
def create_proxy(
    request: Request,
    url: str = Form(...),
    proxy_type: str = Form("http"),
) -> HTMLResponse:
    """Create a new proxy and return the HTML row for HTMX beforeend swap."""
    with get_sync_db() as db:
        proxy = Proxy(
            url=url,
            proxy_type=ProxyType(proxy_type),
            status=ProxyStatus.unchecked,
        )
        db.add(proxy)
        db.flush()
        db.commit()
        db.refresh(proxy)
        return _jinja_templates.TemplateResponse(
            request, "admin/partials/proxy_row.html", {"p": proxy}
        )


@router.put("/{proxy_id}", response_class=HTMLResponse)
def update_proxy(
    proxy_id: str,
    request: Request,
    url: str = Form(...),
    proxy_type: str = Form("http"),
) -> HTMLResponse:
    """Update proxy URL and type; return updated row partial for outerHTML swap."""
    with get_sync_db() as db:
        proxy = db.get(Proxy, uuid.UUID(proxy_id))
        if proxy is None:
            return HTMLResponse("Proxy not found", status_code=404)
        proxy.url = url
        proxy.proxy_type = ProxyType(proxy_type)
        db.flush()
        db.commit()
        db.refresh(proxy)
        return _jinja_templates.TemplateResponse(
            request, "admin/partials/proxy_row.html", {"p": proxy}
        )


@router.delete("/{proxy_id}", response_class=HTMLResponse)
def delete_proxy(proxy_id: str) -> HTMLResponse:
    """Delete proxy by UUID; return empty string for HTMX outerHTML swap."""
    with get_sync_db() as db:
        proxy = db.get(Proxy, uuid.UUID(proxy_id))
        if proxy is None:
            return HTMLResponse("", status_code=200)
        db.delete(proxy)
        db.commit()
    return HTMLResponse("", status_code=200)


@router.get("", response_class=JSONResponse)
def list_proxies() -> JSONResponse:
    """Return all proxies as JSON list."""
    with get_sync_db() as db:
        proxies = db.execute(select(Proxy)).scalars().all()
        return JSONResponse(
            [
                {
                    "id": str(p.id),
                    "url": p.url,
                    "proxy_type": p.proxy_type.value,
                    "status": p.status.value,
                    "response_time_ms": p.response_time_ms,
                    "last_checked_at": (
                        p.last_checked_at.isoformat() if p.last_checked_at else None
                    ),
                }
                for p in proxies
            ]
        )


# ---------------------------------------------------------------------------
# Health check endpoints
# ---------------------------------------------------------------------------


@router.post("/check-all", response_class=HTMLResponse)
def check_all_proxies(request: Request) -> HTMLResponse:
    """Check all proxies, update statuses, fetch balances, return proxy section HTML."""
    with get_sync_db() as db:
        proxies = db.execute(select(Proxy)).scalars().all()
        for proxy in proxies:
            try:
                status, ms = check_proxy_sync(proxy.url)
                proxy.status = ProxyStatus(status)
                proxy.response_time_ms = ms
                proxy.last_checked_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.warning("Error checking proxy {}: {}", proxy.url, exc)
                proxy.status = ProxyStatus.dead
                proxy.response_time_ms = None
                proxy.last_checked_at = datetime.now(timezone.utc)
        db.commit()

        # Re-query after commit to get fresh data
        proxies = db.execute(select(Proxy)).scalars().all()

        # Fetch XMLProxy balance if configured
        xmlproxy_balance = None
        xmlproxy_creds = get_credential_sync(db, "xmlproxy")
        if xmlproxy_creds and xmlproxy_creds.get("user") and xmlproxy_creds.get("key"):
            xmlproxy_balance = fetch_balance_sync(
                xmlproxy_creds["user"], xmlproxy_creds["key"]
            )

        return _jinja_templates.TemplateResponse(
            request,
            "admin/partials/proxy_section.html",
            {"proxies": proxies, "xmlproxy_balance": xmlproxy_balance},
        )


@router.post("/{proxy_id}/check", response_class=HTMLResponse)
def check_single_proxy(proxy_id: str, request: Request) -> HTMLResponse:
    """Check a single proxy health and return updated row partial."""
    with get_sync_db() as db:
        proxy = db.get(Proxy, uuid.UUID(proxy_id))
        if proxy is None:
            return HTMLResponse("Proxy not found", status_code=404)
        try:
            status, ms = check_proxy_sync(proxy.url)
            proxy.status = ProxyStatus(status)
            proxy.response_time_ms = ms
            proxy.last_checked_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning("Error checking proxy {}: {}", proxy.url, exc)
            proxy.status = ProxyStatus.dead
            proxy.response_time_ms = None
            proxy.last_checked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(proxy)
        return _jinja_templates.TemplateResponse(
            request, "admin/partials/proxy_row.html", {"p": proxy}
        )


# ---------------------------------------------------------------------------
# Credential endpoints
# ---------------------------------------------------------------------------


@router.post("/credentials/xmlproxy")
def save_xmlproxy_credentials(
    user: str = Form(...),
    key: str = Form(...),
) -> RedirectResponse:
    """Save XMLProxy credentials and redirect back to settings."""
    with get_sync_db() as db:
        save_credential_sync(db, "xmlproxy", {"user": user, "key": key})
    return RedirectResponse("/ui/admin/settings", status_code=303)


@router.post("/credentials/rucaptcha")
def save_rucaptcha_credentials(
    key: str = Form(...),
) -> RedirectResponse:
    """Save rucaptcha.com API key and redirect back to settings."""
    with get_sync_db() as db:
        save_credential_sync(db, "rucaptcha", {"key": key})
    return RedirectResponse("/ui/admin/settings", status_code=303)


@router.post("/credentials/anticaptcha")
def save_anticaptcha_credentials(
    key: str = Form(...),
) -> RedirectResponse:
    """Save anticaptcha API key and redirect back to settings."""
    with get_sync_db() as db:
        save_credential_sync(db, "anticaptcha", {"key": key})
    return RedirectResponse("/ui/admin/settings", status_code=303)


# ---------------------------------------------------------------------------
# Balance endpoints
# ---------------------------------------------------------------------------


@router.get("/xmlproxy-balance", response_class=JSONResponse)
def get_xmlproxy_balance() -> JSONResponse:
    """Fetch XMLProxy account balance; return JSON with balance/cur_cost/max_cost."""
    with get_sync_db() as db:
        creds = get_credential_sync(db, "xmlproxy")
    if not creds or not creds.get("user") or not creds.get("key"):
        return JSONResponse({"error": "not configured"})
    result = fetch_balance_sync(creds["user"], creds["key"])
    if result is None:
        return JSONResponse({"error": "balance fetch failed"})
    return JSONResponse(
        {
            "balance": result.get("data"),
            "cur_cost": result.get("cur_cost"),
            "max_cost": result.get("max_cost"),
        }
    )


@router.get("/rucaptcha-balance", response_class=JSONResponse)
def get_rucaptcha_balance() -> JSONResponse:
    """Fetch rucaptcha.com balance via their API."""
    with get_sync_db() as db:
        creds = get_credential_sync(db, "rucaptcha")
    if not creds or not creds.get("key"):
        return JSONResponse({"error": "not configured"})
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                "https://api.rucaptcha.com/getBalance",
                json={"clientKey": creds["key"]},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errorId") == 0:
                return JSONResponse({"balance": data.get("balance", 0)})
            return JSONResponse({"error": data.get("errorDescription", "API error")})
    except Exception as exc:
        logger.warning("rucaptcha balance fetch failed: {}", exc)
        return JSONResponse({"error": str(exc)})
