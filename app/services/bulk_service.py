"""Bulk operations service: batch move, assign, delete, export, import with audit log."""
from __future__ import annotations

import csv
import io
import os
import uuid
from pathlib import Path
from typing import Any

import openpyxl
from loguru import logger
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword import Keyword
from app.services.audit_service import log_action
from app.services.keyword_service import bulk_add_keywords


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


async def bulk_move_to_group(
    db: AsyncSession,
    keyword_ids: list[uuid.UUID],
    group_id: uuid.UUID | None,
) -> int:
    """Set group_id for all given keywords. group_id=None removes from group.

    Returns count of updated rows.
    """
    if not keyword_ids:
        return 0
    result = await db.execute(
        update(Keyword)
        .where(Keyword.id.in_(keyword_ids))
        .values(group_id=group_id)
        .execution_options(synchronize_session="fetch")
    )
    await db.flush()
    return result.rowcount or 0


async def bulk_move_to_cluster(
    db: AsyncSession,
    keyword_ids: list[uuid.UUID],
    cluster_id: uuid.UUID | None,
) -> int:
    """Set cluster_id for all given keywords. cluster_id=None removes from cluster.

    Returns count of updated rows.
    """
    if not keyword_ids:
        return 0
    result = await db.execute(
        update(Keyword)
        .where(Keyword.id.in_(keyword_ids))
        .values(cluster_id=cluster_id)
        .execution_options(synchronize_session="fetch")
    )
    await db.flush()
    return result.rowcount or 0


async def bulk_assign_target_url(
    db: AsyncSession,
    keyword_ids: list[uuid.UUID],
    target_url: str,
) -> int:
    """Set target_url for all given keywords.

    Returns count of updated rows.
    """
    if not keyword_ids:
        return 0
    result = await db.execute(
        update(Keyword)
        .where(Keyword.id.in_(keyword_ids))
        .values(target_url=target_url)
        .execution_options(synchronize_session="fetch")
    )
    await db.flush()
    return result.rowcount or 0


async def bulk_delete(
    db: AsyncSession,
    keyword_ids: list[uuid.UUID],
) -> int:
    """Delete keywords by IDs.

    Returns count of deleted rows.
    """
    if not keyword_ids:
        return 0
    result = await db.execute(
        delete(Keyword)
        .where(Keyword.id.in_(keyword_ids))
        .execution_options(synchronize_session="fetch")
    )
    await db.flush()
    return result.rowcount or 0


async def bulk_delete_by_filter(
    db: AsyncSession,
    site_id: uuid.UUID,
    *,
    group_id: uuid.UUID | None = None,
    cluster_id: uuid.UUID | None = None,
    search: str | None = None,
) -> int:
    """Delete keywords matching filter criteria.

    Returns count of deleted rows.
    """
    q = select(Keyword.id).where(Keyword.site_id == site_id)
    if group_id is not None:
        q = q.where(Keyword.group_id == group_id)
    if cluster_id is not None:
        q = q.where(Keyword.cluster_id == cluster_id)
    if search:
        q = q.where(Keyword.phrase.ilike(f"%{search}%"))

    id_result = await db.execute(q)
    ids = [row[0] for row in id_result.all()]
    if not ids:
        return 0

    del_result = await db.execute(
        delete(Keyword)
        .where(Keyword.id.in_(ids))
        .execution_options(synchronize_session="fetch")
    )
    await db.flush()
    return del_result.rowcount or 0


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

_CSV_HEADERS = [
    "Phrase", "Frequency", "Region", "Engine",
    "Group", "Cluster", "Target URL", "Position", "Delta",
]


async def _fetch_export_rows(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword_ids: list[uuid.UUID] | None = None,
    **filters: Any,
) -> list[list[Any]]:
    """Fetch keyword rows for export.

    If keyword_ids is provided, exports those exact keywords.
    Otherwise applies filter kwargs (group_id, cluster_id, region, engine, search).
    Returns list of value lists (no header).
    """
    from app.models.cluster import KeywordCluster
    from app.models.keyword import KeywordGroup
    from app.models.position import KeywordPosition

    if keyword_ids:
        q = select(Keyword).where(
            Keyword.site_id == site_id,
            Keyword.id.in_(keyword_ids),
        )
    else:
        q = select(Keyword).where(Keyword.site_id == site_id)
        if filters.get("group_id"):
            q = q.where(Keyword.group_id == filters["group_id"])
        if filters.get("cluster_id"):
            q = q.where(Keyword.cluster_id == filters["cluster_id"])
        if filters.get("region"):
            q = q.where(Keyword.region == filters["region"])
        if filters.get("engine"):
            q = q.where(Keyword.engine == filters["engine"])
        if filters.get("search"):
            q = q.where(Keyword.phrase.ilike(f"%{filters['search']}%"))

    kw_result = await db.execute(q.order_by(Keyword.phrase))
    keywords = kw_result.scalars().all()

    if not keywords:
        return []

    kw_ids = [k.id for k in keywords]

    # Latest position per keyword
    latest_pos_sq = (
        select(
            KeywordPosition.keyword_id,
            KeywordPosition.position,
            KeywordPosition.delta,
        )
        .where(KeywordPosition.keyword_id.in_(kw_ids))
        .distinct(KeywordPosition.keyword_id)
        .order_by(KeywordPosition.keyword_id, KeywordPosition.checked_at.desc())
        .subquery()
    )
    pos_result = await db.execute(select(latest_pos_sq))
    pos_map = {row.keyword_id: (row.position, row.delta) for row in pos_result.all()}

    # Group names
    group_ids = {k.group_id for k in keywords if k.group_id}
    group_names: dict[uuid.UUID, str] = {}
    if group_ids:
        gr = await db.execute(
            select(KeywordGroup.id, KeywordGroup.name).where(KeywordGroup.id.in_(group_ids))
        )
        group_names = {row.id: row.name for row in gr.all()}

    # Cluster names
    cluster_ids = {k.cluster_id for k in keywords if k.cluster_id}
    cluster_names: dict[uuid.UUID, str] = {}
    if cluster_ids:
        cr = await db.execute(
            select(KeywordCluster.id, KeywordCluster.name).where(
                KeywordCluster.id.in_(cluster_ids)
            )
        )
        cluster_names = {row.id: row.name for row in cr.all()}

    rows = []
    for k in keywords:
        pos, delta = pos_map.get(k.id, (None, None))
        engine = k.engine.value if hasattr(k.engine, "value") else (k.engine or "")
        rows.append([
            k.phrase,
            k.frequency if k.frequency is not None else "",
            k.region or "",
            engine,
            group_names.get(k.group_id, "") if k.group_id else "",
            cluster_names.get(k.cluster_id, "") if k.cluster_id else "",
            k.target_url or "",
            pos,
            delta,
        ])
    return rows


