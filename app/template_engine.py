"""Shared template engine with navigation context injection.

All routers MUST import `templates` from this module instead of creating
their own Jinja2Templates instance. This ensures sidebar, breadcrumbs,
and active state work on every page.

Usage in routers:
    from app.template_engine import templates
"""
from __future__ import annotations

import markdown as _md
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from starlette.requests import Request

from app.navigation import build_sidebar_sections, resolve_nav_context

_jinja_templates = Jinja2Templates(directory="app/templates")


def _markdown_filter(text: str) -> Markup:
    """Jinja2 filter: render Markdown to safe HTML.

    Supported extensions (Phase 999.8):
    - nl2br        — single newline → <br>
    - tables       — GFM tables
    - fenced_code  — ``` fenced code blocks
    """
    if not text:
        return Markup("")
    return Markup(_md.markdown(text, extensions=["nl2br", "tables", "fenced_code"]))


_jinja_templates.env.filters["markdown"] = _markdown_filter

# Help module mapping: URL prefix → module name for context-sensitive help
_HELP_MODULE_MAP = {
    "/ui/sites": "sites",
    "/ui/keywords": "keywords",
    "/ui/positions": "positions",
    "/ui/clusters": "clusters",
    "/ui/cannibalization": "clusters",
    "/ui/projects": "projects",
    "/ui/pipeline": "pipeline",
    "/ui/content-publish": "pipeline",
    "/ui/dashboard": "reports",
    "/ui/uploads": "keywords",
    "/ui/tasks": "projects",
    "/ui/crm": "crm",
    "/ui/templates": "crm",
    "/ui/admin": "admin",
    "/ui/metrika": "metrika",
    "/audit": "audit",
    "/monitoring": "monitoring",
    "/analytics": "analytics",
    "/gap": "gap",
    "/architecture": "architecture",
    "/bulk": "bulk",
    "/traffic-analysis": "traffic-analysis",
    "/intent": "intent",
    "/ui/competitors": "competitors",
    "/ui/playbooks": "playbooks",
}


class _NavAwareTemplates:
    """Wrapper that auto-injects nav context + help module into every template response."""

    def __init__(self, jinja_templates: Jinja2Templates):
        self._t = jinja_templates

    def TemplateResponse(self, request_or_name, name_or_context=None, context=None, **kwargs):
        # Handle both calling conventions:
        # New style: TemplateResponse(request, name, context)
        # Old style: TemplateResponse(name, {"request": request, ...})
        if isinstance(request_or_name, str):
            # Old style: first arg is template name
            name = request_or_name
            ctx = dict(name_or_context or {})
            request = ctx.get("request")
        else:
            # New style: first arg is request
            request = request_or_name
            name = name_or_context
            ctx = dict(context or {})

        if request is None:
            return self._t.TemplateResponse(name, ctx, **kwargs)

        # Inject help module
        if "help_module" not in ctx:
            path = str(request.url.path)
            for prefix, module in _HELP_MODULE_MAP.items():
                if path.startswith(prefix):
                    ctx["help_module"] = module
                    break

        # Inject navigation context for sidebar
        if "nav_sections" not in ctx:
            path = str(request.url.path)
            nav_ctx = resolve_nav_context(path)
            ctx.update(nav_ctx)

            # Selected site: sync from URL if it contains a UUID
            import re as _re
            raw = request.cookies.get("selected_site_id")
            url_uuid_match = _re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', path)
            url_site_id = url_uuid_match.group(0) if url_uuid_match else None
            # If URL has a site_id, use it (and flag cookie update needed)
            if url_site_id and url_site_id != raw:
                ctx["selected_site_id"] = url_site_id
                ctx["_sync_site_cookie"] = url_site_id
            else:
                ctx["selected_site_id"] = raw if raw else None

            # Admin check from JWT cookie
            is_admin = False
            try:
                from app.auth.jwt import decode_access_token
                token = request.cookies.get("access_token", "")
                if token:
                    payload = decode_access_token(token)
                    is_admin = payload.get("role") == "admin"
            except Exception:
                pass
            ctx["nav_sections"] = build_sidebar_sections(ctx["selected_site_id"], is_admin)
            ctx["is_admin"] = is_admin

        # Ensure request is in context for old-style Starlette rendering
        if "request" not in ctx and request is not None:
            ctx["request"] = request

        sync_cookie = ctx.pop("_sync_site_cookie", None)
        response = self._t.TemplateResponse(name, ctx, **kwargs)

        # Auto-sync selected_site_id cookie when URL contains a different site
        if sync_cookie:
            response.set_cookie(
                key="selected_site_id", value=sync_cookie,
                path="/", max_age=31536000, samesite="lax", httponly=False,
            )
        return response


templates = _NavAwareTemplates(_jinja_templates)
