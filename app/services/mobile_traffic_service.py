"""Mobile traffic comparison service.

Orchestrates Yandex Metrika per-page traffic comparison between two periods.
Used by /m/traffic mobile page.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.metrika_service import (
    compute_period_delta,
    fetch_page_traffic,
    get_page_traffic,
    save_page_snapshots,
)

# ---------------------------------------------------------------------------
# Period preset labels for template rendering
# ---------------------------------------------------------------------------

PERIOD_PRESETS = {
    "this_week_vs_last": "Эта неделя vs прошлая",
    "this_month_vs_last": "Этот месяц vs прошлый",
    "30d_vs_30d": "30 дней vs 30 дней",
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _period_dates(preset: str) -> tuple[tuple[date, date], tuple[date, date]]:
    """Return ((a_start, a_end), (b_start, b_end)) for the given preset.

    Period A is the older (comparison) period; period B is the current period.
    """
    today = date.today()

    if preset == "this_week_vs_last":
        b_start = today - timedelta(days=today.weekday())  # Monday of current week
        b_end = today
        a_start = b_start - timedelta(weeks=1)
        a_end = b_start - timedelta(days=1)

    elif preset == "this_month_vs_last":
        b_start = today.replace(day=1)
        b_end = today
        a_end = b_start - timedelta(days=1)
        a_start = a_end.replace(day=1)

    else:  # "30d_vs_30d" — default
        b_start = today - timedelta(days=29)
        b_end = today
        a_start = today - timedelta(days=59)
        a_end = today - timedelta(days=30)

    return (a_start, a_end), (b_start, b_end)


# ---------------------------------------------------------------------------
# Main orchestration function
# ---------------------------------------------------------------------------


async def get_traffic_comparison(
    db: AsyncSession,
    site_id: uuid.UUID,
    counter_id: str,
    token: str,
    preset: str = "30d_vs_30d",
) -> dict:
    """Fetch and compare per-page traffic between two periods.

    Uses DB cache first; falls back to Metrika API on cache miss.
    Sorts result by biggest drops first (most negative visits_delta first).

    Returns dict with:
        period_a: (start_str, end_str)
        period_b: (start_str, end_str)
        total_a: int
        total_b: int
        delta_pct: float
        pages: list[dict] (up to 50, sorted by visits_delta ascending)
    """
    (a_start, a_end), (b_start, b_end) = _period_dates(preset)

    # Period A: try cache, then fetch from Metrika API
    rows_a = await get_page_traffic(db, site_id, a_start, a_end)
    if not rows_a:
        try:
            rows_a = await fetch_page_traffic(counter_id, token, str(a_start), str(a_end))
            if rows_a:
                await save_page_snapshots(db, site_id, a_start, a_end, rows_a)
                await db.commit()
        except Exception as exc:
            logger.error("Metrika fetch failed for period A: {}", exc)
            rows_a = []

    # Period B: try cache, then fetch from Metrika API
    rows_b = await get_page_traffic(db, site_id, b_start, b_end)
    if not rows_b:
        try:
            rows_b = await fetch_page_traffic(counter_id, token, str(b_start), str(b_end))
            if rows_b:
                await save_page_snapshots(db, site_id, b_start, b_end, rows_b)
                await db.commit()
        except Exception as exc:
            logger.error("Metrika fetch failed for period B: {}", exc)
            rows_b = []

    comparison = compute_period_delta(rows_a, rows_b)
    # Sort biggest drops first (most negative visits_delta first) per D-08
    comparison.sort(key=lambda r: r["visits_delta"])

    total_a = sum(r.get("visits_a", 0) or 0 for r in comparison)
    total_b = sum(r.get("visits_b", 0) or 0 for r in comparison)
    delta_pct = round((total_b - total_a) / total_a * 100, 1) if total_a else 0.0

    return {
        "period_a": (str(a_start), str(a_end)),
        "period_b": (str(b_start), str(b_end)),
        "total_a": total_a,
        "total_b": total_b,
        "delta_pct": delta_pct,
        "pages": comparison[:50],  # limit top 50 for mobile
    }
