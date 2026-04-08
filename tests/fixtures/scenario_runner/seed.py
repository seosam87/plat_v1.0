"""Idempotent live-stack seed for the scenario_runner.

Runnable out-of-process inside the api container:

    docker compose exec -T api python -m tests.fixtures.scenario_runner.seed

Reuses the public ``seed_core`` / ``seed_extended`` helpers from
``tests.fixtures.smoke_seed`` so live-stack scenarios reference the SAME
deterministic ``SMOKE_IDS`` as Phase 15.1 in-process smoke tests.

Differences from ``smoke_seed.py``:
  - Commits for real (no SAVEPOINT rollback)
  - Idempotent: exits as a no-op if ``smoke_admin`` (SMOKE_IDS["user_id"])
    already exists in the target DB
  - Uses ``app.config.settings.DATABASE_URL`` directly — the REAL dev DB
    inside the api container, NOT the TEST_DATABASE_URL override
"""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.services.suggest_service import SUGGEST_CACHE_TTL, suggest_cache_key

# Import the full models package so every mapper is registered before
# SQLAlchemy resolves FK relationships during flush. Without this the ORM
# fails on orphan FKs like audit_results.wp_content_job_id → wp_content_jobs.
import app.models  # noqa: F401
import app.models.wp_content_job  # noqa: F401  (orphan FK target from audit_results)
from app.models.user import User
from tests.fixtures.smoke_seed import SMOKE_IDS, seed_core, seed_extended


async def main() -> None:
    # NOTE: schema is managed by Alembic in the live stack. We do NOT run
    # Base.metadata.create_all here — the dev DB is already migrated, and
    # create_all requires importing every model module which is fragile.
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as s:
            existing = await s.get(User, UUID(SMOKE_IDS["user_id"]))
            if existing is not None:
                print("Already seeded, skipping DB seed")
                # Still reseed Redis cache — Redis may have been flushed
                # between runs while the DB persists; the P0 suggest
                # scenario depends on the cache being present.
                await _seed_suggest_cache()
                return

            # Pre-clean any rows in tables with unique constraints that
            # seed_core re-inserts unconditionally. The dev DB may already
            # contain operator-added rows (e.g. ServiceCredential) that
            # collide with smoke seed inserts. We only clean if the smoke
            # user is absent — so this runs at most once per DB lifetime.
            from sqlalchemy import delete
            from app.models.service_credential import ServiceCredential

            await s.execute(
                delete(ServiceCredential).where(
                    ServiceCredential.service_name.in_(
                        ["wordstat", "gsc", "xmlproxy", "rucaptcha"]
                    )
                )
            )

            await seed_core(s)
            await seed_extended(s)
            await s.commit()
            print(f"Seeded {len(SMOKE_IDS)} entities")

        # Seed Redis cache for the smoke SuggestJob so the P0 scenario
        # `01-suggest-to-results.yaml` deterministically hits the cache
        # (status=complete immediately, results rendered) without needing
        # the Celery worker to reach live proxies.
        await _seed_suggest_cache()
    finally:
        await engine.dispose()


async def _seed_suggest_cache() -> None:
    """Pre-populate Redis suggest cache for seed='smoke seed', yandex-only."""
    from redis import asyncio as aioredis

    key = suggest_cache_key("smoke seed", include_google=False)
    payload = [
        {"keyword": "smoke seed alpha", "source": "yandex", "frequency": None},
        {"keyword": "smoke seed beta", "source": "yandex", "frequency": None},
        {"keyword": "smoke seed gamma", "source": "yandex", "frequency": None},
    ]
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.set(key, json.dumps(payload), ex=SUGGEST_CACHE_TTL)
        print(f"Seeded Redis suggest cache: {key} ({len(payload)} rows)")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
