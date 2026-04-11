"""Mobile reports helpers: client list, Redis download token storage."""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.client import Client

TOKEN_TTL_SECONDS = 604800  # 7 days
TOKEN_KEY_PREFIX = "reports:dl:"


@dataclass
class ClientForReports:
    id: uuid.UUID
    company_name: str
    email: str | None
    has_email: bool


async def list_clients_for_reports(db: AsyncSession) -> list[ClientForReports]:
    """Return non-deleted clients with email (for recipient select on /m/reports/new).

    Per D-05: flat select from Client CRM filtered by email IS NOT NULL.
    Telegram delivery goes to system chat (not per-client), so email is the
    only hard-filter criterion here.
    """
    stmt = (
        select(Client)
        .where(Client.is_deleted == False)  # noqa: E712
        .where(Client.email.isnot(None))
        .order_by(Client.company_name)
    )
    result = await db.execute(stmt)
    clients = result.scalars().all()
    return [
        ClientForReports(
            id=c.id,
            company_name=c.company_name,
            email=c.email,
            has_email=bool(c.email),
        )
        for c in clients
    ]


def _binary_redis_client() -> aioredis.Redis:
    """Redis client WITHOUT decode_responses — required for PDF bytes storage."""
    return aioredis.from_url(settings.REDIS_URL)


async def store_report_pdf(pdf_bytes: bytes) -> str:
    """Store PDF bytes under a fresh token key. Returns the token.

    Key: reports:dl:{token}  TTL: 7 days.
    """
    token = secrets.token_urlsafe(32)
    r = _binary_redis_client()
    try:
        await r.set(f"{TOKEN_KEY_PREFIX}{token}", pdf_bytes, ex=TOKEN_TTL_SECONDS)
        logger.info("stored report pdf token={} bytes={}", token, len(pdf_bytes))
    finally:
        await r.aclose()
    return token


async def load_report_pdf(token: str) -> bytes | None:
    """Load PDF bytes by token. Returns None if missing/expired."""
    r = _binary_redis_client()
    try:
        data = await r.get(f"{TOKEN_KEY_PREFIX}{token}")
    finally:
        await r.aclose()
    return data


def build_download_url(token: str) -> str:
    """Build absolute /m/reports/download/{token} URL using settings.APP_BASE_URL."""
    base = (settings.APP_BASE_URL or "http://localhost:8000").rstrip("/")
    return f"{base}/m/reports/download/{token}"
