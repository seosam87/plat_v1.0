"""Impact score service: compute and persist audit error impact scores.

Impact score = severity_weight x monthly_traffic_from_metrika.

Design decisions (D-02, D-03 from 13-CONTEXT.md):
- severity_weight: warning=1, error=3, critical=5
- Pre-computed into error_impact_scores table for fast dashboard queries
- URL normalization via normalize_url() ensures audit URLs match Metrika URLs
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.impact_score import ErrorImpactScore
from app.utils.url_normalize import normalize_url

# Severity weights per D-02, D-03
SEVERITY_WEIGHTS: dict[str, int] = {
    "warning": 1,
    "error": 3,
    "critical": 5,
}


def compute_single_impact_score(severity: str, monthly_traffic: int) -> int:
    """Compute impact_score = severity_weight * monthly_traffic.

    Args:
        severity: One of 'warning', 'error', 'critical'.
        monthly_traffic: Page visits for the latest Metrika period (>= 0).

    Returns:
        Integer impact score.

    Raises:
        ValueError: If severity is not a known key in SEVERITY_WEIGHTS.
    """
    if severity not in SEVERITY_WEIGHTS:
        raise ValueError(
            f"Unknown severity '{severity}'. Must be one of: {list(SEVERITY_WEIGHTS)}"
        )
    return SEVERITY_WEIGHTS[severity] * monthly_traffic


def build_impact_rows(
    audit_rows: list[dict[str, Any]],
    traffic_by_norm_url: dict[str, int],
) -> list[dict[str, Any]]:
    """Build upsert-ready rows for error_impact_scores.

    Normalizes each audit row's page_url via normalize_url() before
    looking up monthly traffic in traffic_by_norm_url.

    Args:
        audit_rows: List of dicts with keys: page_url, check_code, severity.
        traffic_by_norm_url: Dict mapping normalized page_url -> monthly visits.

    Returns:
        List of dicts ready for upsert into error_impact_scores.
        Each dict has: page_url (normalized), check_code, severity,
        severity_weight, monthly_traffic, impact_score.
    """
    now = datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []

    for row in audit_rows:
        raw_url = row["page_url"]
        norm_url = normalize_url(raw_url) or raw_url
        check_code = row["check_code"]
        severity = row["severity"]

        weight = SEVERITY_WEIGHTS.get(severity, 1)
        traffic = traffic_by_norm_url.get(norm_url, 0)
        score = weight * traffic

        result.append(
            {
                "page_url": norm_url,
                "check_code": check_code,
                "severity": severity,
                "severity_weight": weight,
                "monthly_traffic": traffic,
                "impact_score": score,
                "computed_at": now,
            }
        )

    return result


async def get_impact_scores_for_site(
    db: AsyncSession,
    site_id: uuid.UUID,
    limit: int = 200,
) -> list[ErrorImpactScore]:
    """Return impact scores for a site, ordered by impact_score DESC.

    Args:
        db: Async DB session.
        site_id: Site UUID to query.
        limit: Max rows to return (default 200).

    Returns:
        List of ErrorImpactScore ORM objects.
    """
    result = await db.execute(
        select(ErrorImpactScore)
        .where(ErrorImpactScore.site_id == site_id)
        .order_by(ErrorImpactScore.impact_score.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def upsert_impact_scores(
    db: AsyncSession,
    rows: list[dict[str, Any]],
) -> int:
    """Bulk upsert impact score rows into error_impact_scores.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE to handle re-runs.
    Conflict key: (site_id, page_url, check_code).

    Args:
        db: Async DB session (caller must commit).
        rows: List of dicts, each must include: site_id, page_url, check_code,
              severity, severity_weight, monthly_traffic, impact_score, computed_at.

    Returns:
        Number of rows upserted.
    """
    if not rows:
        return 0

    stmt = pg_insert(ErrorImpactScore).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["site_id", "page_url", "check_code"],
        set_={
            "severity": stmt.excluded.severity,
            "severity_weight": stmt.excluded.severity_weight,
            "monthly_traffic": stmt.excluded.monthly_traffic,
            "impact_score": stmt.excluded.impact_score,
            "computed_at": stmt.excluded.computed_at,
        },
    )
    await db.execute(stmt)
    return len(rows)


async def get_max_impact_score_by_url(
    db: AsyncSession,
    site_id: uuid.UUID,
) -> dict[str, int]:
    """Return dict mapping normalized page_url -> MAX(impact_score) for Kanban use.

    Args:
        db: Async DB session.
        site_id: Site UUID to query.

    Returns:
        Dict of {normalized_url: max_impact_score}.
    """
    result = await db.execute(
        text(
            "SELECT page_url, MAX(impact_score) AS max_score "
            "FROM error_impact_scores "
            "WHERE site_id = :sid "
            "GROUP BY page_url"
        ),
        {"sid": site_id},
    )
    return {row.page_url: row.max_score for row in result.fetchall()}
