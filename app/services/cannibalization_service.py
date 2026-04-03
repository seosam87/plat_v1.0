"""Cannibalization resolver: resolution proposals, action plans, tracking."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cannibalization import CannibalizationResolution, ResolutionStatus, ResolutionType
from app.models.task import SeoTask, TaskType


# ---- Pure functions ----


def suggest_resolution_type(competing_urls: list[str], keyword: str) -> str:
    """Heuristic suggestion for resolution type."""
    if len(competing_urls) < 2:
        return ResolutionType.split_keywords.value

    # If URLs share a common path prefix → merge
    prefixes = ["/".join(u.split("/")[:4]) for u in competing_urls]
    if len(set(prefixes)) == 1:
        return ResolutionType.merge_content.value

    # Default to canonical as safest option
    return ResolutionType.set_canonical.value


_ACTION_TEMPLATES = {
    "merge_content": (
        "Объединить контент страниц:\n{urls}\n\n"
        "1. Перенести уникальный контент на основную страницу: {primary}\n"
        "2. Настроить 301-редирект с удалённых страниц на основную\n"
        "3. Обновить внутренние ссылки\n"
        "4. Проверить через 2 недели, что каннибализация устранена"
    ),
    "set_canonical": (
        "Установить canonical для ключа «{keyword}»:\n\n"
        "1. На всех конкурирующих страницах добавить <link rel='canonical' href='{primary}'>\n"
        "2. Конкурирующие страницы:\n{urls}\n"
        "3. Проверить индексацию через 1-2 недели"
    ),
    "redirect_301": (
        "Настроить 301-редирект для ключа «{keyword}»:\n\n"
        "1. Основная страница: {primary}\n"
        "2. Перенаправить на неё:\n{urls}\n"
        "3. Обновить внутренние ссылки на новый URL\n"
        "4. Проверить индексацию через неделю"
    ),
    "split_keywords": (
        "Разнести ключи между страницами для «{keyword}»:\n\n"
        "1. Назначить ключ «{keyword}» на основную страницу: {primary}\n"
        "2. Для остальных страниц подобрать другие ключевые слова:\n{urls}\n"
        "3. Обновить title и H1 на каждой странице под свой ключ\n"
        "4. Проверить позиции через 2-3 недели"
    ),
}


def generate_action_plan(
    resolution_type: str, keyword: str, competing_urls: list[str], primary_url: str
) -> str:
    """Generate detailed action plan text."""
    other_urls = [u for u in competing_urls if u != primary_url]
    urls_text = "\n".join(f"  - {u}" for u in other_urls)
    template = _ACTION_TEMPLATES.get(resolution_type, _ACTION_TEMPLATES["set_canonical"])
    return template.format(keyword=keyword, primary=primary_url, urls=urls_text)


# ---- Async CRUD ----


async def create_resolution(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword: str,
    competing_urls: list[str],
    resolution_type: str,
    primary_url: str,
) -> CannibalizationResolution:
    action_plan = generate_action_plan(resolution_type, keyword, competing_urls, primary_url)
    r = CannibalizationResolution(
        site_id=site_id,
        keyword_phrase=keyword,
        competing_urls=competing_urls,
        resolution_type=resolution_type,
        primary_url=primary_url,
        action_plan=action_plan,
    )
    db.add(r)
    await db.flush()
    return r


async def create_resolution_task(
    db: AsyncSession, resolution_id: uuid.UUID
) -> SeoTask:
    result = await db.execute(
        select(CannibalizationResolution).where(CannibalizationResolution.id == resolution_id)
    )
    r = result.scalar_one()
    task = SeoTask(
        site_id=r.site_id,
        task_type=TaskType.cannibalization,
        title=f"Каннибализация: {r.keyword_phrase}",
        description=r.action_plan,
        url=r.primary_url,
    )
    db.add(task)
    await db.flush()
    r.task_id = task.id
    await db.flush()
    return task


async def list_resolutions(
    db: AsyncSession, site_id: uuid.UUID, status: str | None = None
) -> list[CannibalizationResolution]:
    q = select(CannibalizationResolution).where(CannibalizationResolution.site_id == site_id)
    if status:
        q = q.where(CannibalizationResolution.status == status)
    q = q.order_by(CannibalizationResolution.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_resolution_status(
    db: AsyncSession, resolution_id: uuid.UUID, status: str
) -> CannibalizationResolution | None:
    result = await db.execute(
        select(CannibalizationResolution).where(CannibalizationResolution.id == resolution_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        return None
    r.status = status
    if status == "resolved":
        r.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return r


async def check_resolution(
    db: AsyncSession, resolution_id: uuid.UUID
) -> dict:
    """Re-run cannibalization check for this keyword."""
    from app.services.cluster_service import detect_cannibalization

    result = await db.execute(
        select(CannibalizationResolution).where(CannibalizationResolution.id == resolution_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        return {"error": "not found"}

    cannibs = await detect_cannibalization(db, r.site_id)
    still = any(c.get("phrase") == r.keyword_phrase for c in cannibs)
    return {"still_cannibalized": still, "keyword": r.keyword_phrase}
