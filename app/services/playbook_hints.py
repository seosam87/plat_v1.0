"""Playbook completion hint service.

Phase 999.8 D-18: for a ProjectPlaybookStep, check whether the action
associated with its action_kind appears to have been performed AFTER
`step.opened_at`. Used only on playbook tab load to render the
"✓ Похоже, выполнено" amber badge.

All queries are cheap `exists()` checks scoped by `site_id` or
`project_id` wherever possible, so the whole tab load stays well below
the 3s UI budget even for playbooks with 20+ steps.

Scope note (RESEARCH.md open question #1, reaffirmed by CONTEXT.md):
CommerceCheckJob and BriefJob have NO site_id/project_id FKs — they
are per-user ad-hoc tool runs. Time-only filtering would produce
false positives across unrelated projects, so the MVP returns False
for those action kinds. A future Phase 999.8.1 should add nullable
project_id FKs to both tables to enable hints.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.content_plan import ContentPlanItem
from app.models.crawl import CrawlJob, CrawlJobStatus
from app.models.keyword import Keyword

if TYPE_CHECKING:
    from app.models.playbook import ProjectPlaybookStep


async def check_step_hint(
    db: AsyncSession,
    step: "ProjectPlaybookStep",
    *,
    site_id: uuid.UUID | None,
    project_id: uuid.UUID,
) -> bool:
    """Return True if the step's action_kind appears complete after `opened_at`.

    Caller must eager-load `step.block` (the query reads `step.block.action_kind`).
    """
    if step.opened_at is None:
        # Step has never been opened — we have no anchor for the hint query.
        return False

    kind = step.block.action_kind.value

    if kind == "run_crawl":
        if site_id is None:
            return False
        q = select(
            exists().where(
                CrawlJob.site_id == site_id,
                CrawlJob.status == CrawlJobStatus.done,
                CrawlJob.started_at > step.opened_at,
            )
        )
    elif kind == "open_keywords":
        if site_id is None:
            return False
        q = select(
            exists().where(
                Keyword.site_id == site_id,
                Keyword.created_at > step.opened_at,
            )
        )
    elif kind == "open_competitors":
        if site_id is None:
            return False
        q = select(
            exists().where(
                Competitor.site_id == site_id,
                Competitor.created_at > step.opened_at,
            )
        )
    elif kind == "open_content_plan":
        q = select(
            exists().where(
                ContentPlanItem.project_id == project_id,
                ContentPlanItem.created_at > step.opened_at,
            )
        )
    elif kind in ("open_commercial_check", "open_brief"):
        # TODO(999.8.1): CommerceCheckJob and BriefJob have no site_id/project_id FK
        # (they're per-user tool runs). Adding a nullable project_id FK via Alembic
        # would enable precise hints. For MVP we return False to avoid false
        # positives across unrelated projects.
        return False
    else:
        # manual_note or unknown action_kind — always manual.
        return False

    result = await db.execute(q)
    return bool(result.scalar())


async def compute_hints_for_playbook(
    db: AsyncSession,
    steps: list["ProjectPlaybookStep"],
    *,
    site_id: uuid.UUID | None,
    project_id: uuid.UUID,
) -> dict[uuid.UUID, bool]:
    """Bulk hint check for all steps on the playbook tab.

    Only steps with status `open` are checked — `in_progress` and `done`
    already have an explicit state the user has chosen. Returns a
    `{step_id: has_hint}` mapping keyed by ProjectPlaybookStep.id.
    """
    from app.models.playbook import ProjectPlaybookStepStatus

    out: dict[uuid.UUID, bool] = {}
    for s in steps:
        if s.status != ProjectPlaybookStepStatus.open:
            out[s.id] = False
            continue
        out[s.id] = await check_step_hint(
            db, s, site_id=site_id, project_id=project_id
        )
    return out
