"""Smoke seed fixture for UI smoke crawler (Phase 15.1).

Per CONTEXT D-01 and RESEARCH Pattern 2 + "Critical detail" SAVEPOINT strategy:
session-scoped, ORM-based deterministic seed bound to an OUTER connection+
transaction so each request can join via its own savepoint.

Exports:
- SMOKE_IDS: deterministic UUID strings for every path-param key
- SeedHandle: dataclass with ids/session/connection
- smoke_seed: pytest-asyncio session-scoped fixture (populated in task 2/3)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base

# Deterministic UUID strings for URL parameter substitution.
# NOTE: "job_id" is a generic alias for suggest_job_id so routes using the
# generic name resolve to the same row.
SMOKE_IDS: dict[str, str] = {
    "site_id":        "11111111-1111-1111-1111-111111111111",
    "user_id":        "22222222-2222-2222-2222-222222222222",
    "keyword_id":     "33333333-3333-3333-3333-333333333333",
    "gap_keyword_id": "44444444-4444-4444-4444-444444444444",
    "suggest_job_id": "55555555-5555-5555-5555-555555555555",
    "crawl_job_id":   "66666666-6666-6666-6666-666666666666",
    "job_id":         "55555555-5555-5555-5555-555555555555",  # alias for suggest_job_id
    "report_id":      "77777777-7777-7777-7777-777777777777",
    "audit_id":       "88888888-8888-8888-8888-888888888888",
    "audit_check_id": "99999999-9999-9999-9999-999999999999",
    "project_id":     "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "task_id":        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "session_id":     "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "cluster_id":     "dddddddd-dddd-dddd-dddd-dddddddddddd",
    "brief_id":       "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    "competitor_id":  "ffffffff-ffff-ffff-ffff-ffffffffffff",
    "group_id":       "12121212-1212-1212-1212-121212121212",
}


@dataclass
class SeedHandle:
    """Handle returned by the smoke_seed fixture.

    `connection` is exposed so downstream per-request sessions can bind to the
    same outer transaction via `join_transaction_mode="create_savepoint"`.
    """

    ids: dict[str, str]
    session: AsyncSession
    connection: AsyncConnection


try:
    from app.config import settings
    TEST_DATABASE_URL = settings.DATABASE_URL.replace(
        f"/{settings.DATABASE_URL.split('/')[-1]}",
        "/seo_platform_test",
    )
except Exception:
    TEST_DATABASE_URL = (
        "postgresql+asyncpg://seo_user:changeme@postgres:5432/seo_platform_test"
    )


@pytest_asyncio.fixture(scope="session")
async def smoke_seed() -> Any:
    """Session-scoped smoke seed. Populated in tasks 2/3."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    conn = await engine.connect()
    outer_trans = await conn.begin()

    Session = async_sessionmaker(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = Session()
    try:
        yield SeedHandle(ids=SMOKE_IDS, session=session, connection=conn)
    finally:
        await session.close()
        await outer_trans.rollback()
        await conn.close()
        await engine.dispose()
