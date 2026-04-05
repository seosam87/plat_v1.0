"""Keyword CRUD service."""
from __future__ import annotations

import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword import Keyword, KeywordGroup, SearchEngine


# ---- KeywordGroup ----

async def get_or_create_group(
    db: AsyncSession,
    site_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None = None,
) -> KeywordGroup:
    """Return existing group by (site_id, name) or create a new one."""
    result = await db.execute(
        select(KeywordGroup).where(
            KeywordGroup.site_id == site_id,
            KeywordGroup.name == name,
        )
    )
    group = result.scalar_one_or_none()
    if group:
        return group
    group = KeywordGroup(site_id=site_id, name=name, parent_id=parent_id)
    db.add(group)
    await db.flush()
    return group


async def list_groups(db: AsyncSession, site_id: uuid.UUID) -> list[KeywordGroup]:
    result = await db.execute(
        select(KeywordGroup)
        .where(KeywordGroup.site_id == site_id)
        .order_by(KeywordGroup.name)
    )
    return list(result.scalars().all())


# ---- Keyword ----

async def add_keyword(
    db: AsyncSession,
    site_id: uuid.UUID,
    phrase: str,
    frequency: int | None = None,
    region: str | None = None,
    engine: str | None = None,
    target_url: str | None = None,
    group_id: uuid.UUID | None = None,
) -> Keyword:
    kw = Keyword(
        site_id=site_id,
        phrase=phrase.strip().lower(),
        frequency=frequency,
        region=region,
        engine=SearchEngine(engine) if engine else SearchEngine.yandex,
        target_url=target_url,
        group_id=group_id,
    )
    db.add(kw)
    await db.flush()
    return kw


async def bulk_add_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    rows: list[dict],
    batch_size: int = 1000,
    on_duplicate: str = "skip",
) -> int:
    """Insert multiple keywords from parsed file data.

    Each row dict may contain: phrase, frequency, region, engine, target_url, group_id.
    Flushes in batches of `batch_size` to handle large imports (up to 100k rows).

    on_duplicate controls behaviour when a keyword with the same phrase already exists
    for this site:
      - "skip"    — ignore the duplicate row (default)
      - "update"  — update non-null fields from the new row
      - "replace" — delete old keyword and insert new one
    Returns count of inserted/updated rows.
    """
    existing_map: dict[str, Keyword] = {}
    if on_duplicate in ("skip", "update", "replace"):
        result = await db.execute(
            select(Keyword).where(Keyword.site_id == site_id)
        )
        for kw in result.scalars().all():
            existing_map[kw.phrase] = kw

    count = 0
    for row in rows:
        phrase = (row.get("phrase") or "").strip()
        if not phrase:
            continue
        normalized = phrase.lower()

        existing = existing_map.get(normalized)
        if existing:
            if on_duplicate == "skip":
                continue
            elif on_duplicate == "update":
                if row.get("frequency") is not None:
                    existing.frequency = row["frequency"]
                if row.get("region"):
                    existing.region = row["region"]
                if row.get("engine"):
                    existing.engine = SearchEngine(row["engine"])
                if row.get("target_url"):
                    existing.target_url = row["target_url"]
                if row.get("group_id"):
                    existing.group_id = row["group_id"]
                count += 1
            elif on_duplicate == "replace":
                await db.delete(existing)
                new_kw = Keyword(
                    site_id=site_id,
                    phrase=normalized,
                    frequency=row.get("frequency"),
                    region=row.get("region"),
                    engine=SearchEngine(row["engine"]) if row.get("engine") else SearchEngine.yandex,
                    target_url=row.get("target_url"),
                    group_id=row.get("group_id"),
                )
                db.add(new_kw)
                existing_map[normalized] = new_kw
                count += 1
        else:
            kw = Keyword(
                site_id=site_id,
                phrase=normalized,
                frequency=row.get("frequency"),
                region=row.get("region"),
                engine=SearchEngine(row["engine"]) if row.get("engine") else SearchEngine.yandex,
                target_url=row.get("target_url"),
                group_id=row.get("group_id"),
            )
            db.add(kw)
            existing_map[normalized] = kw
            count += 1

        if count % batch_size == 0:
            await db.flush()
    if count % batch_size != 0:
        await db.flush()
    return count


async def update_keyword(
    db: AsyncSession,
    keyword: Keyword,
    target_url: str | None = None,
    group_id: uuid.UUID | None = None,
    clear_group: bool = False,
) -> Keyword:
    """Update keyword fields. Set clear_group=True to remove group assignment."""
    if target_url is not None:
        keyword.target_url = target_url or None
    if clear_group:
        keyword.group_id = None
    elif group_id is not None:
        keyword.group_id = group_id
    return keyword


async def list_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    group_id: uuid.UUID | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[Keyword]:
    query = (
        select(Keyword)
        .where(Keyword.site_id == site_id)
        .order_by(Keyword.phrase)
        .limit(limit)
        .offset(offset)
    )
    if group_id:
        query = query.where(Keyword.group_id == group_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def count_keywords(db: AsyncSession, site_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Keyword).where(Keyword.site_id == site_id)
    )
    return result.scalar_one()


async def get_keyword(db: AsyncSession, keyword_id: uuid.UUID) -> Keyword | None:
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    return result.scalar_one_or_none()


async def delete_keyword(db: AsyncSession, keyword: Keyword) -> None:
    await db.delete(keyword)
