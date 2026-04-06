"""Celery task for pre-computing audit error impact scores.

Triggered automatically after each site audit completes.
JOINs audit_results + audit_check_definitions + metrika_traffic_pages
to compute impact_score = severity_weight x monthly_traffic per error.
"""
from __future__ import annotations

import asyncio
import uuid

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.impact_tasks.compute_impact_scores",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def compute_impact_scores(self, site_id: str) -> dict:
    """Pre-compute impact scores for all audit errors on a site.

    Fetches non-passing audit results, joins with check definitions for
    severity, looks up latest Metrika per-page traffic, then upserts
    impact_score = severity_weight * monthly_traffic into error_impact_scores.

    Args:
        site_id: Site UUID as string.

    Returns:
        Dict with status, site_id, rows_upserted.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_compute_scores(site_id))
    except Exception as exc:
        logger.error(
            "Impact score computation failed",
            site_id=site_id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()


async def _compute_scores(site_id: str) -> dict:
    """Async implementation of impact score computation."""
    from sqlalchemy import select, text

    from app.database import AsyncSessionLocal
    from app.models.audit import AuditCheckDefinition, AuditResult
    from app.models.metrika import MetrikaTrafficPage
    from app.services.impact_score_service import build_impact_rows, upsert_impact_scores
    from app.utils.url_normalize import normalize_url

    site_uuid = uuid.UUID(site_id)

    async with AsyncSessionLocal() as db:
        # Step 1: Fetch all failing/warning audit results for the site
        audit_result = await db.execute(
            select(
                AuditResult.page_url,
                AuditResult.check_code,
                AuditCheckDefinition.severity,
            )
            .join(
                AuditCheckDefinition,
                AuditResult.check_code == AuditCheckDefinition.code,
            )
            .where(
                AuditResult.site_id == site_uuid,
                AuditResult.status != "pass",
            )
        )
        audit_rows = [
            {
                "page_url": row.page_url,
                "check_code": row.check_code,
                "severity": row.severity,
            }
            for row in audit_result.fetchall()
        ]

        if not audit_rows:
            logger.info(
                "No audit errors found for site, skipping impact scoring",
                site_id=site_id,
            )
            return {"status": "done", "site_id": site_id, "rows_upserted": 0}

        # Step 2: Fetch latest Metrika per-page traffic using DISTINCT ON
        # DISTINCT ON (page_url) ORDER BY period_end DESC gives the most recent period per URL
        traffic_result = await db.execute(
            text(
                "SELECT DISTINCT ON (page_url) page_url, visits "
                "FROM metrika_traffic_pages "
                "WHERE site_id = :sid "
                "ORDER BY page_url, period_end DESC"
            ),
            {"sid": site_uuid},
        )
        # Build normalized traffic lookup
        traffic_by_norm_url: dict[str, int] = {}
        for row in traffic_result.fetchall():
            norm = normalize_url(row.page_url) or row.page_url
            # Keep higher value if same normalized URL appears multiple times
            existing = traffic_by_norm_url.get(norm, 0)
            traffic_by_norm_url[norm] = max(existing, row.visits)

        # Step 3: Build impact rows (pure function — normalizes URLs, computes scores)
        rows = build_impact_rows(audit_rows, traffic_by_norm_url)

        # Attach site_id to each row for upsert
        for row in rows:
            row["site_id"] = site_uuid

        # Step 4: Upsert into error_impact_scores
        count = await upsert_impact_scores(db, rows)
        await db.commit()

        logger.info(
            "Impact scores computed",
            site_id=site_id,
            rows_upserted=count,
        )
        return {"status": "done", "site_id": site_id, "rows_upserted": count}
