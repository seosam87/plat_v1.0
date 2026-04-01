"""Google Search Console integration.

OAuth 2.0 flow + Search Analytics API (positions, clicks, CTR, impressions).
Tokens stored encrypted per site in oauth_tokens table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.oauth_token import OAuthToken
from app.services.crypto_service import decrypt, encrypt

GSC_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GSC_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"
GSC_SEARCH_ANALYTICS_URL = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"

SCOPES = "https://www.googleapis.com/auth/webmasters.readonly"


def build_authorize_url(site_id: str) -> str:
    """Build Google OAuth2 authorize URL. state carries site_id for callback."""
    params = {
        "client_id": settings.GSC_CLIENT_ID,
        "redirect_uri": settings.GSC_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": site_id,
    }
    return f"{GSC_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GSC_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GSC_CLIENT_ID,
                "client_secret": settings.GSC_CLIENT_SECRET,
                "redirect_uri": settings.GSC_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token_encrypted: str) -> dict:
    """Use refresh token to get a new access token."""
    refresh_token = decrypt(refresh_token_encrypted)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GSC_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.GSC_CLIENT_ID,
                "client_secret": settings.GSC_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def save_tokens(
    db: AsyncSession,
    site_id: uuid.UUID,
    token_data: dict,
) -> OAuthToken:
    """Save or update GSC OAuth tokens (encrypted) for a site."""
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.site_id == site_id,
            OAuthToken.provider == "gsc",
        )
    )
    token = result.scalar_one_or_none()

    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    if token is None:
        token = OAuthToken(
            site_id=site_id,
            provider="gsc",
            access_token=encrypt(token_data["access_token"]),
            refresh_token=encrypt(token_data["refresh_token"]) if token_data.get("refresh_token") else None,
            expires_at=expires_at,
        )
        db.add(token)
    else:
        token.access_token = encrypt(token_data["access_token"])
        if token_data.get("refresh_token"):
            token.refresh_token = encrypt(token_data["refresh_token"])
        token.expires_at = expires_at

    await db.flush()
    return token


async def get_valid_token(db: AsyncSession, site_id: uuid.UUID) -> str | None:
    """Get a valid (non-expired) access token for a site, refreshing if needed."""
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.site_id == site_id,
            OAuthToken.provider == "gsc",
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        return None

    # Check if expired (with 5-min buffer)
    now = datetime.now(timezone.utc)
    if token.expires_at and token.expires_at < now + timedelta(minutes=5):
        if not token.refresh_token:
            logger.warning("GSC token expired and no refresh token", site_id=str(site_id))
            return None
        try:
            new_data = await refresh_access_token(token.refresh_token)
            token.access_token = encrypt(new_data["access_token"])
            token.expires_at = now + timedelta(seconds=new_data.get("expires_in", 3600))
            if new_data.get("refresh_token"):
                token.refresh_token = encrypt(new_data["refresh_token"])
            await db.flush()
        except Exception as exc:
            logger.error("GSC token refresh failed", site_id=str(site_id), error=str(exc))
            return None

    return decrypt(token.access_token)


async def fetch_search_analytics(
    access_token: str,
    site_url: str,
    start_date: str,
    end_date: str,
    row_limit: int = 1000,
    start_row: int = 0,
) -> list[dict]:
    """Fetch Search Analytics data from GSC.

    Returns list of rows with: keys (query, page), clicks, impressions, ctr, position.
    Handles pagination via start_row.
    """
    url = GSC_SEARCH_ANALYTICS_URL.format(site_url=site_url)
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["query", "page"],
        "rowLimit": row_limit,
        "startRow": start_row,
    }

    all_rows: list[dict] = []
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("rows", [])
            if not rows:
                break

            for row in rows:
                keys = row.get("keys", [])
                all_rows.append({
                    "query": keys[0] if len(keys) > 0 else "",
                    "page": keys[1] if len(keys) > 1 else "",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": round(row.get("ctr", 0), 4),
                    "position": round(row.get("position", 0), 1),
                })

            if len(rows) < row_limit:
                break
            payload["startRow"] = payload.get("startRow", 0) + row_limit

    logger.info("GSC Search Analytics fetched", site_url=site_url, rows=len(all_rows))
    return all_rows
