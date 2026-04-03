"""Gap analysis service: detection, scoring, import, groups, proposals."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gap import GapGroup, GapKeyword, GapProposal, ProposalStatus


# ---- Scoring ----

SCORE_FORMULA_DESCRIPTION = (
    "Потенциал = Частотность × Коэффициент позиции конкурента. "
    "Коэффициент: TOP-3 = 1.0, TOP-10 = 0.7, TOP-30 = 0.3, остальные = 0.1. "
    "Чем выше значение — тем перспективнее ключ для создания контента."
)


def compute_potential_score(
    frequency: int | None, competitor_position: int | None
) -> float:
    """Compute potential score: frequency × position factor."""
    if not frequency or not competitor_position:
        return 0.0
    if competitor_position <= 3:
        factor = 1.0
    elif competitor_position <= 10:
        factor = 0.7
    elif competitor_position <= 30:
        factor = 0.3
    else:
        factor = 0.1
    return round(frequency * factor, 1)


# ---- Gap detection from SERP (async) ----


async def detect_gaps_from_session(
    db: AsyncSession,
    site_id: uuid.UUID,
    session_id: uuid.UUID,
    competitor_domain: str,
) -> list[dict]:
    """Find keywords where competitor ranks in TOP-10 but we don't."""
    from app.models.analytics import SessionSerpResult
    from app.models.keyword import Keyword
    from app.services.serp_analysis_service import extract_domain

    # Our keyword phrases
    our_kws = (await db.execute(
        select(Keyword.phrase).where(Keyword.site_id == site_id)
    )).scalars().all()
    our_phrases = {p.lower().strip() for p in our_kws}

    # SERP results
    serp_rows = (await db.execute(
        select(SessionSerpResult).where(SessionSerpResult.session_id == session_id)
    )).scalars().all()

    # Get our site domain for SERP matching
    from app.models.site import Site
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    our_domain = extract_domain(site.url).removeprefix("www.")

    comp_lower = competitor_domain.lower().removeprefix("www.")
    gaps = []

    for row in serp_rows:
        results = row.results_json or []
        comp_pos = None
        our_pos = None

        for r in results:
            domain = extract_domain(r.get("url", "")).removeprefix("www.")
            pos = r.get("position", 0)

            if comp_lower in domain and comp_pos is None:
                comp_pos = pos
            if our_domain in domain and our_pos is None:
                our_pos = pos

        # Gap = competitor ranks in TOP-10 but we either don't appear or rank worse
        if comp_pos is not None and our_pos is None:
            # Skip keywords we already have in our keyword set
            if row.keyword_phrase.lower().strip() in our_phrases:
                continue
            gaps.append({
                "phrase": row.keyword_phrase,
                "frequency": None,
                "competitor_position": comp_pos,
                "our_position": our_pos,
            })

    return gaps


async def save_gap_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    competitor_domain: str,
    gaps: list[dict],
    source: str = "serp",
) -> int:
    """Upsert gap keywords with potential score."""
    count = 0
    for g in gaps:
        score = compute_potential_score(g.get("frequency"), g.get("competitor_position"))
        stmt = insert(GapKeyword).values(
            id=uuid.uuid4(),
            site_id=site_id,
            competitor_domain=competitor_domain,
            phrase=g["phrase"],
            frequency=g.get("frequency"),
            competitor_position=g.get("competitor_position"),
            our_position=g.get("our_position"),
            potential_score=score,
            source=source,
            created_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gap_keyword_site_comp_phrase",
            set_={
                "frequency": stmt.excluded.frequency,
                "competitor_position": stmt.excluded.competitor_position,
                "our_position": stmt.excluded.our_position,
                "potential_score": stmt.excluded.potential_score,
                "source": stmt.excluded.source,
            },
        )
        await db.execute(stmt)
        count += 1
    await db.flush()
    return count


# ---- Import from file ----


async def import_competitor_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    competitor_domain: str,
    file_path: str,
) -> dict:
    """Import competitor keywords from CSV/XLSX and find gaps."""
    from app.parsers.base import read_file
    from app.parsers.gap_parser import parse_gap_file

    rows = read_file(file_path)
    parsed = parse_gap_file(rows)

    if not parsed:
        return {"imported": 0, "gaps_found": 0}

    suffix = Path(file_path).suffix.lower()
    source = "xlsx_import" if suffix == ".xlsx" else "csv_import"

    gaps = [
        {
            "phrase": p["phrase"],
            "frequency": p.get("frequency"),
            "competitor_position": p.get("position"),
            "our_position": None,
        }
        for p in parsed
    ]

    saved = await save_gap_keywords(db, site_id, competitor_domain, gaps, source=source)
    return {"imported": len(parsed), "gaps_found": saved}


# ---- Group management ----


