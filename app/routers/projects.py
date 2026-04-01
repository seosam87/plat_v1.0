"""Projects router: CRUD, content plan, page briefs, Kanban task management."""
import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.content_plan import ContentPlanItem, ContentStatus
from app.models.project import Project, ProjectStatus
from app.models.task import SeoTask, TaskStatus
from app.models.user import User

router = APIRouter(prefix="/projects", tags=["projects"])
templates = Jinja2Templates(directory="app/templates")


# ---- Project CRUD ----

class ProjectCreate(BaseModel):
    site_id: uuid.UUID
    name: str
    description: str | None = None
    client_user_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    p = Project(site_id=payload.site_id, name=payload.name, description=payload.description, client_user_id=payload.client_user_id)
    db.add(p)
    await db.flush()
    await db.commit()
    return _project_dict(p)


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> list[dict]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return [_project_dict(p) for p in result.scalars().all()]


@router.get("/{project_id}")
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    p = await _get_or_404(db, project_id)
    return _project_dict(p)


@router.put("/{project_id}")
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    p = await _get_or_404(db, project_id)
    if payload.name is not None:
        p.name = payload.name
    if payload.description is not None:
        p.description = payload.description
    if payload.status is not None:
        p.status = ProjectStatus(payload.status)
    await db.flush()
    await db.commit()
    return _project_dict(p)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    p = await _get_or_404(db, project_id)
    await db.delete(p)
    await db.commit()


# ---- Tasks (Kanban) ----

