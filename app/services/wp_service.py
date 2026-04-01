import base64

import httpx
from loguru import logger

from app.models.site import ConnectionStatus, Site
from app.services.site_service import get_decrypted_password

WP_VERIFY_PATH = "/wp-json/wp/v2/users/me"
REQUEST_TIMEOUT = 10.0


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


async def verify_connection(site: Site) -> ConnectionStatus:
    """
    Ping {site.url}/wp-json/wp/v2/users/me with WP Application Password auth.
    Returns ConnectionStatus.connected on HTTP 200, ConnectionStatus.failed otherwise.
    Password is decrypted at call time and never logged.
    """
    password = get_decrypted_password(site)
    url = site.url.rstrip("/") + WP_VERIFY_PATH
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                url,
                headers={"Authorization": _basic_auth_header(site.wp_username, password)},
            )
        if resp.status_code == 200:
            logger.info("WP connection verified", site_id=str(site.id), url=site.url)
            return ConnectionStatus.connected
        else:
            logger.warning(
                "WP connection failed",
                site_id=str(site.id),
                url=site.url,
                status_code=resp.status_code,
            )
            return ConnectionStatus.failed
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
        logger.warning("WP connection error", site_id=str(site.id), url=site.url, error=str(exc))
        return ConnectionStatus.failed