async def export_keywords_csv(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword_ids: list[uuid.UUID] | None = None,
    **filters: Any,
) -> str:
    """Export keywords to CSV string.

    If keyword_ids provided, export those. Otherwise use filters.
    Returns CSV string with headers: Phrase, Frequency, Region, Engine,
    Group, Cluster, Target URL, Position, Delta.
    """
    rows = await _fetch_export_rows(db, site_id, keyword_ids, **filters)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_CSV_HEADERS)
    writer.writerows(rows)
    return output.getvalue()


async def export_keywords_xlsx(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword_ids: list[uuid.UUID] | None = None,
    **filters: Any,
) -> bytes:
    """Export keywords to XLSX bytes using openpyxl.

    If keyword_ids provided, export those. Otherwise use filters.
    Returns XLSX file as bytes.
    """
    rows = await _fetch_export_rows(db, site_id, keyword_ids, **filters)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Keywords"
    ws.append(_CSV_HEADERS)
    for row in rows:
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Import with audit log
# ---------------------------------------------------------------------------


async def import_keywords_with_log(
    db: AsyncSession,
    site_id: uuid.UUID,
    file_path: str,
    on_duplicate: str = "skip",
    user_id: uuid.UUID | None = None,
) -> dict:
    """Parse a CSV/XLSX keyword file and import with audit logging.

    Steps:
    1. Parse file using existing parsers.
    2. Call bulk_add_keywords for DB insertion.
    3. Write audit_log entry (action: "bulk_keyword_import") with counts.
    4. Return {total, added, updated, skipped}.
    """
    from app.parsers.base import find_column, read_file, safe_int

    path = Path(file_path)
    suffix = path.suffix.lower()

    rows = read_file(file_path)
    keyword_rows: list[dict] = []

    if rows and len(rows) >= 1:
        headers = rows[0]
        data_rows = rows[1:]

        phrase_col = find_column(
            headers,
            ["phrase", "keyword", "фраза", "ключ", "запрос", "ключевое слово"],
        )
        freq_col = find_column(
            headers,
            ["frequency", "freq", "частотность", "частота", "volume"],
        )
        region_col = find_column(headers, ["region", "регион"])
        target_col = find_column(headers, ["target_url", "url", "target", "целевая"])

        if phrase_col is not None:
            for row in data_rows:
                phrase = row[phrase_col].strip() if phrase_col < len(row) else ""
                if not phrase:
                    continue
                frequency = (
                    safe_int(row[freq_col])
                    if freq_col is not None and freq_col < len(row)
                    else None
                )
                region = (
                    row[region_col].strip()
                    if region_col is not None and region_col < len(row) and row[region_col].strip()
                    else None
                )
                target_url = (
                    row[target_col].strip()
                    if target_col is not None and target_col < len(row) and row[target_col].strip()
                    else None
                )
                keyword_rows.append({
                    "phrase": phrase,
                    "frequency": frequency,
                    "region": region,
                    "target_url": target_url,
                })

    total = len(keyword_rows)

    if total == 0:
        detail = {
            "file": os.path.basename(file_path),
            "on_duplicate": on_duplicate,
            "total": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
        }
        await log_action(
            db,
            action="bulk_keyword_import",
            user_id=user_id,
            entity_type="keywords",
            entity_id=str(site_id),
            detail=detail,
        )
        return {"total": 0, "added": 0, "updated": 0, "skipped": 0}

    count = await bulk_add_keywords(db, site_id, keyword_rows, on_duplicate=on_duplicate)

    # Approximate split: bulk_add_keywords returns total affected rows
    if on_duplicate == "update":
        added = 0
        updated = count
    else:
        added = count
        updated = 0
    skipped = total - count

    filename = os.path.basename(file_path)
    detail = {
        "file": filename,
        "on_duplicate": on_duplicate,
        "total": total,
        "added": added,
        "updated": updated,
        "skipped": skipped,
    }
    await log_action(
        db,
        action="bulk_keyword_import",
        user_id=user_id,
        entity_type="keywords",
        entity_id=str(site_id),
        detail=detail,
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
