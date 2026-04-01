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


def _sync_auth_headers(site: Site) -> dict:
    password = get_decrypted_password(site)
    return {"Authorization": _basic_auth_header(site.wp_username, password)}


def get_posts_sync(site: Site, page: int = 1, per_page: int = 20) -> list[dict]:
    """Fetch WP posts synchronously (for use in Celery tasks)."""
    url = site.url.rstrip("/") + "/wp-json/wp/v2/posts"
    try:
        resp = httpx.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_sync_auth_headers(site),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("WP get_posts failed", site_id=str(site.id), error=str(exc))
        return []


def get_pages_sync(site: Site, page: int = 1, per_page: int = 20) -> list[dict]:
    """Fetch WP pages synchronously (for use in Celery tasks)."""
    url = site.url.rstrip("/") + "/wp-json/wp/v2/pages"
    try:
        resp = httpx.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_sync_auth_headers(site),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("WP get_pages failed", site_id=str(site.id), error=str(exc))
        return []


def create_post_sync(site: Site, title: str, content: str, status: str = "draft") -> dict | None:
    """Create a WP post synchronously. Returns post dict or None on failure."""
    url = site.url.rstrip("/") + "/wp-json/wp/v2/posts"
    try:
        resp = httpx.post(
            url,
            json={"title": title, "content": content, "status": status},
            headers=_sync_auth_headers(site),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("WP create_post failed", site_id=str(site.id), error=str(exc))
        return None


async def detect_seo_plugin(client: httpx.AsyncClient, site: Site, auth_header: str) -> str:
    """
    Fetch one post from WP REST API and detect SEO plugin by response fields.
    Returns 'yoast', 'rankmath', or 'unknown'.
    """
    url = site.url.rstrip("/") + "/wp-json/wp/v2/posts?per_page=1"
    try:
        resp = await client.get(url, headers={"Authorization": auth_header})
        if resp.status_code != 200:
            return "unknown"
        posts = resp.json()
        if not posts or not isinstance(posts, list):
            return "unknown"
        post = posts[0]
        if "yoast_head" in post or "yoast_head_json" in post:
            return "yoast"
        if "rank_math_title" in post or "rank_math_description" in post:
            return "rankmath"
        return "unknown"
    except (httpx.HTTPError, ValueError, KeyError):
        return "unknown"


async def verify_connection(site: Site) -> tuple[ConnectionStatus, str]:
    """
    Ping {site.url}/wp-json/wp/v2/users/me with WP Application Password auth.
    Returns (ConnectionStatus, seo_plugin).
    On successful connection, also detects SEO plugin.
    Password is decrypted at call time and never logged.
    """
    password = get_decrypted_password(site)
    url = site.url.rstrip("/") + WP_VERIFY_PATH
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            auth = _basic_auth_header(site.wp_username, password)
            resp = await client.get(url, headers={"Authorization": auth})
        if resp.status_code == 200:
            logger.info("WP connection verified", site_id=str(site.id), url=site.url)
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                seo_plugin = await detect_seo_plugin(client, site, auth)
            if seo_plugin != "unknown":
                logger.info("SEO plugin detected", site_id=str(site.id), plugin=seo_plugin)
            return ConnectionStatus.connected, seo_plugin
        else:
            logger.warning(
                "WP connection failed",
                site_id=str(site.id),
                url=site.url,
                status_code=resp.status_code,
            )
            return ConnectionStatus.failed, site.seo_plugin or "unknown"
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
        logger.warning("WP connection error", site_id=str(site.id), url=site.url, error=str(exc))
        return ConnectionStatus.failed, site.seo_plugin or "unknown"
