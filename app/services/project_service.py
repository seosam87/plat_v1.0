"""Project service: access control, comments, task creation."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, project_users
from app.models.project_comment import ProjectComment
from app.models.task import SeoTask, TaskStatus, TaskType
from app.models.user import User, UserRole


# ---- Project access ----

async def grant_access(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Give a user access to a project."""
    await db.execute(
        project_users.insert().values(user_id=user_id, project_id=project_id)
    )
    await db.flush()


async def revoke_access(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await db.execute(
        delete(project_users).where(
            project_users.c.user_id == user_id,
            project_users.c.project_id == project_id,
        )
    )
    await db.flush()


async def get_project_user_ids(db: AsyncSession, project_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(project_users.c.user_id).where(project_users.c.project_id == project_id)
    )
    return [row[0] for row in result.all()]


async def get_accessible_projects(db: AsyncSession, user: User) -> list[Project]:
    """Return projects visible to a user.

    - Admin: all projects
    - Manager/Client: projects where they are in project_users OR client_user_id
    """
    if user.role == UserRole.admin:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        return list(result.scalars().all())

    # Projects where user is explicitly granted access OR is the client
    result = await db.execute(
        select(Project).where(
            (Project.id.in_(
                select(project_users.c.project_id).where(project_users.c.user_id == user.id)
            )) | (Project.client_user_id == user.id)
        ).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def can_access_project(db: AsyncSession, user: User, project_id: uuid.UUID) -> bool:
    if user.role == UserRole.admin:
        return True
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        return False
    if project.client_user_id == user.id:
        return True
    user_ids = await get_project_user_ids(db, project_id)
    return user.id in user_ids


# ---- Comments ----

async def add_comment(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, text: str
) -> ProjectComment:
    comment = ProjectComment(project_id=project_id, user_id=user_id, text=text)
    db.add(comment)
    await db.flush()
    return comment


async def list_comments(db: AsyncSession, project_id: uuid.UUID) -> list[ProjectComment]:
    result = await db.execute(
        select(ProjectComment)
        .where(ProjectComment.project_id == project_id)
        .order_by(ProjectComment.created_at.asc())
    )
    return list(result.scalars().all())


# ---- Task creation ----

async def create_task(
    db: AsyncSession,
    project_id: uuid.UUID,
    site_id: uuid.UUID,
    title: str,
    description: str | None = None,
    task_type: TaskType = TaskType.manual,
    assignee_id: uuid.UUID | None = None,
    url: str = "",
) -> SeoTask:
    status = TaskStatus.assigned if assignee_id else TaskStatus.open
    task = SeoTask(
        site_id=site_id,
        project_id=project_id,
        task_type=task_type,
        title=title,
        description=description,
        url=url,
        assignee_id=assignee_id,
        status=status,
    )
    db.add(task)
    await db.flush()
    return task
