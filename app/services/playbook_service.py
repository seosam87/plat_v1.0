"""Playbook service layer — Phase 999.8.

CRUD operations for:
- PlaybookBlock (list/get/create/update/delete, with media replacement)
- BlockMedia (nested under block create/update)
- ExpertSource (list/get/create/update/delete with FK null-out)
- BlockCategory (list-only for MVP — categories are seeded)

Pattern: every function takes `db: AsyncSession` first. Functions call
`await db.flush()` only; the `get_db` dependency in `app.dependencies`
commits the session after the request handler returns. This matches the
existing convention in `app.services.template_service` and
`app.services.user_service`.

Plan 02 owns the `# --- Block / Expert / Category CRUD ---` banner; Plan 03
(playbook-builder, parallel agent) owns `# --- Playbook Template CRUD ---`
and appends after this section.
"""
from __future__ import annotations

import re
import uuid
from typing import Sequence

from loguru import logger
from pydantic import AnyHttpUrl, BaseModel, ConfigDict
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.playbook import (
    ActionKind,
    BlockCategory,
    BlockMedia,
    BlockMediaKind,
    ExpertSource,
    PlaybookBlock,
)


# ---------------------------------------------------------------------------
# --- Block / Expert / Category CRUD ---
# ---------------------------------------------------------------------------
# This section is owned by Plan 02 (admin-crud). Plan 03 appends its
# # --- Playbook Template CRUD --- banner AFTER this block. Do not reorder.
# ---------------------------------------------------------------------------


# ---------- Slug helpers ----------


_CYRILLIC_TABLE = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
)


def _slugify(text: str) -> str:
    """Transliterate Cyrillic → latin, lowercase, alnum+hyphen only.

    Returns a short uuid4 hex when input yields empty string so that the
    slug column (NOT NULL + UNIQUE) is always satisfied.
    """
    s = (text or "").lower().translate(_CYRILLIC_TABLE)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or uuid.uuid4().hex[:8]