@router.get("/{project_id}/tasks")
async def project_tasks(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    """Return tasks grouped by status for Kanban board."""
    tasks = (await db.execute(
        select(SeoTask).where(SeoTask.project_id == project_id).order_by(SeoTask.created_at)
    )).scalars().all()
    grouped = {"open": [], "in_progress": [], "resolved": []}
    for t in tasks:
        grouped.setdefault(t.status.value, []).append(_task_dict(t))
    return grouped


class TaskUpdate(BaseModel):
    status: str | None = None
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    result = await db.execute(select(SeoTask).where(SeoTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.status:
        task.status = TaskStatus(payload.status)
    if payload.assignee_id is not None:
        task.assignee_id = payload.assignee_id
    if payload.due_date is not None:
        task.due_date = payload.due_date
    await db.flush()
    await db.commit()
    return _task_dict(task)


# ---- Content Plan ----

class PlanItemCreate(BaseModel):
    proposed_title: str
    keyword_id: uuid.UUID | None = None
    planned_date: date | None = None
    notes: str | None = None


class PlanItemUpdate(BaseModel):
    proposed_title: str | None = None
    status: str | None = None
    planned_date: date | None = None
    wp_post_id: int | None = None
    wp_post_url: str | None = None
    notes: str | None = None


@router.post("/{project_id}/plan", status_code=status.HTTP_201_CREATED)
async def add_plan_item(
    project_id: uuid.UUID, payload: PlanItemCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    await _get_or_404(db, project_id)
    item = ContentPlanItem(
        project_id=project_id, proposed_title=payload.proposed_title,
        keyword_id=payload.keyword_id, planned_date=payload.planned_date, notes=payload.notes,
    )
    db.add(item)
    await db.flush()
    await db.commit()
    return _plan_dict(item)


@router.get("/{project_id}/plan")
async def list_plan(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> list[dict]:
    items = (await db.execute(
        select(ContentPlanItem).where(ContentPlanItem.project_id == project_id).order_by(ContentPlanItem.planned_date.asc().nullslast())
    )).scalars().all()
    return [_plan_dict(i) for i in items]


@router.put("/plan/{item_id}")
async def update_plan_item(
    item_id: uuid.UUID, payload: PlanItemUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    result = await db.execute(select(ContentPlanItem).where(ContentPlanItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plan item not found")
    if payload.proposed_title is not None:
        item.proposed_title = payload.proposed_title
    if payload.status is not None:
        item.status = ContentStatus(payload.status)
    if payload.planned_date is not None:
        item.planned_date = payload.planned_date
    if payload.wp_post_id is not None:
        item.wp_post_id = payload.wp_post_id
    if payload.wp_post_url is not None:
        item.wp_post_url = payload.wp_post_url
    if payload.notes is not None:
        item.notes = payload.notes
    await db.flush()
    await db.commit()
    return _plan_dict(item)


# ---- One-click WP draft ----

@router.post("/plan/{item_id}/create-draft", status_code=status.HTTP_202_ACCEPTED)
async def create_wp_draft(
    item_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    """Create a WP draft post from a content plan item."""
    result = await db.execute(select(ContentPlanItem).where(ContentPlanItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plan item not found")

    project = (await db.execute(select(Project).where(Project.id == item.project_id))).scalar_one()
    from app.services.site_service import get_site
    site = await get_site(db, project.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    from app.services.wp_service import create_post_sync
    result_post = create_post_sync(site, title=item.proposed_title, content="", status="draft")
    if result_post:
        item.wp_post_id = result_post.get("id")
        item.wp_post_url = result_post.get("link", "")
        item.status = ContentStatus.writing
        await db.flush()
        await db.commit()
        return {"wp_post_id": item.wp_post_id, "wp_post_url": item.wp_post_url}
    raise HTTPException(status_code=502, detail="WP draft creation failed")


# ---- Page brief generator ----

@router.get("/{project_id}/brief/{cluster_id}")
async def generate_brief(
    project_id: uuid.UUID,
    cluster_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Generate a page brief from a keyword cluster."""
    from app.models.cluster import KeywordCluster
    from app.models.keyword import Keyword

    cluster = (await db.execute(select(KeywordCluster).where(KeywordCluster.id == cluster_id))).scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    keywords = (await db.execute(
        select(Keyword).where(Keyword.cluster_id == cluster_id).order_by(Keyword.frequency.desc().nullslast())
    )).scalars().all()

    # Build brief structure
    primary_kw = keywords[0] if keywords else None
    brief = {
        "cluster_name": cluster.name,
        "target_url": cluster.target_url,
        "h1": primary_kw.phrase.title() if primary_kw else cluster.name,
        "h2_suggestions": [kw.phrase.title() for kw in keywords[1:6]],
        "keywords": [
            {"phrase": kw.phrase, "frequency": kw.frequency, "target_url": kw.target_url}
            for kw in keywords
        ],
        "total_volume": sum(kw.frequency or 0 for kw in keywords),
    }
    return brief


@router.get("/{project_id}/brief/{cluster_id}/html", response_class=HTMLResponse)
async def brief_html(
    project_id: uuid.UUID, cluster_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> HTMLResponse:
    """Downloadable HTML page brief."""
    brief = await generate_brief(project_id, cluster_id, db, _)
    html = _render_brief_html(brief)
    return HTMLResponse(html, headers={
        "Content-Disposition": f'attachment; filename="brief_{cluster_id}.html"'
    })


# ---- Helpers ----

async def _get_or_404(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _project_dict(p: Project) -> dict:
    return {
        "id": str(p.id), "site_id": str(p.site_id), "name": p.name,
        "description": p.description, "status": p.status.value,
        "client_user_id": str(p.client_user_id) if p.client_user_id else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _task_dict(t: SeoTask) -> dict:
    return {
        "id": str(t.id), "title": t.title, "description": t.description,
        "task_type": t.task_type.value, "status": t.status.value, "url": t.url,
        "assignee_id": str(t.assignee_id) if t.assignee_id else None,
        "due_date": t.due_date.isoformat() if t.due_date else None,
    }


def _plan_dict(i: ContentPlanItem) -> dict:
    return {
        "id": str(i.id), "proposed_title": i.proposed_title, "status": i.status.value,
        "planned_date": i.planned_date.isoformat() if i.planned_date else None,
        "keyword_id": str(i.keyword_id) if i.keyword_id else None,
        "wp_post_id": i.wp_post_id, "wp_post_url": i.wp_post_url, "notes": i.notes,
    }


def _render_brief_html(brief: dict) -> str:
    kw_rows = "\n".join(
        f"<tr><td>{k['phrase']}</td><td>{k['frequency'] or '—'}</td></tr>"
        for k in brief["keywords"]
    )
    h2_list = "\n".join(f"<li>{h}</li>" for h in brief.get("h2_suggestions", []))
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Brief: {brief['cluster_name']}</title>
<style>body{{font-family:system-ui;max-width:800px;margin:2rem auto;padding:0 1rem}}table{{width:100%;border-collapse:collapse}}th,td{{padding:.5rem;border:1px solid #ddd;text-align:left}}</style>
</head><body>
<h1>{brief['h1']}</h1>
<p><strong>Cluster:</strong> {brief['cluster_name']}</p>
<p><strong>Target URL:</strong> {brief.get('target_url') or 'TBD'}</p>
<p><strong>Total search volume:</strong> {brief['total_volume']}</p>
<h2>Suggested H2 structure</h2><ul>{h2_list}</ul>
<h2>Target keywords</h2>
<table><thead><tr><th>Keyword</th><th>Frequency</th></tr></thead><tbody>{kw_rows}</tbody></table>
</body></html>"""
