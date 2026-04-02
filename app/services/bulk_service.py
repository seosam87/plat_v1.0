"""Bulk operations service: batch move, assign, delete, export, import with audit."""
from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path

import openpyxl
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword import Keyword, KeywordGroup
from app.models.cluster import KeywordCluster


# ---- Batch operations (async) ----


async def bulk_move_to_group(
    db: AsyncSession, keyword_ids: list[uuid.UUID], group_id: uuid.UUID | None
) -> int:
    count = 0
    for kid in keyword_ids:
        result = await db.execute(select(Keyword).where(Keyword.id == kid))
        kw = result.scalar_one_or_none()
        if kw:
            kw.group_id = group_id
            count += 1
    await db.flush()
    return count


async def bulk_move_to_cluster(
    db: AsyncSession, keyword_ids: list[uuid.UUID], cluster_id: uuid.UUID | None
) -> int:
    count = 0
    for kid in keyword_ids:
        result = await db.execute(select(Keyword).where(Keyword.id == kid))
        kw = result.scalar_one_or_none()
        if kw:
            kw.cluster_id = cluster_id
            count += 1
    await db.flush()
    return count


async def bulk_assign_target_url(
    db: AsyncSession, keyword_ids: list[uuid.UUID], target_url: str
) -> int:
    count = 0
    for kid in keyword_ids:
        result = await db.execute(select(Keyword).where(Keyword.id == kid))
        kw = result.scalar_one_or_none()
        if kw:
            kw.target_url = target_url
            count += 1
    await db.flush()
    return count


async def bulk_delete(db: AsyncSession, keyword_ids: list[uuid.UUID]) -> int:
    count = 0
    for kid in keyword_ids:
        result = await db.execute(select(Keyword).where(Keyword.id == kid))
        kw = result.scalar_one_or_none()
        if kw:
            await db.delete(kw)
            count += 1
    await db.flush()
    return count


async def bulk_delete_by_filter(
    db: AsyncSession,
    site_id: uuid.UUID,
    *,
    group_id: uuid.UUID | None = None,
    cluster_id: uuid.UUID | None = None,
    search: str | None = None,
) -> int:
    q = select(Keyword).where(Keyword.site_id == site_id)
    if group_id:
        q = q.where(Keyword.group_id == group_id)
    if cluster_id:
        q = q.where(Keyword.cluster_id == cluster_id)
    if search:
        q = q.where(Keyword.phrase.ilike(f"%{search}%"))

    result = await db.execute(q)
    keywords = result.scalars().all()
    for kw in keywords:
        await db.delete(kw)
    await db.flush()
    return len(keywords)


# ---- Export ----


async def export_keywords_csv(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword_ids: list[uuid.UUID] | None = None,
) -> str:
    """Export keywords as CSV string."""
    keywords = await _get_keywords(db, site_id, keyword_ids)
    return _keywords_to_csv(keywords)


async def export_keywords_xlsx(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword_ids: list[uuid.UUID] | None = None,
) -> bytes:
    """Export keywords as XLSX bytes."""
    keywords = await _get_keywords(db, site_id, keyword_ids)
    return _keywords_to_xlsx(keywords)


async def _get_keywords(
    db: AsyncSession, site_id: uuid.UUID, keyword_ids: list[uuid.UUID] | None
) -> list[Keyword]:
    if keyword_ids:
        result = await db.execute(select(Keyword).where(Keyword.id.in_(keyword_ids)))
    else:
        result = await db.execute(
            select(Keyword).where(Keyword.site_id == site_id).order_by(Keyword.phrase)
        )
    return list(result.scalars().all())


_CSV_HEADERS = ["Phrase", "Frequency", "Region", "Engine", "Group", "Cluster", "Target URL"]


def _keywords_to_csv(keywords: list) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_CSV_HEADERS)
    for k in keywords:
        writer.writerow([
            k.phrase,
            k.frequency or "",
            k.region or "",
            k.engine.value if hasattr(k.engine, "value") else (k.engine or ""),
            "",  # group name would need join
            "",  # cluster name would need join
            k.target_url or "",
        ])
    return output.getvalue()


def _keywords_to_xlsx(keywords: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Keywords"
    ws.append(_CSV_HEADERS)
    for k in keywords:
        ws.append([
            k.phrase,
            k.frequency,
            k.region or "",
            k.engine.value if hasattr(k.engine, "value") else (k.engine or ""),
            "",
            "",
            k.target_url or "",
        ])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


# ---- Import with audit log ----


async def import_keywords_with_log(
    db: AsyncSession,
    site_id: uuid.UUID,
    file_path: str,
    on_duplicate: str = "skip",
    user_id: uuid.UUID | None = None,
) -> dict:
    """Import keywords from CSV/XLSX with audit logging."""
    from app.parsers.base import read_file, find_column, safe_int
    from app.services.audit_service import log_action

    rows = read_file(file_path)
    if not rows or len(rows) < 2:
        return {"total": 0, "added": 0, "updated": 0, "skipped": 0}

    headers = rows[0]
    phrase_col = find_column(headers, ["phrase", "keyword", "ключ", "запрос", "ключевое слово"])
    freq_col = find_column(headers, ["frequency", "freq", "частотность", "частота", "volume"])
    region_col = find_column(headers, ["region", "регион"])
    target_col = find_column(headers, ["target_url", "url", "target", "целевая"])

    if phrase_col is None:
        return {"total": 0, "added": 0, "updated": 0, "skipped": 0, "error": "no phrase column found"}

    added = 0
    updated = 0
    skipped = 0

    for row in rows[1:]:
        phrase = row[phrase_col].strip() if phrase_col < len(row) else ""
        if not phrase:
            continue

        frequency = safe_int(row[freq_col]) if freq_col is not None and freq_col < len(row) else None
        region = row[region_col].strip() if region_col is not None and region_col < len(row) else None
        target_url = row[target_col].strip() if target_col is not None and target_col < len(row) else None

        # Check for existing keyword
        existing = (await db.execute(
            select(Keyword).where(Keyword.site_id == site_id, Keyword.phrase == phrase)
        )).scalar_one_or_none()

        if existing:
            if on_duplicate == "skip":
                skipped += 1
                continue
            elif on_duplicate in ("update", "replace"):
                if frequency is not None:
                    existing.frequency = frequency
                if region:
                    existing.region = region
                if target_url:
                    existing.target_url = target_url
                updated += 1
                continue

        kw = Keyword(
            site_id=site_id,
            phrase=phrase,
            frequency=frequency,
            region=region or None,
            target_url=target_url or None,
        )
        db.add(kw)
        added += 1

    await db.flush()

    # Audit log
    filename = Path(file_path).name
    total = added + updated + skipped
    await log_action(
        db,
        action="bulk_keyword_import",
        user_id=user_id,
        entity_type="keywords",
        entity_id=str(site_id),
        detail={
            "file": filename,
            "on_duplicate": on_duplicate,
            "total": total,
            "added": added,
            "updated": updated,
            "skipped": skipped,
        },
    )

    logger.info(
        "Bulk keyword import",
        site_id=str(site_id),
        file=filename,
        total=total,
        added=added,
        updated=updated,
        skipped=skipped,
    )

    return {"total": total, "added": added, "updated": updated, "skipped": skipped}