async def create_gap_group(
    db: AsyncSession, site_id: uuid.UUID, name: str
) -> GapGroup:
    group = GapGroup(site_id=site_id, name=name)
    db.add(group)
    await db.flush()
    return group


async def list_gap_groups(db: AsyncSession, site_id: uuid.UUID) -> list[GapGroup]:
    result = await db.execute(
        select(GapGroup).where(GapGroup.site_id == site_id).order_by(GapGroup.name)
    )
    return list(result.scalars().all())


async def assign_to_group(
    db: AsyncSession, keyword_ids: list[uuid.UUID], group_id: uuid.UUID
) -> int:
    count = 0
    for kid in keyword_ids:
        result = await db.execute(select(GapKeyword).where(GapKeyword.id == kid))
        gk = result.scalar_one_or_none()
        if gk:
            gk.gap_group_id = group_id
            count += 1
    await db.flush()
    return count


async def delete_gap_group(db: AsyncSession, group_id: uuid.UUID) -> bool:
    result = await db.execute(select(GapGroup).where(GapGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        return False
    await db.delete(group)
    await db.flush()
    return True


# ---- Gap keyword queries ----


async def list_gap_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    competitor_domain: str | None = None,
    group_id: uuid.UUID | None = None,
    min_score: float | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[dict], int]:
    q = select(GapKeyword).where(GapKeyword.site_id == site_id)
    if competitor_domain:
        q = q.where(GapKeyword.competitor_domain == competitor_domain)
    if group_id:
        q = q.where(GapKeyword.gap_group_id == group_id)
    if min_score is not None:
        q = q.where(GapKeyword.potential_score >= min_score)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        q.order_by(GapKeyword.potential_score.desc().nullslast())
        .offset(offset).limit(limit)
    )
    keywords = result.scalars().all()

    return [
        {
            "id": str(k.id),
            "phrase": k.phrase,
            "frequency": k.frequency,
            "competitor_position": k.competitor_position,
            "our_position": k.our_position,
            "potential_score": k.potential_score,
            "gap_group_id": str(k.gap_group_id) if k.gap_group_id else None,
            "source": k.source,
            "competitor_domain": k.competitor_domain,
        }
        for k in keywords
    ], total


async def delete_gap_keywords(
    db: AsyncSession, keyword_ids: list[uuid.UUID]
) -> int:
    count = 0
    for kid in keyword_ids:
        result = await db.execute(select(GapKeyword).where(GapKeyword.id == kid))
        gk = result.scalar_one_or_none()
        if gk:
            await db.delete(gk)
            count += 1
    await db.flush()
    return count


# ---- Proposals ----


async def create_proposals_from_gaps(
    db: AsyncSession, site_id: uuid.UUID, keyword_ids: list[uuid.UUID]
) -> list[GapProposal]:
    proposals = []
    for kid in keyword_ids:
        result = await db.execute(select(GapKeyword).where(GapKeyword.id == kid))
        gk = result.scalar_one_or_none()
        if not gk:
            continue
        p = GapProposal(
            site_id=site_id,
            gap_keyword_id=gk.id,
            title=f"Написать текст: {gk.phrase}",
            target_phrase=gk.phrase,
            frequency=gk.frequency,
            potential_score=gk.potential_score,
        )
        db.add(p)
        proposals.append(p)
    await db.flush()
    return proposals


async def approve_proposal(
    db: AsyncSession, proposal_id: uuid.UUID, project_id: uuid.UUID | None = None
) -> GapProposal | None:
    result = await db.execute(select(GapProposal).where(GapProposal.id == proposal_id))
    p = result.scalar_one_or_none()
    if not p:
        return None
    p.status = ProposalStatus.approved
    p.updated_at = datetime.now(timezone.utc)

    # Optionally create content plan item
    if project_id:
        from app.models.project import ContentPlanItem
        item = ContentPlanItem(
            project_id=project_id,
            title=p.title,
            notes=f"Gap-ключ: {p.target_phrase} (частотность: {p.frequency})",
        )
        db.add(item)
        await db.flush()
        p.content_plan_item_id = item.id

    await db.flush()
    return p


async def reject_proposal(
    db: AsyncSession, proposal_id: uuid.UUID
) -> GapProposal | None:
    result = await db.execute(select(GapProposal).where(GapProposal.id == proposal_id))
    p = result.scalar_one_or_none()
    if not p:
        return None
    p.status = ProposalStatus.rejected
    p.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return p


async def list_proposals(
    db: AsyncSession, site_id: uuid.UUID, status: str | None = None
) -> list[GapProposal]:
    q = select(GapProposal).where(GapProposal.site_id == site_id)
    if status:
        q = q.where(GapProposal.status == status)
    q = q.order_by(GapProposal.potential_score.desc().nullslast())
    result = await db.execute(q)
    return list(result.scalars().all())
