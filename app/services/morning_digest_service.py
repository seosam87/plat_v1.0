"""Morning digest service: builds a compact cross-project Telegram summary."""
from __future__ import annotations

from datetime import date

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings

MAX_PROJECTS = 10
MAX_CHARS = 4000


def build_morning_digest(db: Session) -> str:
    """Build a compact Telegram HTML morning digest across all active projects.

    Queries non-archived projects, collects TOP-10 keyword positions,
    open/in-progress task counts, and formats as Telegram HTML.

    Args:
        db: Synchronous SQLAlchemy session (runs inside Celery task).

    Returns:
        Telegram-formatted HTML string, truncated to MAX_CHARS.
    """
    from app.models.project import Project, ProjectStatus
    from app.models.site import Site
    from app.models.task import SeoTask, TaskStatus

    today = date.today().strftime("%Y-%m-%d")

    # Fetch active projects (non-archived), limit to MAX_PROJECTS
    projects_result = db.execute(
        select(Project, Site)
        .join(Site, Project.site_id == Site.id, isouter=True)
        .where(Project.status != ProjectStatus.archived)
        .order_by(Project.name)
        .limit(MAX_PROJECTS)
    ).all()

    lines: list[str] = [
        f"<b>SEO Morning Digest - {today}</b>",
        "",
    ]

    if not projects_result:
        lines.append("Нет активных проектов.")
        lines.append("")
        lines.append(f"<a href='{settings.APP_URL}/ui/dashboard'>Open Dashboard</a>")
        return "\n".join(lines)

    for project, site in projects_result:
        site_name = site.name if site else "—"

        # Count keywords in top-10 using latest positions
        try:
            top10 = _count_top10(db, site.id if site else None)
        except Exception as exc:
            logger.warning("Failed to get top10 for project", project=project.name, error=str(exc))
            top10 = 0

        # Count open and in-progress tasks
        try:
            open_tasks = db.execute(
                select(func.count()).select_from(SeoTask).where(
                    SeoTask.project_id == project.id,
                    SeoTask.status == TaskStatus.open,
                )
            ).scalar() or 0
            in_progress_tasks = db.execute(
                select(func.count()).select_from(SeoTask).where(
                    SeoTask.project_id == project.id,
                    SeoTask.status == TaskStatus.in_progress,
                )
            ).scalar() or 0
        except Exception as exc:
            logger.warning("Failed to get tasks for project", project=project.name, error=str(exc))
            open_tasks = 0
            in_progress_tasks = 0

        status_icon = _status_icon(top10, open_tasks + in_progress_tasks)
        lines.append(
            f"{status_icon} <b>{project.name}</b> ({site_name})"
        )
        lines.append(
            f"TOP-10: {top10}, Tasks: {open_tasks} open / {in_progress_tasks} in progress"
        )

    lines.append("")
    lines.append(f"<a href='{settings.APP_URL}/ui/dashboard'>Open Dashboard</a>")

    msg = "\n".join(lines)
    if len(msg) > MAX_CHARS:
        msg = msg[:MAX_CHARS - 4] + "\n..."
    return msg


def _count_top10(db: Session, site_id) -> int:
    """Count keywords with latest position <= 10 for the given site."""
    if site_id is None:
        return 0

    # Use a subquery to get latest checked_at per keyword
    from app.models.keyword import Keyword

    try:
        from app.models.position import KeywordPosition

        # Count keywords where latest position is <= 10
        subq = (
            select(
                KeywordPosition.keyword_id,
                func.max(KeywordPosition.checked_at).label("latest_checked_at"),
            )
            .where(KeywordPosition.site_id == site_id)
            .group_by(KeywordPosition.keyword_id)
            .subquery()
        )

        count = db.execute(
            select(func.count())
            .select_from(KeywordPosition)
            .join(
                subq,
                (KeywordPosition.keyword_id == subq.c.keyword_id)
                & (KeywordPosition.checked_at == subq.c.latest_checked_at),
            )
            .where(
                KeywordPosition.site_id == site_id,
                KeywordPosition.position <= 10,
            )
        ).scalar() or 0
        return int(count)
    except Exception:
        # If partitioned table doesn't exist yet, return 0
        return 0


def _status_icon(top10: int, active_tasks: int) -> str:
    """Choose a status icon based on metrics."""
    if active_tasks > 5:
        return "\U0001f534"  # red circle
    if top10 > 0:
        return "\U0001f7e2"  # green circle
    return "\U0001f7e1"  # yellow circle