async def _unique_slug(db: AsyncSession, model, base: str) -> str:
    """Return `base` or `base-2`, `base-3`, … until the slug is unused."""
    slug = base
    n = 1
    while True:
        result = await db.execute(select(model).where(model.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        n += 1
        slug = f"{base}-{n}"


# ---------- Pydantic schemas (form parsing + URL validation, CD-09) ----------


class BlockMediaCreate(BaseModel):
    """Single media row for a PlaybookBlock."""

    model_config = ConfigDict(str_strip_whitespace=True)

    kind: BlockMediaKind
    url: AnyHttpUrl
    title: str
    description_md: str | None = None
    display_order: int = 0


class BlockCreate(BaseModel):
    """Core block fields — does not include media (passed separately)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str
    category_id: uuid.UUID
    expert_source_id: uuid.UUID | None = None
    summary_md: str
    checklist_md: str | None = None
    action_kind: ActionKind
    estimated_days: int | None = None
    display_order: int = 0


class BlockUpdate(BlockCreate):
    """Update payload — same shape as create; slug never changes."""

    pass


class ExpertCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    bio_md: str | None = None
    external_url: AnyHttpUrl | None = None


class ExpertUpdate(ExpertCreate):
    pass


# ---------- BlockCategory (read-only for MVP) ----------


async def list_categories(db: AsyncSession) -> Sequence[BlockCategory]:
    result = await db.execute(
        select(BlockCategory).order_by(BlockCategory.display_order, BlockCategory.name)
    )
    return result.scalars().all()


# ---------- ExpertSource ----------


async def list_experts(db: AsyncSession) -> Sequence[ExpertSource]:
    result = await db.execute(select(ExpertSource).order_by(ExpertSource.name))
    return result.scalars().all()


async def get_expert(
    db: AsyncSession, expert_id: uuid.UUID
) -> ExpertSource | None:
    result = await db.execute(
        select(ExpertSource).where(ExpertSource.id == expert_id)
    )
    return result.scalar_one_or_none()


async def create_expert(db: AsyncSession, data: ExpertCreate) -> ExpertSource:
    slug = await _unique_slug(db, ExpertSource, _slugify(data.name))
    expert = ExpertSource(
        name=data.name,
        slug=slug,
        bio_md=data.bio_md,
        external_url=str(data.external_url) if data.external_url else None,
    )
    db.add(expert)
    await db.flush()
    await db.refresh(expert)
    logger.info("Created ExpertSource {} ({})", expert.id, expert.name)
    return expert


async def update_expert(
    db: AsyncSession, expert_id: uuid.UUID, data: ExpertUpdate
) -> ExpertSource | None:
    expert = await get_expert(db, expert_id)
    if expert is None:
        return None
    expert.name = data.name
    expert.bio_md = data.bio_md
    expert.external_url = str(data.external_url) if data.external_url else None
    await db.flush()
    await db.refresh(expert)
    logger.info("Updated ExpertSource {}", expert_id)
    return expert


async def delete_expert(db: AsyncSession, expert_id: uuid.UUID) -> bool:
    """Delete expert + null out `expert_source_id` on any dependent blocks.

    Blocks are intentionally preserved — D-08 says media/expert attribution is
    optional enrichment, not load-bearing content. Null-out rather than cascade.
    """
    expert = await get_expert(db, expert_id)
    if expert is None:
        return False
    await db.execute(
        PlaybookBlock.__table__.update()
        .where(PlaybookBlock.expert_source_id == expert_id)
        .values(expert_source_id=None)
    )
    await db.delete(expert)
    await db.flush()
    logger.info("Deleted ExpertSource {}", expert_id)
    return True


async def count_blocks_by_expert(
    db: AsyncSession, expert_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.count(PlaybookBlock.id)).where(
            PlaybookBlock.expert_source_id == expert_id
        )
    )
    return int(result.scalar() or 0)


# ---------- PlaybookBlock ----------


async def list_blocks(
    db: AsyncSession,
    *,
    category_id: uuid.UUID | None = None,
    expert_source_id: uuid.UUID | None = None,
) -> Sequence[PlaybookBlock]:
    stmt = (
        select(PlaybookBlock)
        .options(
            selectinload(PlaybookBlock.category),
            selectinload(PlaybookBlock.expert_source),
            selectinload(PlaybookBlock.media),
        )
        .order_by(PlaybookBlock.display_order, PlaybookBlock.title)
    )
    if category_id is not None:
        stmt = stmt.where(PlaybookBlock.category_id == category_id)
    if expert_source_id is not None:
        stmt = stmt.where(PlaybookBlock.expert_source_id == expert_source_id)
    result = await db.execute(stmt)
    return result.scalars().unique().all()


async def get_block(
    db: AsyncSession, block_id: uuid.UUID
) -> PlaybookBlock | None:
    result = await db.execute(
        select(PlaybookBlock)
        .options(
            selectinload(PlaybookBlock.category),
            selectinload(PlaybookBlock.expert_source),
            selectinload(PlaybookBlock.media),
        )
        .where(PlaybookBlock.id == block_id)
    )
    return result.scalar_one_or_none()


async def create_block(
    db: AsyncSession,
    data: BlockCreate,
    media: list[BlockMediaCreate],
    created_by: uuid.UUID | None,
) -> PlaybookBlock:
    slug = await _unique_slug(db, PlaybookBlock, _slugify(data.title))
    block = PlaybookBlock(
        title=data.title,
        slug=slug,
        category_id=data.category_id,
        expert_source_id=data.expert_source_id,
        summary_md=data.summary_md,
        checklist_md=data.checklist_md,
        action_kind=data.action_kind,
        estimated_days=data.estimated_days,
        display_order=data.display_order,
        prerequisites=[],
        created_by=created_by,
    )
    db.add(block)
    await db.flush()
    for idx, m in enumerate(media):
        db.add(
            BlockMedia(
                block_id=block.id,
                kind=m.kind,
                url=str(m.url),
                title=m.title,
                description_md=m.description_md,
                display_order=idx,
            )
        )
    await db.flush()
    await db.refresh(block)
    logger.info("Created PlaybookBlock {} ({})", block.id, block.title)
    return block


async def update_block(
    db: AsyncSession,
    block_id: uuid.UUID,
    data: BlockUpdate,
    media: list[BlockMediaCreate],
) -> PlaybookBlock | None:
    block = await get_block(db, block_id)
    if block is None:
        return None
    block.title = data.title
    block.category_id = data.category_id
    block.expert_source_id = data.expert_source_id
    block.summary_md = data.summary_md
    block.checklist_md = data.checklist_md
    block.action_kind = data.action_kind
    block.estimated_days = data.estimated_days
    block.display_order = data.display_order
    # Replace media wholesale — simpler than diffing for MVP.
    await db.execute(
        delete(BlockMedia).where(BlockMedia.block_id == block_id)
    )
    for idx, m in enumerate(media):
        db.add(
            BlockMedia(
                block_id=block_id,
                kind=m.kind,
                url=str(m.url),
                title=m.title,
                description_md=m.description_md,
                display_order=idx,
            )
        )
    await db.flush()
    await db.refresh(block)
    logger.info("Updated PlaybookBlock {}", block_id)
    return block


async def delete_block(db: AsyncSession, block_id: uuid.UUID) -> bool:
    block = await get_block(db, block_id)
    if block is None:
        return False
    await db.delete(block)  # BlockMedia cascades via FK ondelete=CASCADE
    await db.flush()
    logger.info("Deleted PlaybookBlock {}", block_id)
    return True


__all__ = [
    # Schemas
    "BlockCreate",
    "BlockUpdate",
    "BlockMediaCreate",
    "ExpertCreate",
    "ExpertUpdate",
    # Category
    "list_categories",
    # Expert CRUD
    "list_experts",
    "get_expert",
    "create_expert",
    "update_expert",
    "delete_expert",
    "count_blocks_by_expert",
    # Block CRUD
    "list_blocks",
    "get_block",
    "create_block",
    "update_block",
    "delete_block",
]
