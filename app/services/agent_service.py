"""Agent service: CRUD, variable parser, fork, favourite, job management.

Phase 999.9 prompt library / AI agent catalogue service layer.
Pure async functions taking an AsyncSession — no global state.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AIAgent, AgentCategory, AgentFavourite, AgentJob


# ---------------------------------------------------------------------------
# Variable parser
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def parse_template_variables(template: str) -> list[str]:
    """Extract unique ordered variable names from {{var}} template."""
    seen: set[str] = set()
    result: list[str] = []
    for match in _VAR_RE.finditer(template):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def render_template(template: str, inputs: dict[str, str]) -> str:
    """Substitute {{var}} placeholders with provided values."""

    def replacer(m: re.Match) -> str:
        return inputs.get(m.group(1), m.group(0))

    return _VAR_RE.sub(replacer, template)


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


async def list_categories(db: AsyncSession) -> list[AgentCategory]:
    """Return all agent categories ordered by display_order."""
    result = await db.execute(
        select(AgentCategory).order_by(AgentCategory.display_order)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Agent CRUD
# ---------------------------------------------------------------------------


async def list_agents(
    db: AsyncSession,
    *,
    category_slug: str | None = None,
    search: str | None = None,
    favourite_user_id: uuid.UUID | None = None,
) -> list[AIAgent]:
    """List agents with optional filters.

    Args:
        db: Async SQLAlchemy session.
        category_slug: Filter by category slug.
        search: ILIKE search on name + description.
        favourite_user_id: Return only agents favourited by this user.
    """
    stmt = select(AIAgent).options(selectinload(AIAgent.category))

    if category_slug is not None:
        stmt = stmt.join(AgentCategory, AIAgent.category_id == AgentCategory.id).where(
            AgentCategory.slug == category_slug
        )

    if search:
        term = f"%{search}%"
        stmt = stmt.where(
            AIAgent.name.ilike(term) | AIAgent.description.ilike(term)
        )

    if favourite_user_id is not None:
        stmt = stmt.join(
            AgentFavourite,
            (AgentFavourite.agent_id == AIAgent.id)
            & (AgentFavourite.user_id == favourite_user_id),
        )

    stmt = stmt.order_by(AIAgent.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> AIAgent | None:
    """Load a single agent with category selectinloaded."""
    result = await db.execute(
        select(AIAgent)
        .options(selectinload(AIAgent.category))
        .where(AIAgent.id == agent_id)
    )
    return result.scalar_one_or_none()


async def create_agent(
    db: AsyncSession,
    *,
    name: str,
    description: str | None,
    icon: str | None,
    category_id: uuid.UUID,
    system_prompt: str,
    user_template: str,
    model: str = "claude-haiku-4-5-20251001",
    temperature: float = 0.7,
    max_tokens: int = 800,
    output_format: str = "text",
    tags: list | None = None,
    is_public: bool = True,
    created_by: uuid.UUID | None = None,
) -> AIAgent:
    """Create and persist a new AIAgent."""
    agent = AIAgent(
        name=name,
        description=description,
        icon=icon,
        category_id=category_id,
        system_prompt=system_prompt,
        user_template=user_template,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        output_format=output_format,
        tags=tags or [],
        is_public=is_public,
        created_by=created_by,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return agent


async def update_agent(
    db: AsyncSession, agent_id: uuid.UUID, **kwargs
) -> AIAgent | None:
    """Update agent fields by id. Returns updated agent or None if not found."""
    kwargs["updated_at"] = datetime.utcnow()
    await db.execute(
        update(AIAgent).where(AIAgent.id == agent_id).values(**kwargs)
    )
    await db.flush()
    return await get_agent(db, agent_id)


async def delete_agent(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    """Delete agent by id. Returns True if deleted, False if not found."""
    result = await db.execute(
        delete(AIAgent).where(AIAgent.id == agent_id)
    )
    await db.flush()
    return result.rowcount > 0


async def fork_agent(
    db: AsyncSession,
    *,
    original_id: uuid.UUID,
    created_by: uuid.UUID,
) -> AIAgent:
    """Fork an agent: copy all fields except id/created_at/updated_at/usage_count.

    Sets fork_of_id to original_id and appends ' (копия)' to name.
    """
    original = await get_agent(db, original_id)
    if original is None:
        raise ValueError(f"Agent {original_id} not found")

    fork = AIAgent(
        name=f"{original.name} (копия)",
        description=original.description,
        icon=original.icon,
        category_id=original.category_id,
        system_prompt=original.system_prompt,
        user_template=original.user_template,
        model=original.model,
        temperature=original.temperature,
        max_tokens=original.max_tokens,
        output_format=original.output_format,
        tags=list(original.tags) if original.tags else [],
        is_public=original.is_public,
        fork_of_id=original_id,
        created_by=created_by,
        usage_count=0,
    )
    db.add(fork)
    await db.flush()
    await db.refresh(fork)
    return fork


# ---------------------------------------------------------------------------
# Favourite toggle
# ---------------------------------------------------------------------------


async def is_favourited(
    db: AsyncSession, *, user_id: uuid.UUID, agent_id: uuid.UUID
) -> bool:
    """Return True if the agent is favourited by the user."""
    result = await db.execute(
        select(AgentFavourite).where(
            AgentFavourite.user_id == user_id,
            AgentFavourite.agent_id == agent_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def toggle_favourite(
    db: AsyncSession, *, user_id: uuid.UUID, agent_id: uuid.UUID
) -> bool:
    """Toggle favourite status. Returns True if now favourited, False if removed."""
    existing = await db.execute(
        select(AgentFavourite).where(
            AgentFavourite.user_id == user_id,
            AgentFavourite.agent_id == agent_id,
        )
    )
    fav = existing.scalar_one_or_none()

    if fav is not None:
        await db.delete(fav)
        await db.flush()
        return False
    else:
        new_fav = AgentFavourite(user_id=user_id, agent_id=agent_id)
        db.add(new_fav)
        await db.flush()
        return True


# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------


async def create_job(
    db: AsyncSession,
    *,
    agent_id: uuid.UUID | None,
    agent_name: str | None,
    user_id: uuid.UUID | None,
    inputs_json: dict | None,
) -> AgentJob:
    """Create an AgentJob with status='pending'."""
    job = AgentJob(
        agent_id=agent_id,
        agent_name=agent_name,
        user_id=user_id,
        inputs_json=inputs_json,
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: int) -> AgentJob | None:
    """Load a single AgentJob by id."""
    return await db.get(AgentJob, job_id)


async def increment_usage_count(db: AsyncSession, agent_id: uuid.UUID) -> None:
    """Atomically increment usage_count for an agent."""
    await db.execute(
        update(AIAgent)
        .where(AIAgent.id == agent_id)
        .values(usage_count=AIAgent.usage_count + 1)
    )
    await db.flush()
