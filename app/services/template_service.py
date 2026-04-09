"""Template service: CRUD + clone operations for ProposalTemplate."""
from __future__ import annotations

import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proposal_template import ProposalTemplate, TemplateType


async def list_templates(
    db: AsyncSession,
    template_type: TemplateType | None = None,
) -> list[ProposalTemplate]:
    """Return all templates, optionally filtered by type, ordered by created_at DESC."""
    query = select(ProposalTemplate)
    if template_type is not None:
        query = query.where(ProposalTemplate.template_type == template_type)
    query = query.order_by(ProposalTemplate.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_template(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> ProposalTemplate | None:
    """Return template by UUID, or None if not found."""
    result = await db.execute(
        select(ProposalTemplate).where(ProposalTemplate.id == template_id)
    )
    return result.scalar_one_or_none()


async def create_template(
    db: AsyncSession,
    *,
    name: str,
    template_type: TemplateType,
    description: str | None,
    body: str,
    created_by_id: uuid.UUID | None = None,
) -> ProposalTemplate:
    """Create and persist a new proposal template."""
    template = ProposalTemplate(
        name=name,
        template_type=template_type,
        description=description,
        body=body,
        created_by_id=created_by_id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    logger.info("Created proposal template {} ({})", template.id, name)
    return template


async def update_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    *,
    name: str,
    template_type: TemplateType,
    description: str | None,
    body: str,
) -> ProposalTemplate | None:
    """Update an existing template's fields. Returns None if not found."""
    template = await get_template(db, template_id)
    if template is None:
        return None
    template.name = name
    template.template_type = template_type
    template.description = description
    template.body = body
    await db.flush()
    await db.refresh(template)
    logger.info("Updated proposal template {}", template_id)
    return template


async def delete_template(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> bool:
    """Hard-delete a template. Returns True if deleted, False if not found."""
    template = await get_template(db, template_id)
    if template is None:
        return False
    await db.delete(template)
    await db.flush()
    logger.info("Deleted proposal template {}", template_id)
    return True


async def clone_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    *,
    created_by_id: uuid.UUID | None = None,
) -> ProposalTemplate | None:
    """Clone a template with name '{original} (копия)' and a new UUID.

    Returns None if the original template is not found.
    """
    original = await get_template(db, template_id)
    if original is None:
        return None

    clone = ProposalTemplate(
        name=f"{original.name} (копия)",
        template_type=original.template_type,
        description=original.description,
        body=original.body,
        created_by_id=created_by_id,
    )
    db.add(clone)
    await db.flush()
    await db.refresh(clone)
    logger.info(
        "Cloned proposal template {} -> {} ({})",
        template_id,
        clone.id,
        clone.name,
    )
    return clone
