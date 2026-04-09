"""Template variable resolver: resolves ~15 platform variables into a plain dict.

SECURITY: Never pass ORM model objects to SandboxedEnvironment.
All values in the returned dict are plain Python str/int/bool/None types.
"""
from __future__ import annotations

import uuid
from urllib.parse import urlparse

from jinja2 import Undefined
from jinja2.sandbox import SandboxedEnvironment
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.oauth_token import OAuthToken
from app.models.site import Site


class _HighlightUndefined(Undefined):
    """Renders unresolved Jinja2 variables as highlighted HTML spans.

    This makes it visually obvious in the preview when a template references
    a variable that is not present in the resolution context.
    """

    def __str__(self) -> str:
        return (
            '<span class="unresolved-var" style="background:#fef3c7;color:#92400e;'
            'padding:0 4px;border-radius:2px;font-family:monospace;font-size:0.85em;">'
            f"{{{{ {self._undefined_name} }}}}"
            "</span>"
        )

    # Also handle __html__ so HTMX/Jinja2 auto-escaping doesn't double-encode the span.
    def __html__(self) -> str:  # type: ignore[override]
        return self.__str__()


async def resolve_template_variables(
    db: AsyncSession,
    client_id: uuid.UUID,
    site_id: uuid.UUID,
) -> dict:
    """Resolve ~15 platform variables for a (client, site) pair into a plain dict.

    Returns:
        {
            "client": {
                "name": str,
                "legal_name": str | None,
                "inn": str | None,
                "email": str | None,
                "phone": str | None,
                "manager": str,           # manager's username or "" if none
            },
            "site": {
                "url": str,
                "domain": str,            # netloc from urlparse
                "top_positions_count": int,
                "audit_errors_count": int,
                "last_crawl_date": str,   # ISO date string or ""
                "gsc_connected": bool,
                "metrika_id": str,        # metrika_counter_id or ""
            },
        }

    All values are plain Python scalars — no SQLAlchemy ORM objects.
    """
    # ---- Client row ----
    client_result = await db.execute(
        select(Client).where(Client.id == client_id, Client.is_deleted == False)  # noqa: E712
    )
    client = client_result.scalar_one_or_none()

    if client is None:
        client_data: dict = {
            "name": "",
            "legal_name": None,
            "inn": None,
            "email": None,
            "phone": None,
            "manager": "",
        }
    else:
        # Resolve manager name via separate User query
        manager_name = ""
        if client.manager_id is not None:
            from app.models.user import User as UserModel

            mgr_result = await db.execute(
                select(UserModel.username).where(UserModel.id == client.manager_id)
            )
            manager_name = mgr_result.scalar_one_or_none() or ""

        client_data = {
            "name": str(client.company_name),
            "legal_name": str(client.legal_name) if client.legal_name is not None else None,
            "inn": str(client.inn) if client.inn is not None else None,
            "email": str(client.email) if client.email is not None else None,
            "phone": str(client.phone) if client.phone is not None else None,
            "manager": str(manager_name),
        }

    # ---- Site row ----
    site_result = await db.execute(
        select(Site).where(Site.id == site_id)
    )
    site = site_result.scalar_one_or_none()

    if site is None:
        site_data: dict = {
            "url": "",
            "domain": "",
            "top_positions_count": 0,
            "audit_errors_count": 0,
            "last_crawl_date": "",
            "gsc_connected": False,
            "metrika_id": "",
        }
    else:
        site_url = str(site.url)
        domain = urlparse(site_url).netloc

        # ---- GSC connection count ----
        gsc_result = await db.execute(
            select(func.count())
            .select_from(OAuthToken)
            .where(OAuthToken.site_id == site_id, OAuthToken.provider == "gsc")
        )
        gsc_count: int = gsc_result.scalar_one() or 0

        # ---- Last crawl date ----
        last_crawl_result = await db.execute(
            text(
                "SELECT MAX(created_at) FROM crawl_jobs "
                "WHERE site_id = :sid AND status = 'done'"
            ),
            {"sid": str(site_id)},
        )
        last_crawl_raw = last_crawl_result.scalar_one_or_none()
        last_crawl_date = (
            last_crawl_raw.date().isoformat() if last_crawl_raw is not None else ""
        )

        # ---- Audit errors count ----
        audit_errors_result = await db.execute(
            text(
                "SELECT COUNT(DISTINCT page_url) FROM error_impact_scores "
                "WHERE site_id = :sid"
            ),
            {"sid": str(site_id)},
        )
        audit_errors_count: int = int(audit_errors_result.scalar_one() or 0)

        # ---- Top-10 positions count ----
        # CTE: DISTINCT ON (keyword_id, engine) picks the latest position row per keyword+engine.
        # Then count rows where position <= 10.
        top_positions_sql = text(
            """
            WITH latest AS (
                SELECT DISTINCT ON (keyword_id, engine)
                    position
                FROM keyword_positions
                WHERE site_id = :sid
                ORDER BY keyword_id, engine, checked_at DESC
            )
            SELECT COUNT(*) FILTER (WHERE position <= 10)
            FROM latest
            """
        )
        top_positions_result = await db.execute(
            top_positions_sql, {"sid": str(site_id)}
        )
        top_positions_count: int = int(top_positions_result.scalar_one() or 0)

        site_data = {
            "url": site_url,
            "domain": str(domain),
            "top_positions_count": top_positions_count,
            "audit_errors_count": audit_errors_count,
            "last_crawl_date": last_crawl_date,
            "gsc_connected": bool(gsc_count > 0),
            "metrika_id": str(site.metrika_counter_id) if site.metrika_counter_id else "",
        }

    return {"client": client_data, "site": site_data}


def render_template_preview(body: str, context: dict) -> str:
    """Render a Jinja2 template body with the given context dict.

    Uses SandboxedEnvironment for security — user-authored templates cannot
    access config secrets or app globals.

    Unresolved variables are highlighted with _HighlightUndefined (yellow span).
    Syntax/runtime errors return an error HTML string instead of raising.

    Args:
        body: Jinja2 template string.
        context: Plain dict of variables (no ORM objects).

    Returns:
        Rendered HTML string or error HTML on failure.
    """
    try:
        env = SandboxedEnvironment(undefined=_HighlightUndefined)
        template = env.from_string(body)
        return template.render(context)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Template render error: {}", exc)
        return (
            '<span style="color:#dc2626;font-family:monospace;">'
            f"[Template error: {exc}]"
            "</span>"
        )
